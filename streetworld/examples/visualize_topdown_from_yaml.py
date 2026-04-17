#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from lxml import etree

# Allow running via: python streetworld/examples/xxx.py
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from streetworld.misc.nurec_interface.simulator_interface import SimulatorInterface
from streetworld.misc.nurec_interface.nurec_parser import (
    parse_ego_poses_deprecated,
    parse_tracking_data_deprecated,
)
from streetworld.utils.opendrive.parser import parse_opendrive

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError as e:
    raise ModuleNotFoundError(
        "matplotlib is required for visualization. Install it with: pip install matplotlib"
    ) from e

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None


def pose_xy(pose_4x4: list[list[float]]) -> np.ndarray:
    pose = np.asarray(pose_4x4, dtype=np.float64)
    return pose[:2, 3]


def nearest_ts(ts_candidates: list[int], target_ts: int) -> int:
    return min(ts_candidates, key=lambda ts: abs(ts - target_ts))


def _sample_planview_reference_line(plan_view, step_m: float = 1.0) -> np.ndarray:
    length = float(plan_view.length)
    if length <= 0:
        return np.empty((0, 2), dtype=np.float64)
    num_steps = max(2, int(np.ceil(length / step_m)) + 1)
    s_vals = np.linspace(0.0, length, num_steps)
    pts = []
    for s in s_vals:
        xy, _ = plan_view.calc(float(s))
        pts.append(xy)
    return np.asarray(pts, dtype=np.float64)


def load_map_reference_lines(xodr_path: Path, step_m: float = 1.0) -> list[np.ndarray]:
    root = etree.parse(str(xodr_path)).getroot()
    # Some datasets contain non-standard contactPoint values in junction/connection.
    # For top-down reference-line visualization we only need road planView geometry,
    # so normalize invalid values to keep parser from failing.
    for conn in root.findall(".//junction/connection"):
        cp = conn.get("contactPoint")
        if cp not in ("start", "end"):
            conn.set("contactPoint", "start")
    opendrive = parse_opendrive(root)
    lines: list[np.ndarray] = []
    for road in opendrive.roads:
        line = _sample_planview_reference_line(road.planView, step_m=step_m)
        if len(line) > 1:
            lines.append(line)
    return lines


def load_poses_from_yaml(
    yaml_path: Path
) -> tuple[str, dict[int, list[list[float]]], list[int], dict[str, dict], Path | None]:
    try:
        cfg = SimulatorInterface._load_cfg(yaml_path)
        ego_raw = json.loads(Path(cfg["ego_pose_path"]).read_text(encoding="utf-8"))
        ego_poses = {int(ts): np.asarray(pose, dtype=np.float64).reshape(4, 4).tolist() for ts, pose in ego_raw.items()}
        ego_timestamps = sorted(ego_poses.keys())
        traj_raw = json.loads(Path(cfg["trajectory_path"]).read_text(encoding="utf-8"))
        tracking_data = {}
        for obj_id, obj in traj_raw.items():
            if not isinstance(obj, dict) or "local2world" not in obj:
                continue
            tracking_data[str(obj_id)] = {
                "poses": {int(ts): np.asarray(pose, dtype=np.float64).reshape(4, 4).tolist()
                          for ts, pose in obj["local2world"].items()},
                "size": obj.get("size", [4.5, 2.0, 1.5]),
                "type": obj.get("type", "vehicle"),
            }
        map_path = Path(cfg["map_path"]) if "map_path" in cfg else None
        return cfg["scene_name"], ego_poses, ego_timestamps, tracking_data, map_path
    except ValueError:
        pass

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {yaml_path}")
    if "scene_root" not in data or "scene_uuid" not in data:
        raise ValueError(
            "Unsupported YAML format. Need either "
            "(scene_name, scene_root, scene_uuid, ego_pose_path, trajectory_path) "
            "or at least (scene_root, scene_uuid)."
        )

    scene_root = Path(data["scene_root"])
    if not scene_root.is_absolute():
        scene_root = (yaml_path.parent / scene_root).resolve()
    scene_uuid = str(data["scene_uuid"])
    scene_dir = scene_root / scene_uuid
    rig_path = scene_dir / "rig_trajectories.json"
    tracks_path = scene_dir / "sequence_tracks.json"
    if not rig_path.exists() or not tracks_path.exists():
        raise FileNotFoundError(
            f"Expected files not found under scene dir: {scene_dir}. "
            f"Need {rig_path.name} and {tracks_path.name}."
        )

    rig = json.loads(rig_path.read_text(encoding="utf-8"))
    ego_poses, ego_timestamps = parse_ego_poses_deprecated(rig)
    tracks = json.loads(tracks_path.read_text(encoding="utf-8"))
    tracking_data = parse_tracking_data_deprecated(tracks, apply_world_to_nre=False)
    scene_name = str(data.get("scene_name", scene_uuid))
    map_path = scene_dir / "map.xodr"
    return scene_name, ego_poses, ego_timestamps, tracking_data, map_path


def _collect_video_timestamps(
    ego_timestamps: list[int],
    tracking_data: dict[str, dict],
) -> list[int]:
    all_timestamps = set(ego_timestamps)
    for obj in tracking_data.values():
        all_timestamps.update(obj["poses"].keys())
    return sorted(all_timestamps)


