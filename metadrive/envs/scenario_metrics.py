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
        episode_length = env.episode_lengths
        if episode_length < self.warmup_step:
            return

        self.route_progress = env._last_progress_value
        self.route_length = obs["navigation"]["cummulative_length"][-1]
        timestamp = info["relative_timestamp"] * 1e-6
        if episode_length == self.warmup_step:
            # The handoff frame anchors RC/RE but is not a model-controlled sample.
            self.route_start_progress = self.route_progress
            self.route_start_time = timestamp
            return

        self.collision |= info["reason"] in CRASH_REASONS

        states = obs["states"]
        self.dac_total += 1
        if states["current_lane"] is not None:
            self.dac_hits += 1

        ttc = info["ttc"]
        self.ttc_flags.append(1.0 if ttc is None or ttc >= self.ttc_threshold else 0.0)

        acceleration_norm = np.linalg.norm(states["accelerate"][:2])
        self.com_total += 1
        if acceleration_norm <= self.accel_threshold and abs(states["angular_velocity"][2]) <= self.yaw_acc_threshold:
            self.com_hits += 1

        self.route_end_progress = self.route_progress
        self.route_end_time = timestamp

    def finalize(self) -> Dict[str, float]:
        completed_route_length = self.route_end_progress - self.route_start_progress
        remaining_route_length = self.route_length - self.route_start_progress
        elapsed = self.route_end_time - self.route_start_time

        with np.errstate(divide="raise", invalid="raise"):
            metric = {
                "NC": 0.0 if self.collision else 1.0,
                "DAC": self.dac_hits / self.dac_total,
                "TTC": np.mean(self.ttc_flags),
                "COM": self.com_hits / self.com_total,
                "RC": np.clip(completed_route_length / remaining_route_length, 0.0, 1.0),
                "RE": completed_route_length / elapsed,
            }
        self.completed_scene_metrics.append(metric)
        return metric

    def get_average_metric(self) -> Dict[str, float]:
        keys = self.completed_scene_metrics[0].keys()
        return {
            key: np.mean([metric[key] for metric in self.completed_scene_metrics])
            for key in keys
        }
