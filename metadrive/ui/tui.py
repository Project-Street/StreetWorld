from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from metadrive.envs.scenario_metrics import ScenarioMetricTracker


@dataclass
class RuntimeSnapshot:
    status: str = "initializing"
    scene: str | None = None
    queue: tuple[str, ...] = ()
    completed: int = 0
    timestamp_us: int | None = None
    speed_mps: float | None = None
    steering: float | None = None
    throttle: float | None = None
    brake: float | None = None
    termination_reason: str | None = None
    scene_metrics: Mapping[str, float] | None = None
    aggregate_metrics: Mapping[str, float] | None = None
    message: str | None = None


class TUI:
    def __init__(self, scene_ids: Sequence[str]) -> None:
        self._lock = threading.Lock()
        self._snapshot = RuntimeSnapshot(queue=tuple(scene_ids))
        self._live = None

    def start(self) -> None:
        if self._live is not None:
            raise RuntimeError("TUI is already started.")

        from rich.console import Console
        from rich.live import Live

        from metadrive.examples.easydrive_tui import build_runtime_renderable

        tui_live = Live(
            get_renderable=lambda: build_runtime_renderable(self.snapshot()),
            console=Console(file=sys.__stdout__),
            screen=True,
            refresh_per_second=8,
            vertical_overflow="crop",
        )
        with self._lock:
            self._snapshot.status = "waiting"
        tui_live.start()
        self._live = tui_live

    def begin_reset(self) -> None:
        with self._lock:
            snapshot = self._snapshot
            snapshot.status = "reset"
            snapshot.timestamp_us = snapshot.speed_mps = snapshot.steering = snapshot.throttle = snapshot.brake = None
            snapshot.termination_reason = snapshot.scene_metrics = snapshot.message = None

    def finish_evaluation(self) -> None:
        with self._lock:
            self._snapshot.status = "finished"
            self._snapshot.message = "No more scenarios"

    def record_reset(self, info: Mapping[str, Any], states: Mapping[str, Any]) -> None:
        with self._lock:
            snapshot = self._snapshot
            snapshot.scene = str(info.get("scene_name") or snapshot.queue[0])
            snapshot.queue = snapshot.queue[1:]
            snapshot.timestamp_us = info["relative_timestamp"]
            snapshot.speed_mps = states["ego_velo"]

    def record_step(
        self,
        info: Mapping[str, Any],
        payload: Mapping[str, Any],
        terminated: bool,
        truncated: bool,
    ) -> None:
        with self._lock:
            snapshot = self._snapshot
            longitudinal = float(payload["throttle_brake"])
            snapshot.status = "finished" if terminated or truncated else "running"
            snapshot.timestamp_us = int(payload["timestamp"])
            snapshot.speed_mps = float(payload["speed"])
            snapshot.steering = float(payload["steering"])
            snapshot.throttle = max(longitudinal, 0.0)
            snapshot.brake = max(-longitudinal, 0.0)
            if terminated or truncated:
                reason = info.get("reason")
                snapshot.termination_reason = str(getattr(reason, "name", reason)) if reason is not None else (
                    "truncated" if truncated else "terminated"
                )
                snapshot.completed += 1

    def complete_episode(self, metric_tracker: ScenarioMetricTracker) -> None:
        completed_metrics = metric_tracker.completed_scene_metrics
        if not completed_metrics:
            return
        with self._lock:
            self._snapshot.scene_metrics = dict(completed_metrics[-1])
            self._snapshot.aggregate_metrics = metric_tracker.get_average_metric()

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            snapshot = self._snapshot
            return replace(
                snapshot,
                scene_metrics=dict(snapshot.scene_metrics) if snapshot.scene_metrics is not None else None,
                aggregate_metrics=dict(snapshot.aggregate_metrics) if snapshot.aggregate_metrics is not None else None,
            )

    def close(self) -> None:
        with self._lock:
            self._snapshot.status = "finished"
        tui_live = self._live
        self._live = None
        if tui_live is not None:
            tui_live.stop()
