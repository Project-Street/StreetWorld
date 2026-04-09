from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import yaml


TIMESTAMP_INTERVAL_US = 100_000


@dataclass
class SceneData:
    config_path: Path
    scene_name: str
    scene_root: Path
    cache_root: Path
    cache_scene_dir: Path
    start_time_us: int
    end_time_us: int
    timestamps_us: List[int]
    camera_params: Dict[str, dict]
    ego_poses: Dict[int, np.ndarray]
    tracking_path: Path
    cfg_text: dict


def _axes_transformation() -> np.ndarray:
    return np.array(
        [
            [0, 0, 1, 0],
            [-1, 0, 0, 0],
            [0, -1, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float32,
    )


def _load_ego_pose(c2w_path: Path) -> Dict[int, np.ndarray]:
    if c2w_path.suffix == ".json":
        with c2w_path.open("r", encoding="utf-8") as f:
            c2w_data = json.load(f)
    else:
        c2w_data = np.load(str(c2w_path), allow_pickle=True).item()

    axes = _axes_transformation()
    ego_poses: Dict[int, np.ndarray] = {}
    num_frames = len(c2w_data)
    for frame_idx in range(num_frames):
        timestamp = frame_idx * TIMESTAMP_INTERVAL_US
        c2w = c2w_data[f"{frame_idx:06d}"]
        c2w = axes @ c2w["e2w"]
        ego_poses[timestamp] = c2w.astype(np.float32)
    return ego_poses


def _resolve_c2w_json_path(cfg_text: dict) -> Path:
    if "c2w_json_path" in cfg_text and cfg_text["c2w_json_path"]:
        c2w_json = Path(cfg_text["c2w_json_path"])
        if not c2w_json.exists():
            raise FileNotFoundError(f"c2w_json_path not found: {c2w_json}")
        return c2w_json

    c2w_path = Path(cfg_text["c2w_path"])
    if c2w_path.suffix == ".json":
        if not c2w_path.exists():
            raise FileNotFoundError(f"c2w_path json not found: {c2w_path}")
        return c2w_path

    inferred_json = c2w_path.with_suffix(".json")
    if inferred_json.exists():
        return inferred_json

    raise FileNotFoundError(
        f"Expected c2w json file for IL but not found: {inferred_json}. "
        f"Please run converter script to generate json from {c2w_path}."
    )


def _load_camera_rig(camera_rig_config: dict) -> Dict[str, dict]:
    camera_rig_path = Path(camera_rig_config["camera_rig_path"])
    camera_rig_type = camera_rig_config.get("camera_rig_type", None)
    front = set(camera_rig_config.get("front_camera", []))
    return_depth = bool(camera_rig_config.get("return_depth", False))
    return_depth_cameras = set(camera_rig_config.get("return_depth_cameras", []) or [])
    hs = camera_rig_config.get("Hs", None)
    ws = camera_rig_config.get("Ws", None)

    if camera_rig_path.suffix == ".json":
        with camera_rig_path.open("r", encoding="utf-8") as f:
            cameras_data = json.load(f)
    else:
        cameras_data = np.load(str(camera_rig_path))

    if "intrinsics" not in cameras_data or "extrinsics" not in cameras_data:
        raise ValueError("camera rig must include 'intrinsics' and 'extrinsics'")

    intrinsics_array = cameras_data["intrinsics"]
    c2e_array = cameras_data["extrinsics"]

    if camera_rig_type == "waymo-e2e":
        axes_transformation = np.array(
            [
                [0, -1, 0, 0],
                [0, 0, -1, 0],
                [1, 0, 0, 0],
                [0, 0, 0, 1],
            ]
        )
        c2e_array = np.linalg.inv(
            np.array(
                [
                    [0, 1, 0, 0],
                    [-1, 0, 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]
            )
            @ np.array(
                [
                    [0, 0, 1, 0],
                    [0, 1, 0, 0],
                    [-1, 0, 0, 0],
                    [0, 0, 0, 1],
                ]
            )
        ) @ c2e_array @ np.linalg.inv(axes_transformation)

    camera_param_dict: Dict[str, dict] = {}
    for cam_idx in range(len(intrinsics_array)):
        intrinsics = intrinsics_array[cam_idx]
        c2e = c2e_array[cam_idx]
        k_3x3 = np.array(
            [
                [intrinsics[0, 0], 0, intrinsics[0, 2]],
                [0, intrinsics[1, 1], intrinsics[1, 2]],
                [0, 0, 1],
            ],
            dtype=np.float32,
        )
        h = int(hs[cam_idx]) if hs is not None else int(intrinsics[1, 2] * 2)
        w = int(ws[cam_idx]) if ws is not None else int(intrinsics[0, 2] * 2)
        ego2camera = np.linalg.inv(c2e).astype(np.float32)
        meta = {
            "render_gaussian": "front" if cam_idx in front else "back",
            "camera_rig_type": camera_rig_type,
        }
        if return_depth or cam_idx in return_depth_cameras:
            meta["return_depth"] = True
        camera_param_dict[f"camera_{cam_idx}"] = {
            "K": k_3x3,
            "H": h,
            "W": w,
            "ego2camera": ego2camera,
            "meta": meta,
        }
    return camera_param_dict


def _resolve_tracking_path(cfg: dict) -> Path:
    tracking_path = Path(cfg["tracking_data_path"])
    if not tracking_path.exists():
        raise FileNotFoundError(f"tracking_data_path not found: {tracking_path}")
    return tracking_path


def derive_cache_root_from_tracking(tracking_path: Path) -> Path:
    return tracking_path.parent / "cache"


def load_scene_from_config(config_path: Path) -> SceneData:
    with config_path.open("r", encoding="utf-8") as f:
        cfg_text = yaml.safe_load(f)

    scene_name = str(cfg_text["scene_name"])
    start_time_us = int(cfg_text["start_time"])
    end_time_us = int(cfg_text["end_time"]) - TIMESTAMP_INTERVAL_US

    tracking_path = _resolve_tracking_path(cfg_text)
    cache_root = derive_cache_root_from_tracking(tracking_path)
    cache_scene_dir = cache_root / scene_name
    scene_root = cache_root.parent

    camera_params = _load_camera_rig(cfg_text["camera_rig_config"])
    c2w_json_path = _resolve_c2w_json_path(cfg_text)
    ego_poses = _load_ego_pose(c2w_json_path)

    timestamps = sorted(ts for ts in ego_poses.keys() if start_time_us <= ts <= end_time_us)
    if not timestamps:
        raise ValueError(f"No timestamps in [{start_time_us}, {end_time_us}] for {config_path}")

    return SceneData(
        config_path=config_path,
        scene_name=scene_name,
        scene_root=scene_root,
        cache_root=cache_root,
        cache_scene_dir=cache_scene_dir,
        start_time_us=start_time_us,
        end_time_us=end_time_us,
        timestamps_us=timestamps,
        camera_params=camera_params,
        ego_poses=ego_poses,
        tracking_path=tracking_path,
        cfg_text=cfg_text,
    )


def discover_scene_configs(scene_config_dir: Path) -> List[Path]:
    return sorted(scene_config_dir.glob("*.yaml"))


def build_path_xy_and_heading(ego_poses: Dict[int, np.ndarray], timestamps: List[int]) -> Tuple[np.ndarray, np.ndarray]:
    pts = []
    yaws = []
    for ts in timestamps:
        pose = ego_poses[ts]
        pts.append([float(pose[0, 3]), float(pose[1, 3])])
        yaw = float(np.arctan2(pose[1, 0], pose[0, 0]))
        yaws.append(yaw)
    return np.asarray(pts, dtype=np.float32), np.asarray(yaws, dtype=np.float32)
