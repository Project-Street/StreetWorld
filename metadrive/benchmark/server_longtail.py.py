#!/usr/bin/env python
"""
gRPC server for LongTail environment.

This server wraps ScenarioEnv and exposes a gRPC interface
for remote reinforcement learning training.

Usage:
    python -m metadrive.examples.server_longtail \\
        --config /path/to/config_dir \\
        --render-url http://localhost:8000 \\
        --host 0.0.0.0 \\
        --port 50052 \\
        --time-start 0.0 \\
        --time-end 10.0
"""

import argparse
import concurrent.futures
import threading
from pathlib import Path
from typing import Dict, List, Any
from google.protobuf import struct_pb2

import torch
import grpc
import numpy as np

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.gaussian_obs import GaussianObservation
from metadrive.obs.observation_base import DefaultObservation, DummyObservation

from sim_interface import SharpVideoSimulatorInterface as SimulatorInterface

# Import generated protobuf modules
import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import streetworld_grpc.common_pb2 as common_pb2


class StreetStudioServicer(service_pb2_grpc.EnvServiceServicer):
    """
    gRPC service for StreetStudio environment.

    Provides Reset and Step RPCs for remote control.
    """

    def __init__(self, config: dict):
        """
        Initialize servicer with environment configuration.

        Args:
            config: Environment configuration dict
        """
        self.config = config
        self.env: ScenarioEnv = None
        self.model: SimulatorInterface = None
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
            # Update config with request parameters only if provided
            if request.transforms_json_path:
                self.config["transforms_json_path"] = request.transforms_json_path
            if request.render_server_url:
                self.config["render_server_url"] = request.render_server_url

            # # Close existing environment if any
            # if self.env is not None:
            #     self.env.close()

            # Create new model
            if self.model is None:
                self.model = SimulatorInterface()
            # Create new environment
            if self.env is None:
                self.env = ScenarioEnv(self.model, self.config)
            # self.env = StreetStudioScenarioEnv(self.config)

            # Reset environment and get initial observation
            obs, reset_info = self.env.reset()

            scene_name = str(self.env.scene_name) #Path(transforms_path).stem
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
            StepResponse with reward, done flags, images, and info
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
            print(f"Steering: {action[0]:.4f}, Throttle: {action[1]:.4f}")
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
                    # Depth cameras share the same intrinsics as RGB, so we look up the base name without "_depth" suffix for camera info
                    camera_info=self._dict_to_struct(camera_info[cam_name if '_depth' not in cam_name else cam_name.replace('_depth', '')]),
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
    scene_config_directory: str,
    render_server_url: str,
    host: str = "0.0.0.0",
    port: int = 50052,
    max_workers: int = 10,
    time_start: float = None,
    time_end: float = None
) -> None:
    """
    Start gRPC server.

    Args:
        scene_config_directory: Path to config directory for LongTail
        render_server_url: gRPC address for Gaussian renderer (e.g., "localhost:50051")
        host: Server bind address
        port: Server port
        max_workers: Max concurrent RPC handlers
        time_start: Start timestamp for scenario replay (optional)
        time_end: End timestamp for scenario replay (optional)
    """

    from metadrive.policy.replay_policy import ReplayPolicy
    # Create environment configuration
    config = {
        "scene_config_directory": scene_config_directory,
        "physics_world_step_size": 10_000,
        "render_server_url": render_server_url,
        "use_render": False,  # No local rendering needed
        "manual_control": False,  # Server receives actions via gRPC
        "num_scenarios": -1, # Load all scenarios in the directory
        # Disable onscreen rendering for server mode
        "offscreen_render": True,
        "decision_repeat": 10,
        # "actor_config": {
        #     "policy": ReplayPolicy,
        # },
    }

    # Add time range constraints if provided
    if time_start is not None:
        config["time_start_sec"] = time_start
    if time_end is not None:
        config["time_end_sec"] = time_end

    # Create servicer
    servicer = StreetStudioServicer(config)

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
    server_address = f"{host}:{port}"
    server.add_insecure_port(server_address)

    # Start server
    server.start()
    print(f"StreetStudio gRPC server started on {server_address}")
    print(f"Renderer: {render_server_url}")
    print("Press Ctrl+C to stop...")

    # Wait for termination
    server.wait_for_termination()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="StreetStudio gRPC server for remote RL training"
    )
    parser.add_argument(
        "-c", "--scene_config_directory",
        type=str,
        required=True,
        help="Path to config directory for LongTail"
    )
    # parser.add_argument(
    #     "--render-url",
    #     type=str,
    #     required=True,
    #     help="gRPC address of Gaussian renderer (e.g., localhost:50051)"
    # )
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
        "--time-start",
        type=float,
        default=None,
        help="Start timestamp for scenario replay (default: scenario start time)"
    )
    parser.add_argument(
        "--time-end",
        type=float,
        default=None,
        help="End timestamp for scenario replay (default: scenario end time)"
    )
    args = parser.parse_args()

    # Validate transforms path exists
    # transforms_path = Path(args.transforms)
    # if not transforms_path.exists():
    #     print(f"Error: Transforms file not found: {args.transforms}")
    #     return 1

    serve(
        scene_config_directory=args.scene_config_directory,
        render_server_url="127.0.0.1",
        host=args.host,
        port=args.port,
        max_workers=args.max_workers,
        time_start=args.time_start,
        time_end=args.time_end
    )

    return 0


if __name__ == "__main__":
    exit(main())
