import concurrent.futures
import threading
from typing import Any, Dict, List

import grpc
import numpy as np
import torch
from google.protobuf import struct_pb2

import streetworld.grpc.streetworld_grpc.common_pb2 as common_pb2
import streetworld.grpc.streetworld_grpc.service_pb2 as service_pb2
import streetworld.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc


def serve(env, *, host: str, port: int) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        server = grpc.server(
            executor,
            options=[
                ("grpc.max_send_message_length", 200 * 1024 * 1024),
                ("grpc.max_receive_message_length", 200 * 1024 * 1024),
            ],
        )
        service_pb2_grpc.add_EnvServiceServicer_to_server(EnvServicer(env), server)
        if server.add_insecure_port(f"{host}:{port}") == 0:
            raise RuntimeError(f"Could not bind StreetWorld gRPC server to {host}:{port}")
        try:
            server.start()
            if not env.config["tui"]:
                print(f"StreetWorld gRPC server started on {host}:{port}")
                print("Press Ctrl-C to stop.")
            server.wait_for_termination()
        except KeyboardInterrupt:
            pass
        finally:
            server.stop(0).wait()
            # A synchronous server with one worker owns its rendering resources there.
            # Async environments dispatch close to their persistent worker themselves.
            executor.submit(env.close).result()


class EnvServicer(service_pb2_grpc.EnvServiceServicer):
    def __init__(self, env):
        self.env = env
        self._lock = threading.Lock()

    def Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse:
        with self._lock:
            try:
                obs, reset_info = self.env.reset()
            except LookupError as exc:
                if str(exc) != "No more scenarios to evaluate.":
                    raise
                return service_pb2.ResetResponse(status=True, message=str(exc))

            return service_pb2.ResetResponse(
                status=False,
                message="",
                observation=self._serialize_observation(obs),
                StepInfo=self._dict_to_struct(reset_info),
            )

    def Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse:
        with self._lock:
            action = None if not request.action else np.asarray(request.action).reshape(-1, 2)
            obs, reward, terminated, truncated, info = self.env.step(action)
            return service_pb2.StepResponse(
                status=False,
                message="",
                observation=self._serialize_observation(obs),
                reward=float(reward),
                terminated=bool(terminated),
                truncated=bool(truncated),
                StepInfo=self._dict_to_struct(info),
            )

    def _serialize_observation(self, obs: Any) -> common_pb2.Observation:
        if "collision_body" in obs:
            obs = dict(obs)
            # TODO: Add a binary gRPC contract for collision body images when remote use is required.
            obs.pop("collision_body")

        if "gaussian" in obs:
            other_obs = dict(obs)
            gaussian_obs = other_obs.pop("gaussian")
            images = self._serialize_gaussian_images(gaussian_obs["image"], gaussian_obs["camera_info"])
            return common_pb2.Observation(
                images_observation=images,
                other_observation=self._dict_to_struct(other_obs),
            )

        if "image" in obs and "camera_info" in obs:
            images = self._serialize_gaussian_images(obs["image"], obs["camera_info"])
            return common_pb2.Observation(images_observation=images)

        return common_pb2.Observation(other_observation=self._dict_to_struct(obs))

    def _serialize_gaussian_images(
        self,
        gaussian_images: Dict[str, np.ndarray],
        camera_info: Dict[str, Dict[str, Any]],
    ) -> List[common_pb2.CameraImage]:
        images = []
        for cam_name, stacked in gaussian_images.items():
            if stacked.ndim != 4 or stacked.shape[0] != 1:
                raise ValueError(f"gRPC camera image for {cam_name} must have shape (1, H, W, 3), got {stacked.shape}")
            frame = stacked[0]
            images.append(
                common_pb2.CameraImage(
                    camera_name=cam_name,
                    image_data=frame.tobytes(),
                    camera_info=self._dict_to_struct(camera_info[cam_name]),
                )
            )
        return images

    def _to_builtin(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): self._to_builtin(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_builtin(v) for v in value]
        if isinstance(value, np.ndarray):
            return self._to_builtin(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, torch.Tensor):
            return self._to_builtin(value.detach().cpu().tolist())
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _dict_to_struct(self, data: Any) -> struct_pb2.Struct:
        payload = self._to_builtin(data)
        if not isinstance(payload, dict):
            payload = {"__payload__": payload}
        struct = struct_pb2.Struct()
        struct.update(payload)
        return struct
