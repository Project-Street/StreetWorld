"""Runtime state, rendering, and live display for the terminal interface."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from streetworld.ui.tui_style import (
    MUTED_TEXT_STYLE,
    PANEL_BORDER_STYLE,
    PANEL_TEXT_STYLE,
    SUCCESS_TEXT_STYLE,
    VEHICLE_ASCII,
)

if TYPE_CHECKING:
    from streetworld.misc.metric_calculator import MetricCalculator


YAML_SUFFIXES = {".yaml", ".yml"}
LOADING_SPINNER = Spinner("dots", style=PANEL_TEXT_STYLE)


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

    def complete_episode(self, metric_calculator: MetricCalculator) -> None:
        completed_metrics = metric_calculator.completed_scene_metrics
        if not completed_metrics:
            return
        with self._lock:
            self._snapshot.scene_metrics = dict(completed_metrics[-1])
            self._snapshot.aggregate_metrics = metric_calculator.get_average_metric()

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


def build_runtime_renderable(snapshot: RuntimeSnapshot):
    if snapshot.status == "initializing":
        LOADING_SPINNER.update(text=Text("INITIALIZING", style=PANEL_TEXT_STYLE))
        header = LOADING_SPINNER
    elif snapshot.status == "reset":
        LOADING_SPINNER.update(text=Text(f"RESETTING {_scene_label(snapshot.scene)}", style=PANEL_TEXT_STYLE))
        header = LOADING_SPINNER
    elif snapshot.status == "waiting":
        header = Text("WAITING", style=PANEL_TEXT_STYLE)
    elif snapshot.status == "running":
        header = Text(f"RUNNING {_scene_label(snapshot.scene)}", style=PANEL_TEXT_STYLE)
    elif snapshot.message == "No more scenarios":
        header = Text("ALL FINISHED", style=SUCCESS_TEXT_STYLE)
    else:
        header = Text(f"FINISHED {_scene_label(snapshot.scene)}", style=SUCCESS_TEXT_STYLE)
    title = ""
    content = Table.grid(expand=True)
    content.add_column(ratio=1)
    if snapshot.status in ("initializing", "waiting"):
        title = "Scenarios to Run"
        content.add_row(_queue_table(snapshot.queue, snapshot.completed + 1))
    elif snapshot.status == "reset":
        title = None
    elif snapshot.status == "running":
        content.add_row(_runtime_fields(snapshot))
    elif snapshot.message == "No more scenarios":
        if snapshot.aggregate_metrics is not None:
            content.add_row(_metric_table("Average Metrics", snapshot.aggregate_metrics))
    else:
        if snapshot.termination_reason is not None:
            content.add_row(Text(f"Termination: {snapshot.termination_reason}", style=PANEL_TEXT_STYLE))
        if snapshot.scene_metrics is not None:
            content.add_row(_metric_table("Scene Metrics", snapshot.scene_metrics))
        if snapshot.message is not None:
            content.add_row(Text(snapshot.message, style=SUCCESS_TEXT_STYLE))
    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(Text(""))
    body.add_row(header)
    if title is not None:
        body.add_row(Text(""))
        body.add_row(Rule(title, style=PANEL_BORDER_STYLE))
        body.add_row(Text(""))
        body.add_row(content)
    return Group(
        Text(VEHICLE_ASCII, style=MUTED_TEXT_STYLE),
        Text(""),
        Panel(body, border_style=PANEL_BORDER_STYLE, title="StreetWorld", style=PANEL_TEXT_STYLE),
    )


def _runtime_fields(snapshot: RuntimeSnapshot) -> Table:
    fields = Table.grid(expand=True)
    fields.add_column(ratio=1, overflow="ellipsis")
    fields.add_column(ratio=1, overflow="ellipsis")
    timestamp = "n/a" if snapshot.timestamp_us is None else str(snapshot.timestamp_us)
    speed = "n/a" if snapshot.speed_mps is None else f"{snapshot.speed_mps:.2f} m/s"
    fields.add_row(Text(f"Timestamp: {timestamp}", style=PANEL_TEXT_STYLE), Text(f"Speed: {speed}", style=PANEL_TEXT_STYLE))
    steering = "n/a" if snapshot.steering is None else f"{snapshot.steering:.3f}"
    throttle = "n/a" if snapshot.throttle is None else f"{snapshot.throttle:.3f}"
    brake = "n/a" if snapshot.brake is None else f"{snapshot.brake:.3f}"
    fields.add_row(Text(f"Steering: {steering}", style=PANEL_TEXT_STYLE), Text(f"Throttle: {throttle}  Brake: {brake}", style=PANEL_TEXT_STYLE))
    return fields


def _queue_table(scenes: Sequence[str], start_index: int) -> Table:
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="right", width=4, style=MUTED_TEXT_STYLE)
    table.add_column(overflow="ellipsis", style=PANEL_TEXT_STYLE)
    for index, scene in enumerate(scenes, start=start_index):
        table.add_row(f"{index:02d}", _scene_label(scene))
    return table


def _metric_table(title: str, metrics: Mapping[str, float]) -> Table:
    table = Table(title=title, expand=True, border_style=PANEL_BORDER_STYLE, show_header=False)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for metric in ("NC", "DAC", "TTC", "COM", "RC", "RE"):
        if metric in metrics:
            table.add_row(metric, f"{metrics[metric]:.4f}")
    return table


def _scene_label(scene: str | None) -> str:
    if scene is None:
        return "-"
    path = Path(scene)
    if path.suffix.lower() in YAML_SUFFIXES:
        return path.stem
    return str(scene)
