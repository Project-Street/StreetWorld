#!/usr/bin/env python
"""
TransFuser gRPC client for StreetStudio environment.

This client mirrors vad_client/uniad_client but runs TransFuser inference
locally using RGB images + mocked LiDAR from depth images.
"""

import argparse
import json
import os
import sys
import grpc
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

import cv2
import numpy as np

from grpc_obs_adapter import unpack_ad_observation
from grpc_client import GrpcClient
from metrics import MetricsRecorder

os.environ['no_proxy'] = '127.0.0.1,localhost'

TRANSFUSER_ROOT = Path(__file__).resolve().parents[2] / "transfuser" / "team_code_transfuser"
if str(TRANSFUSER_ROOT) not in sys.path:
    sys.path.insert(0, str(TRANSFUSER_ROOT))
RL_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RL_FRAMEWORK_ROOT))

from rl_framework.uniad.traj_parser import traj2control

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


def _command_to_target_point(command: int, lookahead: float, lateral: float) -> np.ndarray:
    # Forward -y, Left x
    if command == 0:  # right
        return np.array([lateral, -lookahead], dtype=np.float32)
    if command == 1:  # left
        return np.array([-lateral, -lookahead], dtype=np.float32)
    return np.array([0.0, -lookahead], dtype=np.float32)


def _extract_path_xy(expert_path: List[float]) -> Optional[np.ndarray]:
    if expert_path is None:
        return None
    path = np.asarray(expert_path, dtype=np.float32)
    if path.size < 2:
        return None
    if path.ndim == 1:
        if path.size % 2 != 0:
            return None
        path = path.reshape(-1, 2)
    elif path.ndim >= 2:
        if path.shape[1] < 2:
            return None
        path = path[:, :2]
    return path


def _world_to_local_point(point_xy: np.ndarray, ego_pos: np.ndarray, ego_yaw: float) -> np.ndarray:
    local_point = np.array([
        float(point_xy[0] - ego_pos[0]),
        float(point_xy[1] - ego_pos[1]),
    ], dtype=np.float32)
    rot = np.array([
        [np.cos(np.pi / 2.0 + ego_yaw), -np.sin(np.pi / 2.0 + ego_yaw)],
        [np.sin(np.pi / 2.0 + ego_yaw),  np.cos(np.pi / 2.0 + ego_yaw)],
    ], dtype=np.float32)
    return rot.T.dot(local_point)


def _path_to_target_point(path_xy: np.ndarray, ego_pos: np.ndarray, ego_yaw: float, lookahead: float) -> Optional[np.ndarray]:
    if path_xy is None or path_xy.shape[0] == 0:
        return None
    target_xy = path_xy[-1]
    return _world_to_local_point(target_xy, ego_pos, ego_yaw)


def _normalize_plan_traj(plan_traj: np.ndarray) -> Optional[np.ndarray]:
    # [x, y] -> [-y, x]
    print(plan_traj)
    if plan_traj is None:
        return None
    traj = np.asarray(plan_traj)
    if traj.ndim == 3 and traj.shape[0] == 1:
        traj = traj[0]
    if traj.ndim != 2 or traj.shape[1] < 2:
        return None
    converted_traj = np.zeros_like(traj, dtype=np.float32)
    converted_traj[:, 0] = -traj[:, 1]
    converted_traj[:, 1] = traj[:, 0]
    traj = converted_traj
    print(traj)
    return traj[:, :2]


def _load_transfuser(model_dir: Path, checkpoint: str, device: str):
    import torch
    from model import LidarCenterNet
    from config import GlobalConfig

    args_path = model_dir / "args.txt"
    if args_path.exists():
        with args_path.open("r") as f:
            args = json.load(f)
    else:
        args = {}

    config = GlobalConfig(setting="eval")
    if "sync_batch_norm" in args:
        config.sync_batch_norm = bool(args["sync_batch_norm"])
    if "use_point_pillars" in args:
        config.use_point_pillars = bool(args["use_point_pillars"])
    if "n_layer" in args:
        config.n_layer = args["n_layer"]
    if "use_target_point_image" in args:
        config.use_target_point_image = bool(args["use_target_point_image"])

    use_velocity = bool(args.get("use_velocity", True))
    image_architecture = args.get("image_architecture", "resnet34")
    lidar_architecture = args.get("lidar_architecture", "resnet18")
    backbone = args.get("backbone", "transFuser")

    if checkpoint:
        ckpt_path = model_dir / checkpoint
    else:
        candidates = sorted(model_dir.glob("*.pth"))
        if not candidates:
            raise FileNotFoundError(f"No .pth checkpoint found in {model_dir}")
        ckpt_path = candidates[0]

    net = LidarCenterNet(config, device, backbone, image_architecture, lidar_architecture, use_velocity)
    state_dict = torch.load(str(ckpt_path), map_location=device)
    if all(k.startswith("module.") for k in state_dict.keys()):
        state_dict = {k[7:]: v for k, v in state_dict.items()}
    net.load_state_dict(state_dict, strict=False)
    net.to(device)
    net.eval()
    return net, config


