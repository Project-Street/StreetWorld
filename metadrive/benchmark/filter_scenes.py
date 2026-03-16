#!/usr/bin/env python3
"""
Scan scene configs and flag scenes with sudden ego motion.
"""

import argparse
import json
import os
from glob import glob

import numpy as np
import yaml


AXES_TRANSFORMATION = np.array([
    [0, 0, 1, 0],
    [-1, 0, 0, 0],
    [0, -1, 0, 0],
    [0, 0, 0, 1],
])


def load_c2w_data(c2w_path):
    if c2w_path.endswith(".json"):
        with open(c2w_path, "r") as f:
            c2w_data = json.load(f)
    else:
        c2w_data = np.load(c2w_path, allow_pickle=True).item()
    return c2w_data


def iter_c2w_frames(c2w_data):
    if isinstance(c2w_data, dict):
        keys = list(c2w_data.keys())
        if all(isinstance(k, str) and k.isdigit() for k in keys):
            keys = sorted(keys, key=lambda x: int(x))
        else:
            keys = sorted(keys)
        for key in keys:
            yield key, c2w_data[key]
    elif isinstance(c2w_data, list):
        for idx, entry in enumerate(c2w_data):
            yield idx, entry
    else:
        raise ValueError("Unsupported c2w data type")


def extract_positions(c2w_data):
    positions = []
    for _, entry in iter_c2w_frames(c2w_data):
        if isinstance(entry, dict) and "e2w" in entry:
            c2w = np.array(entry["e2w"], dtype=np.float32)
        else:
            c2w = np.array(entry, dtype=np.float32)
        c2w = AXES_TRANSFORMATION @ c2w
        pos = c2w[:3, 3]
        positions.append(pos)
    if not positions:
        raise ValueError("No frames found in c2w data")
    return np.vstack(positions)


def analyze_motion(positions, dt_s, max_speed, max_delta_v, max_accel, max_step):
    deltas = positions[1:] - positions[:-1]
    step_dist = np.linalg.norm(deltas, axis=1)
    speed = step_dist / dt_s
    if len(speed) == 0:
        return {
            "max_speed": 0.0,
            "max_delta_v": 0.0,
            "max_accel": 0.0,
            "max_step": 0.0,
            "bad": False,
            "reason": "",
        }

    velocities = deltas / dt_s
    delta_v = np.linalg.norm(velocities[1:] - velocities[:-1], axis=1) if len(velocities) > 1 else np.array([0.0])
    accel = delta_v / dt_s

    max_speed_val = float(np.max(speed))
    max_delta_v_val = float(np.max(delta_v))
    max_accel_val = float(np.max(accel))
    max_step_val = float(np.max(step_dist))

    if max_speed is not None and max_speed_val > max_speed:
        return {
            "max_speed": max_speed_val,
            "max_delta_v": max_delta_v_val,
            "max_accel": max_accel_val,
            "max_step": max_step_val,
            "bad": True,
            "reason": f"max_speed {max_speed_val:.3f} > {max_speed}",
        }
    if max_step is not None and max_step_val > max_step:
        return {
            "max_speed": max_speed_val,
            "max_delta_v": max_delta_v_val,
            "max_accel": max_accel_val,
            "max_step": max_step_val,
            "bad": True,
            "reason": f"max_step {max_step_val:.3f} > {max_step}",
        }
    if max_delta_v is not None and max_delta_v_val > max_delta_v:
        return {
            "max_speed": max_speed_val,
            "max_delta_v": max_delta_v_val,
            "max_accel": max_accel_val,
            "max_step": max_step_val,
            "bad": True,
            "reason": f"max_delta_v {max_delta_v_val:.3f} > {max_delta_v}",
        }
    if max_accel is not None and max_accel_val > max_accel:
        return {
            "max_speed": max_speed_val,
            "max_delta_v": max_delta_v_val,
            "max_accel": max_accel_val,
            "max_step": max_step_val,
            "bad": True,
            "reason": f"max_accel {max_accel_val:.3f} > {max_accel}",
        }

    return {
        "max_speed": max_speed_val,
        "max_delta_v": max_delta_v_val,
        "max_accel": max_accel_val,
        "max_step": max_step_val,
        "bad": False,
        "reason": "",
    }


def main():
    parser = argparse.ArgumentParser(description="Filter erroneous scenes by ego motion.")
    parser.add_argument(
        "--scene-config-dir",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "scene_configs"),
        help="Directory containing scene config YAML files",
    )
    parser.add_argument("--pattern", default="*.yaml", help="Glob pattern for scene configs")
    parser.add_argument("--dt-us", type=int, default=100_000, help="Timestamp interval in microseconds")
    parser.add_argument("--max-speed", type=float, default=None, help="Max speed (m/s) threshold")
    parser.add_argument("--max-delta-v", type=float, default=8.0, help="Max speed change between frames (m/s)")
    parser.add_argument("--max-accel", type=float, default=None, help="Max acceleration (m/s^2)")
    parser.add_argument("--max-step", type=float, default=None, help="Max position step (m) between frames")
    parser.add_argument("--output", default=None, help="Optional JSON output path for bad scenes")
    args = parser.parse_args()

    scene_config_dir = os.path.abspath(args.scene_config_dir)
    config_paths = sorted(glob(os.path.join(scene_config_dir, args.pattern)))
    if not config_paths:
        raise FileNotFoundError(f"No config files found in {scene_config_dir}")

    dt_s = args.dt_us / 1_000_000.0
    bad_scenes = {}

    for cfg_path in config_paths:
        try:
            with open(cfg_path, "r") as f:
                cfg = yaml.safe_load(f)
            scene_name = cfg.get("scene_name", os.path.basename(cfg_path))
            c2w_path = cfg["c2w_path"]
            if not os.path.exists(c2w_path):
                bad_scenes[scene_name] = {
                    "config": cfg_path,
                    "reason": f"c2w_path not found: {c2w_path}",
                }
                continue
            c2w_data = load_c2w_data(c2w_path)
            positions = extract_positions(c2w_data)
            report = analyze_motion(
                positions=positions,
                dt_s=dt_s,
                max_speed=args.max_speed,
                max_delta_v=args.max_delta_v,
                max_accel=args.max_accel,
                max_step=args.max_step,
            )
            if report["bad"]:
                bad_scenes[scene_name] = {
                    "config": cfg_path,
                    "reason": report["reason"],
                    "max_speed": report["max_speed"],
                    "max_delta_v": report["max_delta_v"],
                    "max_accel": report["max_accel"],
                    "max_step": report["max_step"],
                }
        except Exception as exc:
            bad_scenes[os.path.basename(cfg_path)] = {
                "config": cfg_path,
                "reason": f"exception: {exc}",
            }

    total = len(config_paths)
    bad = len(bad_scenes)
    print(f"Scanned {total} configs; flagged {bad} scenes as bad.")
    for scene_name, info in bad_scenes.items():
        print(f"BAD {scene_name}: {info['reason']}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(bad_scenes, f, indent=2)
        print(f"Wrote bad scene report to {args.output}")


if __name__ == "__main__":
    main()
