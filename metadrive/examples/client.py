#!/usr/bin/env python
"""
gRPC client for StreetStudio environment.

This client connects to a remote StreetStudio gRPC server and provides
a gym-like interface for reinforcement learning training.

Usage:
    >>> from metadrive.examples.client import StreetStudioClient
    >>> client = StreetStudioClient(host="localhost", port=50052)
    >>> # Use server's default configuration
    >>> obs, info = client.reset()
    >>> # Or override with custom configuration
    >>> obs, info = client.reset("/path/to/transforms.json", "localhost:50051")
    >>> obs, reward, terminated, truncated, info = client.step([0.0, 0.5])
    >>> client.close()
"""

from typing import Dict, Tuple, List, Optional

import grpc
import numpy as np

# Import generated protobuf modules
import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import streetworld_grpc.common_pb2 as common_pb2
import streetworld_grpc.control_pb2 as control_pb2


class StreetStudioClient:
    """
    gRPC client for StreetStudio environment.

    Provides a gym-like interface (reset, step, close) for remote
    interaction with the StreetStudio server.
    """

    def __init__(self, host: str = "localhost", port: int = 50052):
        """
        Initialize client and connect to server.

        Args:
            host: Server hostname or IP
            port: Server port
        """
        self.channel = None
        self.stub = None
        self.host = host
        self.port = port
        self._connect()

    def _connect(self):
        """Establish gRPC connection to server."""
        server_address = f"{self.host}:{self.port}"
        self.channel = grpc.insecure_channel(
            server_address,
            options=[
                ('grpc.max_send_message_length', 200 * 1024 * 1024),  # 200 MB
                ('grpc.max_receive_message_length', 200 * 1024 * 1024),
            ]
        )
        self.stub = service_pb2_grpc.StreetStudioServiceStub(self.channel)

    def reset(
        self,
        transforms_json_path: Optional[str] = None,
        render_server_url: Optional[str] = None
    ) -> Tuple[Dict[str, np.ndarray], Dict]:
        """
        Reset the environment on the server.

        Args:
            transforms_json_path: Optional path to transforms.json file.
                If None or empty, uses server's initial configuration.
            render_server_url: Optional gRPC address for Gaussian renderer (e.g., "localhost:50051").
                If None or empty, uses server's initial configuration.

        Returns:
            (obs_img, obs_info) tuple matching AssemblyObservation format
            - obs_img: Dict mapping camera_name -> (H, W, 3) array
            - obs_info: Dict with ego state and metadata
        """
        request = service_pb2.ResetRequest(
            transforms_json_path=transforms_json_path or "",
            render_server_url=render_server_url or ""
        )

        response = self.stub.Reset(request)

        if not response.success:
            raise RuntimeError(f"Reset failed: {response.message}")

        print(f"Environment reset: {response.scene_name}")

        # Deserialize images from response
        obs_img = self._deserialize_images(response.images)

        # Deserialize obs_info from response
        obs_info = self._deserialize_obs_info(response.info)

        return obs_img, obs_info

    def step(self, action: List[float]) -> Tuple[Dict, float, bool, bool, Dict]:
        """
        Execute one environment step.

        Args:
            action: [steering, throttle] normalized to [-1, 1]

        Returns:
            Tuple of (obs, reward, terminated, truncated, info)
            - obs: (obs_img, obs_info) tuple
            - reward: float reward value
            - terminated: bool episode ended
            - truncated: bool episode truncated
            - info: dict with additional info
        """
        request = control_pb2.StepRequest(action=action)

        response = self.stub.Step(request)

        # Deserialize images
        obs_img = self._deserialize_images(response.images)

        # Deserialize obs_info
        obs_info = self._deserialize_obs_info(response.info)

        obs = (obs_img, obs_info)

        return obs, response.reward, response.terminated, response.truncated, obs_info

    def _deserialize_images(self, images: List[common_pb2.CameraImage]) -> Dict[str, np.ndarray]:
        """
        Deserialize images from protobuf.

        Args:
            images: List of CameraImage protobuf messages

        Returns:
            Dict mapping camera_name -> (H, W, 3) numpy array
        """
        obs_img = {}
        for img_proto in images:
            cam_name = img_proto.camera_name
            h, w = img_proto.height, img_proto.width

            # Convert bytes back to numpy array
            frame = np.frombuffer(img_proto.image_data, dtype=np.uint8)
            frame = frame.reshape((h, w, 3))

            obs_img[cam_name] = frame

        return obs_img

    def _deserialize_obs_info(self, info: common_pb2.ObservationInfo) -> Dict:
        """
        Deserialize observation info from protobuf.

        Args:
            info: ObservationInfo protobuf message

        Returns:
            Dict matching AssemblyObservation's obs_info format
        """
        return {
            'ego_pos': np.array([
                info.ego_pos_x,
                info.ego_pos_y,
                info.ego_pos_z
            ], dtype=np.float32),
            'ego_rot': np.array([
                info.ego_rot_x,
                info.ego_rot_y,
                info.ego_rot_z
            ], dtype=np.float32),
            'ego_velo': info.ego_velo,
            'ego_steer': info.ego_steer,
            'timestamp': info.timestamp,
            'command': info.command,
            'expert_path': list(info.expert_path)
        }

    def close(self):
        """Close gRPC connection."""
        if self.channel is not None:
            self.channel.close()
            self.channel = None
            self.stub = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    # TODO: Implement RL Action
    # This method will be implemented later based on RL framework requirements
    # def get_rl_action(self, observation: Tuple[Dict, Dict]) -> List[float]:
    #     """
    #     Get action from RL policy.
    #
    #     Args:
    #         observation: Current observation (obs_img, obs_info)
    #
    #     Returns:
    #         Action [steering, throttle] normalized to [-1, 1]
    #     """
    #     raise NotImplementedError("RL policy integration to be implemented")


def main():
    """Example usage of StreetStudioClient."""
    import argparse

    parser = argparse.ArgumentParser(description="StreetStudio gRPC client example")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server hostname (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="Server port (default: 50052)"
    )
    parser.add_argument(
        "--transforms",
        type=str,
        default=None,
        help="Path to transforms.json file (optional, uses server config if not provided)"
    )
    parser.add_argument(
        "--render-url",
        type=str,
        default=None,
        help="gRPC address for Gaussian renderer (optional, uses server config if not provided)"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100,
        help="Number of steps to run (default: 100)"
    )
    args = parser.parse_args()

    # Create client
    with StreetStudioClient(host=args.host, port=args.port) as client:
        # Reset environment
        if args.transforms and args.render_url:
            print(f"Resetting environment with custom config: {args.transforms}...")
            obs_img, obs_info = client.reset(args.transforms, args.render_url)
        else:
            print("Resetting environment with server's default configuration...")
            obs_img, obs_info = client.reset()

        print(f"Cameras: {list(obs_img.keys())}")
        for cam_name, img in obs_img.items():
            print(f"  {cam_name}: shape={img.shape}")

        # Run episode
        print(f"\nRunning for {args.steps} steps...")
        for step_idx in range(args.steps):
            # Simple example action: slight forward
            action = [0.0, 0.3]

            obs, reward, terminated, truncated, info = client.step(action)

            if step_idx % 10 == 0:
                print(f"Step {step_idx}: reward={reward:.4f}")

            if terminated or truncated:
                print(f"\nEpisode finished at step {step_idx}")
                print(f"Terminated: {terminated}, Truncated: {truncated}")
                break

    print("\nClient closed.")


if __name__ == "__main__":
    main()