class TransFuserClient(GrpcClient):
    def __init__(
        self,
        model_dir: str,
        checkpoint: str,
        host: str = "localhost",
        port: int = 50052,
        device: str = "cuda:0",
        cameras: Optional[List[str]] = None,
        depth_cameras: Optional[List[str]] = None,
        depth_stride: int = 4,
        depth_max_m: float = 1000.0,
        lookahead: float = 8.0,
        lateral: float = 3.0,
    ):
        super().__init__(host=host, port=port)
        self.device = device

        self.model, self.config = _load_transfuser(Path(model_dir), checkpoint, device)

        self.cameras = cameras or ["camera_2", "camera_0", "camera_1"]
        self.depth_cameras = depth_cameras or ["camera_0"]
        self.depth_stride = max(1, int(depth_stride))
        self.depth_max_m = float(depth_max_m)
        self.lookahead = float(lookahead)
        self.lateral = float(lateral)

    def run_transfuser_inference(
        self,
        obs_img: Dict,
        obs_info: Dict,
        debug_dir: str = "",
        step_idx: int = -1,
    ) -> Tuple[float, float, float, np.ndarray]:
        import torch
        from data import crop_image_cv2, lidar_to_histogram_features, draw_target_point

        rgb_list = []
        for cam_name in self.cameras:
            if cam_name not in obs_img:
                raise KeyError(f"Missing camera image: {cam_name}")
            rgb_list.append(obs_img[cam_name][0])

        rgb_concat = np.concatenate(rgb_list, axis=1)
        rgb_cropped = crop_image_cv2(rgb_concat, crop=self.config.img_resolution, crop_shift=0)
        rgb_tensor = torch.from_numpy(rgb_cropped).unsqueeze(0).to(self.device, dtype=torch.float32)

        lidar_points_list = []
        cam_params_all = obs_info.get("cam_params", {})
        for cam_name in self.depth_cameras:
            depth_key = f"{cam_name}_depth"
            if depth_key not in obs_img:
                continue
            cam_params = cam_params_all.get(cam_name, {})
            if not cam_params:
                continue
            depth_rgb = obs_img[depth_key][0]
            depth_m = _decode_depth_from_rgb(depth_rgb, self.depth_max_m)
            k_mat = cam_params.get("K")
            l2c = cam_params.get("l2c")
            if k_mat is None or l2c is None:
                continue
            points = _depth_to_lidar_points(depth_m, np.asarray(k_mat), np.asarray(l2c), self.depth_stride)
            if points.shape[0] > 0:
                lidar_points_list.append(points)

        if lidar_points_list:
            lidar_points = np.concatenate(lidar_points_list, axis=0)
        else:
            lidar_points = np.zeros((0, 3), dtype=np.float32)

        use_point_pillars = bool(self.config.use_point_pillars)
        lidar_bev_tensor = None
        num_points = None
        lidar_bev = None
        if lidar_points.shape[0] == 0:
            if use_point_pillars:
                lidar_points = np.zeros((1, 4), dtype=np.float32)
                num_points = [torch.tensor(0, device=self.device, dtype=torch.int32)]
                lidar_bev_tensor = [torch.from_numpy(lidar_points).to(self.device, dtype=torch.float32)]
            else:
                lidar_bev = np.zeros((2, self.config.lidar_resolution_width, self.config.lidar_resolution_height), dtype=np.float32)
                lidar_bev_tensor = torch.from_numpy(lidar_bev).unsqueeze(0).to(self.device, dtype=torch.float32)
        else:
            lidar_points[:, 1] *= -1.0
            if use_point_pillars:
                num_points = [torch.tensor(lidar_points.shape[0], device=self.device, dtype=torch.int32)]
                lidar_bev_tensor = [torch.from_numpy(lidar_points).to(self.device, dtype=torch.float32)]
            else:
                lidar_bev = lidar_to_histogram_features(lidar_points)
                lidar_bev_tensor = torch.from_numpy(lidar_bev).unsqueeze(0).to(self.device, dtype=torch.float32)

        command = int(obs_info.get("command", 2))
        target_point = None
        path_xy = _extract_path_xy(obs_info.get("expert_path", []))
        if path_xy is not None:
            ego_pos = np.asarray(obs_info.get("ego_pos", np.zeros(3, dtype=np.float32)), dtype=np.float32)
            ego_rot = np.asarray(obs_info.get("ego_rot", np.zeros(3, dtype=np.float32)), dtype=np.float32)
            target_point = _path_to_target_point(path_xy, ego_pos, float(ego_rot[2]), self.lookahead)
        if target_point is None:
            target_point = _command_to_target_point(command, self.lookahead, self.lateral)
        
        target_point_image = draw_target_point(target_point)

        if debug_dir and step_idx >= 0 and (not use_point_pillars) and lidar_bev is not None:
            os.makedirs(debug_dir, exist_ok=True)
            lidar_img = np.zeros((lidar_bev.shape[1], lidar_bev.shape[2], 3), dtype=np.uint8)
            lidar_img[..., 2] = np.clip(lidar_bev[0] * 255.0, 0, 255).astype(np.uint8)
            lidar_img[..., 1] = np.clip(lidar_bev[1] * 255.0, 0, 255).astype(np.uint8)
            lidar_path = os.path.join(debug_dir, f"lidar_hist_{step_idx:06d}.png")
            cv2.imwrite(lidar_path, lidar_img)

            target_img = np.clip(target_point_image[0] * 255.0, 0, 255).astype(np.uint8)
            target_path = os.path.join(debug_dir, f"target_point_{step_idx:06d}.png")
            cv2.imwrite(target_path, target_img)

        target_point_tensor = torch.from_numpy(target_point).unsqueeze(0).to(self.device, dtype=torch.float32)
        target_point_image_tensor = torch.from_numpy(target_point_image).unsqueeze(0).to(self.device, dtype=torch.float32)

        speed = float(obs_info.get("ego_velo", 0.0))
        velocity_tensor = torch.tensor([[speed]], dtype=torch.float32, device=self.device)

        with torch.no_grad():
            pred_wp, _ = self.model.forward_ego(
                rgb_tensor,
                lidar_bev_tensor,
                target_point_tensor,
                target_point_image_tensor,
                velocity_tensor,
                num_points=num_points,
            )
            steer, throttle, brake = self.model.control_pid(pred_wp, velocity_tensor, is_stuck=False)
        return float(steer), float(throttle), float(brake), pred_wp.detach().cpu().numpy()


