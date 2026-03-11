#!/usr/bin/env python
"""
DiffusionDrive gRPC client for StreetStudio environment.

This client mirrors transfuser_client but runs DiffusionDrive inference
using NAVSIM-style inputs built from RGB + mocked LiDAR from depth.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import grpc
import numpy as np
import cv2
import torch

from grpc_obs_adapter import unpack_ad_observation
from grpc_client import GrpcClient
from metrics import MetricsRecorder

os.environ["no_proxy"] = "127.0.0.1,localhost"

DIFFUSIONDRIVE_ROOT = Path(__file__).resolve().parents[2] / "DiffusionDrive"
if str(DIFFUSIONDRIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(DIFFUSIONDRIVE_ROOT))

RL_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RL_FRAMEWORK_ROOT))

from rl_framework.uniad.traj_parser import traj2control

from navsim.agents.diffusiondrive.transfuser_agent import TransfuserAgent
from navsim.agents.diffusiondrive.transfuser_config import TransfuserConfig
from navsim.agents.diffusiondrive.transfuser_features import TransfuserFeatureBuilder
from navsim.common.dataclasses import AgentInput, Camera, Cameras, EgoStatus, Lidar


def _decode_depth_from_rgb(depth_rgb: np.ndarray, max_depth_m: float) -> np.ndarray:
    depth_rgb = depth_rgb.astype(np.float32)
    normalized = (depth_rgb[..., 0] * 65536.0 + depth_rgb[..., 1] * 256.0 + depth_rgb[..., 2])
    normalized /= (256.0 * 256.0 * 256.0 - 1.0)
    return normalized * max_depth_m


def _depth_to_lidar_points(depth_m: np.ndarray, k_mat: np.ndarray, l2c: np.ndarray, stride: int) -> np.ndarray:
    h, w = depth_m.shape[:2]
    fx = float(k_mat[0, 0])
    fy = float(k_mat[1, 1])
    cx = float(k_mat[0, 2])
    cy = float(k_mat[1, 2])

    v, u = np.mgrid[0:h:stride, 0:w:stride]
    z = depth_m[v, u]
    mask = np.isfinite(z) & (z > 1e-3)
    if not np.any(mask):
        return np.zeros((0, 3), dtype=np.float32)

    u = u[mask].astype(np.float32)
    v = v[mask].astype(np.float32)
    z = z[mask].astype(np.float32)

    x = (u - cx) * z / fx
    y = (v - cy) * z / fy

    points_cam = np.stack([x, y, z, np.ones_like(z)], axis=1)
    c2l = np.linalg.inv(l2c)
    points_lidar = (c2l @ points_cam.T).T
    points_lidar[:, 0] *= -1.0
    return points_lidar[:, :3].astype(np.float32)


def _lidar_to_navsim(points_lidar: np.ndarray) -> np.ndarray:
    if points_lidar.size == 0:
        return points_lidar
    navsim_points = np.zeros_like(points_lidar, dtype=np.float32)
    navsim_points[:, 0] = -points_lidar[:, 1]
    navsim_points[:, 1] = -points_lidar[:, 0]
    navsim_points[:, 2] = points_lidar[:, 2]
    return navsim_points


def _latest_frame(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 4:
        return frame[-1]
    return frame


def _pad_image(image: np.ndarray, left: int = 0, right: int = 0, top: int = 0, bottom: int = 0) -> np.ndarray:
    if left <= 0 and right <= 0 and top <= 0 and bottom <= 0:
        return image
    return np.pad(
        image,
        ((top, bottom), (left, right), (0, 0)),
        mode="constant",
        constant_values=0,
    )


def _command_one_hot(command: int) -> np.ndarray:
    # Ours: right, left, straight
    # NAVSIM: left, straight, right
    command_mapping = {0:2, 1:0, 2:1, 3:3}
    out = np.zeros(4, dtype=np.float32)
    idx = int(command_mapping[command])
    if idx < 0 or idx > 2:
        idx = 3
    out[idx] = 1.0
    return out


def _normalize_plan_traj(plan_traj: np.ndarray) -> Optional[np.ndarray]:
    if plan_traj is None:
        return None
    traj = np.asarray(plan_traj)
    if traj.ndim == 3 and traj.shape[0] == 1:
        traj = traj[0]
    if traj.ndim != 2 or traj.shape[1] < 2:
        return None
    converted = np.zeros_like(traj, dtype=np.float32)
    converted[:, 0] = -traj[:, 1]
    converted[:, 1] = traj[:, 0]
    print(converted)
    return converted[:, :2]


def _save_debug_features(features: Dict[str, "torch.Tensor"], debug_dir: str, step_idx: int) -> None:
    if not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)

    camera_feature = features.get("camera_feature")
    if camera_feature is not None:
        cam = camera_feature.detach().cpu().numpy()
        if cam.ndim == 3:
            cam_img = np.transpose(cam, (1, 2, 0))
        else:
            cam_img = cam
        cam_img = np.clip(cam_img * 255.0, 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(debug_dir, f"camera_feature_{step_idx:06d}.png"), cam_img)
        np.save(os.path.join(debug_dir, f"camera_feature_{step_idx:06d}.npy"), cam)

    lidar_feature = features.get("lidar_feature")
    if lidar_feature is not None:
        lid = lidar_feature.detach().cpu().numpy()
        np.save(os.path.join(debug_dir, f"lidar_feature_{step_idx:06d}.npy"), lid)
        if lid.ndim == 3:
            channels = []
            for ch in range(min(2, lid.shape[0])):
                channel = lid[ch]
                if channel.max() > channel.min():
                    channel = (channel - channel.min()) / (channel.max() - channel.min())
                channel = np.clip(channel * 255.0, 0, 255).astype(np.uint8)
                channels.append(channel)
            if channels:
                if len(channels) == 1:
                    lidar_img = np.stack([channels[0]] * 3, axis=-1)
                else:
                    lidar_img = np.stack([channels[0], channels[1], np.zeros_like(channels[0])], axis=-1)
                cv2.imwrite(os.path.join(debug_dir, f"lidar_feature_{step_idx:06d}.png"), lidar_img)


class DiffusionDriveClient(GrpcClient):
    def __init__(
        self,
        checkpoint: str,
        host: str = "localhost",
        port: int = 50052,
        device: str = "cuda:0",
        cameras: Optional[List[str]] = None,
        depth_cameras: Optional[List[str]] = None,
        depth_stride: int = 4,
        depth_max_m: float = 1000.0,
        backbone_path: str = "",
        plan_anchor_path: str = "",
    ):
        super().__init__(host=host, port=port)
        self.device = device

        self.cameras = cameras or ["camera_2", "camera_0", "camera_1"]
        self.depth_cameras = depth_cameras or ["camera_0"]
        self.depth_stride = max(1, int(depth_stride))
        self.depth_max_m = float(depth_max_m)

        config = TransfuserConfig()
        if backbone_path:
            config.bkb_path = backbone_path
        if plan_anchor_path:
            config.plan_anchor_path = plan_anchor_path

        self.agent = TransfuserAgent(config=config, lr=1e-4, checkpoint_path=checkpoint)
        self.agent.to(self.device)
        self.agent.eval()
        self.feature_builder = TransfuserFeatureBuilder(config=config)

    def _build_agent_input(self, obs_img: Dict, obs_info: Dict) -> AgentInput:
        cam_params_all = obs_info.get("cam_params", {})

        def _make_camera(cam_name: str, role: str) -> Camera:
            if cam_name not in obs_img:
                return Camera()
            img = _latest_frame(obs_img[cam_name])
            if role == "l0":
                img = _pad_image(img, right=416)
            elif role == "r0":
                img = _pad_image(img, left=416)
            cam_params = cam_params_all.get(cam_name, {})
            return Camera(image=img, intrinsics=cam_params.get("K"))

        cam_l0 = _make_camera(self.cameras[0], "l0")
        cam_f0 = _make_camera(self.cameras[1], "f0") if len(self.cameras) > 1 else Camera()
        cam_r0 = _make_camera(self.cameras[2], "r0") if len(self.cameras) > 2 else Camera()

        cameras = Cameras(
            cam_f0=cam_f0,
            cam_l0=cam_l0,
            cam_l1=Camera(),
            cam_l2=Camera(),
            cam_r0=cam_r0,
            cam_r1=Camera(),
            cam_r2=Camera(),
            cam_b0=Camera(),
        )

        lidar_points_list = []
        for cam_name in self.depth_cameras:
            depth_key = f"{cam_name}_depth"
            if depth_key not in obs_img:
                continue
            cam_params = cam_params_all.get(cam_name, {})
            k_mat = cam_params.get("K")
            l2c = cam_params.get("l2c")
            if k_mat is None or l2c is None:
                continue
            depth_rgb = _latest_frame(obs_img[depth_key])
            depth_m = _decode_depth_from_rgb(depth_rgb, self.depth_max_m)
            points = _depth_to_lidar_points(depth_m, np.asarray(k_mat), np.asarray(l2c), self.depth_stride)
            if points.shape[0] > 0:
                lidar_points_list.append(points)

        if lidar_points_list:
            lidar_points = np.concatenate(lidar_points_list, axis=0)
            lidar_points = _lidar_to_navsim(lidar_points)
        else:
            lidar_points = np.zeros((0, 3), dtype=np.float32)

        if lidar_points.shape[0] > 0:
            zeros = np.zeros((lidar_points.shape[0], 3), dtype=np.float32)
            lidar_pc = np.concatenate([lidar_points, zeros], axis=1).T.astype(np.float32)
        else:
            lidar_pc = np.zeros((6, 0), dtype=np.float32)

        velocity = np.asarray(obs_info.get("linear_velocity", [0.0, 0.0, 0.0]), dtype=np.float32)
        acceleration = np.asarray(obs_info.get("linear_acceleration", [0.0, 0.0, 0.0]), dtype=np.float32)
        command = _command_one_hot(int(obs_info.get("command", 2)))
        print(f"Driving command: {command}")
        ego_status = EgoStatus(
            ego_pose=np.zeros(3, dtype=np.float32),
            ego_velocity=velocity[:2],
            ego_acceleration=acceleration[:2],
            driving_command=command,
        )

        return AgentInput([ego_status], [cameras], [Lidar(lidar_pc)])

    def run_diffusiondrive_inference(
        self,
        obs_img: Dict,
        obs_info: Dict,
        debug_dir: str = "",
        step_idx: int = -1,
    ) -> np.ndarray:
        import torch

        agent_input = self._build_agent_input(obs_img, obs_info)
        features = self.feature_builder.compute_features(agent_input)
        features = {k: v.unsqueeze(0).to(self.device) for k, v in features.items()}

        if debug_dir and step_idx >= 0:
            _save_debug_features({k: v[0] for k, v in features.items()}, debug_dir, step_idx)

        with torch.no_grad():
            predictions = self.agent.forward(features)
        traj = predictions["trajectory"][0].detach().cpu().numpy()
        return traj


def main():
    parser = argparse.ArgumentParser(description="DiffusionDrive client for StreetStudio gRPC")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--transforms", type=str, default="")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--cameras", type=str, default="camera_2,camera_0,camera_1")
    parser.add_argument("--depth-cameras", type=str, default="camera_2,camera_0,camera_1,camera_3,camera_4,camera_5")
    parser.add_argument("--depth-stride", type=int, default=16)
    parser.add_argument("--depth-max-m", type=float, default=1000.0)
    parser.add_argument("--backbone-path", type=str, default="")
    parser.add_argument("--plan-anchor-path", type=str, default="")
    parser.add_argument("--debug-dir", type=str, default="")
    parser.add_argument("--gaussian-video", type=str, default="./driving_diffusiondrive.mp4")
    parser.add_argument("--horizon", type=float, default=4.0)
    parser.add_argument("--control-dt", type=float, default=0.1)
    args = parser.parse_args()

    cameras = [c.strip() for c in args.cameras.split(",") if c.strip()]
    depth_cameras = [c.strip() for c in args.depth_cameras.split(",") if c.strip()]

    client = DiffusionDriveClient(
        checkpoint=args.checkpoint,
        host=args.host,
        port=args.port,
        device=args.device,
        cameras=cameras,
        depth_cameras=depth_cameras,
        depth_stride=args.depth_stride,
        depth_max_m=args.depth_max_m,
        backbone_path=args.backbone_path,
        plan_anchor_path=args.plan_anchor_path,
    )

    from visualize_utils import GaussianFrameRecorder, print_step_info

    gaussian_recorder = GaussianFrameRecorder(output_path=args.gaussian_video, fps=10)
    metrics_recorder = MetricsRecorder()

    try:
        episode_index = 0
        total_reward = 0.0
        while True:
            try:
                if episode_index == 0:
                    obs, reset_info = client.reset(transforms_json_path="full_reset,sequential")
                else:
                    obs, reset_info = client.reset(transforms_json_path=args.transforms)
            except grpc.RpcError as exc:
                if exc.code() == grpc.StatusCode.OUT_OF_RANGE:
                    print("All scenarios exhausted, stopping.")
                    break
                raise

            episode_index += 1
            obs_img, obs_info, _navigation, _surrounding = unpack_ad_observation(obs)
            print(f"Environment ready. Cameras: {list(obs_img.keys())}")

            plan_traj = client.run_diffusiondrive_inference(
                obs_img,
                obs_info,
                debug_dir=args.debug_dir,
                step_idx=0,
            )
            plan_traj_lidar = _normalize_plan_traj(plan_traj)
            gaussian_recorder.update_frame((obs_img, obs_info), plan_traj_lidar)
            acc, steer = traj2control(plan_traj_lidar, obs_info, horizon=args.horizon, control_dt=args.control_dt)
            action = [steer, acc]

            print(f"Initial action: steer={steer:.4f}, accel={acc:.4f}")
                
            reward_sum = 0.0
            last_info = None
            for step in range(1, args.steps + 1):
                obs, reward, terminated, truncated, info = client.step(action)
                last_info = info
                obs_img, obs_info, _navigation, _surrounding = unpack_ad_observation(obs)

                print_step_info(info)
                reward_sum += reward
                total_reward += reward
                metrics_recorder.update(info)

                plan_traj = client.run_diffusiondrive_inference(
                    obs_img,
                    obs_info,
                    debug_dir=args.debug_dir,
                    step_idx=step,
                )
                plan_traj_lidar = _normalize_plan_traj(plan_traj)
                # gaussian_recorder.update_frame((obs_img, obs_info), plan_traj_lidar)
                acc, steer = traj2control(plan_traj_lidar, obs_info, horizon=args.horizon, control_dt=args.control_dt)
                action = [steer, acc]

                if step % 1 == 0:
                    print(f"Step {step}: reward={reward:.2f}, steer={steer:.4f}, accel={acc:.4f}")

                if terminated or truncated:
                    print(f"Episode finished at step {step}")
                    break

            metrics_recorder.end_episode(last_info)
            print(f"Episode {episode_index} reward: {reward_sum:.2f}")
            print(f"Metrics so far: {metrics_recorder.summary()}")

        print(f"Total reward: {total_reward:.2f}")
        print(f"Final metrics: {metrics_recorder.summary()}")
        # gaussian_recorder.save_video()
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    exit(main())
