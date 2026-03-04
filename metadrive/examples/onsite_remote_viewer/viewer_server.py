#!/usr/bin/env python3
"""OnSite remote viewer server.

This process connects to the OnSite multicast network, receives images, exposes
an RPC endpoint for remote clients, and sends VehicleControl to the OnSite
server using the latest action from remote clients.
"""

import argparse
import json
import logging
import fcntl
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np
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
def get_ip_address(ifname: str) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return socket.inet_ntoa(
            fcntl.ioctl(
                sock.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack("256s", bytes(ifname[:15], "utf-8")),
            )[20:24]
        )
    except Exception:
        return ""
    finally:
        sock.close()


class OnSiteBridge:
    _ANSI_PURPLE = "\033[95m"
    _ANSI_RESET = "\033[0m"

    def __init__(self, args: argparse.Namespace, action_state, frame_state, state_lock: threading.Lock) -> None:
        self._args = args
        self._action_state = action_state
        self._frame_state = frame_state
        self._state_lock = state_lock
        self._stop = False

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
    def _color_purple(cls, value):
        return f"{cls._ANSI_PURPLE}{value}{cls._ANSI_RESET}"

    def _init_logger(self) -> None:
        logger.setLevel(logging.DEBUG)
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

    def _log_message_debug(self, direction, message_type, payload, enum_scope):
        if not logger.isEnabledFor(logging.DEBUG):
            return
        payload_text = payload
        if hasattr(payload, "DESCRIPTOR"):
            payload_text = self._proto_to_dict(payload)
        elif not isinstance(payload, dict):
            payload_text = {"value": payload}
        if isinstance(payload_text, dict) and "expected_type" in payload_text:
            payload_text = dict(payload_text)
            payload_text["expected_type"] = self._format_type_name(payload_text["expected_type"], enum_scope)
        payload_text = json.dumps(payload_text, ensure_ascii=False, sort_keys=True, indent=2)
        logger.debug(
            "%s type=%s dict=%s",
            direction,
            self._color_purple(self._format_type_name(message_type, enum_scope)),
            self._color_purple(payload_text),
        )

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
        local_ip = get_ip_address(self._args.net_interface)
        if not local_ip:
            raise RuntimeError(f"Failed to resolve IP for interface {self._args.net_interface}")

        param.config_center_addr = self._args.config_center
        param.local_ip = local_ip
        param.net_interface_name = self._args.net_interface
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
        ret, msg = self._notify_channel.get()
        if msg is None:
            return

        if ret >= 0 and msg.type() == MT_NOTIFY:
            notify = Notify()
            data = libMulticastNetwork.getMessageData(msg)
            notify.ParseFromString(data)
            self._log_message_debug(
                "recv",
                MT_NOTIFY,
                notify,
                "main",
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
            self._log_message_debug("recv", msg.type(), {"expected_type": MT_NOTIFY}, "main")

    def _get_prepare(self) -> None:
        ret, msg = self._prepare_channel.get()
        if msg is None:
            return

        if ret >= 0 and msg.type() == MT_ACTOR_PREPARE:
            data = libMulticastNetwork.getMessageData(msg)
            prepare_msg = ActorPrepare()
            prepare_msg.ParseFromString(data)
            self._log_message_debug(
                "recv",
                MT_ACTOR_PREPARE,
                prepare_msg,
                "main",
            )
            self._recv_prepare = True
            self._prepare_sent = False
            self._session_id = prepare_msg.session_id
            self._actor_id = prepare_msg.actor_id
            logger.info("Received prepare: session_id=%s actor_id=%s", self._session_id, self._actor_id)
        else:
            self._log_message_debug("recv", msg.type(), {"expected_type": MT_ACTOR_PREPARE}, "main")

    def _send_prepare_result(self) -> None:
        result = ActorPrepareResult()
        result.session_id = self._session_id
        result.actor_id = self._actor_id
        result.result = True
        result.reason = ""

        data = result.SerializeToString()
        ret = self._prepare_channel.put(MT_ACTOR_PREPARE_RESULT, len(data), data)
        self._log_message_debug(
            "send",
            MT_ACTOR_PREPARE_RESULT,
            {**self._proto_to_dict(result), "ret": ret},
            "main",
        )
        if ret != 0:
            logger.warning("send prepare result error")
        else:
            logger.info("Sent prepare result: session_id=%s actor_id=%s", self._session_id, self._actor_id)
            self._prepare_sent = True

    def _get_image(self) -> Optional[np.ndarray]:
        msg = self._image_channel.get_image_simple()
        if len(msg) == 0:
            return None

        img = None
        images_meta = []
        for image in msg:
            img = image.data.astype(np.uint8).reshape(image.height, image.width, 3)
            images_meta.append(
                {
                    "timestamp_sec": float(image.timestamp_sec),
                    "camera_timestamp": int(image.camera_timestamp),
                    "sequence_num": int(image.sequence_num),
                    "measurement_time": float(image.measurement_time),
                    "height": int(image.height),
                    "width": int(image.width),
                    "encoding": image.encoding,
                }
            )
        self._log_message_debug(
            "recv",
            "image_batch",
            {"image_count": len(images_meta), "images": images_meta},
            "raw",
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
        ret = self._cmd_channel.put(VEHICLE_CONTROL, len(data), data)
        self._log_message_debug(
            "send",
            VEHICLE_CONTROL,
            {**self._proto_to_dict(cmd), "ret": ret},
            "chassis",
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
                format="BGR",
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
    parser.add_argument("--config_center", type=str, default="www.zjvts.cn:52009")
    parser.add_argument("--field_id", type=str, default="unique_fieldid")
    parser.add_argument("--net_interface", type=str, default="eno2")
    parser.add_argument("--grpc_host", type=str, default="0.0.0.0", help="viewer server bind host")
    parser.add_argument("--grpc_port", type=int, default=50051, help="viewer server bind port")
    parser.add_argument("--log_level", type=str, default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), force=True)

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

    bridge = OnSiteBridge(args, action_state, frame_state, state_lock)

    try:
        bridge.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        bridge.stop()
        grpc_server.stop(grace=1)


if __name__ == "__main__":
    main()
