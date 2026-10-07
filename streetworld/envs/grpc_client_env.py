from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import grpc
import gymnasium as gym
import numpy as np
from google.protobuf.json_format import MessageToDict

import streetworld.grpc.streetworld_grpc.service_pb2 as service_pb2  # type: ignore
import streetworld.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc  # type: ignore



class GrpcClientEnv(gym.Env):
    """
    Gym-compatible gRPC client env.

    It mirrors ScenarioEnv's IO contract:
    - reset() returns: (obs, reset_info)
    - step(action) returns: (obs, reward, terminated, truncated, step_info)
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
        self.channel.subscribe(self.__on_connectivity_change, try_to_connect=True)
        self.stub = service_pb2_grpc.EnvServiceStub(self.channel)

        if auto_wait_ready:
            self.__wait_channel_ready()

        self.action_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(2,), dtype=np.float32)
        self.observation_space = gym.spaces.Dict({})

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        del seed, options

        request = service_pb2.ResetRequest()

        # Reset often includes heavy scene/model initialization, so allow a longer RPC deadline.
        response = self.stub.Reset(
            request,
            timeout=self.timeout_sec * 2.0,
            wait_for_ready=True,
        )
        if response.status:
            raise RuntimeError(f"Reset failed: {response.message}")

        obs = self.__deserialize_observation(response.observation)
        reset_info = self.__struct_to_builtin(response.StepInfo)

        return obs, reset_info

    def step(
        self, action: Optional[np.ndarray]
    ) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:

        response = self.stub.Step(
            service_pb2.StepRequest(action=[] if action is None else np.asarray(action).reshape(-1).tolist()),
            timeout=self.timeout_sec,
            wait_for_ready=True,
        )
        if response.status:
            raise RuntimeError(f"Step failed: {response.message}")

        obs = self.__deserialize_observation(response.observation)
        step_info = self.__struct_to_builtin(response.StepInfo)

        return (
            obs,
            float(response.reward),
            bool(response.terminated),
            bool(response.truncated),
            step_info,
        )

    def close(self) -> None:
        if self.channel is not None:
            self.channel.unsubscribe(self.__on_connectivity_change)
            self.channel.close()
            self.channel = None

    def __on_connectivity_change(self, state: grpc.ChannelConnectivity) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._connectivity_events.append((timestamp, state.name))
        if len(self._connectivity_events) > 20:
            self._connectivity_events = self._connectivity_events[-20:]

    def __wait_channel_ready(self) -> None:
        try:
            grpc.channel_ready_future(self.channel).result(timeout=self.timeout_sec)
        except grpc.FutureTimeoutError as exc:
            states = ", ".join(f"{ts}={name}" for ts, name in self._connectivity_events) or "none"
            raise grpc.FutureTimeoutError(
                "gRPC channel did not become READY within "
                f"{self.timeout_sec:.1f}s for {self.host}:{self.port}. "
                f"Connectivity states: {states}"
            ) from exc

    def __deserialize_observation(
        self, observation: Any
    ) -> Any:
        has_images = len(observation.images_observation) > 0
        has_other = observation.HasField("other_observation")

        if has_images and has_other:
            obs = self.__struct_to_builtin(observation.other_observation)
            obs["gaussian"] = self.__deserialize_gaussian_observation(observation.images_observation)
            return self.__restore_numeric_lists(obs)

        if has_images:
            return self.__deserialize_gaussian_observation(observation.images_observation)

        if has_other:
            return self.__restore_numeric_lists(self.__struct_to_builtin(observation.other_observation))

        raise ValueError("Observation payload is empty.")

    def __deserialize_gaussian_observation(self, images_observation: Any) -> Dict[str, Any]:
        camera_info: Dict[str, Any] = {}
        image: Dict[str, Any] = {}

        for camera_image in images_observation:
            cam_name = camera_image.camera_name
            cam_info = self.__restore_numeric_lists(self.__struct_to_builtin(camera_image.camera_info))
            h = int(cam_info["H"])
            w = int(cam_info["W"])
            frame = np.ascontiguousarray(np.frombuffer(camera_image.image_data, dtype=np.uint8).reshape(h, w, 3))
            camera_info[cam_name] = cam_info
            image[cam_name] = frame

        return {
            "camera_info": camera_info,
            "image": image,
        }

    @staticmethod
    def __restore_numeric_lists(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: GrpcClientEnv.__restore_numeric_lists(item) for key, item in value.items()}
        if isinstance(value, list):
            items = [GrpcClientEnv.__restore_numeric_lists(item) for item in value]
            array = np.asarray(items)
            if np.issubdtype(array.dtype, np.number):
                return array
            return items
        return value

    @staticmethod
    def __struct_to_builtin(struct_msg: Any) -> Any:
        result = MessageToDict(struct_msg, preserving_proto_field_name=True)
        if "__payload__" in result and len(result) == 1:
            return result["__payload__"]
        return result
