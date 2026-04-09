from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

import numpy as np
import torch
from PIL import Image

from .scene_io import SceneData


def _camera_c2w(ego_pose_c2w: np.ndarray, ego2camera: np.ndarray) -> np.ndarray:
    return ego_pose_c2w @ np.linalg.inv(ego2camera)


def _all_cached_images_exist(scene: SceneData) -> tuple[bool, int]:
    total = 0
    for ts in scene.timestamps_us:
        frame_dir = scene.cache_scene_dir / f"{ts:09d}"
        for cam_name in scene.camera_params.keys():
            total += 1
            if not (frame_dir / f"{cam_name}.jpg").exists():
                return False, total
    return True, total


def ensure_scene_cache(scene: SceneData, force: bool = False) -> Dict[str, float]:
    """Render NuScenes camera images once into cache.

    Cache root policy follows user requirement:
    if tracking is at <xxx>/tracking.json, cache is <xxx>/cache.
    """
    start = time.time()

    if not force:
        complete, total = _all_cached_images_exist(scene)
        if complete:
            elapsed = time.time() - start
            return {
                "rendered": 0.0,
                "skipped": float(total),
                "total": float(total),
                "cache_hit_ratio": 1.0,
                "elapsed_sec": float(elapsed),
            }
    try:
        from metadrive.benchmark.sim_interface import SharpVideoSimulatorInterface
    except ImportError:
        print("SharpVideoSimulatorInterface not found. Please install the benchmark dependencies to use render cache.")
    
    sim = SharpVideoSimulatorInterface()
    cfg_text = scene.cfg_text
    camera_params = scene.camera_params
    ego_poses = scene.ego_poses
    sim.load_model(cfg_text)

    scene.cache_root.mkdir(parents=True, exist_ok=True)
    scene_cache = scene.cache_scene_dir
    scene_cache.mkdir(parents=True, exist_ok=True)

    rendered = 0
    skipped = 0
    for ts in scene.timestamps_us:
        frame_dir = scene_cache / f"{ts:09d}"
        frame_dir.mkdir(parents=True, exist_ok=True)

        ego_pose = ego_poses[int(ts)]
        frame_meta = {
            "timestamp_us": int(ts),
            "scene_name": scene.scene_name,
            "cameras": {},
        }

        for cam_name, cam in camera_params.items():
            image_path = frame_dir / f"{cam_name}.jpg"
            if image_path.exists() and not force:
                skipped += 1
            else:
                c2w_cam = _camera_c2w(ego_pose, np.asarray(cam["ego2camera"], dtype=np.float32))
                rendered_img = sim.render(
                    K=torch.tensor(cam["K"], dtype=torch.float32),
                    H=int(cam["H"]),
                    W=int(cam["W"]),
                    extrinsics=torch.tensor(c2w_cam, dtype=torch.float32),
                    timestamp_us=int(ts),
                    meta=cam.get("meta", {}),
                )
                if isinstance(rendered_img, dict):
                    rendered_img = rendered_img["rgb"]
                Image.fromarray(np.asarray(rendered_img, dtype=np.uint8)).save(image_path)
                rendered += 1

            frame_meta["cameras"][cam_name] = {
                "path": str(image_path),
                "K": np.asarray(cam["K"], dtype=np.float32).tolist(),
                "ego2camera": np.asarray(cam["ego2camera"], dtype=np.float32).tolist(),
                "H": int(cam["H"]),
                "W": int(cam["W"]),
            }

        frame_meta_path = frame_dir / "meta.json"
        with frame_meta_path.open("w", encoding="utf-8") as f:
            json.dump(frame_meta, f)

    elapsed = time.time() - start
    total = rendered + skipped
    return {
        "rendered": float(rendered),
        "skipped": float(skipped),
        "total": float(total),
        "cache_hit_ratio": float(skipped / max(1, total)),
        "elapsed_sec": float(elapsed),
    }
