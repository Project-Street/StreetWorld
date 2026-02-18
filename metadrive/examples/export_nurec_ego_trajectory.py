#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def parse_batch_num(batch_name: str) -> str:
    m = re.fullmatch(r"Batch0*([0-9]+)", batch_name)
    return m.group(1) if m else batch_name


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


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_rig_data(rig_path: Path | str) -> Dict[str, Any]:
    return _load_json(Path(rig_path))


def load_tracks_data(tracks_path: Path | str) -> Dict[str, Any]:
    return _load_json(Path(tracks_path))


def compute_sim_world_to_xodr_map(rig_data: Dict[str, Any], xodr_path: Path) -> np.ndarray:
    from trajdata.dataset_specific.xodr.geo_transform import get_t_rig_enu_from_ecef

    xodr_xml = xodr_path.read_text(encoding="utf-8")
    t_world_base = np.asarray(rig_data["T_world_base"], dtype=np.float64)
    t_sim_world_to_xodr_map = np.asarray(get_t_rig_enu_from_ecef(t_world_base, xodr_xml), dtype=np.float64)
    return t_sim_world_to_xodr_map


def parse_ego_poses(rig: Dict[str, Any]) -> Tuple[Dict[int, List[List[float]]], List[int]]:
    traj = rig["rig_trajectories"][0]
    timestamps = [int(ts) for ts in traj["T_rig_world_timestamps_us"]]
    poses = np.array(traj["T_rig_worlds"], dtype=np.float64)
    ego_poses: Dict[int, List[List[float]]] = {}
    for ts, pose in zip(timestamps, poses):
        ego_poses[ts] = pose.tolist()
    return ego_poses, timestamps


def parse_tracking_data(
    tracks: Dict[str, Any],
    inv_world_to_nre: np.ndarray,
    t_sim_world_to_xodr_map: np.ndarray,
) -> Dict[str, Dict[str, Any]]:
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
        size = sizes[idx]
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
        timestamps = timestamps_list[idx]
        poses = poses_list[idx]
        pose_map: Dict[int, List[float]] = {}
        for ts, pose in zip(timestamps, poses):
            x, y, z, qx, qy, qz, qw = pose
            rot = _quat_xyzw_to_matrix(qx, qy, qz, qw)
            mat = np.eye(4, dtype=np.float64)
            mat[:3, :3] = rot
            mat[:3, 3] = [x, y, z]
           # mat = inv_world_to_nre @ mat
            mat = t_sim_world_to_xodr_map @ mat
            pose_map[int(ts)] = mat.tolist()
        tracking[obj_id] = {"poses": pose_map, "size": size, "type": obj_type}
    return tracking


def discover_scenes(nurec_path: Path) -> Dict[Path, List[Tuple[str, Path]]]:
    by_batch: Dict[Path, List[Tuple[str, Path]]] = defaultdict(list)

    for root, _, files in os.walk(nurec_path, followlinks=True):
        if "rig_trajectories.json" not in files:
            continue
        rig_path = Path(root) / "rig_trajectories.json"
        scene_dir = rig_path.parent
        wrapper_dir = scene_dir.parent
        batch_dir = wrapper_dir.parent
        if not batch_dir.name.startswith("Batch"):
            continue
        if scene_dir.name != wrapper_dir.name:
            continue
        by_batch[batch_dir].append((scene_dir.name, scene_dir))
    for batch_dir in by_batch:
        by_batch[batch_dir].sort(key=lambda x: x[0])
    return dict(sorted(by_batch.items(), key=lambda x: x[0].name))


def flatten_4x4(mat: List[List[float]]) -> List[float]:
    return [v for row in mat for v in row]


def export_one_scene(scene_dir: Path, out_dir: Path) -> None:
    rig = load_rig_data(scene_dir / "rig_trajectories.json")
    t_sim_world_to_xodr_map = compute_sim_world_to_xodr_map(rig, scene_dir / "map.xodr")
    ego_poses, _ = parse_ego_poses(rig)
    ego_pose_out = {
        str(int(ts)): (t_sim_world_to_xodr_map @ np.asarray(mat, dtype=np.float64)).tolist()
        for ts, mat in sorted(ego_poses.items(), key=lambda x: int(x[0]))
    }

    tracks = load_tracks_data(scene_dir / "sequence_tracks.json")
    inv_world_to_nre = np.linalg.inv(np.array(rig["world_to_nre"]["matrix"], dtype=np.float64))
    tracking = parse_tracking_data(tracks, inv_world_to_nre, t_sim_world_to_xodr_map)

    trajectory_out = {}
    for obj_id, obj in tracking.items():
        local2world = {
            str(int(ts)): flatten_4x4(mat)
            for ts, mat in sorted(obj["poses"].items(), key=lambda x: int(x[0]))
        }
        trajectory_out[str(obj_id)] = {
            "type": obj["type"],
            "size": list(obj["size"]),
            "local2world": local2world,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ego_pose.json").write_text(json.dumps(ego_pose_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "trajectory.json").write_text(json.dumps(trajectory_out, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("nurec_path", type=Path, help="NuRec root path")
    parser.add_argument("output_path", type=Path, help="Output folder")
    args = parser.parse_args()

    nurec_path = args.nurec_path.expanduser().resolve()
    output_path = args.output_path.expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    scenes_by_batch = discover_scenes(nurec_path)
    total = 0
    for batch_dir, scenes in scenes_by_batch.items():
        batch_num = parse_batch_num(batch_dir.name)
        for idx, (_, scene_dir) in enumerate(scenes, start=1):
            out_dir = output_path / f"{batch_num}_{idx}"
            export_one_scene(scene_dir, out_dir)
            total += 1

    print(f"Done. exported {total} scenes to {output_path}")


if __name__ == "__main__":
    main()
