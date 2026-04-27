from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
from PIL import Image
from torch.utils.data import Dataset

from .command import derive_command_from_pose
from .scene_io import SceneData, build_path_xy_and_heading

# NOTE: We do not use translation here, since the prediction target is relative to ego. Only rotation matters for the transformation between LiDAR and ego frames.
LIDAR_TO_EGO_4X4 = np.array(
    [
        [0.0, 1.0, 0.0, 0.0],
        [-1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float32,
)
EGO_TO_LIDAR_4X4 = np.linalg.inv(LIDAR_TO_EGO_4X4).astype(np.float32)


@dataclass
class FrameRecord:
    scene_idx: int
    frame_idx: int


def _load_cached_images(cache_root: Path, timestamp_us: int, camera_names: Sequence[str]) -> Dict[str, np.ndarray]:
    frame_dir = cache_root / f"{timestamp_us:09d}"
    images: Dict[str, np.ndarray] = {}
    for cam_name in camera_names:
        path = frame_dir / f"{cam_name}.jpg"
        if not path.exists():
            raise FileNotFoundError(f"Missing cached camera image: {path}")
        images[cam_name] = np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)[None, ...]
    return images


def _pose_to_yaw(c2w: np.ndarray) -> float:
    return float(np.arctan2(c2w[1, 0], c2w[0, 0]))


def _world_to_lidar_xy(c2w: np.ndarray, world_xyz: np.ndarray) -> np.ndarray:
    w2e = np.linalg.inv(c2w).astype(np.float32)
    n = world_xyz.shape[0]
    world_h = np.concatenate([world_xyz, np.ones((n, 1), dtype=np.float32)], axis=1)
    ego_h = (w2e @ world_h.T).T
    lidar_h = (EGO_TO_LIDAR_4X4 @ ego_h.T).T
    return lidar_h[:, :2]


class ILSceneDataset(Dataset):
    def __init__(
        self,
        scenes: Sequence[SceneData],
        horizon: int,
        future_step_stride: int,
        indices: Sequence[FrameRecord],
        dt_seconds: float = 0.1,
        early_signal_distance: float = 10.0,
        turn_inradius_threshold: float = 15.0,
        intent_data_dir: str = "/data/users/jrguo/WOD-E2E-train-intents",
    ):
        self.scenes = list(scenes)
        self.horizon = int(horizon)
        self.future_step_stride = max(1, int(future_step_stride))
        self.indices = list(indices)
        self.dt = float(dt_seconds)
        self.early_signal_distance = float(early_signal_distance)
        self.turn_inradius_threshold = float(turn_inradius_threshold)
        self.intent_data_dir = str(intent_data_dir)

        self.scene_path_xy: List[np.ndarray] = []
        self.scene_yaws: List[np.ndarray] = []
        for scene in self.scenes:
            path_xy, path_yaws = build_path_xy_and_heading(scene.ego_poses, scene.timestamps_us)
            self.scene_path_xy.append(path_xy)
            self.scene_yaws.append(path_yaws)

    def __len__(self) -> int:
        return len(self.indices)

    def _future_target(self, scene_idx: int, frame_idx: int) -> tuple[np.ndarray, np.ndarray]:
        scene = self.scenes[scene_idx]
        c2w_curr = scene.ego_poses[scene.timestamps_us[frame_idx]]

        target = np.zeros((self.horizon, 2), dtype=np.float32)
        mask = np.zeros((self.horizon,), dtype=np.float32)

        world_xyz_seq = []
        for k in range(1, self.horizon + 1):
            j = frame_idx + k * self.future_step_stride
            if j >= len(scene.timestamps_us):
                break
            ts = scene.timestamps_us[j]
            world_xyz_seq.append(scene.ego_poses[ts][:3, 3].astype(np.float32))
            mask[k - 1] = 1.0

        if world_xyz_seq:
            world_xyz = np.stack(world_xyz_seq, axis=0)
            lidar_xy = _world_to_lidar_xy(c2w_curr, world_xyz)
            target[: lidar_xy.shape[0]] = lidar_xy
        return target, mask

    def _kinematics(self, scene_idx: int, frame_idx: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        scene = self.scenes[scene_idx]
        ts_list = scene.timestamps_us
        curr = scene.ego_poses[ts_list[frame_idx]]
        curr_pos = curr[:3, 3].astype(np.float32)

        if frame_idx > 0:
            prev = scene.ego_poses[ts_list[frame_idx - 1]]
            prev_pos = prev[:3, 3].astype(np.float32)
            prev_yaw = _pose_to_yaw(prev)
        else:
            prev_pos = curr_pos
            prev_yaw = _pose_to_yaw(curr)

        linear_velocity = (curr_pos - prev_pos) / max(self.dt, 1e-6)

        if frame_idx > 1:
            prev2 = scene.ego_poses[ts_list[frame_idx - 2]]
            prev2_pos = prev2[:3, 3].astype(np.float32)
            prev_vel = (prev_pos - prev2_pos) / max(self.dt, 1e-6)
        else:
            prev_vel = linear_velocity

        linear_acceleration = (linear_velocity - prev_vel) / max(self.dt, 1e-6)
        curr_yaw = _pose_to_yaw(curr)
        yaw_rate = (curr_yaw - prev_yaw) / max(self.dt, 1e-6)
        angular_velocity = np.array([0.0, 0.0, yaw_rate], dtype=np.float32)
        return linear_velocity, linear_acceleration, angular_velocity

    def _build_info(self, scene_idx: int, frame_idx: int, scene_token: str) -> dict:
        scene = self.scenes[scene_idx]
        ts = scene.timestamps_us[frame_idx]
        c2w = scene.ego_poses[ts]
        ego_xy = c2w[:2, 3].astype(np.float32)
        ego_yaw = _pose_to_yaw(c2w)
        turn_signal, command = derive_command_from_pose(
            path_xy=self.scene_path_xy[scene_idx],
            ego_xy=ego_xy,
            ego_yaw=ego_yaw,
            early_signal_distance=self.early_signal_distance,
            turn_inradius_threshold=self.turn_inradius_threshold,
            scene_name=scene.scene_name,
            timestamp_us=ts,
            intent_data_dir=self.intent_data_dir,
        )
        linear_velocity, linear_acceleration, angular_velocity = self._kinematics(scene_idx, frame_idx)
        return {
            "scene_token": scene_token,
            "relative_timestamp": float(ts - scene.start_time_us) / 1e6,
            "ego_rot": np.array([0.0, 0.0, ego_yaw], dtype=np.float32),
            "ego_pos": c2w[:3, 3].astype(np.float32),
            "linear_velocity": linear_velocity.astype(np.float32),
            "linear_acceleration": linear_acceleration.astype(np.float32),
            "angular_velocity": angular_velocity.astype(np.float32),
            "command": int(command),
            "turn_signal": int(turn_signal),
            "cam_params": scene.camera_params,
        }

    def __getitem__(self, index: int) -> dict:
        rec = self.indices[index]
        scene = self.scenes[rec.scene_idx]
        ts = scene.timestamps_us[rec.frame_idx]

        camera_names = sorted(scene.camera_params.keys())
        obs = _load_cached_images(scene.cache_scene_dir, ts, camera_names)
        bundle_scene_token = f"{scene.scene_name}_{ts}"
        info = self._build_info(rec.scene_idx, rec.frame_idx, scene_token=bundle_scene_token)

        warmup_obs = []
        warmup_info = []
        for hist_idx in (rec.frame_idx - 2, rec.frame_idx - 1):
            hist_ts = scene.timestamps_us[hist_idx]
            warmup_obs.append(_load_cached_images(scene.cache_scene_dir, hist_ts, camera_names))
            warmup_info.append(self._build_info(rec.scene_idx, hist_idx, scene_token=bundle_scene_token))

        target_xy, target_mask = self._future_target(rec.scene_idx, rec.frame_idx)

        return {
            "obs": obs,
            "info": info,
            "warmup_obs": warmup_obs,
            "warmup_info": warmup_info,
            "target_xy": target_xy,
            "target_mask": target_mask,
            "scene_name": scene.scene_name,
            "timestamp_us": int(ts),
        }


def split_records(
    scenes: Sequence[SceneData],
    train_ratio: float,
    horizon: int,
    future_step_stride: int,
    seed: int = 42,
) -> tuple[List[FrameRecord], List[FrameRecord]]:
    del horizon
    stride = max(1, int(future_step_stride))
    all_records: List[FrameRecord] = []
    for scene_idx, scene in enumerate(scenes):
        for frame_idx in range(2, max(0, len(scene.timestamps_us) - 1)):
            # Drop samples whose future mask would be all zeros.
            if frame_idx + stride >= len(scene.timestamps_us):
                continue
            all_records.append(FrameRecord(scene_idx=scene_idx, frame_idx=frame_idx))

    if not all_records:
        return [], []

    rng = np.random.default_rng(int(seed))
    rng.shuffle(all_records)

    n_train = int(round(len(all_records) * float(train_ratio)))
    n_train = max(1, min(n_train, len(all_records) - 1)) if len(all_records) > 1 else 1
    return all_records[:n_train], all_records[n_train:]


def collate_list(batch: Sequence[dict]) -> List[dict]:
    return list(batch)
