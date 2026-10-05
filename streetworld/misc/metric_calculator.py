from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
from scipy.spatial.transform import Rotation


CRASH_REASONS = {
    "crash_vehicle",
    "crash_human",
    "crash_object",
    "crash_world",
}


@dataclass
class MetricCalculator:
    ttc_threshold: float = 5.0
    accel_threshold: float = 2.0
    yaw_acc_threshold: float = 0.5

    completed_scene_metrics: List[Dict[str, float]] = field(default_factory=list)
    collision: bool = False
    eval_steps: int = 0
    dac_hits: int = 0
    ttc_flags: List[float] = field(default_factory=list)
    com_hits: int = 0
    route_progress: float = 0.0
    route_length: float = 0.0
    route_start_progress: float | None = None
    route_end_progress: float | None = None
    route_start_time: float | None = None
    route_end_time: float | None = None
    warmup_step: int = 0
    _route_index: int | None = field(default=None, init=False)

    def reset(self, warmup_step: int | None = None) -> None:
        self.warmup_step = 0 if warmup_step is None else warmup_step
        self.collision = False
        self.eval_steps = 0
        self.dac_hits = 0
        self.ttc_flags = []
        self.com_hits = 0
        self.route_progress = 0.0
        self.route_length = 0.0
        self.route_start_progress = None
        self.route_end_progress = None
        self.route_start_time = None
        self.route_end_time = None
        self._route_index = None

    def update(self, obs: dict, info: dict) -> None:
        """Calculate metrics from observations and episode metadata."""
        states = obs["states"]
        navigation = obs["navigation"]
        episode_length = info["episode_length"]
        self.route_progress = self._compute_route_progress(
            states["ego_pos"][:2], navigation["waypoint"], navigation["cummulative_length"]
        )
        self.route_length = navigation["cummulative_length"][-1]
        if episode_length < self.warmup_step:
            return
        timestamp = info["relative_timestamp"] * 1e-6
        if episode_length == self.warmup_step:
            # The handoff frame anchors RC/RE but is not a model-controlled sample.
            self.route_start_progress = self.route_progress
            self.route_end_progress = self.route_progress
            self.route_start_time = timestamp
            self.route_end_time = timestamp
            return

        self.collision |= info["reason"] in CRASH_REASONS

        self.eval_steps += 1
        if states["current_lane"] is not None:
            self.dac_hits += 1

        ttc = self._compute_min_ttc(obs)
        self.ttc_flags.append(1.0 if ttc is None or ttc >= self.ttc_threshold else 0.0)

        acceleration_norm = np.linalg.norm(states["accelerate"][:2])
        yaw_rate = states["angular_velocity"][2]
        if acceleration_norm <= self.accel_threshold and abs(yaw_rate) <= self.yaw_acc_threshold:
            self.com_hits += 1

        self.route_end_progress = self.route_progress
        self.route_end_time = timestamp

    def _compute_route_progress(self, position, path_xy, cumulative_length):
        points = np.asarray(path_xy, dtype=np.float32)
        position = np.asarray(position, dtype=np.float32)
        if len(points) < 2:
            raise ValueError("Navigation route must contain at least two points.")
        if len(cumulative_length) != len(points):
            raise ValueError("Navigation route and cumulative lengths must have equal lengths.")
        start = 0 if self._route_index is None else max(0, self._route_index - 5)
        end = len(points) - 1 if self._route_index is None else min(len(points) - 1, self._route_index + 50)
        indices = np.arange(start, end)
        segments = points[indices + 1] - points[indices]
        lengths = np.linalg.norm(segments, axis=1)
        valid = lengths >= 1e-6
        if not valid.any():
            raise ValueError("Navigation route has no nonzero-length segment.")
        indices, segments, lengths = indices[valid], segments[valid], lengths[valid]
        offsets = position - points[indices]
        fractions = np.clip(np.sum(offsets * segments, axis=1) / lengths**2, 0.0, 1.0)
        projections = points[indices] + fractions[:, None] * segments
        closest = np.argmin(np.linalg.norm(projections - position, axis=1))
        self._route_index = int(indices[closest])
        return float(cumulative_length[self._route_index] + fractions[closest] * lengths[closest])

    @staticmethod
    def _compute_min_ttc(obs):
        states = obs["states"]
        world_to_ego = Rotation.from_euler("XYZ", states["ego_rot"]).as_matrix().T
        ego_velocity = (world_to_ego @ states["linear_velocity"])[:2]
        minimum = None
        # Surrounding observations use the actor's coordinate frame.
        for obj in obs["surrounding"].values():
            relative_position = np.asarray(obj["position"])[:2]
            relative_velocity = np.asarray(obj["velocity"])[:2] - ego_velocity
            distance = float(np.linalg.norm(relative_position))
            if distance < 1e-3:
                return 0.0
            closing_speed = -float(np.dot(relative_velocity, relative_position / distance))
            if closing_speed > 1e-3:
                ttc = distance / closing_speed
                minimum = ttc if minimum is None else min(minimum, ttc)
        return minimum

    def finalize(self) -> Dict[str, float]:
        if self.eval_steps == 0:
            metric = {
                "NC": 0.0 if self.collision else 1.0,
                "DAC": np.nan,
                "TTC": np.nan,
                "COM": np.nan,
                "RC": 0.0,
                "RE": np.nan,
            }
        else:
            completed_route_length = self.route_end_progress - self.route_start_progress
            remaining_route_length = self.route_length - self.route_start_progress
            elapsed = self.route_end_time - self.route_start_time

            with np.errstate(divide="raise", invalid="raise"):
                metric = {
                    "NC": 0.0 if self.collision else 1.0,
                    "DAC": self.dac_hits / self.eval_steps,
                    "TTC": np.mean(self.ttc_flags),
                    "COM": self.com_hits / self.eval_steps,
                    "RC": np.clip(completed_route_length / remaining_route_length, 0.0, 1.0),
                    "RE": completed_route_length / elapsed,
                }
        self.completed_scene_metrics.append(metric)
        return metric

    def get_average_metric(self) -> Dict[str, float]:
        keys = self.completed_scene_metrics[0].keys()
        average = {}
        for key in keys:
            values = [metric[key] for metric in self.completed_scene_metrics if not np.isnan(metric[key])]
            average[key] = np.mean(values) if values else np.nan
        return average
