"""
OnSite Middleware for MetaDrive integration.

This module provides the OnSiteMiddleware class that encapsulates all OnSite communication logic,
including message sending/receiving and data format conversion between OnSite proto and MetaDrive.
"""

import json
import logging
import sys
import time
import subprocess
from enum import Enum
from pathlib import Path
import numpy as np
import torch
import yaml
from google.protobuf.json_format import MessageToDict

import libMulticastNetwork
from metadrive.utils.trajectory import matrix_to_quaternion

# Import proto messages and enums
from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto.chassis_messages_pb2 import VehicleFeedback, VehicleControl
from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto.chassis_enums_pb2 import VEHICLE_FEEDBACK, VEHICLE_CONTROL
from metadrive.misc.onsite_middleware.onsite_proto.chassis.proto import chassis_enums_pb2
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.messages_pb2 import (
    PubRole, SubRole, Notify, ActorPrepare, ActorPrepareResult, SessionInfo
)
from metadrive.misc.onsite_middleware.onsite_proto.main.proto.enums_pb2 import (
    MT_PUBROLE, MT_SUBROLE, MT_NOTIFY, MT_SESSIONINFO,
    MT_ACTOR_PREPARE, MT_ACTOR_PREPARE_RESULT,
    NT_ABORT_TEST, NT_START_TEST, NT_FINISH_TEST, NT_DESTROY_ROLE
)
from metadrive.misc.onsite_middleware.onsite_proto.main.proto import enums_pb2
from metadrive.utils.logger import get_log_timestamp

logger = logging.getLogger(__name__)


class TERMINAL_TYPE(Enum):
    SIMULATOR = "simulator"
    TESTEE = "apollo_testee"