def main():
    parser = argparse.ArgumentParser(description="TransFuser client for StreetStudio gRPC")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--transforms", type=str, default="")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--model-dir", type=str, default="/home/guojiarui/river/models/transfuser/model_ckpt/models_2022/transfuser")
    parser.add_argument("--checkpoint", type=str, default="")
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--cameras", type=str, default="camera_0,camera_1,camera_2")
    parser.add_argument("--depth-cameras", type=str, default="camera_0,camera_1,camera_2")
    parser.add_argument("--depth-stride", type=int, default=4)
    parser.add_argument("--depth-max-m", type=float, default=1000.0)
    parser.add_argument("--lookahead", type=float, default=8.0)
    parser.add_argument("--lateral", type=float, default=3.0)
    parser.add_argument("--debug-dir", type=str, default="")
    parser.add_argument("--gaussian-video", type=str, default="./driving_transfuser.mp4")
    args = parser.parse_args()

    cameras = [c.strip() for c in args.cameras.split(",") if c.strip()]

    depth_cameras = [c.strip() for c in args.depth_cameras.split(",") if c.strip()]

    client = TransFuserClient(
        model_dir=args.model_dir,
        checkpoint=args.checkpoint,
        host=args.host,
        port=args.port,
        device=args.device,
        cameras=cameras,
        depth_cameras=depth_cameras,
        depth_stride=args.depth_stride,
        depth_max_m=args.depth_max_m,
        lookahead=args.lookahead,
        lateral=args.lateral,
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
            obs_img, obs_info, navigation, surrounding = unpack_ad_observation(obs)
            print(f"Environment ready. Cameras: {list(obs_img.keys())}")

            steer, throttle, brake, pred_wp = client.run_transfuser_inference(
                obs_img,
                obs_info,
                debug_dir=args.debug_dir,
                step_idx=0,
            )
            gaussian_recorder.update_frame((obs_img, obs_info), _normalize_plan_traj(pred_wp))
            acc, steer = traj2control(_normalize_plan_traj(pred_wp), obs_info, horizon=2.0, control_dt=0.5)
            action = [steer, acc]

            print(f"Initial action: steer={steer:.4f}, throttle={action[1]:.4f}, brake={brake:.4f}")

            reward_sum = 0.0
            last_info = None
            for step in range(1, args.steps + 1):
                obs, reward, terminated, truncated, info = client.step(action)
                last_info = info
                obs_img, obs_info, navigation, surrounding = unpack_ad_observation(obs)
                
                print_step_info(info)
                reward_sum += reward
                total_reward += reward
                metrics_recorder.update(info)

                steer, throttle, brake, pred_wp = client.run_transfuser_inference(
                    obs_img,
                    obs_info,
                    debug_dir=args.debug_dir,
                    step_idx=step,
                )
                
                # gaussian_recorder.update_frame((obs_img, obs_info), _normalize_plan_traj(pred_wp))
                acc, steer = traj2control(_normalize_plan_traj(pred_wp), obs_info, horizon=2.0, control_dt=0.5)
                action = [steer, acc]
            
                if step % 1 == 0:
                    print(f"Step {step}: reward={reward:.2f}, steer={steer:.4f}, throttle={action[1]:.4f}")

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