def _draw_current_positions(
    ax,
    ego_poses: dict[int, list[list[float]]],
    ego_timestamps: list[int],
    traffic_items: list[tuple[str, dict]],
    timestamp_us: int,
):
    ego_ts = nearest_ts(ego_timestamps, timestamp_us)
    ego_now = pose_xy(ego_poses[ego_ts])
    ego_artist = ax.scatter(ego_now[0], ego_now[1], s=80, c="red", marker="o", label=None, zorder=4)

    traffic_xy = []
    for _, obj in traffic_items:
        poses = obj["poses"]
        ts_list = sorted(poses.keys())
        if not ts_list:
            continue
        cur_ts = nearest_ts(ts_list, timestamp_us)
        traffic_xy.append(pose_xy(poses[cur_ts]))

    traffic_artist = None
    if traffic_xy:
        traffic_xy = np.asarray(traffic_xy, dtype=np.float64)
        traffic_artist = ax.scatter(
            traffic_xy[:, 0],
            traffic_xy[:, 1],
            s=10,
            c="black",
            alpha=0.45,
            zorder=3,
        )
    return ego_artist, traffic_artist, ego_ts


def _save_motion_video(
    scene_name: str,
    fig,
    ax,
    ego_poses: dict[int, list[list[float]]],
    ego_timestamps: list[int],
    traffic_items: list[tuple[str, dict]],
    video_timestamps: list[int],
    out_path: Path,
    fps: float,
) -> None:
    if cv2 is None:
        raise ModuleNotFoundError("opencv-python is required for video export. Install it with: pip install opencv-python")
    if not video_timestamps:
        raise ValueError("No timestamps available for video export")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    writer = cv2.VideoWriter(
        str(out_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        float(fps),
        (int(width), int(height)),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open video writer: {out_path}")

    title_artist = ax.set_title("")
    try:
        for timestamp_us in video_timestamps:
            ego_artist, traffic_artist, ego_ts = _draw_current_positions(
                ax=ax,
                ego_poses=ego_poses,
                ego_timestamps=ego_timestamps,
                traffic_items=traffic_items,
                timestamp_us=timestamp_us,
            )
            title_artist.set_text(f"Top-Down Motion: {scene_name} @ {timestamp_us} us (ego={ego_ts})")

            fig.canvas.draw()
            frame = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8).reshape(height, width, 4)
            writer.write(cv2.cvtColor(frame[:, :, :3], cv2.COLOR_RGB2BGR))

            ego_artist.remove()
            if traffic_artist is not None:
                traffic_artist.remove()
    finally:
        writer.release()
        title_artist.set_text(f"Top-Down Trajectories: {scene_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read scene yaml like SimulatorInterface and visualize ego/traffic top-down trajectories"
    )
    parser.add_argument("yaml_path", type=str, help="Path to scene yaml")
    parser.add_argument("--timestamp", type=int, default=None, help="Optional timestamp(us) to highlight current positions")
    parser.add_argument("--save", type=str, default=None, help="Save figure path. If omitted, show window")
    parser.add_argument("--save-video", type=str, default=None, help="Optional mp4 path for top-down motion video")
    parser.add_argument("--video-fps", type=float, default=50.0, help="FPS for exported top-down motion video")
    parser.add_argument("--max-traffic", type=int, default=None, help="Optional max number of traffic agents to draw")
    parser.add_argument("--map-step", type=float, default=1.0, help="Sampling step(m) for map reference lines")
    args = parser.parse_args()

    scene_name, ego_poses, ego_timestamps, tracking_data, map_path = load_poses_from_yaml(Path(args.yaml_path))

    fig, ax = plt.subplots(figsize=(10, 10))

    if map_path is not None and map_path.exists():
        for i, ref_line in enumerate(load_map_reference_lines(map_path, step_m=args.map_step)):
            label = "map_ref_line" if i == 0 else None
            ax.plot(ref_line[:, 0], ref_line[:, 1], color="yellow", alpha=0.9, linewidth=1.2, label=label)

    ego_xy = np.array([pose_xy(ego_poses[ts]) for ts in ego_timestamps], dtype=np.float64)
    ax.plot(ego_xy[:, 0], ego_xy[:, 1], color="tab:red", linewidth=2.5, label="ego")

    traffic_items = list(tracking_data.items())
    if args.max_traffic is not None:
        traffic_items = traffic_items[: args.max_traffic]

    for obj_id, obj in traffic_items:
        poses = obj["poses"]
        ts_list = sorted(poses.keys())
        if not ts_list:
            continue
        xy = np.array([pose_xy(poses[ts]) for ts in ts_list], dtype=np.float64)
        ax.plot(xy[:, 0], xy[:, 1], color="tab:blue", alpha=0.25, linewidth=1.0)

    if args.timestamp is not None:
        ego_ts = nearest_ts(ego_timestamps, args.timestamp)
        ego_now = pose_xy(ego_poses[ego_ts])
        ax.scatter(ego_now[0], ego_now[1], s=80, c="red", marker="o", label=f"ego@{ego_ts}")

        for _, obj in traffic_items:
            poses = obj["poses"]
            ts_list = sorted(poses.keys())
            if not ts_list:
                continue
            cur_ts = nearest_ts(ts_list, args.timestamp)
            cur_xy = pose_xy(poses[cur_ts])
            ax.scatter(cur_xy[0], cur_xy[1], s=8, c="black", alpha=0.35)

    ax.set_title(f"Top-Down Trajectories: {scene_name}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")

    if args.save_video:
        video_timestamps = _collect_video_timestamps(ego_timestamps, tracking_data)
        _save_motion_video(
            scene_name=scene_name,
            fig=fig,
            ax=ax,
            ego_poses=ego_poses,
            ego_timestamps=ego_timestamps,
            traffic_items=traffic_items,
            video_timestamps=video_timestamps,
            out_path=Path(args.save_video),
            fps=args.video_fps,
        )
        print(f"Saved motion video to: {args.save_video}")

    if args.save:
        out_path = Path(args.save)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_path, dpi=200, bbox_inches="tight")
        print(f"Saved figure to: {out_path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
