from __future__ import annotations

import math
from typing import Tuple

import numpy as np

import numpy as np

def nearest_front_index(path, xy, heading_vec):
    rel = path - xy[None, :]
    dot = rel @ heading_vec
    mask = dot >= 0.0
    d2 = np.sum(rel[mask] ** 2, axis=1)
    if not np.any(mask):
        return int(path.shape[0])
    idx_in_mask = int(np.argmin(d2))
    return int(np.arange(len(path))[mask][idx_in_mask])

def _first_index_by_arclen(cumlen: np.ndarray, i0: int, ahead_len: float) -> int:
    target = float(cumlen[i0]) + max(0.0, float(ahead_len))
    idx = np.searchsorted(cumlen, target, side="right")
    return int(idx)


def _build_cumlen(path_xy: np.ndarray) -> np.ndarray:
    seg = np.linalg.norm(path_xy[1:] - path_xy[:-1], axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)])


def _wrapped_angle_diff(a: float, b: float) -> float:
    d = a - b
    while d > math.pi:
        d -= 2.0 * math.pi
    while d < -math.pi:
        d += 2.0 * math.pi
    return d


def turn_signal_from_path(
    path_xy: np.ndarray,
    ego_xy: np.ndarray,
    heading_vec: np.ndarray,
    early_signal_distance: float = 10.0,
    turn_inradius_threshold: float = 15.0,
) -> int:
    """Mirror NavigationObservation._get_turn_signal logic.

    Returns: -1 (right), 0 (straight), 1 (left).
    """
    if path_xy is None or len(path_xy) < 5:
        return 0

    path_xy = np.asarray(path_xy, dtype=np.float32)
    ego_xy = np.asarray(ego_xy, dtype=np.float32)
    heading_vec = np.asarray(heading_vec, dtype=np.float32)

    path_cumlen = _build_cumlen(path_xy)
    i0 = nearest_front_index(path_xy, ego_xy, heading_vec)
    if i0 >= len(path_xy):
        return 0

    j = _first_index_by_arclen(path_cumlen, i0, early_signal_distance)
    if j == len(path_cumlen) or j == 0:
        return 0

    n_pts = len(path_xy)
    k_start = max(i0 + 1, 1)
    k_end = min(j - 1, n_pts - 2)
    if k_start > k_end:
        return 0

    idx = np.arange(k_start, k_end + 1, dtype=np.int32)
    p0 = path_xy[idx - 1]
    p1 = path_xy[idx]
    p2 = path_xy[idx + 1]

    v01 = p1 - p0
    v12 = p2 - p1
    v02 = p2 - p0

    len01 = np.linalg.norm(v01, axis=1)
    len12 = np.linalg.norm(v12, axis=1)
    len02 = np.linalg.norm(v02, axis=1)
    cross = v01[:, 0] * v12[:, 1] - v01[:, 1] * v12[:, 0]
    area2 = np.abs(cross)

    eps = 1e-10
    valid = (len01 >= eps) & (len12 >= eps) & (len02 >= eps)
    radius = np.full_like(len01, np.inf, dtype=np.float32)
    radius[valid] = (len01[valid] * len12[valid] * len02[valid]) / (2.0 * area2[valid] + eps)
    meets = valid & (radius <= float(turn_inradius_threshold))

    c = np.sign(cross * meets.astype(np.float32))
    if len(c) < 5:
        return 0

    for i in range(0, len(c) - 4):
        s = np.sum(c[i : i + 5])
        if s == 5:
            return 1
        if s == -5:
            return -1
    return 0


def turn_signal_to_command(turn_signal: int) -> int:
    sign = int(np.sign(float(turn_signal)))
    mapping = {-1: 0, 0: 2, 1: 1}
    return mapping[sign]


def derive_command_from_pose(
    path_xy: np.ndarray,
    ego_xy: np.ndarray,
    ego_yaw: float,
    early_signal_distance: float = 10.0,
    turn_inradius_threshold: float = 15.0,
) -> Tuple[int, int]:
    heading = np.array([math.cos(ego_yaw), math.sin(ego_yaw)], dtype=np.float32)
    turn_signal = turn_signal_from_path(
        path_xy=path_xy,
        ego_xy=ego_xy,
        heading_vec=heading,
        early_signal_distance=early_signal_distance,
        turn_inradius_threshold=turn_inradius_threshold,
    )
    return turn_signal, turn_signal_to_command(turn_signal)


__all__ = [
    "derive_command_from_pose",
    "turn_signal_from_path",
    "turn_signal_to_command",
]
