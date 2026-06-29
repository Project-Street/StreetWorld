from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np


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

    def reset(self) -> None:
        self.collision = False
        self.dac_total = 0
        self.dac_hits = 0
        self.ttc_flags = []
        self.com_total = 0
        self.com_hits = 0
        self.route_progress = 0.0
        self.route_length = 0.0

    def update(self, info: Dict[str, Any], obs: Dict[str, Any], env) -> None:
        self.collision |= bool(info["collision"])

        states = obs["states"]
        self.dac_total += 1
        if states["current_lane"] is not None:
            self.dac_hits += 1

        ttc = info["ttc"]
        self.ttc_flags.append(1.0 if ttc is None or float(ttc) >= self.ttc_threshold else 0.0)

        angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32)
        self.com_total += 1
        if float(states["accelerate"]) <= self.accel_threshold and abs(float(angular_velocity[2])) <= self.yaw_acc_threshold:
            self.com_hits += 1

        self.route_progress = float(env._last_progress_value)
        self.route_length = float(np.asarray(obs["navigation"]["cummulative_length"], dtype=np.float32)[-1])

    def finalize(self) -> Dict[str, float]:
        if self.dac_total == 0:
            raise RuntimeError("DAC has no samples.")
        if not self.ttc_flags:
            raise RuntimeError("TTC has no samples.")
        if self.com_total == 0:
            raise RuntimeError("COM has no samples.")
        if self.route_length <= 0.0:
            raise RuntimeError("RC route length must be positive.")

        metric = {
            "NC": 0.0 if self.collision else 1.0,
            "DAC": self.dac_hits / self.dac_total,
            "TTC": float(np.mean(self.ttc_flags)),
            "COM": self.com_hits / self.com_total,
            "RC": float(np.clip(self.route_progress / self.route_length, 0.0, 1.0)),
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
