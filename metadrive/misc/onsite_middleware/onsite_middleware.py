"""
OnSite Middleware for MetaDrive integration.

This module provides the OnSiteMiddleware class that encapsulates all OnSite communication logic,
including message sending/receiving and data format conversion between OnSite proto and MetaDrive.
"""

import json
import logging
import sys
import time
from pathlib import Path
import numpy as np
from google.protobuf.json_format import MessageToDict

import libMulticastNetwork

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
    _ANSI_PURPLE = "\033[95m"
    _ANSI_RESET = "\033[0m"

    def __init__(self, config_center, field_id, net_interface, local_ip):
        """
        Initialize OnSite middleware.

        Args:
            config_center: Config center address (e.g., "10.11.17.88:52009")
            field_id: Unique field ID (must match daemon and simulator)
            net_interface: Network interface name (e.g., "eno2")
            local_ip: Local IP address
        """
        self.config_center = config_center
        self.field_id = field_id
        self.net_interface = net_interface
        self.local_ip = local_ip

        # Channel references
        self.channels = None
        self.channel_map = {}
        self.prepare_channel = None
        self.notify_channel = None
        self.role_channel = None
        self.cmd_channel = None
        self.session_channel = None
        self.image_channel = None
        self.actor_id 
        # Sequence counters
        self.image_seq = 0
        self._seq_by_type = {}

        # Send only this logger to a dedicated file.
        self._init_logger()

        # Initialize channels
        self.initialize_channels()

    def _init_logger(self):
        logger.setLevel(logging.DEBUG)
        ts = get_log_timestamp()
        self.log_ts = ts
        # Share timestamp with other modules (e.g., onsite_integration).
        try:
            import os
            os.environ["ONSITE_LOG_TS"] = ts
        except Exception:
            pass
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"onsitemiddleware_{ts}.logs"
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

    def _log_message_debug(self, direction, message_type, payload, enum_scope):
        if not logger.isEnabledFor(logging.DEBUG):
            return
        if hasattr(payload, "DESCRIPTOR"):
            payload_dict = self._proto_to_dict(payload)
        elif isinstance(payload, dict):
            payload_dict = payload
        else:
            payload_dict = {"value": payload}
        if isinstance(payload_dict, dict):
            if "expected_type" in payload_dict:
                payload_dict = dict(payload_dict)
                payload_dict["expected_type"] = self._format_type_name(payload_dict["expected_type"], enum_scope)
        payload_text = json.dumps(payload_dict, ensure_ascii=False, sort_keys=True, indent=2)
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
        param.client_name = "simulator"
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
        self.role_channel = self.channel_map['pubrole']
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

    # ==================== Receive Methods ====================

    def recv_actor_prepare(self):
        """
        Receive ActorPrepare message from OnSite server.

        Returns:
            tuple: (session_id, actor_id, brief_data, scene_name) if message received, None otherwise
        """
        if self.prepare_channel is None:
            return None

        ret, msg = self.prepare_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == MT_ACTOR_PREPARE:
            data = libMulticastNetwork.getMessageData(msg)
            prepare_msg = ActorPrepare()
            prepare_msg.ParseFromString(data)
            self._log_message_debug("recv", MT_ACTOR_PREPARE, prepare_msg, "main")

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

        self._log_message_debug("recv", msg.type(), {"expected_type": MT_ACTOR_PREPARE}, "main")
        return None

    def recv_notify(self):
        """
        Receive Notify message from OnSite server.

        Returns:
            Notify: Notify proto message if received, None otherwise
        """
        if self.notify_channel is None:
            return None

        ret, msg = self.notify_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == MT_NOTIFY:
            data = libMulticastNetwork.getMessageData(msg)
            notify = Notify()
            notify.ParseFromString(data)
            self._log_message_debug("recv", MT_NOTIFY, notify, "main")
            return notify

        self._log_message_debug("recv", msg.type(), {"expected_type": MT_NOTIFY}, "main")
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
            return None

        ret, msg = self.role_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == MT_PUBROLE:
            data = libMulticastNetwork.getMessageData(msg)
            pub_role = PubRole()
            pub_role.ParseFromString(data)
            self._log_message_debug("recv", MT_PUBROLE, pub_role, "main")
            return pub_role

        self._log_message_debug("recv", msg.type(), {"expected_type": MT_PUBROLE}, "main")
        return None

    def recv_vehicle_control(self):
        """
        Receive VehicleControl message and convert to MetaDrive action.

        Returns:
            list: [steering, throttle_brake] if message received, None otherwise
        """
        if self.cmd_channel is None:
            return None

        ret, msg = self.cmd_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == VEHICLE_CONTROL:
            data = libMulticastNetwork.getMessageData(msg)
            control = VehicleControl()
            control.ParseFromString(data)
            self._log_message_debug("recv", VEHICLE_CONTROL, control, "chassis")

            # Convert to MetaDrive action
            action = self._vehicle_control_to_action(control)
            return action

        self._log_message_debug("recv", msg.type(), {"expected_type": VEHICLE_CONTROL}, "chassis")
        return None

    def recv_vehicle_feedback(self):
        """
        Receive VehicleFeedback message from OnSite server.
        Note: This is only received, not used for simulation state.

        Returns:
            VehicleFeedback: VehicleFeedback proto message if received, None otherwise
        """
        if self.cmd_channel is None:
            return None

        ret, msg = self.cmd_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == VEHICLE_FEEDBACK:
            data = libMulticastNetwork.getMessageData(msg)
            feedback = VehicleFeedback()
            feedback.ParseFromString(data)
            self._log_message_debug("recv", VEHICLE_FEEDBACK, feedback, "chassis")
            return feedback

        self._log_message_debug("recv", msg.type(), {"expected_type": VEHICLE_FEEDBACK}, "chassis")
        return None

    def recv_session_info(self):
        """
        Receive SessionInfo message from OnSite server.

        Returns:
            SessionInfo: SessionInfo proto message if received, None otherwise
        """
        if self.session_channel is None:
            return None

        ret, msg = self.session_channel.get()
        if msg is None or ret < 0:
            return None

        if msg.type() == MT_SESSIONINFO:
            data = libMulticastNetwork.getMessageData(msg)
            session_info = SessionInfo()
            session_info.ParseFromString(data)
            self._log_message_debug("recv", MT_SESSIONINFO, session_info, "main")
            return session_info

        self._log_message_debug("recv", msg.type(), {"expected_type": MT_SESSIONINFO}, "main")
        return None

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
        ret = self.prepare_channel.put(MT_ACTOR_PREPARE_RESULT, length, data)
        self._log_message_debug("send", MT_ACTOR_PREPARE_RESULT, {**self._proto_to_dict(msg), "ret": ret}, "main")

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
        ret = self.role_channel.put(MT_SUBROLE, length, data)
        self._log_message_debug("send", MT_SUBROLE, {**self._proto_to_dict(msg), "ret": ret}, "main")

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

        # Add actor first

        # Add participants
        for agent_id, state in role_states.items():
            if agent_id == "actor":
                role = self._agent_state_to_single_role(
                    self.actor_id, role_states['actor'], last_received_pub_role, current_timestamp, pub_role_seq
                )
            else:
                role = self._agent_state_to_single_role(
                    agent_id, state, last_received_pub_role, current_timestamp, pub_role_seq
                )
            msg.s_roles.append(role)

        data = msg.SerializeToString()
        length = len(data)
        ret = self.role_channel.put(MT_PUBROLE, length, data)
        self._log_message_debug("send", MT_PUBROLE, {**self._proto_to_dict(msg), "ret": ret}, "main")

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
        ret = self.cmd_channel.put(VEHICLE_FEEDBACK, length, data)
        self._log_message_debug("send", VEHICLE_FEEDBACK, {**self._proto_to_dict(msg), "ret": ret}, "chassis")

        if ret != 0:
            logger.error(f"Failed to send VehicleFeedback, ret: {ret}")

    def send_images(self, images, timestamp):
        """
        Send multiple images to OnSite server.

        Args:
            images: List of numpy arrays (H, W, 3) in BGR format
            timestamp: Timestamp in seconds
        """
        if self.image_channel is None:
            logger.warning("Image channel not available")
            return

        if not images:
            return

        for img in images:
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

            ret = self.image_channel.put_image_simple(py_images)
            images_meta = [
                {
                    "timestamp_sec": float(py_img.timestamp_sec),
                    "camera_timestamp": int(py_img.camera_timestamp),
                    "sequence_num": int(py_img.sequence_num),
                    "measurement_time": float(py_img.measurement_time),
                    "height": int(py_img.height),
                    "width": int(py_img.width),
                    "encoding": py_img.encoding,
                }
                for py_img in py_images
            ]
            self._log_message_debug(
                "send",
                "image_batch",
                {"image_count": len(py_images), "images": images_meta, "ret": ret},
                "raw",
            )
            if ret != 0:
                logger.error(f"Failed to send images, ret: {ret}")

    def _extract_role_states_from_obs(self, obs):
        role_states = {}

        actor_state = dict(obs["states"])
        actor_state["rlsl"] = None
        if "global_rlsl" in obs and "actor" in obs["global_rlsl"]:
            actor_state["rlsl"] = obs["global_rlsl"]["actor"]
        role_states["actor"] = actor_state

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

    def _euler_to_quaternion(self, roll, pitch, yaw):
        """
        Convert Euler angles to quaternion.

        Args:
            roll: Roll angle in radians
            pitch: Pitch angle in radians
            yaw: Yaw angle in radians

        Returns:
            tuple: (x, y, z, w) quaternion
        """
        cy = np.cos(yaw * 0.5)
        sy = np.sin(yaw * 0.5)
        cp = np.cos(pitch * 0.5)
        sp = np.sin(pitch * 0.5)
        cr = np.cos(roll * 0.5)
        sr = np.sin(roll * 0.5)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy

        return (x, y, z, w)

    def _quaternion_to_matrix(self, position, quaternion):
        """
        Convert quaternion and position to 4x4 transform matrix.

        Args:
            position: Position proto message with x, y, z
            quaternion: Quaternion proto message with x, y, z, w

        Returns:
            np.ndarray: 4x4 transformation matrix
        """
        x, y, z, w = quaternion.x, quaternion.y, quaternion.z, quaternion.w

        # Quaternion to rotation matrix
        R = np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - w*z), 2*(x*z + w*y)],
            [2*(x*y + w*z), 1 - 2*(x*x + z*z), 2*(y*z - w*x)],
            [2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x*x + y*y)]
        ])

        # Construct 4x4 transform matrix
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = [position.x, position.y, position.z]

        return T

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
        role.f_status = [1] + [0] * 8  # Placeholder for status flags
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
        quat = self._euler_to_quaternion(0, 0, heading)
        role.box.rotation.x = quat[0]
        role.box.rotation.y = quat[1]
        role.box.rotation.z = quat[2]
        role.box.rotation.w = quat[3]

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