class OnSiteMiddleware:
    """
    OnSite communication middleware for MetaDrive.

    Encapsulates all OnSite communication logic, providing simple APIs for:
    - Receiving messages from OnSite server
    - Sending messages to OnSite server
    - Converting between OnSite proto format and MetaDrive format
    """

    # Constants for conversion
    MAX_STEERING_RAD = 1.047  # 60 degrees in radians
    _ANSI_GREEN = "\033[92m"
    _ANSI_BLUE = "\033[94m"
    _ANSI_PURPLE = "\033[95m"
    _ANSI_RESET = "\033[0m"

    def __init__(self, onsite_dir, recv_none_sleep=0.02, terminal_type=TERMINAL_TYPE.SIMULATOR):
        """
        Initialize OnSite middleware.

        Args:
            onsite_dir: OnSite workspace directory, containing config/common.yaml and daemon/start.sh
            recv_none_sleep: Sleep time (seconds) when recv returns None/invalid
            terminal_type: OnSite terminal type enum for channel client_name
        """
        self.onsite_dir = Path(onsite_dir).expanduser().resolve()
        self._daemon_proc = None
        self.recv_none_sleep = float(recv_none_sleep)
        if not isinstance(terminal_type, TERMINAL_TYPE):
            raise TypeError("terminal_type must be TERMINAL_TYPE enum")
        self.terminal_type = terminal_type

        multicast = self._load_multicast_config(self.onsite_dir)
        self.config_center = multicast["config_center_addr"]
        self.field_id = multicast["field_id"]
        self.net_interface = multicast["net_interface_name"]
        self.local_ip = multicast["local_ip"]

        # Channel references
        self.channels = None
        self.channel_map = {}
        self.prepare_channel = None
        self.notify_channel = None
        self.role_channel = None
        self.cmd_channel = None
        self.session_channel = None
        self.image_channel = None
        self.actor_id = None
        # Sequence counters
        self.image_seq = 0
        self._seq_by_type = {}

        # Send only this logger to a dedicated file.
        self._init_logger()

        # Initialize channels
        self.initialize_channels()

    @staticmethod
    def _load_multicast_config(onsite_dir: Path):
        cfg_path = onsite_dir / "config" / "common.yaml"
        if not cfg_path.exists():
            raise FileNotFoundError(f"OnSite config not found: {cfg_path}")
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        multicast = cfg.get("multicast") or {}
        required = ("config_center_addr", "local_ip", "net_interface_name", "field_id")
        missing = [k for k in required if not multicast.get(k)]
        if missing:
            raise ValueError(f"Missing multicast config keys in {cfg_path}: {missing}")
        return multicast

    def start_onsite_daemon(self):
        start_script = self.onsite_dir / "daemon" / "start.sh"
        if not start_script.exists():
            raise FileNotFoundError(f"OnSite daemon start script not found: {start_script}")
        if self._daemon_proc is not None and self._daemon_proc.poll() is None:
            logger.info("OnSite daemon already running, pid=%s", self._daemon_proc.pid)
            return
        self._daemon_proc = subprocess.Popen(
            ["bash", str(start_script)],
            cwd=str(start_script.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(3)
        logger.info("Started OnSite daemon process pid=%s via %s", self._daemon_proc.pid, start_script)

    def _init_logger(self):
        # Follow root logger level (set by entrypoint --log-level).
        logger.setLevel(logging.NOTSET)
        ts = get_log_timestamp()
        self.log_ts = ts
        # Share timestamp with other modules (e.g., onsite_integration).
        try:
            import os
            os.environ["ONSITE_LOG_TS"] = ts
        except Exception:
            logger.exception("Failed to set ONSITE_LOG_TS")
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{self.terminal_type.value}_{ts}.logs"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        handler.addFilter(lambda record: record.name == __name__)
        if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_file)
                   for h in logger.handlers):
            logger.addHandler(handler)

    @classmethod
    def _color_green(cls, value):
        return f"{cls._ANSI_GREEN}{value}{cls._ANSI_RESET}"

    @classmethod
    def _color_blue(cls, value):
        return f"{cls._ANSI_BLUE}{value}{cls._ANSI_RESET}"

    @classmethod
    def _color_purple(cls, value):
        return f"{cls._ANSI_PURPLE}{value}{cls._ANSI_RESET}"

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

    def _log_message_debug(self, direction, message_type, payload, enum_scope, channel_op=None, channel_elapsed_ms=None):
        if not logger.isEnabledFor(logging.DEBUG):
            return
        if hasattr(payload, "DESCRIPTOR"):
            payload_dict = self._proto_to_dict(payload)
        elif isinstance(payload, dict):
            payload_dict = payload
        else:
            payload_dict = {"value": payload}
        payload_dict = self._normalize_debug_payload(payload_dict)
        if isinstance(payload_dict, dict):
            if "expected_type" in payload_dict:
                payload_dict = dict(payload_dict)
                payload_dict["expected_type"] = self._format_type_name(payload_dict["expected_type"], enum_scope)
        payload_text = json.dumps(payload_dict, ensure_ascii=False, sort_keys=True, indent=2)
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
    def _timed_get(get_fn, *args):
        t0 = time.perf_counter()
        result = get_fn(*args)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return result, elapsed_ms

    @staticmethod
    def _timed_put(send_fn, *args):
        t0 = time.perf_counter()
        ret = send_fn(*args)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ret, elapsed_ms

    def _next_seq(self, message_type) -> int:
        seq = int(self._seq_by_type.get(message_type, 0))
        self._seq_by_type[message_type] = seq + 1
        return seq

    @staticmethod
    def _to_float(value, default=0.0):
        if value is None:
            return float(default)
        if isinstance(value, np.ndarray):
            if value.size == 0:
                return float(default)
            return float(value.reshape(-1)[0])
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _to_int(value, default=0):
        if value is None:
            return int(default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @classmethod
    def _to_vec3(cls, value, default=(0.0, 0.0, 0.0)):
        if value is None:
            return tuple(float(v) for v in default)
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
        if arr.size < 3:
            padded = np.asarray(default, dtype=np.float64).copy()
            padded[:arr.size] = arr
            arr = padded
        return float(arr[0]), float(arr[1]), float(arr[2])

    @staticmethod
    def _map_role_type(type_value):
        t = str(type_value).lower()
        if t in ("vehicle", "motorvehicle", "car", "veh", "metadrivetype.vehicle"):
            return enums_pb2.RT_MOTORVEHICLE
        if t in ("pedestrian", "human", "person", "metadrivetype.pedestrian"):
            return enums_pb2.RT_PEDESTRIAN
        if t in ("bicycle", "cyclist", "bike", "nonmotorvehicle", "metadrivetype.cyclist"):
            return enums_pb2.RT_NONMOTORVEHICLE
        return enums_pb2.RT_MOTORVEHICLE

    @staticmethod
    def parse_scene_name_from_session_id(session_id: str) -> str:
        """
        Parse OnSite session_id into MetaDrive scene_name.

        Expected session_id format:
            用户-运行次数-场地编号-作业id-时间戳_目前运行的次数
        Example:
            tj2026-test1-1-1-1771007315895005_20260214022843_1

        Returns:
            scene_name in "{场地编号}_{作业id}" format, e.g. "1_1"
        """
        raw = str(session_id).strip()
        parts = raw.rsplit("-", 3)
        if len(parts) != 4:
            raise ValueError(f"Invalid session_id format: {session_id}")
        field_id = parts[1].strip()
        job_id = parts[2].strip()
        if not field_id or not job_id:
            raise ValueError(f"Invalid session_id format: {session_id}")
        return f"{field_id}_{job_id}"

    def initialize_channels(self):
        """
        Initialize multicast network channels.

        Raises:
            RuntimeError: If channel creation fails
        """
        param = libMulticastNetwork.CreateChannelsParam()
        param.config_center_addr = self.config_center
        param.local_ip = self.local_ip
        param.net_interface_name = self.net_interface
        param.field_id = self.field_id
        param.log_level = 1  # 1-info, 2-warning, 3-error
        param.client_name = self.terminal_type.value
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

        self.channels = libMulticastNetwork.ChannelPtrVector()
        ret = libMulticastNetwork.create_channels(param, self.channels)

        if ret:
            raise RuntimeError(f"Failed to create channels, ret: {ret}")

        # Build channel map
        for c in self.channels:
            logger.info(f"Created channel: {c.name()}, id: {c.id()}")
            self.channel_map[c.name()] = c

        # Assign channel references
        self.prepare_channel = self.channel_map['prepare']
        self.notify_channel = self.channel_map['notify']
        self.role_channel = self.channel_map['pubrole_encrypt']
        self.cmd_channel = self.channel_map['vehiclecontrol']
        self.session_channel = self.channel_map['sessioninfo']
        self.image_channel = self.channel_map['camera']

        # Initialize image decoder
        if not libMulticastNetwork.InitImageDecoder():
            raise RuntimeError("Failed to initialize image decoder")

        logger.info("OnSite middleware initialized successfully")

    def close(self):
        """Close all channels and cleanup resources."""
        logger.info("Closing OnSite middleware")
        # Channels are managed by libMulticastNetwork, no explicit cleanup needed
        if self._daemon_proc is not None:
            if self._daemon_proc.poll() is None:
                self._daemon_proc.terminate()
                try:
                    self._daemon_proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self._daemon_proc.kill()
            self._daemon_proc = None

    # ==================== Receive Methods ====================

    def recv_actor_prepare(self):
        """
        Receive ActorPrepare message from OnSite server.

        Returns:
            tuple: (session_id, actor_id, brief_data, scene_name) if message received, None otherwise
        """
        if self.prepare_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.prepare_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == MT_ACTOR_PREPARE:
            data = libMulticastNetwork.getMessageData(msg)
            prepare_msg = ActorPrepare()
            prepare_msg.ParseFromString(data)
            self._log_message_debug("recv", MT_ACTOR_PREPARE, prepare_msg, "main", channel_op="get", channel_elapsed_ms=get_ms)

            session_id = prepare_msg.session_id
            actor_id = prepare_msg.actor_id
            self.actor_id = actor_id
            scene_name = self.parse_scene_name_from_session_id(session_id)

            # Parse brief_data if available
            brief_data = None
            if prepare_msg.archive_info.brief_data:
                try:
                    brief_data = json.loads(prepare_msg.archive_info.brief_data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse brief_data: {e}")

            logger.info(f"Received ActorPrepare: session={session_id}, actor={actor_id}")
            return (session_id, actor_id, brief_data, scene_name)

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": MT_ACTOR_PREPARE}, "main", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_notify(self):
        """
        Receive Notify message from OnSite server.

        Returns:
            Notify: Notify proto message if received, None otherwise
        """
        if self.notify_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.notify_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == MT_NOTIFY:
            data = libMulticastNetwork.getMessageData(msg)
            notify = Notify()
            notify.ParseFromString(data)
            self._log_message_debug("recv", MT_NOTIFY, notify, "main", channel_op="get", channel_elapsed_ms=get_ms)
            return notify

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": MT_NOTIFY}, "main", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_all_notifies(self):
        """
        Receive all pending Notify messages from OnSite server.

        Returns:
            list: List of Notify proto messages
        """
        notifies = []
        while True:
            notify = self.recv_notify()
            if notify is None:
                break
            notifies.append(notify)
        if notifies:
            logger.debug("OnSite RX notify batch size=%d", len(notifies))
        return notifies

    def recv_pub_role(self):
        """
        Receive PubRole message from OnSite server.

        Returns:
            PubRole: PubRole proto message if received, None otherwise
        """
        if self.role_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.role_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == MT_PUBROLE:
            data = libMulticastNetwork.getMessageData(msg)
            pub_role = PubRole()
            pub_role.ParseFromString(data)
            self._log_message_debug("recv", MT_PUBROLE, pub_role, "main", channel_op="get", channel_elapsed_ms=get_ms)
            return pub_role

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": MT_PUBROLE}, "main", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_vehicle_control(self):
        """
        Receive VehicleControl message and convert to MetaDrive action.

        Returns:
            list: [steering, throttle_brake] if message received, None otherwise
        """
        if self.cmd_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.cmd_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == VEHICLE_CONTROL:
            data = libMulticastNetwork.getMessageData(msg)
            control = VehicleControl()
            control.ParseFromString(data)
            self._log_message_debug(
                "recv", VEHICLE_CONTROL, control, "chassis", channel_op="get", channel_elapsed_ms=get_ms
            )

            # Convert to MetaDrive action
            action = self._vehicle_control_to_action(control)
            return action

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": VEHICLE_CONTROL}, "chassis", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_vehicle_feedback(self):
        """
        Receive VehicleFeedback message from OnSite server.
        Note: This is only received, not used for simulation state.

        Returns:
            VehicleFeedback: VehicleFeedback proto message if received, None otherwise
        """
        if self.cmd_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.cmd_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == VEHICLE_FEEDBACK:
            data = libMulticastNetwork.getMessageData(msg)
            feedback = VehicleFeedback()
            feedback.ParseFromString(data)
            self._log_message_debug(
                "recv", VEHICLE_FEEDBACK, feedback, "chassis", channel_op="get", channel_elapsed_ms=get_ms
            )
            return feedback

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": VEHICLE_FEEDBACK}, "chassis", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_session_info(self):
        """
        Receive SessionInfo message from OnSite server.

        Returns:
            SessionInfo: SessionInfo proto message if received, None otherwise
        """
        if self.session_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        (ret, msg), get_ms = self._timed_get(self.session_channel.get)
        if msg is None or ret < 0:
            time.sleep(self.recv_none_sleep)
            return None

        if msg.type() == MT_SESSIONINFO:
            data = libMulticastNetwork.getMessageData(msg)
            session_info = SessionInfo()
            session_info.ParseFromString(data)
            self._log_message_debug(
                "recv", MT_SESSIONINFO, session_info, "main", channel_op="get", channel_elapsed_ms=get_ms
            )
            return session_info

        self._log_message_debug(
            "recv", msg.type(), {"expected_type": MT_SESSIONINFO}, "main", channel_op="get", channel_elapsed_ms=get_ms
        )
        return None

    def recv_image_rgb(self):
        """
        Receive latest RGB image from OnSite camera channel.

        Returns:
            np.ndarray: Latest image in (H, W, 3) RGB uint8, or None if unavailable
        """
        if self.image_channel is None:
            time.sleep(self.recv_none_sleep)
            return None

        msg, get_ms = self._timed_get(self.image_channel.get_image_simple)
        if len(msg) == 0:
            time.sleep(self.recv_none_sleep)
            return None

        img = None
        images_meta = []
        for image in msg:
            height = int(image.height)
            width = int(image.width)
            encoding = str(image.encoding).lower()
            if encoding != "rgb8":
                logger.warning("Drop image frame: unsupported OnSite image encoding %s, expected rgb8", image.encoding)
                continue
            arr = np.asarray(image.data, dtype=np.uint8).reshape(-1)
            expected = height * width * 3
            if arr.size != expected:
                logger.warning(
                    "Drop image frame: size mismatch got=%d expected=%d (w=%d h=%d c=3)",
                    arr.size,
                    expected,
                    width,
                    height,
                )
                continue
            img = arr.reshape(height, width, 3)
            images_meta.append(
                {
                    "timestamp_sec": float(image.timestamp_sec),
                    "camera_timestamp": int(image.camera_timestamp),
                    "sequence_num": int(image.sequence_num),
                    "measurement_time": float(image.measurement_time),
                    "height": height,
                    "width": width,
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

    # ==================== Send Methods ====================

    def send_actor_prepare_result(self, session_id, actor_id, result=True):
        """
        Send ActorPrepareResult message to OnSite server.

        Args:
            session_id: Session ID from ActorPrepare
            actor_id: Actor ID
            result: Preparation result (default: True)
        """
        if self.prepare_channel is None:
            logger.warning("Prepare channel not available")
            return

        msg = ActorPrepareResult()
        msg.session_id = session_id
        msg.actor_id = actor_id
        msg.result = result
        msg.reason = ""
        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.prepare_channel.put, MT_ACTOR_PREPARE_RESULT, length, data)
        self._log_message_debug(
            "send",
            MT_ACTOR_PREPARE_RESULT,
            {**self._proto_to_dict(msg), "ret": ret},
            "main",
            channel_op="put",
            channel_elapsed_ms=put_ms,
        )

        if ret != 0:
            logger.error(f"Failed to send ActorPrepareResult, ret: {ret}")
        else:
            logger.info(f"Sent ActorPrepareResult: session={session_id}, result={result}")

    def send_sub_role(self, session_id):
        """
        Send SubRole message to OnSite server.
        Note: Only session_id is required, other fields are left empty.

        Args:
            session_id: Current session ID
        """
        if self.role_channel is None:
            logger.warning("Role channel not available")
            return

        msg = SubRole()
        msg.session_id = session_id
        # Other fields (role_types, role_ids, role_AOIs) are left empty

        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.role_channel.put, MT_SUBROLE, length, data)
        self._log_message_debug(
            "send", MT_SUBROLE, {**self._proto_to_dict(msg), "ret": ret}, "main", channel_op="put", channel_elapsed_ms=put_ms
        )

        if ret != 0:
            logger.error(f"Failed to send SubRole, ret: {ret}")
        else:
            logger.info(f"Sent SubRole: session={session_id}")

    def send_pub_role(self, obs, last_received_pub_role, current_timestamp):
        """
        Send PubRole message to OnSite server from env observation.

        Args:
            obs: Actor observation dict (must contain `states`, `surrounding`, optional `global_rlsl`)
            last_received_pub_role: Last received PubRole message (for preserving fields)
            current_timestamp: Current simulation timestamp in microseconds
        """
        if self.role_channel is None:
            logger.warning("Role channel not available")
            return

        role_states = self._extract_role_states_from_obs(obs)

        msg = PubRole()
        ts_us = int(current_timestamp)
        pub_role_seq = self._next_seq(MT_PUBROLE)
        msg.header.sim_ts = ts_us // 1000
        msg.header.send_ts = int(time.time() * 1000)
        msg.header.seq_no = pub_role_seq

        for role_id, state in role_states.items():
            role = self._agent_state_to_single_role(
                role_id, state, last_received_pub_role, current_timestamp, pub_role_seq
            )
            msg.s_roles.append(role)

        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.role_channel.put, MT_PUBROLE, length, data)
        self._log_message_debug(
            "send", MT_PUBROLE, {**self._proto_to_dict(msg), "ret": ret}, "main", channel_op="put", channel_elapsed_ms=put_ms
        )

        if ret != 0:
            logger.error(f"Failed to send PubRole, ret: {ret}")

    def send_vehicle_feedback(self, obs, current_timestamp, last_received_feedback=None):
        """
        Send VehicleFeedback message to OnSite server from env observation.

        Args:
            obs: Actor observation dict (must contain `states`)
            current_timestamp: Current simulation timestamp in microseconds
            last_received_feedback: Last received VehicleFeedback (for preserving fields)
        """
        if self.cmd_channel is None:
            logger.warning("Command channel not available")
            return

        if "states" not in obs:
            logger.warning("Observation missing states, skip VehicleFeedback.")
            return
        vehicle_state = obs["states"]
        msg = self._vehicle_state_to_feedback(vehicle_state, current_timestamp, last_received_feedback)

        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.cmd_channel.put, VEHICLE_FEEDBACK, length, data)
        self._log_message_debug(
            "send",
            VEHICLE_FEEDBACK,
            {**self._proto_to_dict(msg), "ret": ret},
            "chassis",
            channel_op="put",
            channel_elapsed_ms=put_ms,
        )

        if ret != 0:
            logger.error(f"Failed to send VehicleFeedback, ret: {ret}")

    def send_vehicle_control(self, steering, throttle_brake):
        """
        Send VehicleControl message to OnSite server.

        Args:
            steering: Normalized steering in [-1, 1]
            throttle_brake: Normalized throttle/brake in [-1, 1]
        """
        if self.cmd_channel is None:
            logger.warning("Command channel not available")
            return

        steering = float(np.clip(float(steering), -1.0, 1.0))
        throttle_brake = float(np.clip(float(throttle_brake), -1.0, 1.0))

        cmd = VehicleControl()
        cmd.header.send_ts = int(time.time() * 1000)
        cmd.header.sim_ts = int(time.time() * 1000)
        cmd.header.seq_no = self._next_seq(VEHICLE_CONTROL)
        cmd.steering_control.target_steering_wheel_angle = steering * self.MAX_STEERING_RAD

        if throttle_brake >= 0:
            cmd.driving_control.target_accelerator_pedal_position = throttle_brake * 100.0
            cmd.brake_control.target_brake_pedal_position = 0.0
        else:
            cmd.driving_control.target_accelerator_pedal_position = 0.0
            cmd.brake_control.target_brake_pedal_position = -throttle_brake * 100.0

        data = cmd.SerializeToString()
        ret, put_ms = self._timed_put(self.cmd_channel.put, VEHICLE_CONTROL, len(data), data)
        self._log_message_debug(
            "send",
            VEHICLE_CONTROL,
            {**self._proto_to_dict(cmd), "ret": ret},
            "chassis",
            channel_op="put",
            channel_elapsed_ms=put_ms,
        )
        if ret != 0:
            logger.error(f"Failed to send VehicleControl, ret: {ret}")

    def send_images(self, images, timestamp):
        """
        Send multiple images to OnSite server.

        Args:
            images: List of numpy arrays (H, W, 3) in RGB format
            timestamp: Timestamp in seconds
        """
        if self.image_channel is None:
            logger.warning("Image channel not available")
            return

        if not images:
            return

        for img in images:
            if img is None or img.ndim != 3 or img.shape[2] != 3:
                logger.warning(f"Skip invalid image shape: {None if img is None else img.shape}")
                continue
            py_images = []
            py_img = libMulticastNetwork.PyImage()
            py_img.timestamp_sec = timestamp
            py_img.camera_timestamp = int(timestamp * 1e6)
            py_img.sequence_num = self.image_seq
            py_img.measurement_time = timestamp
            py_img.height = img.shape[0]
            py_img.width = img.shape[1]
            py_img.encoding = "rgb8"
            py_img.data = img.ravel()
            py_images.append(py_img)
            self.image_seq += 1

            ret, put_ms = self._timed_put(self.image_channel.put_image_simple, py_images)
            images_meta = [
                {
                    "timestamp_sec": float(py_img.timestamp_sec),
                    "camera_timestamp": int(py_img.camera_timestamp),
                    "sequence_num": int(py_img.sequence_num),
                    "measurement_time": float(py_img.measurement_time),
                    "height": int(py_img.height),
                    "width": int(py_img.width),
                    "encoding": py_img.encoding,
                    "byte_len": int(np.asarray(py_img.data).nbytes),
                }
                for py_img in py_images
            ]
            total_byte_len = int(sum(img_meta["byte_len"] for img_meta in images_meta))
            self._log_message_debug(
                "send",
                "image_batch",
                {"image_count": len(py_images), "images": images_meta, "total_byte_len": total_byte_len, "ret": ret},
                "raw",
                channel_op="put",
                channel_elapsed_ms=put_ms,
            )
            if ret != 0:
                logger.error(f"Failed to send images, ret: {ret}")

    def _extract_role_states_from_obs(self, obs):
        role_states = {}

        actor_state = dict(obs["states"])
        actor_state["rlsl"] = None
        if "global_rlsl" in obs and "actor" in obs["global_rlsl"]:
            actor_state["rlsl"] = obs["global_rlsl"]["actor"]
        role_states[self.actor_id] = actor_state

        if "surrounding" not in obs:
            return role_states

        surrounding = obs["surrounding"]
        has_global_rlsl = "global_rlsl" in obs
        for role_id, s in surrounding.items():
            state = dict(s)
            state["rlsl"] = None
            if has_global_rlsl and role_id in obs["global_rlsl"]:
                state["rlsl"] = obs["global_rlsl"][role_id]
            role_states[role_id] = state

        return role_states

    # ==================== Conversion Utility Functions ====================

    def _vehicle_control_to_action(self, control):
        """
        Convert VehicleControl proto message to MetaDrive action.

        Args:
            control: VehicleControl proto message

        Returns:
            list: [steering, throttle_brake] normalized to [-1, 1]
        """
        # Steering: normalize to [-1, 1]
        steering_angle = control.steering_control.target_steering_wheel_angle
        steering = np.clip(steering_angle / self.MAX_STEERING_RAD, -1.0, 1.0)

        # Throttle/Brake: combine pedal positions
        accelerator = control.driving_control.target_accelerator_pedal_position
        brake = control.brake_control.target_brake_pedal_position
        throttle_brake = (accelerator - brake) / 100.0
        throttle_brake = np.clip(throttle_brake, -1.0, 1.0)

        return [float(steering), float(throttle_brake)]

    def _agent_state_to_single_role(self, agent_id, state, last_received_pub_role, current_timestamp, seq_no):
        """
        Convert agent state to SingleRole proto message.

        Args:
            agent_id: Agent identifier
            state: Dictionary with agent state (position, velocity, heading, etc.)
            last_received_pub_role: Last received PubRole for preserving fields
            current_timestamp: Current timestamp in microseconds

        Returns:
            SingleRole proto message
        """
        from metadrive.misc.onsite_middleware.onsite_proto.main.proto.fields_pb2 import SingleRole

        role = SingleRole()
        role.id = agent_id
        role.name = agent_id
        role.f_status.extend([1.0] + [0.0] * 8)  # Placeholder for status flags
        # Preserve type and size from last received PubRole if available
        cached_role = None
        if last_received_pub_role:
            for r in last_received_pub_role.s_roles:
                if r.id == agent_id:
                    cached_role = r
                    break

        if cached_role:
            role.type = cached_role.type
        else:
            role.type = self._map_role_type(state["type"])
        size_x, size_y, size_z = self._to_vec3(state["size"])
        role.box.size.x = size_x
        role.box.size.y = size_y
        role.box.size.z = size_z

        # Position to ColliderBox bottom_center (x,y unchanged; z shifted by half height).
        pos_x, pos_y, pos_z = self._to_vec3(state['position'])
        role.box.bottom_center.x = pos_x
        role.box.bottom_center.y = pos_y
        role.box.bottom_center.z = pos_z - 0.5 * size_z

        # Rotation (from heading_theta to quaternion)
        heading = self._to_float(state['heading_theta'])
        cos_h = float(np.cos(heading))
        sin_h = float(np.sin(heading))
        rotation = torch.tensor(
            [[[cos_h, -sin_h, 0.0], [sin_h, cos_h, 0.0], [0.0, 0.0, 1.0]]], dtype=torch.float32
        )
        quat_wxyz = matrix_to_quaternion(rotation)[0]
        role.box.rotation.x = float(quat_wxyz[1])
        role.box.rotation.y = float(quat_wxyz[2])
        role.box.rotation.z = float(quat_wxyz[3])
        role.box.rotation.w = float(quat_wxyz[0])

        # Linear velocity
        vel_x, vel_y, vel_z = self._to_vec3(state['velocity'])
        role.linear_speed.x = vel_x
        role.linear_speed.y = vel_y
        role.linear_speed.z = vel_z

        # Angular velocity
        angular_velocity = self._to_float(state['angular_velocity'])
        role.angular_speed.z = angular_velocity

        # Linear acceleration
        acc_x, acc_y, acc_z = self._to_vec3(state['acceleration'])
        role.linear_acceleration.x = acc_x
        role.linear_acceleration.y = acc_y
        role.linear_acceleration.z = acc_z

        # Angular acceleration
        ang_acc = state["angular_acceleration"]
        if isinstance(ang_acc, (int, float, np.integer, np.floating)):
            ang_acc_x, ang_acc_y, ang_acc_z = 0.0, 0.0, float(ang_acc)
        else:
            ang_acc_x, ang_acc_y, ang_acc_z = self._to_vec3(ang_acc)
        role.angular_acceleration.x = ang_acc_x
        role.angular_acceleration.y = ang_acc_y
        role.angular_acceleration.z = ang_acc_z

        # RLSL (optional)
        if "rlsl" in state and state["rlsl"] is not None:
            rlsl = state["rlsl"]
            role.rlsl.road_id = str(rlsl["road_id"])
            role.rlsl.lane_id = self._to_int(rlsl["lane_id"])
            role.rlsl.s = self._to_float(rlsl["s"])
            role.rlsl.l = self._to_float(rlsl["l"])
            role.rlsl.z = self._to_float(rlsl["z"])

        # Timestamp (microseconds to milliseconds, int64)
        ts_us = int(current_timestamp)
        role.report_ts = ts_us // 1000
        role.seq_no = int(seq_no)

        return role

    def _vehicle_state_to_feedback(self, vehicle_state, current_timestamp, last_received_feedback=None):
        """
        Convert vehicle state to VehicleFeedback proto message.

        Args:
            vehicle_state: Dictionary with vehicle state from MetaDrive
            current_timestamp: Current timestamp in microseconds
            last_received_feedback: Last received feedback for preserving fields

        Returns:
            VehicleFeedback proto message
        """
        feedback = VehicleFeedback()

        # Header
        ts_us = int(current_timestamp)
        feedback.header.sim_ts = ts_us // 1000  # microseconds to milliseconds, int64
        feedback.header.send_ts = int(time.time() * 1000)
        feedback.header.seq_no = self._next_seq(VEHICLE_FEEDBACK)

        # Steering feedback
        feedback.steering_feedback.steering_wheel_angle = self._to_float(vehicle_state['steering_wheel_angle'])
        feedback.steering_feedback.steering_wheel_speed = self._to_float(vehicle_state['steering_wheel_speed'])
        feedback.steering_feedback.left_directive_wheel_angle = self._to_float(
            vehicle_state['left_directive_wheel_angle']
        )
        feedback.steering_feedback.right_directive_wheel_angle = self._to_float(
            vehicle_state['right_directive_wheel_angle']
        )

        # Driving feedback
        throttle_brake = self._to_float(vehicle_state['throttle_brake'])
        feedback.driving_feedback.accelerator_pedal_position = max(0, throttle_brake * 100)

        # Brake feedback
        feedback.brake_feedback.brake_pedal_position = max(0, -throttle_brake * 100)

        # BCM feedback
        vel = np.asarray(vehicle_state["velocity"], dtype=np.float64).reshape(-1)
        vehicle_speed = np.linalg.norm(vel[:2]) if vel.size >= 2 else 0.0
        feedback.bcm_feedback.vehicle_speed = float(vehicle_speed)  # m/s
        feedback.bcm_feedback.longitudinal_acceleration = self._to_float(
            vehicle_state['longitudinal_acceleration']
        )
        feedback.bcm_feedback.front_left_wheel_speed = self._to_float(vehicle_state['front_left_wheel_speed'])  # m/s
        feedback.bcm_feedback.fron_right_wheel_speed = self._to_float(vehicle_state['front_right_wheel_speed'])  # m/s
        feedback.bcm_feedback.rear_left_wheel_speed = self._to_float(vehicle_state['rear_left_wheel_speed'])  # m/s
        feedback.bcm_feedback.rear_right_wheel_speed = self._to_float(vehicle_state['rear_right_wheel_speed'])  # m/s

        # Preserve fields from last received feedback if available
        if last_received_feedback:
            # Copy fields that MetaDrive cannot provide
            if last_received_feedback.HasField('driving_feedback'):
                feedback.driving_feedback.engine_rpm = last_received_feedback.driving_feedback.engine_rpm
            if last_received_feedback.HasField('gear_feedback'):
                feedback.gear_feedback.CopyFrom(last_received_feedback.gear_feedback)

        return feedback
