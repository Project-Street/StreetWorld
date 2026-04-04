"""
OnSite Middleware for MetaDrive integration.

This module provides the OnSiteMiddleware class that encapsulates all OnSite communication logic,
including message sending/receiving and data format conversion between OnSite proto and MetaDrive.
"""

import json
import logging
import os
import signal
import sys
import time
import subprocess
import ctypes as C
from enum import Enum
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
import PyNvVideoCodec as nvc
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

_INT64_MAX = (1 << 63) - 1


class TERMINAL_TYPE(Enum):
    SIMULATOR = "simulator"
    TESTEE = "apollo_testee"


class SIM_STATE(Enum):
    IDLE = "idle"
    PREPARED = "prepared"
    STARTED = "started"


class OnSiteSwitch:
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
    _PUBROLE_ENCRYPT_KEY = (57, 13, 101, 66, 98, 99, 17, 92, 111, 151)

    def __init__(
        self,
        onsite_dir,
        terminal_type=TERMINAL_TYPE.SIMULATOR,
        image_sizes=None,
        n_warm_up=10,
    ):
        """
        Initialize OnSite middleware.

        Args:
            onsite_dir: OnSite workspace directory, containing config/common.yaml and daemon/start.sh
            terminal_type: OnSite terminal type enum for channel client_name
            image_sizes: Dict of camera_name -> (H, W) image sizes for warm-up
            n_warm_up: Number of random warm-up image batches to send (timestamp=-1)
        """
        self.onsite_dir = Path(onsite_dir).expanduser().resolve()
        self._daemon_proc = None
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
        self.actor_id = None
        # Sequence counters
        self.image_seq = 0
        self._seq_by_type = {}
        self._camera_encoders = {}
        self._camera_decoders = {}
        self._image_sizes = image_sizes or {}
        self._n_warm_up = max(0, int(n_warm_up))
        self._vts_map_module = None
        self._rlsl_map = None
        self._rlsl_scene_name = None

        # Send only this logger to a dedicated file.
        self._init_logger()

        # Initialize channels

        self.initialize_channels()
        if self.terminal_type == TERMINAL_TYPE.SIMULATOR:
            self._setup_camera_encoders_and_warmup()

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
        daemon_dir = self.onsite_dir / "daemon"
        daemon_bin = daemon_dir / "daemon"
        daemon_lib_dir = daemon_dir / "Lib"
        if not daemon_bin.exists():
            logger.info("OnSite daemon not started because binary is missing: %s", daemon_bin)
            raise FileNotFoundError(f"OnSite daemon binary not found: {daemon_bin}")

        daemon_query = subprocess.run(
            ["pgrep", "-a", "-x", daemon_bin.name],
            capture_output=True,
            text=True,
        )
        if daemon_query.returncode == 0:
            logger.info(
                "OnSite daemon already running, skip start. %s",
                daemon_query.stdout.splitlines()[0].strip(),
            )
            return
        if daemon_query.returncode != 1:
            raise RuntimeError(f"Failed to query existing daemon process: {daemon_query.stderr.strip()}")

        env = os.environ.copy()
        ld_library_path = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = (
            f"{daemon_lib_dir}:{ld_library_path}" if ld_library_path else str(daemon_lib_dir)
        )
        self._daemon_proc = subprocess.Popen(
            [str(daemon_bin)],
            cwd=str(daemon_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(3)
        if self._daemon_proc.poll() is None:
            logger.info("Started OnSite daemon process pid=%s via %s", self._daemon_proc.pid, daemon_bin)
            return
        logger.info(
            "OnSite daemon was not started successfully; pid=%s exited early with code=%s",
            self._daemon_proc.pid,
            self._daemon_proc.returncode,
        )

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

    @classmethod
    def _pubrole_encrypt(cls, data: bytes) -> bytes:
        if not data:
            return data
        encrypted = bytearray(data)
        key = cls._PUBROLE_ENCRYPT_KEY
        key_len = len(key)
        for i in range(len(encrypted)):
            encrypted[i] ^= key[i % key_len]
        return bytes(encrypted)

    @staticmethod
    def _timed_put(send_fn, *args):
        t0 = time.perf_counter()
        ret = send_fn(*args)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return ret, elapsed_ms

    def _setup_camera_encoders_and_warmup(self):
        if not self._image_sizes:
            return
        enc_config = {
            "preset": "P3",
            "tuning_info": "high_quality",
            "rc": "vbr",
            "fps": 10,
            "bitrate": 5000000,
            "maxbitrate": 5000000,
            "codec": "h264",
        }
        for name, (height, width) in self._image_sizes.items():
            self._camera_encoders[name] = nvc.CreateEncoder(width, height, "NV12", True, **enc_config)
        if self._n_warm_up <= 0:
            return
        rng = np.random.default_rng()
        logger.info(
            "Warming up image encoder with %d batches, sizes=%s",
            self._n_warm_up,
            self._image_sizes,
        )
        for _ in range(self._n_warm_up):
            warm_images = {
                name: rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
                for name, (height, width) in self._image_sizes.items()
            }
            self.send_images(warm_images, timestamp=-1)

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
    def parse_scene_name_from_archive_id(archive_id: str) -> str:
        """
        Parse scene_name from ActorPrepare.archive_info.id.

        Example:
            lua/replay/2_1 -> 2_1
        """
        raw = str(archive_id).strip().strip("/")
        scene_name = raw.rsplit("/", 1)[-1].strip()
        if not scene_name:
            raise ValueError(f"Invalid archive_id format: {archive_id}")
        return scene_name

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
        try:
            ret = libMulticastNetwork.create_channels(param, self.channels)

            if ret:
                raise RuntimeError(f"ret is not zero, {ret}.")
        except Exception as e:
            raise RuntimeError(f"Exception while creating channels: {e}") from e

        # Build channel map.
        # NOTE: Avoid iterating ChannelPtrVector directly. Some pybind11 bindings
        # throw pybind11::stop_iteration without translating to Python, which
        # aborts the process. Index-based access is safer here.
        count = len(self.channels)
        for i in range(count):
            c = self.channels[i]
            logger.info(f"Created channel: {c.name()}, id: {c.id()}")
            self.channel_map[c.name()] = c

        logger.info("OnSite middleware initialized successfully")

    def close(self):
        """Close all channels and cleanup resources."""
        # Channels are managed by libMulticastNetwork, no explicit cleanup needed
        if self._daemon_proc is not None:
            if self._daemon_proc.poll() is None:
                logger.info("Closing OnSite middleware")
                os.killpg(self._daemon_proc.pid, signal.SIGINT)
                try:
                    self._daemon_proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    logger.warning("OnSite daemon did not exit after SIGINT, escalating to SIGTERM")
                    os.killpg(self._daemon_proc.pid, signal.SIGTERM)
                    try:
                        self._daemon_proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        logger.warning("OnSite daemon did not exit after SIGTERM, escalating to SIGKILL")
                        os.killpg(self._daemon_proc.pid, signal.SIGKILL)
                        try:
                            self._daemon_proc.wait(timeout=1.0)
                        except subprocess.TimeoutExpired:
                            logger.error("Timed out waiting for OnSite daemon to reap after SIGKILL")
                            self._daemon_proc = None
                            return
            logger.info("OnSite daemon process exited. pid=%s, returncode=%s", self._daemon_proc.pid, self._daemon_proc.returncode)
            self._daemon_proc = None

    # ==================== Receive Methods ====================

    def recv_actor_prepare(self):
        """
        Receive ActorPrepare message from OnSite server.

        Returns:
            tuple: (session_id, actor_id, brief_data, scene_name) if message received, None otherwise
        """
        (ret, msg), get_ms = self._timed_get(self.channel_map["prepare"].get)
        if msg is None or ret < 0:
            return None

        if msg.type() == MT_ACTOR_PREPARE:
            data = libMulticastNetwork.getMessageData(msg)
            prepare_msg = ActorPrepare()
            prepare_msg.ParseFromString(data)
            self._log_message_debug("recv", MT_ACTOR_PREPARE, prepare_msg, "main", channel_op="get", channel_elapsed_ms=get_ms)

            session_id = prepare_msg.session_id
            actor_id = prepare_msg.actor_id
            self.actor_id = actor_id
            scene_name = self.parse_scene_name_from_archive_id(prepare_msg.archive_info.id)

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

    def configure_rlsl_map(self, scene_config_directory, scene_name):
        """
        Configure RLSL map source from scene config.

        Args:
            scene_config_directory: Directory that contains scene yaml configs.
            scene_name: Scene name, yaml file is "<scene_name>.yaml".
        """

        if self._rlsl_map is not None and self._rlsl_scene_name == scene_name:
            return

        cfg_dir = Path(scene_config_directory).expanduser()
        cfg_path = cfg_dir / f"{scene_name}.yaml"

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        scene_root = data.get("scene_root")
        scene_uuid = data.get("scene_uuid")

        scene_root_path = Path(scene_root)
        if not scene_root_path.is_absolute():
            scene_root_path = (Path.cwd() / scene_root_path).resolve()

        xodr_path = scene_root_path / str(scene_uuid) / "corrected_map.xodr"
        if not xodr_path.exists():
            logger.warning("RLSL xodr not found: %s", xodr_path)
            self._rlsl_map = None
            self._rlsl_scene_name = None
            return

        if self._vts_map_module is None:
            try:
                import vts_map  # pylint: disable=import-outside-toplevel
                self._vts_map_module = vts_map
            except Exception as e:
                logger.warning("Cannot import vts_map, disable RLSL map lookup: %s", e)
                self._rlsl_map = None
                self._rlsl_scene_name = None
                return

        try:
            m = self._vts_map_module.Map()
            handle = 0
            m.load(str(xodr_path), handle)
            self._rlsl_map = m
            self._rlsl_scene_name = scene_name
            logger.info("Configured RLSL xodr map for scene=%s from %s", scene_name, xodr_path)
        except Exception as e:
            logger.warning("Failed to load RLSL xodr map from %s: %s", xodr_path, e)
            self._rlsl_map = None
            self._rlsl_scene_name = None

    def _build_rlsl_from_position(self, position) -> Optional[dict]:
        if self._rlsl_map is None or self._vts_map_module is None:
            return None

        try:
            px, py, pz = self._to_vec3(position)
            xyz = self._vts_map_module.XYZ(px, py, pz)
            slz = self._vts_map_module.SLZ()
            self._rlsl_map.find_slz_global(xyz, slz)
            return {
                "road_id": str(slz.lane_id.road_id),
                "lane_id": int(slz.lane_id.local_id),
                "s": float(slz.s),
                "l": float(slz.l),
                "z": float(slz.z),
            }
        except Exception:
            logger.debug("Failed to build RLSL from position=%s", position, exc_info=True)
            return None

    def recv_notify(self):
        """
        Receive Notify message from OnSite server.

        Returns:
            Notify: Notify proto message if received, None otherwise
        """
        (ret, msg), get_ms = self._timed_get(self.channel_map["notify"].get)
        if msg is None or ret < 0:
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
        (ret, msg), get_ms = self._timed_get(self.channel_map["pubrole_encrypt"].get)
        if msg is None or ret < 0:
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

        (ret, msg), get_ms = self._timed_get(self.channel_map["vehiclecontrol"].get)
        if msg is None or ret < 0:
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

        (ret, msg), get_ms = self._timed_get(self.channel_map["vehiclecontrol"].get)
        if msg is None or ret < 0:
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

        (ret, msg), get_ms = self._timed_get(self.channel_map["sessioninfo"].get)
        if msg is None or ret < 0:
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

    def recv_image(self):
        """
        Receive image batch from OnSite camera channel and decode to RGB.

        Returns:
            list: list[dict], each item contains:
                - rgb: np.ndarray with shape (H, W, 3) in RGB uint8
                - camera_timestamp: int
        """
        images, get_ms = self._timed_get(self.channel_map["camera"].get_image_simple)
        if images is None or len(images) == 0:
            return None

        decoded_images = []
        for i, image in enumerate(images):
            if image.measurement_time == -1:
                logger.debug("Drop warm-up image: index=%d measurement_time=%s", i, image.measurement_time)
                continue
            if image.data is None or len(image.data) == 0:
                logger.warning("Drop empty image payload: index=%d", i)
                continue
            # if str(image.encoding).lower() != "h264":
            #     raise ValueError(f"Unsupported image encoding: {image.encoding}, expected h264")
            packet = nvc.PacketData()
            packet.bsl = len(image.data)
            packet.bsl_data = image.data.__array_interface__["data"][0]

            decoder = self._camera_decoders.get(i)
            if decoder is None:
                decoder = nvc.CreateDecoder(
                    gpuid=0,
                    codec=nvc.cudaVideoCodec.H264,
                    usedevicememory=False,
                )
                self._camera_decoders[i] = decoder
            raw_frames = decoder.Decode(packet)
            if len(raw_frames) == 0:
                logger.warning("Failed to decode image packet, empty raw frames: index=%d", i)
                continue
            for raw_frame in raw_frames:
                luma_base_addr = raw_frame.GetPtrToPlane(0)
                frame_data = np.ctypeslib.as_array(
                    C.cast(luma_base_addr, C.POINTER(C.c_uint8)),
                    shape=(raw_frame.framesize(),),
                )
                frame_nv12 = frame_data.reshape(int(image.height * 1.5), int(image.width))
                frame_rgb = cv2.cvtColor(frame_nv12, cv2.COLOR_YUV2RGB_NV12)
                camera_timestamp = int(image.camera_timestamp)
                if camera_timestamp < 0 or camera_timestamp > _INT64_MAX:
                    logger.error(
                        "Suspicious camera_timestamp detected: index=%d sequence_num=%s measurement_time=%s camera_timestamp=%s",
                        i,
                        image.sequence_num,
                        image.measurement_time,
                        camera_timestamp,
                    )
                    breakpoint()
                decoded_images.append(
                    {
                        "rgb": frame_rgb,
                        "camera_timestamp": camera_timestamp,
                    }
                )

        if len(decoded_images) == 0:
            return None

        self._log_message_debug(
            "recv",
            "image_batch",
            {
                "image_count": len(images),
                "decoded_count": len(decoded_images),
            },
            "raw",
            channel_op="get",
            channel_elapsed_ms=get_ms,
        )
        return decoded_images

    # ==================== Send Methods ====================

    def send_actor_prepare_result(self, session_id, actor_id, result=True):
        """
        Send ActorPrepareResult message to OnSite server.

        Args:
            session_id: Session ID from ActorPrepare
            actor_id: Actor ID
            result: Preparation result (default: True)
        """
        msg = ActorPrepareResult()
        msg.session_id = session_id
        msg.actor_id = actor_id
        msg.result = result
        msg.reason = ""
        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.channel_map["prepare"].put, MT_ACTOR_PREPARE_RESULT, length, data)
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
        msg = SubRole()
        msg.session_id = session_id
        # Other fields (role_types, role_ids, role_AOIs) are left empty

        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.channel_map["pubrole_encrypt"].put, MT_SUBROLE, length, data)
        self._log_message_debug(
            "send", MT_SUBROLE, {**self._proto_to_dict(msg), "ret": ret}, "main", channel_op="put", channel_elapsed_ms=put_ms
        )

        if ret != 0:
            logger.error(f"Failed to send SubRole, ret: {ret}")
        else:
            logger.info(f"Sent SubRole: session={session_id}")

    def send_pub_role(self, obs, last_received_pub_role, current_timestamp, session_id=""):
        """
        Send PubRole message to OnSite server from env observation.

        Args:
            obs: Actor observation dict (must contain `states`, `surrounding`)
            last_received_pub_role: Last received PubRole message (for preserving fields)
            current_timestamp: Current simulation timestamp in microseconds
            session_id: Current session ID
        """
        role_states = self._extract_role_states_from_obs(obs)

        msg = PubRole()
        msg.session_id = str(session_id)
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
        ret, put_ms = self._timed_put(self.channel_map["pubrole"].put, MT_PUBROLE, len(data), data)
        data_enc = self._pubrole_encrypt(data)
        ret_enc, put_enc_ms = self._timed_put(self.channel_map["pubrole_encrypt"].put, MT_PUBROLE, len(data_enc), data_enc)
        self._log_message_debug(
            "send", MT_PUBROLE, {**self._proto_to_dict(msg), "ret": [ret, ret_enc]}, "main", channel_op="put", channel_elapsed_ms=put_ms + put_enc_ms
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
        vehicle_state = obs["states"]
        msg = self._vehicle_state_to_feedback(vehicle_state, current_timestamp, last_received_feedback)

        data = msg.SerializeToString()
        length = len(data)
        ret, put_ms = self._timed_put(self.channel_map["vehiclecontrol"].put, VEHICLE_FEEDBACK, length, data)
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
        ret, put_ms = self._timed_put(self.channel_map["vehiclecontrol"].put, VEHICLE_CONTROL, len(data), data)
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
            images: Dict of camera_name -> numpy array (H, W, 3) in RGB format
            timestamp: Timestamp in seconds
        """
        if not images:
            raise ValueError("images must be a non-empty dict")

        py_images = []
        for camera_name, img in images.items():
            height, width = img.shape[:2]
            encoder = self._camera_encoders[camera_name]

            img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            img_i420 = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2YUV_I420)
            y = img_i420[:height, :]
            u = img_i420[height:height + height // 4, :].reshape(-1)
            v = img_i420[height + height // 4:, :].reshape(-1)
            uv = np.empty((u.size + v.size,), dtype=u.dtype)
            uv[0::2] = u
            uv[1::2] = v
            img_nv12 = np.concatenate([y.ravel(), uv])
            bitstream = encoder.Encode(img_nv12)
            if bitstream is None or len(bitstream) == 0:
                logger.warning(
                    "Encoder returned empty bitstream, sending empty payload (height=%d, width=%d)",
                    height,
                    width,
                )
                payload = np.frombuffer(b"", dtype=np.uint8)
            else:
                payload = np.frombuffer(bitstream, dtype=np.uint8)

            py_img = libMulticastNetwork.PyImage()
            py_img.timestamp_sec = float(timestamp)
            if timestamp < 0:
                py_img.camera_timestamp = 0
            else:
                py_img.camera_timestamp = int(timestamp * 1e6)
            py_img.measurement_time = float(timestamp)
            py_img.sequence_num = self.image_seq
            py_img.height = height
            py_img.width = width
            py_img.encoding = "h264"
            py_img.data = payload
            py_images.append(py_img)
            self.image_seq += 1

        ret, put_ms = self._timed_put(self.channel_map["camera"].put_image_simple, py_images)
        images_meta = [
            {
                "timestamp_sec": py_img.timestamp_sec,
                "camera_timestamp": py_img.camera_timestamp,
                "sequence_num": py_img.sequence_num,
                "measurement_time": py_img.measurement_time,
                "height": py_img.height,
                "width": py_img.width,
                "encoding": py_img.encoding,
                "byte_len": np.asarray(py_img.data).nbytes,
            }
            for py_img in py_images
        ]
        total_byte_len = sum(img_meta["byte_len"] for img_meta in images_meta)
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
        actor_state["rlsl"] = self._build_rlsl_from_position(actor_state.get("position"))
        role_states[self.actor_id] = actor_state

        if "surrounding" not in obs:
            return role_states

        surrounding = obs["surrounding"]
        for role_id, s in surrounding.items():
            state = dict(s)
            state["rlsl"] = self._build_rlsl_from_position(state.get("position"))
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
        role.s_status.append(str(agent_id))
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
