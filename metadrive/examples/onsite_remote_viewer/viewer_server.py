#!/usr/bin/env python3
"""OnSite remote viewer server.

This process connects to the OnSite multicast network, receives images, exposes
an RPC endpoint for remote clients, and sends VehicleControl to the OnSite
server using the latest action from remote clients.
"""

import argparse
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np
import yaml
from google.protobuf.json_format import MessageToDict

try:
    import grpc
except ImportError as exc:  # pragma: no cover - runtime dependency
    raise ImportError("grpcio is required for viewer_server.py") from exc

import libMulticastNetwork

from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto.chassis_enums_pb2 import VEHICLE_CONTROL
from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto.chassis_messages_pb2 import VehicleControl
from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto import chassis_enums_pb2
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    MT_NOTIFY,
    MT_ACTOR_PREPARE,
    MT_ACTOR_PREPARE_RESULT,
    NT_START_TEST,
    NT_ABORT_TEST,
    NT_FINISH_TEST,
)
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.messages_pb2 import Notify, ActorPrepare, ActorPrepareResult
from metadrive.misc.onsite_middleware.onsite_proto.main.proto import enums_pb2
from metadrive.utils.logger import get_log_timestamp

from metadrive.utils.remote_viewer_proto import remote_viewer_pb2, remote_viewer_pb2_grpc

logger = logging.getLogger("onsite_viewer_server")

MAX_STEERING_RAD = 1.047  # 60 degrees


def load_multicast_config(onsite_dir: str):
    cfg_path = Path(onsite_dir).expanduser().resolve() / "config" / "common.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(f"OnSite config not found: {cfg_path}")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    multicast = cfg.get("multicast") or {}
    required = ("config_center_addr", "local_ip", "net_interface_name", "field_id")
    missing = [k for k in required if not multicast.get(k)]
    if missing:
        raise ValueError(f"Missing multicast config keys in {cfg_path}: {missing}")
    return multicast


