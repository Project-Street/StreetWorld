#!/usr/bin/env python
"""
gRPC server for EasyDrive-style ScenarioEnv environment.

This server wraps ScenarioEnv and exposes a gRPC interface
for remote reinforcement learning training.

Usage:
    python -m metadrive.examples.env_server_easydrive \\
        -c /path/to/scene_config_directory \\
        --host 0.0.0.0 \\
        --port 50052 \\
        --time-start 0.0 \\
        --time-end 10.0
"""

import argparse
import concurrent.futures
import threading
from typing import Any, Dict, List

import grpc
import numpy as np
from google.protobuf import struct_pb2

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.gaussian_obs import GaussianObservation
from metadrive.obs.observation_base import DefaultObservation, DummyObservation
from easydrive.models.scenes.simulator_interface import SimulatorInterface

try:
    import torch
except Exception:  # pragma: no cover - torch may be unavailable in lightweight runtime
    torch = None

# Import generated protobuf modules
import metadrive.grpc.streetworld_grpc.service_pb2 as service_pb2
import metadrive.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import metadrive.grpc.streetworld_grpc.common_pb2 as common_pb2


class EnvServicer(service_pb2_grpc.EnvServiceServicer):
    """
    gRPC service for ScenarioEnv environment.

    Provides Reset and Step RPCs for remote control.
    """

    def __init__(self, config: dict):
        """
        Initialize servicer with environment configuration.

        Args:
            config: Environment configuration dict
        """
        self.config = config
        # Initialize model/env once and only reset episode state on Reset().
        self.model: SimulatorInterface = SimulatorInterface()
        self.env: ScenarioEnv = ScenarioEnv(self.model, self.config)
        self._lock = threading.Lock()
        self._current_scene = None

    def Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse:
        """
        Reset the environment.

        Args:
            request: ResetRequest
            context: gRPC context

        Returns:
            ResetResponse with initial observation and reset info.
        """
        with self._lock:
                # Keep fields for protocol compatibility; they are ignored by easydrive server mode.
                _ = request
                # Reset environment and get initial observation
                obs, reset_info = self.env.reset()
                scene_name = str(self.env.scene_name)
                self._current_scene = scene_name
                reset_info = dict(reset_info) if isinstance(reset_info, dict) else {}
                reset_info.setdefault("scene_name", scene_name)

                return service_pb2.ResetResponse(
                    status=False,
                    message="",
                    observation=self._serialize_observation(obs),
                    StepInfo=self._dict_to_struct(reset_info)
                )

    def Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse:
        """
        Execute one environment step.

        Args:
            request: StepRequest with action array [steering, throttle]
            context: gRPC context

        Returns:
            StepResponse with reward, done flags, observation, and step info
        """
        with self._lock:
            if self.env is None:
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Environment not initialized. Call Reset first.")
                return service_pb2.StepResponse(
                    status=True,
                    message="Environment not initialized. Call Reset first.",
                    observation=common_pb2.Observation(),
                    reward=0.0,
                    terminated=False,
                    truncated=True,
                    StepInfo=self._dict_to_struct({})
                )

            # Extract action from request
            action = list(request.action)  # [steering, throttle]

            # Step environment
            obs, reward, terminated, truncated, info = self.env.step(action)
            return service_pb2.StepResponse(
                status=False,
                message="",
                observation=self._serialize_observation(obs),
                reward=float(reward),
                terminated=bool(terminated),
                truncated=bool(truncated),
                StepInfo=self._dict_to_struct(info)
            )


    def _serialize_observation(self, obs: Any) -> common_pb2.Observation:
        """
        Serialize environment observation to protobuf Observation.

        Rules:
        1) AssemblyObservation: gaussian -> images_observation, remaining dict -> other_observation
        2) GaussianObservation: gaussian -> images_observation
        3) Other observations: all payload -> other_observation
        4) Dummy/Default observations: raise error
        """
        observer = self.env.agent_managers["actor"].observer

        if isinstance(observer, AssemblyObservation):
            assembly_obs = dict(obs)
            gaussian_obs = assembly_obs.pop("gaussian")
            images = self._serialize_gaussian_images(gaussian_obs["image"], gaussian_obs["camera_info"])
            return common_pb2.Observation(
                images_observation=images,
                other_observation=self._dict_to_struct(assembly_obs),
            )

        if isinstance(observer, GaussianObservation):
            images = self._serialize_gaussian_images(obs["image"], obs["camera_info"])
            return common_pb2.Observation(images_observation=images)

        if isinstance(observer, (DummyObservation, DefaultObservation)):
            raise ValueError("DummyObservation and DefaultObservation are not supported in streetworld grpc mode.")

        return common_pb2.Observation(
            other_observation=self._dict_to_struct(obs),
        )

    def _serialize_gaussian_images(
        self,
        gaussian_images: Dict[str, np.ndarray],
        camera_info: Dict[str, Dict[str, Any]],
    ) -> List[common_pb2.CameraImage]:
        """
        Serialize gaussian observation image + camera_info to CameraImage.
        """
        images = []
        for cam_name, stacked in gaussian_images.items():
            frame = stacked[-1] if stacked.ndim == 4 else stacked
            images.append(
                common_pb2.CameraImage(
                    camera_name=cam_name,
                    image_data=frame.tobytes(),
                    camera_info=self._dict_to_struct(camera_info[cam_name]),
                )
            )
        return images

    def _to_builtin(self, value: Any) -> Any:
        """
        Convert nested numpy-containing structures to protobuf-Struct-compatible python types.
        """
        if isinstance(value, dict):
            return {str(k): self._to_builtin(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_builtin(v) for v in value]
        if isinstance(value, np.ndarray):
            return self._to_builtin(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        if torch is not None and isinstance(value, torch.Tensor):
            return self._to_builtin(value.detach().cpu().tolist())
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _dict_to_struct(self, data: Any) -> struct_pb2.Struct:
        """
        Convert arbitrary dict-like payload to protobuf Struct.
        """
        payload = self._to_builtin(data)
        if not isinstance(payload, dict):
            payload = {"__payload__": payload}
        struct = struct_pb2.Struct()
        struct.update(payload)
        return struct


def serve(
    scene_config_directory: str = "",
    random_scenario: bool = True,
    host: str = "0.0.0.0",
    port: int = 50052,
    max_workers: int = 10,
) -> None:
    """
    Start gRPC server.

    Args:
        scene_config_directory: Scenario config directory
        host: Server bind address
        port: Server port
        max_workers: Max concurrent RPC handlers
    """
    # Create environment configuration
    config = {
        "scene_config_directory": scene_config_directory,
        "random_scenario": random_scenario,
    }
    # Create servicer
    servicer = EnvServicer(config)

    # Create gRPC server
    server = grpc.server(
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_send_message_length', 200 * 1024 * 1024),  # 200 MB
            ('grpc.max_receive_message_length', 200 * 1024 * 1024),
        ]
    )

    # Add servicer to server
    service_pb2_grpc.add_EnvServiceServicer_to_server(servicer, server)

    # Bind server to address
    server.add_insecure_port(f"{host}:{port}")

    # Start server
    server.start()
    print(f"EasyDrive ScenarioEnv gRPC server started on {host}:{port}")
    print(f"Scene config directory: {scene_config_directory}")
    print("Press Ctrl+C to stop...")

    # Wait for termination
    server.wait_for_termination()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="EasyDrive ScenarioEnv gRPC server for remote RL training"
    )
    parser.add_argument(
        "-c", "--scene_config_directory",
        type=str,
        required=True,
        help="Scenario config directory"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="Server port (default: 50052)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Max concurrent RPC handlers (default: 10)"
    )
    parser.add_argument(
        "--ordered-scenario",
        action="store_true",
        help="Use ordered (sequential) scenarios instead of random sampling"
    )
    args = parser.parse_args()

    try:
        import os
        if not os.path.isdir(args.scene_config_directory):
            print(f"Error: scene_config_directory not found: {args.scene_config_directory}")
            return 1
    except Exception:
        print(f"Error: invalid scene_config_directory: {args.scene_config_directory}")
        return 1

    serve(
        scene_config_directory=args.scene_config_directory,
        random_scenario=not args.ordered_scenario,
        host=args.host,
        port=args.port,
        max_workers=args.max_workers,
    )

    return 0


if __name__ == "__main__":
    exit(main())
