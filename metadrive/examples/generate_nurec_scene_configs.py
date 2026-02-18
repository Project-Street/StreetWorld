#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import yaml

logger = logging.getLogger(__name__)


def parse_batch_num(batch_name: str) -> str:
    m = re.fullmatch(r"Batch0*([0-9]+)", batch_name)
    return m.group(1) if m else batch_name


def discover_scenes_by_batch(nurec_path: Path) -> List[Tuple[str, List[Tuple[str, Path]]]]:
    by_batch: Dict[str, List[Tuple[str, Path]]] = defaultdict(list)
    for usdz_path in nurec_path.rglob("*.usdz"):
        scene_name = usdz_path.stem
        scene_root = usdz_path.parent
        rig_path = scene_root / scene_name / "rig_trajectories.json"
        if rig_path.is_file():
            batch_name = scene_root.parent.name
            by_batch[batch_name].append((scene_name, scene_root))
    return [
        (batch_name, sorted(scenes, key=lambda x: x[0]))
        for batch_name, scenes in sorted(by_batch.items(), key=lambda x: x[0])
    ]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _quat_xyzw_to_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    x = float(qx)
    y = float(qy)
    z = float(qz)
    w = float(qw)
    n = w * w + x * x + y * y + z * z
    if n < 1e-12:
        return np.eye(3, dtype=np.float64)
    s = 2.0 / n
    wx, wy, wz = s * w * x, s * w * y, s * w * z
    xx, xy, xz = s * x * x, s * x * y, s * x * z
    yy, yz, zz = s * y * y, s * y * z, s * z * z
    return np.array(
        [
            [1.0 - (yy + zz), xy - wz, xz + wy],
            [xy + wz, 1.0 - (xx + zz), yz - wx],
            [xz - wy, yz + wx, 1.0 - (xx + yy)],
        ],
        dtype=np.float64,
    )


def _parse_ego_poses(rig: Dict[str, Any]) -> Dict[int, List[List[float]]]:
    traj = rig["rig_trajectories"][0]
    timestamps = [int(ts) for ts in traj["T_rig_world_timestamps_us"]]
    poses = np.array(traj["T_rig_worlds"], dtype=np.float64)
    ego_poses: Dict[int, List[List[float]]] = {}
    for ts, pose in zip(timestamps, poses):
        # Keep original world frame. Do not apply world->map transform in this merged script.
        ego_poses[ts] = pose.tolist()
    return ego_poses


def _parse_tracking_data(tracks: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not tracks:
        return {}
    chunk_key = next(iter(tracks))
    tracks_data = tracks[chunk_key]["tracks_data"]
    cuboid_data = tracks[chunk_key]["cuboidtracks_data"]
    track_ids = tracks_data["tracks_id"]
    labels = tracks_data["tracks_label_class"]
    timestamps_list = tracks_data["tracks_timestamps_us"]
    poses_list = tracks_data["tracks_poses"]
    sizes = cuboid_data["cuboids_dims"]

    tracking: Dict[str, Dict[str, Any]] = {}
    for idx, track_id in enumerate(track_ids):
        obj_id = str(track_id)
        raw_obj_type = str(labels[idx])
        obj_type_key = raw_obj_type.lower()
        obj_type = {
            "automobile": "vehicle",
            "trailer": "vehicle",
            "heavy_truck": "vehicle",
            "other_vehicle": "vehicle",
            "bus": "vehicle",
            "person": "pedestrian",
            "bicycle": "cyclist",
            "stroller": "pedestrian",
        }.get(obj_type_key, obj_type_key)
        if obj_type not in ("vehicle", "pedestrian", "cyclist"):
            logger.warning(
                "Drop unsupported NuRec object type: track_id=%s, type=%s",
                obj_id,
                raw_obj_type,
            )
            continue

        pose_map: Dict[int, List[List[float]]] = {}
        for ts, pose in zip(timestamps_list[idx], poses_list[idx]):
            x, y, z, qx, qy, qz, qw = pose
            rot = _quat_xyzw_to_matrix(qx, qy, qz, qw)
            mat = np.eye(4, dtype=np.float64)
            mat[:3, :3] = rot
            mat[:3, 3] = [x, y, z]
            # Keep original world frame. Do not apply world->map transform in this merged script.
            pose_map[int(ts)] = mat.tolist()
        tracking[obj_id] = {
            "poses": pose_map,
            "size": sizes[idx],
            "type": obj_type,
        }
    return tracking


def _flatten_4x4(mat: List[List[float]]) -> List[float]:
    return [v for row in mat for v in row]


def export_pose_data(scene_dir: Path, out_dir: Path) -> Tuple[Path, Path]:
    rig = _load_json(scene_dir / "rig_trajectories.json")
    ego_poses = _parse_ego_poses(rig)

    tracks = _load_json(scene_dir / "sequence_tracks.json")
    tracking = _parse_tracking_data(tracks)

    ego_pose_out = {str(int(ts)): mat for ts, mat in sorted(ego_poses.items(), key=lambda x: int(x[0]))}
    trajectory_out: Dict[str, Dict[str, Any]] = {}
    for obj_id, obj in tracking.items():
        local2world = {
            str(int(ts)): _flatten_4x4(mat)
            for ts, mat in sorted(obj["poses"].items(), key=lambda x: int(x[0]))
        }
        trajectory_out[obj_id] = {
            "type": obj["type"],
            "size": list(obj["size"]),
            "local2world": local2world,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    ego_pose_path = out_dir / "ego_pose.json"
    trajectory_path = out_dir / "trajectory.json"
    ego_pose_path.write_text(json.dumps(ego_pose_out, ensure_ascii=False, indent=2), encoding="utf-8")
    trajectory_path.write_text(json.dumps(trajectory_out, ensure_ascii=False, indent=2), encoding="utf-8")
    return ego_pose_path, trajectory_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nurec_path", type=Path)
    parser.add_argument("pose_output_path", type=Path)
    parser.add_argument("config_path", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    nurec_path = args.nurec_path.expanduser().resolve()
    pose_output_path = args.pose_output_path.expanduser().resolve()
    config_path = args.config_path.expanduser().resolve()
    pose_output_path.mkdir(parents=True, exist_ok=True)
    config_path.mkdir(parents=True, exist_ok=True)

    scenes_by_batch = discover_scenes_by_batch(nurec_path)
    scene_total = sum(len(scenes) for _, scenes in scenes_by_batch)
    written = 0
    skipped = 0
    exported_pose = 0

    for batch_name, scenes in scenes_by_batch:
        batch_num = parse_batch_num(batch_name)
        for idx, (scene_uuid, scene_root) in enumerate(scenes, start=1):
            scene_index = f"{batch_num}_{idx}"
            out_path = config_path / f"{scene_index}.yaml"
            if out_path.exists() and not args.overwrite:
                skipped += 1
                continue
            scene_dir = scene_root / scene_uuid
            pose_dir = pose_output_path / scene_index
            ego_pose_path, trajectory_path = export_pose_data(scene_dir, pose_dir)
            exported_pose += 1
            cfg = {
                "scene_name": scene_index,
                "scene_uuid": scene_uuid,
                "scene_root": str(scene_root),
                "pose_data_path": str(pose_dir),
                "ego_pose_path": str(ego_pose_path),
                "trajectory_path": str(trajectory_path),
            }
            out_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8")
            written += 1

    print(
        f"Done. scenes={scene_total}, pose_exported={exported_pose}, "
        f"written={written}, skipped={skipped}, pose_output={pose_output_path}, output={config_path}"
    )


if __name__ == "__main__":
    main()
