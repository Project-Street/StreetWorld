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
from typing import Dict, List

import grpc
import numpy as np

from metadrive.envs.streetstudio_scenario_env import StreetStudioScenarioEnv
from metadrive.envs.scenario_env import ScenarioEnv
from sim_interface import SharpVideoSimulatorInterface as SimulatorInterface

# Import generated protobuf modules
import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import streetworld_grpc.common_pb2 as common_pb2
import streetworld_grpc.control_pb2 as control_pb2


class StreetStudioServicer(service_pb2_grpc.StreetStudioServiceServicer):
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
        Reset the environment with new scene configuration.

        Args:
            request: ResetRequest with optional transforms_json_path and render_server_url
            context: gRPC context

        Returns:
            ResetResponse with success status, scene name, and initial observation

        Note:
            If transforms_json_path or render_server_url are empty strings,
            the server will use its initial configuration from startup.
        """
        with self._lock:
            try:
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
                obs, info = self.env.reset()

                # Serialize observation
                obs_img, obs_info = obs  # AssemblyObservation returns (obs_img, obs_info)

                # Convert images to protobuf
                images = self._serialize_images(obs_img)

                # Convert obs_info to protobuf
                obs_info_proto = self._serialize_obs_info(obs_info)

                # Get scene name from path
                # transforms_path = self.config["transforms_json_path"]
                scene_name = str(self.env.scene_name) #Path(transforms_path).stem
                self._current_scene = scene_name

                return service_pb2.ResetResponse(
                    success=True,
                    message="Environment reset successfully",
                    scene_name=scene_name,
                    images=images,
                    info=obs_info_proto
                )

            except Exception as e:
                print(e)
                raise e
                return service_pb2.ResetResponse(
                    success=False,
                    message=f"Reset failed: {str(e)}",
                    scene_name="",
                    images=[],
                    info=common_pb2.ObservationInfo()
                )

    def Step(self, request: control_pb2.StepRequest, context) -> control_pb2.StepResponse:
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
                return control_pb2.StepResponse()

            try:
                # Extract action from request
                action = list(request.action)  # [steering, throttle]
                print(f"Steering: {action[0]:.4f}, Throttle: {action[1]:.4f}")
                # Step environment
                obs, reward, terminated, truncated, info = self.env.step(action)

                # Serialize observation
                obs_img, obs_info = obs  # AssemblyObservation returns (obs_img, obs_info)

                # Convert images to protobuf
                images = self._serialize_images(obs_img)

                # Convert obs_info to protobuf
                obs_info_proto = self._serialize_obs_info(obs_info)

                return control_pb2.StepResponse(
                    reward=float(reward),
                    terminated=terminated,
                    truncated=truncated,
                    images=images,
                    info=obs_info_proto
                )

            except Exception as e:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Step failed: {str(e)}")
                return control_pb2.StepResponse()

    def _serialize_images(self, obs_img: Dict[str, np.ndarray]) -> List[common_pb2.CameraImage]:
        """
        Serialize observation images to protobuf.

        Args:
            obs_img: Dict mapping camera_name -> (stack, H, W, 3) array

        Returns:
            List of CameraImage protobuf messages
        """
        images = []
        for cam_name, stacked in obs_img.items():
            # Get latest frame from stack (last element)
            if stacked.ndim == 4:  # (stack, H, W, 3)
                frame = stacked[-1]
            else:  # (H, W, 3)
                frame = stacked

            h, w = frame.shape[:2]

            # Convert to raw RGB bytes
            image_bytes = frame.tobytes()

            images.append(common_pb2.CameraImage(
                camera_name=cam_name,
                image_data=image_bytes,
                height=h,
                width=w
            ))

        return images

    def _serialize_matrix(self, matrix: np.ndarray) -> common_pb2.Matrix:
        """
        Serialize numpy matrix to protobuf.

        Args:
            matrix: 2D numpy array (3x3 or 4x4)

        Returns:
            Matrix protobuf message
        """
        return common_pb2.Matrix(
            data=matrix.flatten().tolist(),
            rows=matrix.shape[0],
            cols=matrix.shape[1]
        )

    def _serialize_camera_params(self, camera_info: Dict) -> List[common_pb2.CameraParams]:
        """
        Serialize camera parameters to protobuf.

        Args:
            camera_info: Dict from GaussianObservation with camera metadata

        Returns:
            List of CameraParams protobuf messages
        """
        params_list = []
        for cam_name, cam_info in camera_info.items():
            intrinsic = cam_info['intrinsic']
            params_list.append(common_pb2.CameraParams(
                camera_name=cam_name,
                intrinsic=common_pb2.CameraIntrinsic(
                    fovx=float(intrinsic['fovx']),
                    fovy=float(intrinsic['fovy']),
                    height=int(intrinsic['H']),
                    width=int(intrinsic['W']),
                    cx=float(intrinsic['cx']),
                    cy=float(intrinsic['cy'])
                ),
                l2c=self._serialize_matrix(cam_info['l2c']),
                ego2camera=self._serialize_matrix(cam_info['ego2camera']),
                K=self._serialize_matrix(cam_info['K']),
                w2c=self._serialize_matrix(cam_info['w2c'])
            ))
        return params_list

    def _serialize_obs_info(self, obs_info: Dict) -> common_pb2.ObservationInfo:
        """
        Serialize observation info to protobuf.

        Args:
            obs_info: Dict from AssemblyObservation with ego state and metadata

        Returns:
            ObservationInfo protobuf message
        """
        ego_pos = obs_info.get('ego_pos', np.zeros(3))
        ego_rot = obs_info.get('ego_rot', np.zeros(3))

        # Extract linear and angular velocities
        linear_velocity = obs_info.get('linear_velocity', np.zeros(3))
        linear_acceleration = obs_info.get('linear_acceleration', np.zeros(3))
        angular_velocity = obs_info.get('angular_velocity', np.zeros(3))

        # Serialize camera parameters
        camera_params = self._serialize_camera_params(obs_info.get('cam_params', {}))

        return common_pb2.ObservationInfo(
            ego_pos_x=float(ego_pos[0]) if len(ego_pos) > 0 else 0.0,
            ego_pos_y=float(ego_pos[1]) if len(ego_pos) > 1 else 0.0,
            ego_pos_z=float(ego_pos[2]) if len(ego_pos) > 2 else 0.0,
            ego_rot_x=float(ego_rot[0]) if len(ego_rot) > 0 else 0.0,
            ego_rot_y=float(ego_rot[1]) if len(ego_rot) > 1 else 0.0,
            ego_rot_z=float(ego_rot[2]) if len(ego_rot) > 2 else 0.0,
            ego_velo=float(obs_info.get('ego_velo', 0.0)),
            ego_steer=float(obs_info.get('ego_steer', 0.0)),
            timestamp=float(obs_info.get('timestamp', 0.0)),
            command=int(obs_info.get('command', 2)),
            expert_path=list(obs_info.get('expert_path', []) or []),
            # Additional fields for UniAD
            linear_velocity=linear_velocity.flatten().tolist() if linear_velocity.size > 0 else [0.0, 0.0, 0.0],
            linear_acceleration=linear_acceleration.flatten().tolist() if linear_acceleration.size > 0 else [0.0, 0.0, 0.0],
            angular_velocity=angular_velocity.flatten().tolist() if angular_velocity.size > 0 else [0.0, 0.0, 0.0],
            accelerate=float(obs_info.get('accelerate', 0.0)),
            steer_rate=float(obs_info.get('steer_rate', 0.0)),
            # Camera parameters
            camera_params=camera_params
        )


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
    service_pb2_grpc.add_StreetStudioServiceServicer_to_server(servicer, server)

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
