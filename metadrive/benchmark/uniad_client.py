#!/usr/bin/env python
"""
UniAD gRPC client for remote StreetStudio environment.

This client connects to a StreetStudio gRPC server and runs UniAD model
inference locally to generate driving actions.

Usage:
    python -m metadrive.examples.uniad_client \\
        --uniad-config /path/to/uniad_config.json \\
        --host localhost \\
        --port 50052
"""

import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import sys
RL_FRAMEWORK_ROOT="../../"
sys.path.insert(0, str(RL_FRAMEWORK_ROOT))
import os
os.environ['no_proxy'] = '127.0.0.1,localhost'
from rl_framework.rl_modules.closeLoop import create_uniad

import grpc
import numpy as np

# Import gRPC protobuf modules
import streetworld_grpc.service_pb2 as service_pb2
import streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import streetworld_grpc.common_pb2 as common_pb2
import streetworld_grpc.control_pb2 as control_pb2


class UniADClient:
    """
    gRPC client with UniAD model integration.

    This client connects to a remote StreetStudio environment via gRPC,
    receives observations, maintains image stacks locally, and runs
    UniAD model inference to generate control actions.
    """

    def __init__(
        self,
        uniad_config: dict,
        host: str = "localhost",
        port: int = 50052,
        stack_size: int = 3
    ):
        """
        Initialize UniAD gRPC client.

        Args:
            uniad_config: Configuration dict for UniAD model
            host: Server host address
            port: Server port
            stack_size: Number of frames to stack for temporal input
        """
        self.host = host
        self.port = port

        # Create gRPC channel and stub
        self.channel = grpc.insecure_channel(
            f"{host}:{port}",
            options = [
                ('grpc.max_send_message_length', 200 * 1024 * 1024),
                ('grpc.max_receive_message_length', 200 * 1024 * 1024),
            ])
        self.stub = service_pb2_grpc.StreetStudioServiceStub(self.channel)

        # Initialize UniAD model
        self.uniad = self._create_uniad(uniad_config)

        # Image stack configuration
        self.stack_size = stack_size
        self.image_stacks: Dict[str, np.ndarray] = {}

        # Image normalization config
        self.img_norm_cfg = {
            'mean': np.array([103.530, 116.280, 123.675]),
            'std': np.array([1.0, 1.0, 1.0]),
            'to_rgb': False
        }

        # Camera set to use for UniAD
        # self.cameras = {'camera_0', 'camera_1', 'camera_2', 'camera_6', 'camera_5', 'camera_7'}

        self.cameras = {'camera_0', 'camera_1', 'camera_2', 'camera_3', 'camera_4', 'camera_5'}
        # self.cameras = {'camera_2', 'camera_0', 'camera_1', 'camera_5', 'camera_4', 'camera_3'}
        # self.cameras = {'FRONT', 'FRONT_LEFT', 'FRONT_RIGHT', 'BACK', 'BACK_LEFT', 'BACK_RIGHT'}

        # Record current scene name
        self.scene_name = None

    def _create_uniad(self, config: dict):
        """Create UniAD model from config."""
        # Import here to avoid dependency if not using UniAD
        from rl_framework.rl_modules.closeLoop import create_uniad
        return create_uniad(config)

    def reset(
        self,
        transforms_json_path: str = "",
        render_server_url: str = ""
    ) -> Tuple[Dict, Dict]:
        """
        Reset the remote environment.

        Args:
            transforms_json_path: Optional path to override server config
            render_server_url: Optional renderer URL to override server config

        Returns:
            (obs_img, obs_info) tuple
                - obs_img: Dict of latest camera frames (camera_name -> (H, W, 3))
                - obs_info: Dict with metadata (ego state, camera params, etc.)
        """
        request = service_pb2.ResetRequest(
            transforms_json_path=transforms_json_path,
            render_server_url=render_server_url
        )

        response = self.stub.Reset(request)

        if not response.success:
            raise RuntimeError(f"Reset failed: {response.message}")

        # Parse response
        obs_img, obs_info = self._parse_reset_response(response)

        # Initialize image stacks with repeated first frame
        self._init_image_stacks(obs_img)

        return obs_img, obs_info

    def step(self, action: List[float]) -> Tuple[Dict, float, bool, bool, Dict]:
        """
        Execute one environment step.

        Args:
            action: Control action [steering, throttle]

        Returns:
            (obs_img, reward, terminated, truncated, obs_info) tuple
        """
        request = control_pb2.StepRequest(action=action)
        response = self.stub.Step(request)

        # Parse observation
        obs_img, obs_info = self._parse_step_response(response)

        # Update image stacks
        self._update_image_stacks(obs_img)

        return (
            obs_img,
            float(response.reward),
            bool(response.terminated),
            bool(response.truncated),
            obs_info
        )

    def run_uniad_inference(self, obs_img: Dict, obs_info: Dict) -> np.ndarray:
        """
        Run UniAD inference on current observation.

        Args:
            obs_img: Latest camera frames (single frame)
            obs_info: Observation metadata

        Returns:
            plan_traj: Planned trajectory (N, 2) array
        """
        # Stack images for temporal input
        obs_img_stacked = {}
        for cam_name in self.cameras:
            if cam_name in self.image_stacks:
                obs_img_stacked[cam_name] = self.image_stacks[cam_name]

        # Prepare UniAD input
        raw_data = self._prepare_uniad_input(obs_img_stacked, obs_info)

        # Run inference
        import torch
        with torch.no_grad():
            results = self.uniad(
                return_loss=False,
                rescale=True,
                # feature_extractor=False,
                **raw_data
            )
            plan_traj = results[0]['planning']['result_planning']['sdc_traj'][0]
            plan_traj = plan_traj.detach().cpu().numpy()

        return plan_traj

    def _init_image_stacks(self, obs_img: Dict[str, np.ndarray]):
        """Initialize image stacks with repeated first frame."""
        for cam_name, frame in obs_img.items():
            if cam_name in self.cameras:
                self.image_stacks[cam_name] = np.stack([frame] * self.stack_size, axis=0)

    def _update_image_stacks(self, obs_img: Dict[str, np.ndarray]):
        """Roll stacks and add new frame."""
        for cam_name, frame in obs_img.items():
            if cam_name in self.cameras and cam_name in self.image_stacks:
                self.image_stacks[cam_name] = np.roll(self.image_stacks[cam_name], -1, axis=0)
                self.image_stacks[cam_name][-1] = frame

    def _parse_reset_response(self, response: service_pb2.ResetResponse) -> Tuple[Dict, Dict]:
        """Parse ResetResponse to obs_img and obs_info."""
        obs_img = self._parse_images(response.images)
        obs_info = self._parse_obs_info(response.info)
        obs_info['scene_token'] = response.scene_name
        self.scene_name = response.scene_name
        return obs_img, obs_info

    def _parse_step_response(self, response: control_pb2.StepResponse) -> Tuple[Dict, Dict]:
        """Parse StepResponse to obs_img and obs_info."""
        obs_img = self._parse_images(response.images)
        obs_info = self._parse_obs_info(response.info)
        obs_info['scene_token'] = self.scene_name
        return obs_img, obs_info

    def _parse_images(self, images: List[common_pb2.CameraImage]) -> Dict[str, np.ndarray]:
        """Parse camera images from protobuf."""
        obs_img = {}
        for img in images:
            frame = np.frombuffer(img.image_data, dtype=np.uint8)
            frame = frame.reshape(img.height, img.width, 3)
            obs_img[img.camera_name] = frame
        return obs_img

    def _parse_obs_info(self, info: common_pb2.ObservationInfo) -> Dict:
        """Parse ObservationInfo from protobuf."""
        obs_info = {
            'ego_pos': np.array([info.ego_pos_x, info.ego_pos_y, info.ego_pos_z]),
            'ego_rot': np.array([info.ego_rot_x, info.ego_rot_y, info.ego_rot_z]),
            'ego_velo': float(info.ego_velo),
            'ego_steer': float(info.ego_steer),
            'timestamp': float(info.timestamp),
            'command': int(info.command),
            "expert_path": np.array(info.expert_path).reshape(-1, 2),
            # Additional fields for UniAD
            'linear_velocity': np.array(info.linear_velocity) if info.linear_velocity else np.zeros(3),
            'linear_acceleration': np.array(info.linear_acceleration) if info.linear_acceleration else np.zeros(3),
            'angular_velocity': np.array(info.angular_velocity) if info.angular_velocity else np.zeros(3),
            'accelerate': float(info.accelerate),
            'steer_rate': float(info.steer_rate),
            # Camera parameters
            'cam_params': self._parse_camera_params(info.camera_params)
        }
        return obs_info

    def _parse_camera_params(self, params_proto) -> Dict:
        """Parse CameraParams list from protobuf."""
        cam_params = {}
        for p in params_proto:
            # Parse matrices
            l2c = np.array(p.l2c.data).reshape(p.l2c.rows, p.l2c.cols)
            ego2camera = np.array(p.ego2camera.data).reshape(p.ego2camera.rows, p.ego2camera.cols)
            K = np.array(p.K.data).reshape(p.K.rows, p.K.cols)
            w2c = np.array(p.w2c.data).reshape(p.w2c.rows, p.w2c.cols)

            # Parse intrinsic
            intrinsic = {
                'fovx': float(p.intrinsic.fovx),
                'fovy': float(p.intrinsic.fovy),
                'H': int(p.intrinsic.height),
                'W': int(p.intrinsic.width),
                'cx': float(p.intrinsic.cx),
                'cy': float(p.intrinsic.cy)
            }

            cam_params[p.camera_name] = {
                'l2c': l2c,
                'ego2camera': ego2camera,
                'K': K,
                'w2c': w2c,
                'intrinsic': intrinsic
            }
        return cam_params

    def _prepare_uniad_input(self, obs_img: Dict, obs_info: Dict) -> Dict:
        """Convert observation to UniAD input format."""
        from rl_framework.rl_modules.dataparser import parse_raw

        raw_data = parse_raw(obs_img, obs_info, self.cameras, self.img_norm_cfg)
        # Store raw images for reference
        self._raw_images = raw_data.get('raw_imgs', {})
        # Remove raw_imgs from data to pass to model
        raw_data.pop('raw_imgs', None)
        return raw_data

    def close(self):
        """Close the gRPC channel."""
        self.channel.close()


