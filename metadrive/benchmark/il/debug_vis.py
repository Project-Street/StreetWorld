from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np


_UNIAD_BEV_RECORDER: Optional[Any] = None
_VAD_BEV_RECORDER: Optional[Any] = None


def _to_numpy(value: Any) -> Optional[np.ndarray]:
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        return value
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        return value.numpy()
    try:
        return np.asarray(value)
    except Exception:
        return None


def _latest_rgb(img: np.ndarray) -> np.ndarray:
    arr = np.asarray(img)
    if arr.ndim == 4:
        arr = arr[-1]
    if arr.ndim != 3:
        raise ValueError(f"Expected image with 3 dims, got shape {arr.shape}")
    return arr.astype(np.uint8)


def _lidar_to_cam_points(plan_traj: np.ndarray, cam_params: dict, z_pos: float = -4.0) -> Optional[np.ndarray]:
    if plan_traj is None or len(plan_traj) == 0:
        return None

    pts_xy = np.asarray(plan_traj, dtype=np.float32)
    if pts_xy.ndim != 2 or pts_xy.shape[1] < 2:
        return None

    ego2camera = np.asarray(cam_params.get("ego2camera"), dtype=np.float32)
    k = np.asarray(cam_params.get("K"), dtype=np.float32)
    if ego2camera.shape != (4, 4) or k.shape != (3, 3):
        return None

    lidar_to_ego = np.array(
        [
            [0.0, 1.0, 0.0, 0.5],
            [-1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 1.5],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    l2c = ego2camera @ lidar_to_ego

    ones = np.ones((pts_xy.shape[0], 1), dtype=np.float32)
    pts_lidar = np.concatenate([pts_xy[:, :2], np.full((pts_xy.shape[0], 1), z_pos, dtype=np.float32), ones], axis=1)
    cam_pts = (l2c @ pts_lidar.T).T
    depth = cam_pts[:, 2]
    valid = depth > 1e-5
    if not np.any(valid):
        return None

    cam_valid = cam_pts[valid, :3]
    proj = (k @ cam_valid.T).T
    u = proj[:, 0] / cam_valid[:, 2]
    v = proj[:, 1] / cam_valid[:, 2]
    return np.stack([u, v], axis=1)


def _draw_plan_on_camera(img: np.ndarray, plan_traj: np.ndarray, cam_params: dict) -> np.ndarray:
    out = img.copy()
    pts = _lidar_to_cam_points(plan_traj, cam_params)
    if pts is None or len(pts) < 2:
        return out

    h, w = out.shape[:2]
    inb = (pts[:, 0] >= 0) & (pts[:, 0] < w) & (pts[:, 1] >= 0) & (pts[:, 1] < h)
    pts = pts[inb]
    if len(pts) < 2:
        return out
    pts_int = np.round(pts).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(out, [pts_int], isClosed=False, color=(0, 255, 0), thickness=2)
    return out


def _draw_bev(plan_traj: np.ndarray, size: int = 800, meter_range: float = 40.0) -> np.ndarray:
    img = np.zeros((size, size, 3), dtype=np.uint8)
    center = size // 2

    for r in (10, 20, 30, 40):
        px = int(r / meter_range * (size / 2))
        cv2.circle(img, (center, center), px, (40, 40, 40), 1)

    cv2.line(img, (center, 0), (center, size - 1), (60, 60, 60), 1)
    cv2.line(img, (0, center), (size - 1, center), (60, 60, 60), 1)

    if plan_traj is not None and len(plan_traj) > 0:
        pts = np.asarray(plan_traj, dtype=np.float32)
        # Lidar frame: x right, y forward -> image: +x right, +y up
        x = pts[:, 0]
        y = pts[:, 1]
        u = center + (x / meter_range) * (size / 2)
        v = center - (y / meter_range) * (size / 2)
        poly = np.stack([u, v], axis=1)
        inb = (poly[:, 0] >= 0) & (poly[:, 0] < size) & (poly[:, 1] >= 0) & (poly[:, 1] < size)
        poly = poly[inb]
        if len(poly) >= 2:
            cv2.polylines(img, [np.round(poly).astype(np.int32)], isClosed=False, color=(0, 255, 0), thickness=2)

    cv2.circle(img, (center, center), 5, (0, 0, 255), -1)
    return img


def _render_bev_with_recorder(
    model_type: str,
    bev_render_mode: str,
    plan_traj: np.ndarray,
    uniad_output: Optional[Dict[str, Any]],
    vad_output: Optional[Dict[str, Any]],
    out_h: int = 800,
    out_w: int = 800,
) -> np.ndarray:
    global _UNIAD_BEV_RECORDER, _VAD_BEV_RECORDER

    mode = str(bev_render_mode).strip().lower()
    if mode not in {"none", "traj", "output"}:
        mode = "traj"

    if mode == "none":
        return np.zeros((out_h, out_w, 3), dtype=np.uint8)

    if model_type == "uniad":
        from metadrive.benchmark.visualize_utils_uniad import UniADGaussianFrameRecorder

        if _UNIAD_BEV_RECORDER is None or _UNIAD_BEV_RECORDER.bev_render_mode != mode:
            _UNIAD_BEV_RECORDER = UniADGaussianFrameRecorder(
                output_path="/tmp/il_debug_uniad.mp4",
                fps=1,
                enable_bev=True,
                bev_render_mode=mode,
            )
        payload = _UNIAD_BEV_RECORDER._build_bev_payload(plan_traj, uniad_output)
        return _UNIAD_BEV_RECORDER._render_bev(payload, out_h=out_h, out_w=out_w)

    from metadrive.benchmark.visualize_utils_vad import VADGaussianFrameRecorder

    if _VAD_BEV_RECORDER is None or _VAD_BEV_RECORDER.bev_render_mode != mode:
        _VAD_BEV_RECORDER = VADGaussianFrameRecorder(
            output_path="/tmp/il_debug_vad.mp4",
            fps=1,
            enable_bev=True,
            bev_render_mode=mode,
        )
    payload = _VAD_BEV_RECORDER._build_bev_payload(plan_traj, vad_output)
    return _VAD_BEV_RECORDER._render_bev(payload, out_h=out_h, out_w=out_w)


def save_debug_visuals(
    sample: dict,
    pred_traj: np.ndarray,
    out_dir: Path,
    step: int,
    model_type: str,
    bev_render_mode: str,
    uniad_output: Optional[Dict[str, Any]] = None,
    vad_output: Optional[Dict[str, Any]] = None,
    prefix: str = "train",
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    obs = sample["obs"]
    info = sample["info"]
    cam_params = info.get("cam_params", {})

    for cam_name, cam_img in obs.items():
        try:
            img = _latest_rgb(cam_img)
        except Exception:
            continue
        cp = cam_params.get(cam_name, None)
        if cp is not None:
            img = _draw_plan_on_camera(img, pred_traj, cp)
        cv2.imwrite(str(out_dir / f"{prefix}_step_{step:06d}_{cam_name}.jpg"), img[:, :, ::-1])

    try:
        if model_type == "vad" and bev_render_mode == "output" and vad_output is None:
            bev_render_mode = "traj"
        bev = _render_bev_with_recorder(
            model_type=model_type,
            bev_render_mode=bev_render_mode,
            plan_traj=pred_traj,
            uniad_output=uniad_output,
            vad_output=vad_output,
            out_h=800,
            out_w=800,
        )
    except Exception:
        bev = _draw_bev(pred_traj)
    cv2.imwrite(str(out_dir / f"{prefix}_step_{step:06d}_bev.jpg"), bev)
