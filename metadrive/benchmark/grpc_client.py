import grpc
import numpy as np
from typing import Any, Dict, List, Tuple

import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
from google.protobuf.json_format import MessageToDict


class GrpcClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 50052,
        timeout_sec: float = 10.0,
        auto_wait_ready: bool = True,
    ):
        self.host = host
        self.port = port
        self.timeout_sec = float(timeout_sec)
        self._connectivity_events = []

        self.channel = grpc.insecure_channel(
            f"{host}:{port}",
            options=[
                ("grpc.max_send_message_length", 200 * 1024 * 1024),
                ("grpc.max_receive_message_length", 200 * 1024 * 1024),
            ],
        )

        self.channel.subscribe(self._on_connectivity_change, try_to_connect=True)
        self.stub = service_pb2_grpc.EnvServiceStub(self.channel)

        if auto_wait_ready:
            self._wait_channel_ready()

    def reset(self, transforms_json_path: str = "", render_server_url: str = "") -> Tuple[Any, Dict[str, Any]]:
        request = service_pb2.ResetRequest(
            transforms_json_path=transforms_json_path,
            render_server_url=render_server_url,
        )
        response = self.stub.Reset(request)

        obs = self._deserialize_observation(response.observation)
        reset_info = self._struct_to_builtin(response.StepInfo)
        reset_info['scene_name'] = str(reset_info['scene_name'])
        return obs, reset_info

    def step(self, action: List[float]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]:
        request = service_pb2.StepRequest(action=action)
        response = self.stub.Step(request)

        if response.status:
            raise RuntimeError(f"Step failed: {response.message}")

        obs = self._deserialize_observation(response.observation)
        step_info = self._struct_to_builtin(response.StepInfo)
        step_info['scene_name'] = str(step_info['scene_name'])
        return (
            obs,
            float(response.reward),
            bool(response.terminated),
            bool(response.truncated),
            step_info,
        )

    def _deserialize_observation(self, observation: Any) -> Any:
        has_images = len(observation.images_observation) > 0
        has_other = observation.HasField("other_observation")

        if has_images and has_other:
            obs = self._struct_to_builtin(observation.other_observation)
            obs["gaussian"] = self._deserialize_gaussian_observation(observation.images_observation)
            return obs

        if has_images:
            return self._deserialize_gaussian_observation(observation.images_observation)

        if has_other:
            return self._struct_to_builtin(observation.other_observation)

        raise ValueError("Observation payload is empty.")

    def _deserialize_gaussian_observation(self, images_observation: Any) -> Dict[str, Any]:
        camera_info: Dict[str, Any] = {}
        image: Dict[str, Any] = {}

        for camera_image in images_observation:
            cam_name = camera_image.camera_name
            cam_info = self._struct_to_builtin(camera_image.camera_info)
            h = int(cam_info["H"])
            w = int(cam_info["W"])
            frame = np.frombuffer(camera_image.image_data, dtype=np.uint8).reshape(h, w, 3)
            camera_info[cam_name] = cam_info
            image[cam_name] = np.expand_dims(frame, axis=0)

        return {
            "camera_info": camera_info,
            "image": image,
        }

    @staticmethod
    def _struct_to_builtin(struct_msg: Any) -> Any:
        result = MessageToDict(struct_msg, preserving_proto_field_name=True)
        if "__payload__" in result and len(result) == 1:
            return result["__payload__"]
        return result

    def close(self) -> None:
        if self.channel is not None:
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