class OnSiteBridge:
    _ANSI_GREEN = "\033[92m"
    _ANSI_BLUE = "\033[94m"
    _ANSI_PURPLE = "\033[95m"
    _ANSI_RESET = "\033[0m"

    def __init__(
        self,
        args: argparse.Namespace,
        action_state,
        frame_state,
        state_lock: threading.Lock,
        recv_none_sleep: float = 0.02,
    ) -> None:
        self._args = args
        self._action_state = action_state
        self._frame_state = frame_state
        self._state_lock = state_lock
        self._stop = False
        self._recv_none_sleep = float(recv_none_sleep)

        self._recv_prepare = False
        self._start_test = False
        self._session_id = ""
        self._actor_id = ""
        self._prepare_sent = False

        self._notify_channel = None
        self._cmd_channel = None
        self._prepare_channel = None
        self._image_channel = None
        self._seq_by_type = {}

        self._init_logger()
        self._init_channels()

    @classmethod
    def _color_green(cls, value):
        return f"{cls._ANSI_GREEN}{value}{cls._ANSI_RESET}"

    @classmethod
    def _color_blue(cls, value):
        return f"{cls._ANSI_BLUE}{value}{cls._ANSI_RESET}"

    @classmethod
    def _color_purple(cls, value):
        return f"{cls._ANSI_PURPLE}{value}{cls._ANSI_RESET}"

    def _init_logger(self) -> None:
        # Follow root logger level (set by entrypoint --log_level).
        logger.setLevel(logging.NOTSET)
        ts = get_log_timestamp()
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"onsitebridge_{ts}.logs"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        handler.addFilter(lambda record: record.name == logger.name)
        if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_file)
                   for h in logger.handlers):
            logger.addHandler(handler)

    def _log_message_debug(self, direction, message_type, payload, enum_scope, channel_op=None, channel_elapsed_ms=None):
        if not logger.isEnabledFor(logging.DEBUG):
            return
        payload_text = payload
        if hasattr(payload, "DESCRIPTOR"):
            payload_text = self._proto_to_dict(payload)
        elif not isinstance(payload, dict):
            payload_text = {"value": payload}
        payload_text = self._normalize_debug_payload(payload_text)
        if isinstance(payload_text, dict) and "expected_type" in payload_text:
            payload_text = dict(payload_text)
            payload_text["expected_type"] = self._format_type_name(payload_text["expected_type"], enum_scope)
        payload_text = json.dumps(payload_text, ensure_ascii=False, sort_keys=True, indent=2)
        channel_key = "channel"
        channel_value = "-"
        if channel_op and channel_elapsed_ms is not None:
            channel_key = f"channel_{channel_op}_ms"
            channel_value = f"{float(channel_elapsed_ms):.3f}"
        logger.debug(
            "%s %s=%s type=%s dict=%s",
            direction,
            channel_key,
            self._color_blue(channel_value),
            self._color_green(self._format_type_name(message_type, enum_scope)),
            self._color_purple(payload_text),
        )

    @staticmethod
    def _timed_get(channel):
        t0 = time.perf_counter()
        ret, msg = channel.get()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ret, msg, elapsed_ms

    @staticmethod
    def _timed_put(channel, msg_type, length, data):
        t0 = time.perf_counter()
        ret = channel.put(msg_type, length, data)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ret, elapsed_ms

    def _next_seq(self, message_type) -> int:
        seq = int(self._seq_by_type.get(message_type, 0))
        self._seq_by_type[message_type] = seq + 1
        return seq

    @staticmethod
    def _proto_to_dict(message):
        return MessageToDict(
            message,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
            including_default_value_fields=True
        )

    @classmethod
    def _normalize_debug_payload(cls, value):
        if isinstance(value, (bytes, bytearray, memoryview)):
            return {"byte_len": len(value)}
        if isinstance(value, dict):
            return {k: cls._normalize_debug_payload(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize_debug_payload(v) for v in value]
        return value

    @staticmethod
    def _format_type_name(value, enum_scope):
        if isinstance(value, str):
            return value
        if not isinstance(value, int):
            return str(value)
        if enum_scope == "main":
            try:
                return f"{enums_pb2.MsgType.Name(value)} ({value})"
            except ValueError:
                return f"UNKNOWN_MAIN_TYPE ({value})"
        if enum_scope == "chassis":
            try:
                return f"{chassis_enums_pb2.MsgType.Name(value)} ({value})"
            except ValueError:
                return f"UNKNOWN_CHASSIS_TYPE ({value})"
        return f"UNKNOWN_TYPE ({value})"

    def _init_channels(self) -> None:
        param = libMulticastNetwork.CreateChannelsParam()
        param.config_center_addr = self._args.config_center_addr
        param.local_ip = self._args.local_ip
        param.net_interface_name = self._args.net_interface_name
        param.field_id = self._args.field_id
        param.log_level = 1
        param.client_name = "apollo_testee"
        param.recv_self_msg = False
        logger.info(
            "OnSite create_channels param=%s",
            {
                "config_center_addr": param.config_center_addr,
                "local_ip": param.local_ip,
                "net_interface_name": param.net_interface_name,
                "field_id": param.field_id,
                "log_level": param.log_level,
                "client_name": param.client_name,
                "recv_self_msg": param.recv_self_msg,
            },
        )

        channels = libMulticastNetwork.ChannelPtrVector()
        ret = libMulticastNetwork.create_channels(param, channels)
        if ret:
            raise RuntimeError(f"create channels failed, ret: {ret}")

        channel_map = {c.name(): c for c in channels}
        self._notify_channel = channel_map["notify"]
        self._cmd_channel = channel_map["vehiclecontrol"]
        self._prepare_channel = channel_map["prepare"]
        self._image_channel = channel_map["camera"]

        if not libMulticastNetwork.InitImageDecoder():
            raise RuntimeError("image decoder init error")

        logger.info("OnSite channels initialized")

    def stop(self) -> None:
        self._stop = True

    def _process_notify(self) -> None:
        ret, msg, get_ms = self._timed_get(self._notify_channel)
        if msg is None or ret < 0:
            time.sleep(self._recv_none_sleep)
            return

        if msg.type() == MT_NOTIFY:
            notify = Notify()
            data = libMulticastNetwork.getMessageData(msg)
            notify.ParseFromString(data)
            self._log_message_debug(
                "recv",
                MT_NOTIFY,
                notify,
                "main",
                channel_op="get",
                channel_elapsed_ms=get_ms,
            )

            if notify.type in [NT_ABORT_TEST, NT_FINISH_TEST]:
                logger.info("Finish session")
                self._start_test = False
                self._recv_prepare = False
                self._prepare_sent = False
                self._session_id = ""
            elif notify.type == NT_START_TEST:
                logger.info("Start session")
                self._start_test = True
            else:
                notify_type = f"{enums_pb2.NotifyType.Name(notify.type)}({notify.type})"
                logger.info("Notify: session=%s type=%s", notify.session_id, notify_type)
        else:
            self._log_message_debug(
                "recv", msg.type(), {"expected_type": MT_NOTIFY}, "main", channel_op="get", channel_elapsed_ms=get_ms
            )

    def _get_prepare(self) -> None:
        ret, msg, get_ms = self._timed_get(self._prepare_channel)
        if msg is None or ret < 0:
            time.sleep(self._recv_none_sleep)
            return

        if msg.type() == MT_ACTOR_PREPARE:
            data = libMulticastNetwork.getMessageData(msg)
            prepare_msg = ActorPrepare()
            prepare_msg.ParseFromString(data)
            self._log_message_debug(
                "recv",
                MT_ACTOR_PREPARE,
                prepare_msg,
                "main",
                channel_op="get",
                channel_elapsed_ms=get_ms,
            )
            self._recv_prepare = True
            self._prepare_sent = False
            self._session_id = prepare_msg.session_id
            self._actor_id = prepare_msg.actor_id
            logger.info("Received prepare: session_id=%s actor_id=%s", self._session_id, self._actor_id)
        else:
            self._log_message_debug(
                "recv",
                msg.type(),
                {"expected_type": MT_ACTOR_PREPARE},
                "main",
                channel_op="get",
                channel_elapsed_ms=get_ms,
            )

    def _send_prepare_result(self) -> None:
        result = ActorPrepareResult()
        result.session_id = self._session_id
        result.actor_id = self._actor_id
        result.result = True
        result.reason = ""

        data = result.SerializeToString()
        ret, put_ms = self._timed_put(self._prepare_channel, MT_ACTOR_PREPARE_RESULT, len(data), data)
        self._log_message_debug(
            "send",
            MT_ACTOR_PREPARE_RESULT,
            {**self._proto_to_dict(result), "ret": ret},
            "main",
            channel_op="put",
            channel_elapsed_ms=put_ms,
        )
        if ret != 0:
            logger.warning("send prepare result error")
        else:
            logger.info("Sent prepare result: session_id=%s actor_id=%s", self._session_id, self._actor_id)
            self._prepare_sent = True

    @staticmethod
    def _decode_onsite_image(image) -> np.ndarray:
        return np.asarray(image.data, dtype=np.uint8).reshape(int(image.height), int(image.width),  3)

    def _get_image(self) -> Optional[np.ndarray]:
        t0 = time.perf_counter()
        msg = self._image_channel.get_image_simple()
        get_ms = (time.perf_counter() - t0) * 1000.0
        if len(msg) == 0:
            time.sleep(self._recv_none_sleep)
            return None

        img = None
        images_meta = []
        for image in msg:
            if image.encoding == "rgb8":
                img = self._decode_onsite_image(image)
            else:
                logger.warning("Drop image frame: unsupported OnSite image encoding, expected rgb8")
                continue
            images_meta.append(
                {
                    "timestamp_sec": image.timestamp_sec,
                    "camera_timestamp": image.camera_timestamp,
                    "sequence_num": image.sequence_num,
                    "measurement_time": image.measurement_time,
                    "height": image.height,
                    "width": image.width,
                    "encoding": image.encoding,
                }
            )
        self._log_message_debug(
            "recv",
            "image_batch",
            {"image_count": len(images_meta), "images": images_meta},
            "raw",
            channel_op="get",
            channel_elapsed_ms=get_ms,
        )
        return img

    def _send_vehicle_control(self, steering: float, throttle_brake: float) -> None:
        cmd = VehicleControl()
        cmd.header.send_ts = int(time.time() * 1000)
        cmd.header.sim_ts = int(time.time() * 1000)
        cmd.header.seq_no = self._next_seq(VEHICLE_CONTROL)
        cmd.steering_control.target_steering_wheel_angle = steering * MAX_STEERING_RAD

        if throttle_brake >= 0:
            cmd.driving_control.target_accelerator_pedal_position = throttle_brake * 100.0
            cmd.brake_control.target_brake_pedal_position = 0.0
        else:
            cmd.driving_control.target_accelerator_pedal_position = 0.0
            cmd.brake_control.target_brake_pedal_position = -throttle_brake * 100.0

        data = cmd.SerializeToString()
        ret, put_ms = self._timed_put(self._cmd_channel, VEHICLE_CONTROL, len(data), data)
        self._log_message_debug(
            "send",
            VEHICLE_CONTROL,
            {**self._proto_to_dict(cmd), "ret": ret},
            "chassis",
            channel_op="put",
            channel_elapsed_ms=put_ms,
        )
        if ret != 0:
            logger.warning("send vehicle control error")

    def run(self) -> None:
        while not self._stop:
            self._process_notify()

            if not self._recv_prepare:
                self._get_prepare()
                time.sleep(0.05)
                continue

            if self._recv_prepare and not self._start_test:
                if not self._prepare_sent:
                    self._send_prepare_result()
                time.sleep(0.2)
                continue

            img = self._get_image()
            if img is None:
                continue

            image_msg = remote_viewer_pb2.Image(
                data=img.tobytes(),
                width=img.shape[1],
                height=img.shape[0],
                channels=img.shape[2],
                format="RGB",
                timestamp_us=int(time.time() * 1e6),
            )
            with self._state_lock:
                self._frame_state["image"] = image_msg
                steering = float(self._action_state["steering"])
                throttle_brake = float(self._action_state["throttle_brake"])

            self._send_vehicle_control(steering, throttle_brake)


class OnsiteViewerGrpcServicer(remote_viewer_pb2_grpc.OnsiteViewerServiceServicer):
    def __init__(self, action_state, frame_state, state_lock: threading.Lock) -> None:
        self._action_state = action_state
        self._frame_state = frame_state
        self._state_lock = state_lock

    def SendAction(self, request, context):
        with self._state_lock:
            self._action_state["steering"] = float(request.steering)
            self._action_state["throttle_brake"] = float(request.throttle_brake)
            image = self._frame_state["image"]
            if image is None:
                return remote_viewer_pb2.Image()
            return remote_viewer_pb2.Image(
                data=image.data,
                width=image.width,
                height=image.height,
                channels=image.channels,
                format=image.format,
                timestamp_us=image.timestamp_us,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="OnSite remote viewer server")
    parser.add_argument("--onsite_dir", type=str, default="onsite", help="OnSite workspace directory")
    parser.add_argument("--grpc_host", type=str, default="0.0.0.0", help="viewer server bind host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server bind port")
    parser.add_argument("--recv_none_sleep", type=float, default=0.02, help="sleep seconds when recv returns empty")
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)
    multicast = load_multicast_config(args.onsite_dir)
    args.config_center_addr = multicast["config_center_addr"]
    args.local_ip = multicast["local_ip"]
    args.net_interface_name = multicast["net_interface_name"]
    args.field_id = multicast["field_id"]

    action_state = {"steering": 0.0, "throttle_brake": 0.0}
    frame_state = {"image": None}
    state_lock = threading.Lock()

    max_bytes = 2048 * 2048 * 3
    logger.info("Using gRPC max message bytes: %d", max_bytes)

    server_options = [
        ("grpc.max_send_message_length", max_bytes),
        ("grpc.max_receive_message_length", max_bytes),
    ]
    grpc_server = grpc.server(ThreadPoolExecutor(max_workers=2), options=server_options)
    remote_viewer_pb2_grpc.add_OnsiteViewerServiceServicer_to_server(
        OnsiteViewerGrpcServicer(action_state, frame_state, state_lock),
        grpc_server,
    )
    grpc_server.add_insecure_port(f"{args.grpc_host}:{args.grpc_port}")
    grpc_server.start()
    logger.info("Viewer gRPC server listening at %s:%s", args.grpc_host, args.grpc_port)

    bridge = OnSiteBridge(
        args,
        action_state,
        frame_state,
        state_lock,
        recv_none_sleep=args.recv_none_sleep,
    )

    try:
        bridge.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        bridge.stop()
        grpc_server.stop(grace=1)


if __name__ == "__main__":
    main()