def traj2control(plan_traj: np.ndarray, obs_info: Dict) -> Tuple[float, float]:
    """
    Convert planned trajectory to control actions.

    Args:
        plan_traj: Planned trajectory (N, 2) array
        obs_info: Observation info dictionary

    Returns:
        (steer, accel) tuple
    """
    from rl_framework.rl_modules.env_wrapper import traj2control as _traj2control
    return _traj2control(plan_traj, obs_info)

def print_info(obs_info):
    print('-' * 10)
    print(f"Ego Position: {obs_info['ego_pos']}")
    print(f"Ego Rotation: {obs_info['ego_rot']}")
    print(f"Ego Velocity: {obs_info['ego_velo']}")
    print(f"Ego Steer: {obs_info['ego_steer']}")
    print(f"Linear Velocity: {obs_info['linear_velocity']}")
    print(f"Linear Acceleration: {obs_info['linear_acceleration']}")
    print(f"Angular Velocity: {obs_info['angular_velocity']}")
    print(f"Accelerate: {obs_info['accelerate']}")
    print(f"Steer Rate: {obs_info['steer_rate']}")
    print('-' * 10)

def main():
    """CLI entry point for running UniAD through gRPC."""
    parser = argparse.ArgumentParser(
        description="UniAD client for remote StreetStudio environment"
    )
    # parser.add_argument(
    #     "--uniad-config",
    #     type=str,
    #     required=True,
    #     help="Path to UniAD configuration JSON"
    # )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server host address (default: localhost)"
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
        default="",
        help="Optional path to transforms.json to override server config"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=1000,
        help="Number of steps to run (default: 1000)"
    )

    args = parser.parse_args()

    # Load UniAD config
    # import json
    # with open(args.uniad_config, 'r') as f:
    #     uniad_config = json.load(f)
    uniad_config = {
        'config_path': "/nas2/home/jrguo/CarCrash/submodules/StreetWorld/UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py",
        'checkpoint_path': "/nas2/home/jrguo/CarCrash/submodules/StreetWorld/UniAD_SIM/ckpts/uniad_base_e2e.pth",
        'device': 'cuda:0'
    }

    # Create client
    client = UniADClient(
        uniad_config=uniad_config,
        host=args.host,
        port=args.port
    )

    # Initialize FrameRecorder for visualization
    from visualize_utils import GaussianFrameRecorder
    gaussian_recorder = GaussianFrameRecorder(output_path='./driving_uniad.mp4', fps=10)
    
    try:
        # Reset environment
        print("Resetting environment...")
        obs_img, obs_info = client.reset(transforms_json_path=args.transforms)
        print(f"Environment ready. Cameras: {list(obs_img.keys())}")

        # Run UniAD inference for first step
        print("Running initial UniAD inference...")
        plan_traj = client.run_uniad_inference(obs_img, obs_info)
        acc, steer = traj2control(plan_traj, obs_info)
        action = [steer, acc]
        print(f"Initial action: steer={steer:.4f}, acc={acc:.4f}")

        # Main loop
        reward_sum = 0.0
        for step in range(1, args.steps + 1):
            obs_img, reward, terminated, truncated, obs_info = client.step(action)

            reward_sum += reward

            # Run UniAD inference
            plan_traj = client.run_uniad_inference(obs_img, obs_info)
            gaussian_recorder.update_frame((obs_img, obs_info), plan_traj)
            acc, steer = traj2control(plan_traj, obs_info)
            action = [steer, acc]

            if step % 1 == 0:
                print(f"Step {step}: reward={reward:.2f}, steer={steer:.4f}, acc={acc:.4f}")

            if terminated or truncated:
                print(f"Episode finished at step {step}")
                break

        print(f"Total reward: {reward_sum:.2f}")
        gaussian_recorder.save_video()
        
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    exit(main())
