from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import grpc
import gymnasium as gym
import numpy as np
from google.protobuf.json_format import MessageToDict

import metadrive.grpc.streetworld_grpc.service_pb2 as service_pb2  # type: ignore
import metadrive.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc  # type: ignore



class GrpcClientEnv(gym.Env):
    """
    Gym-compatible gRPC client env.

    It mirrors ScenarioEnv's IO contract:
    - reset() returns: ((obs_img, obs_info), reset_info)
    - step(action) returns: ((obs_img, obs_info), reward, terminated, truncated, step_info)
    """

    metadata = {}

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 50052,
        timeout_sec: float = 10.0,
        auto_wait_ready: bool = True,
    ):
        super().__init__()
        self.host = host
        self.port = int(port)
        self.timeout_sec = float(timeout_sec)
        self._connectivity_events = []

        channel_options = [
            ("grpc.max_send_message_length", 200 * 1024 * 1024),
            ("grpc.max_receive_message_length", 200 * 1024 * 1024),
        ]

        self.channel = grpc.insecure_channel(
            f"{self.host}:{self.port}",
            options=channel_options,
        )
        self.channel.subscribe(self._on_connectivity_change, try_to_connect=True)
        self.stub = service_pb2_grpc.EnvServiceStub(self.channel)

        if auto_wait_ready:
            self._wait_channel_ready()

        self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)
        self.observation_space = gym.spaces.Dict({})

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Tuple[Dict[str, np.ndarray], Dict[str, Any]], Dict[str, Any]]:
        del seed

        req_kwargs: Dict[str, Any] = {}
        # Reset often includes heavy scene/model initialization, so allow a longer RPC deadline.
        response = self.stub.Reset(
            service_pb2.ResetRequest(**req_kwargs),
            timeout=self.timeout_sec * 2.0,
            wait_for_ready=True,
        )
        if getattr(response, "status", False):
            raise RuntimeError(f"Reset failed: {getattr(response, 'message', '')}")

        obs_img, obs_info = self._deserialize_observation(response.observation)
        reset_info = self._struct_to_dict(getattr(response, "StepInfo", None))

        return (obs_img, obs_info), reset_info

    def step(
        self, action: np.ndarray
    ) -> Tuple[Tuple[Dict[str, np.ndarray], Dict[str, Any]], float, bool, bool, Dict[str, Any]]:
        act = np.asarray(action, dtype=np.float32).reshape(-1)
        if act.size < 2:
            raise ValueError(f"Action must have at least 2 elements, got shape {act.shape}")

        response = self.stub.Step(
            service_pb2.StepRequest(action=act[:2].tolist()),
            timeout=self.timeout_sec,
            wait_for_ready=True,
        )
        if getattr(response, "status", False):
            raise RuntimeError(f"Step failed: {getattr(response, 'message', '')}")

        obs_img, obs_info = self._deserialize_observation(response.observation)
        step_info = self._struct_to_dict(getattr(response, "StepInfo", None))

        return (
            (obs_img, obs_info),
            float(response.reward),
            bool(response.terminated),
            bool(response.truncated),
            step_info,
        )

    def close(self) -> None:
        if getattr(self, "channel", None) is not None:
            self.channel.unsubscribe(self._on_connectivity_change)
            self.channel.close()
            self.channel = None

    def _on_connectivity_change(self, state: grpc.ChannelConnectivity) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._connectivity_events.append((timestamp, state.name))
        if len(self._connectivity_events) > 20:
            self._connectivity_events = self._connectivity_events[-20:]

    def _wait_channel_ready(self) -> None:
        try:
            grpc.channel_ready_future(self.channel).result(timeout=self.timeout_sec)
        except grpc.FutureTimeoutError as exc:
            states = ", ".join(f"{ts}={name}" for ts, name in self._connectivity_events) or "none"
            raise grpc.FutureTimeoutError(
                "gRPC channel did not become READY within "
                f"{self.timeout_sec:.1f}s for {self.host}:{self.port}. "
                f"Connectivity states: {states}"
            ) from exc

    def _deserialize_observation(
        self, observation: Any
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        obs_img: Dict[str, np.ndarray] = {}
        for img in observation.images:
            frame = np.frombuffer(img.image_data, dtype=np.uint8).reshape(img.height, img.width, 3)
            obs_img[img.camera_name] = frame

        obs_info = self._struct_to_dict(observation.info)
        self._normalize_obs_info(obs_info)
        return obs_img, obs_info

    @staticmethod
    def _struct_to_dict(struct_msg: Any) -> Dict[str, Any]:
        if struct_msg is None:
            return {}
        try:
            result = MessageToDict(struct_msg, preserving_proto_field_name=True)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _normalize_obs_info(obs_info: Dict[str, Any]) -> None:
        for key in ("ego_pos", "ego_rot", "linear_velocity", "linear_acceleration", "angular_velocity"):
            value = obs_info.get(key)
            if isinstance(value, list):
                obs_info[key] = np.asarray(value, dtype=np.float32)

        cam_params = obs_info.get("cam_params")
        if not isinstance(cam_params, dict):
            return

        for _, cam in cam_params.items():
            if not isinstance(cam, dict):
                continue
            for mat_key in ("l2c", "ego2camera", "K", "w2c"):
                mat = cam.get(mat_key)
                if isinstance(mat, list):
                    cam[mat_key] = np.asarray(mat, dtype=np.float32)
