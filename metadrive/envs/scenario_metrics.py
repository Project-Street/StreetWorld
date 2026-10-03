from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np


CRASH_REASONS = {
    "crash_vehicle",
    "crash_human",
    "crash_object",
    "crash_world",
}


@dataclass
class ScenarioMetricTracker:
    ttc_threshold: float = 5.0
    accel_threshold: float = 2.0
    yaw_acc_threshold: float = 0.5

    completed_scene_metrics: List[Dict[str, float]] = field(default_factory=list)
    collision: bool = False
    dac_total: int = 0
    dac_hits: int = 0
    ttc_flags: List[float] = field(default_factory=list)
    com_total: int = 0
    com_hits: int = 0
    route_progress: float = 0.0
    route_length: float = 0.0
    route_start_progress: float | None = None
    route_end_progress: float | None = None
    route_start_time: float | None = None
    route_end_time: float | None = None
    warmup_step: int = 0

    def reset(self, warmup_step: int | None = None) -> None:
        self.warmup_step = 0 if warmup_step is None else warmup_step
        self.collision = False
        self.dac_total = 0
        self.dac_hits = 0
        self.ttc_flags = []
        self.com_total = 0
        self.com_hits = 0
        self.route_progress = 0.0
        self.route_length = 0.0
        self.route_start_progress = None
        self.route_end_progress = None
        self.route_start_time = None
        self.route_end_time = None

    def update(self, info: Dict[str, Any], obs: Dict[str, Any], env) -> None:
        if int(info.get("episode_length", 0)) < self.warmup_step:
            return
        self.collision |= info["reason"] in CRASH_REASONS

        states = obs["states"]
        self.dac_total += 1
        if states["current_lane"] is not None:
            self.dac_hits += 1

        ttc = info["ttc"]
        self.ttc_flags.append(1.0 if ttc is None or float(ttc) >= self.ttc_threshold else 0.0)

        acceleration = np.asarray(states["accelerate"], dtype=np.float32).reshape(-1)
        angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32)
        acceleration_norm = float(np.linalg.norm(acceleration[:2]))
        self.com_total += 1
        if acceleration_norm <= self.accel_threshold and abs(float(angular_velocity[2])) <= self.yaw_acc_threshold:
            self.com_hits += 1

        self.route_progress = float(env._last_progress_value)
        self.route_length = float(np.asarray(obs["navigation"]["cummulative_length"], dtype=np.float32)[-1])
        timestamp = float(info["relative_timestamp"]) * 1e-6
        if self.route_start_progress is None:
            self.route_start_progress = self.route_progress
            self.route_start_time = timestamp
        self.route_end_progress = self.route_progress
        self.route_end_time = timestamp

    def finalize(self) -> Dict[str, float]:
        if self.dac_total == 0:
            raise RuntimeError("DAC has no samples.")
        if not self.ttc_flags:
            raise RuntimeError("TTC has no samples.")
        if self.com_total == 0:
            raise RuntimeError("COM has no samples.")
        if self.route_length <= 0.0:
            raise RuntimeError("RC route length must be positive.")
        if (
            self.route_start_progress is None
            or self.route_end_progress is None
            or self.route_start_time is None
            or self.route_end_time is None
        ):
            raise RuntimeError("RE requires route progress and timestamp samples.")
        elapsed = self.route_end_time - self.route_start_time
        if elapsed <= 0.0:
            raise RuntimeError(f"RE requires positive elapsed time, got {elapsed}.")
        remaining_route_length = self.route_length - self.route_start_progress
        if remaining_route_length < 0.0:
            raise RuntimeError(f"RC remaining route length cannot be negative, got {remaining_route_length}.")
        if remaining_route_length == 0.0:
            route_completion = 1.0
        else:
            completed_route_length = self.route_end_progress - self.route_start_progress
            route_completion = float(np.clip(completed_route_length / remaining_route_length, 0.0, 1.0))

        metric = {
            "NC": 0.0 if self.collision else 1.0,
            "DAC": self.dac_hits / self.dac_total,
            "TTC": float(np.mean(self.ttc_flags)),
            "COM": self.com_hits / self.com_total,
            "RC": route_completion,
            "RE": float((self.route_end_progress - self.route_start_progress) / elapsed),
        }
        self.completed_scene_metrics.append(metric)
        return metric

    def get_average_metric(self) -> Dict[str, float]:
        if not self.completed_scene_metrics:
            raise RuntimeError("No completed scene metrics.")
        keys = self.completed_scene_metrics[0].keys()
        return {
            key: float(np.mean([metric[key] for metric in self.completed_scene_metrics]))
            for key in keys
        }
