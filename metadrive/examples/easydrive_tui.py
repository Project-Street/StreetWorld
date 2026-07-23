"""Interactive scene selection and runtime status for the environment server."""

from __future__ import annotations

import math
import os
import select
import sys
import termios
import threading
import tty
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


BACKENDS = ("easydrive", "nurec")
CATALOG_BACKENDS = {"nuScenes": "easydrive", "Waymo": "easydrive", "NuRec": "nurec"}
CATALOG_FILENAMES = {"nuScenes": "nuScenes.yaml", "Waymo": "Waymo.yaml", "NuRec": "NuRec.yaml"}
YAML_SUFFIXES = {".yaml", ".yml"}
PANEL_BORDER_STYLE = "#D97941"
PANEL_TEXT_STYLE = "white"
MUTED_TEXT_STYLE = "#CFCFCF"
FOCUSED_TEXT_STYLE = "#C8B6FF"
ACTION_TEXT_STYLE = "#9B9B9B"
SUCCESS_TEXT_STYLE = "green"
LOADING_SPINNER = Spinner("dots", style=PANEL_TEXT_STYLE)
VEHICLE_ASCII = "\n".join(
    [
        "   ______",
        "  /|_||_\\\\`.__",
        " (   _    _ _\\\\",
        " =`-(_)--(_)-'",
    ]
)
_SELECTION_BACK = object()


class CatalogError(ValueError):
    """Raised when a catalog or selected scene input is invalid."""


@dataclass(frozen=True)
class CatalogSelection:
    dataset: str
    backend: str
    scenes: tuple[str, ...]
    tags: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class RuntimeSnapshot:
    status: str
    backend: str
    scene: str | None
    queue: tuple[str, ...]
    completed: int
    total: int
    timestamp_us: int | None
    speed_mps: float | None
    steering: float | None
    throttle: float | None
    brake: float | None
    termination_reason: str | None
    scene_metrics: Mapping[str, float] | None
    aggregate_metrics: Mapping[str, float] | None
    message: str | None


@dataclass
class _SelectionPage:
    title: str
    detail: str
    options: Sequence[str]
    mode: str
    cursor: int = 0
    selected: set[str] = field(default_factory=set)
    notice: str | None = None


def catalog_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "catalog"


def load_catalog(path: str | Path) -> dict[str, dict[str, list[str]]]:
    catalog_path = Path(path).expanduser().resolve()
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Catalog file does not exist: {catalog_path}")
    if catalog_path.suffix.lower() not in YAML_SUFFIXES:
        raise CatalogError(f"Catalog file must be YAML: {catalog_path}")

    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise CatalogError(f"Catalog root must be a non-empty mapping: {catalog_path}")

    catalog: dict[str, dict[str, list[str]]] = {}
    for category, tags in data.items():
        if not isinstance(category, str) or not category:
            raise CatalogError("Catalog category names must be non-empty strings.")
        if not isinstance(tags, dict) or not tags:
            raise CatalogError(f"Catalog category {category!r} must be a non-empty mapping.")
        parsed_tags: dict[str, list[str]] = {}
        for tag, scenes in tags.items():
            if not isinstance(tag, str) or not tag:
                raise CatalogError(f"Catalog tag names in {category!r} must be non-empty strings.")
            if not isinstance(scenes, list) or not all(isinstance(scene, str) and scene for scene in scenes):
                raise CatalogError(f"Catalog entry {category!r}/{tag!r} must be a list of non-empty strings.")
            parsed_tags[tag] = list(scenes)
        catalog[category] = parsed_tags
    return catalog


def filter_catalog_scenes(
    catalog: Mapping[str, Mapping[str, Sequence[str]]],
    selected_tags: Mapping[str, Sequence[str]],
) -> list[str]:
    """Union tags within each category, then intersect category result sets."""
    if set(selected_tags) != set(catalog):
        missing = [category for category in catalog if category not in selected_tags]
        unexpected = [category for category in selected_tags if category not in catalog]
        raise CatalogError(f"Tag selection must cover every category; missing={missing}, unexpected={unexpected}")

    category_unions: list[list[str]] = []
    for category, tags in catalog.items():
        chosen_tags = selected_tags[category]
        if not chosen_tags:
            raise CatalogError(f"Select at least one tag for category {category!r}.")

        union: list[str] = []
        seen: set[str] = set()
        for tag in chosen_tags:
            if tag not in tags:
                raise CatalogError(f"Unknown tag {tag!r} in category {category!r}.")
            for scene in tags[tag]:
                if scene not in seen:
                    seen.add(scene)
                    union.append(scene)
        category_unions.append(union)

    scenes = category_unions[0]
    for union in category_unions[1:]:
        allowed = set(union)
        scenes = [scene for scene in scenes if scene in allowed]
    return scenes


def resolve_scene_config(scene_config: str | Path, backend: str) -> list[str]:
    if backend not in BACKENDS:
        raise CatalogError(f"Unknown backend {backend!r}.")

    config_path = Path(scene_config).expanduser().resolve()
    if backend == "nurec":
        if not config_path.is_file():
            raise CatalogError("NuRec --scene-config must be a YAML list file.")
        return _load_nurec_scene_list(config_path)

    if config_path.is_dir():
        scenes = sorted(
            path.resolve()
            for path in config_path.iterdir()
            if path.is_file() and path.suffix.lower() in YAML_SUFFIXES
        )
        if not scenes:
            raise CatalogError(f"EasyDrive scene config directory contains no YAML files: {config_path}")
        return [str(scene) for scene in scenes]
    if config_path.is_file():
        return _load_easydrive_scene_list(config_path)
    raise FileNotFoundError(f"Scene config path does not exist: {config_path}")


def resolve_catalog_scenes(scenes: Sequence[str], backend: str) -> list[str]:
    if not scenes:
        raise CatalogError("Selected tags match zero scenes.")
    if backend == "nurec":
        return _validate_nurec_scene_ids(scenes)
    if backend != "easydrive":
        raise CatalogError(f"Unknown backend {backend!r}.")

    resolved: list[str] = []
    for scene in scenes:
        path = Path(scene).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"EasyDrive scene config does not exist: {path}")
        if path.suffix.lower() not in YAML_SUFFIXES:
            raise CatalogError(f"EasyDrive scene config must be YAML: {path}")
        resolved.append(str(path))
    return resolved


def _load_easydrive_scene_list(config_path: Path) -> list[str]:
    scenes = _load_list_yaml(config_path)
    resolved: list[str] = []
    for scene in scenes:
        path = Path(scene).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"EasyDrive scene config does not exist: {path}")
        if path.suffix.lower() not in YAML_SUFFIXES:
            raise CatalogError(f"EasyDrive scene config must be YAML: {path}")
        resolved.append(str(path))
    return resolved


def _load_nurec_scene_list(config_path: Path) -> list[str]:
    return _validate_nurec_scene_ids(_load_list_yaml(config_path))


def _load_list_yaml(path: Path) -> list[str]:
    if path.suffix.lower() not in YAML_SUFFIXES:
        raise CatalogError(f"Scene list must be YAML: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data or not all(isinstance(scene, str) and scene for scene in data):
        raise CatalogError(f"Scene list root must be a non-empty list of strings: {path}")
    return list(data)


def _validate_nurec_scene_ids(scenes: Sequence[str]) -> list[str]:
    result: list[str] = []
    for scene in scenes:
        path = PurePosixPath(scene)
        if (
            len(path.parts) != 2
            or not path.parts[0].startswith("Batch")
            or not path.parts[0][len("Batch"):].isdigit()
            or not path.parts[1]
            or any(part in (".", "..") for part in path.parts)
        ):
            raise CatalogError(f"NuRec scene ID must have the form Batch<digits>/<scene>, got {scene!r}")
        result.append(scene)
    return result


def select_catalog_scenes() -> CatalogSelection:
    """Interactively select a dataset and tags, returning a non-empty queue."""
    dataset_page = _SelectionPage(
        title="Scene Catalog",
        detail="Choose a dataset",
        options=list(CATALOG_BACKENDS),
        mode="single",
    )
    while True:
        dataset = _run_selection_page(dataset_page)
        if dataset is _SELECTION_BACK:
            continue

        catalog = load_catalog(catalog_directory() / CATALOG_FILENAMES[dataset])
        tag_pages = [
            _SelectionPage(
                title=category,
                detail="Choose one or more tags",
                options=list(tags),
                mode="multiple",
            )
            for category, tags in catalog.items()
        ]
        tag_index = 0
        while tag_index >= 0:
            if tag_index < len(tag_pages):
                chosen = _run_selection_page(tag_pages[tag_index])
                if chosen is _SELECTION_BACK:
                    tag_index -= 1
                    continue
                tag_pages[tag_index].selected = set(chosen)
                tag_index += 1
                continue

            selected_tags = {
                category: tuple(page.selected)
                for category, page in zip(catalog, tag_pages, strict=True)
            }
            scenes = filter_catalog_scenes(catalog, selected_tags)
            if scenes:
                backend = CATALOG_BACKENDS[dataset]
                resolved_scenes = resolve_catalog_scenes(scenes, backend)
                return CatalogSelection(dataset, backend, tuple(resolved_scenes), selected_tags)

            retry = _run_selection_page(
                _SelectionPage(
                    title="No Matching Scenarios",
                    detail="No scenarios match the selected tags",
                    options=(),
                    mode="notice",
                )
            )
            tag_index = len(tag_pages) - 1 if retry is _SELECTION_BACK else 0


class _RawTerminal:
    """Read keys while Rich owns all rendering for the selection screens."""

    def __enter__(self):
        if not sys.stdin.isatty():
            raise RuntimeError("Catalog selection requires an interactive terminal.")
        self._fd = sys.stdin.fileno()
        self._previous = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._previous)

    def read_key(self) -> str:
        key = os.read(self._fd, 1)
        if key == b"\x03":
            raise KeyboardInterrupt
        if key in (b"\r", b"\n"):
            return "enter"
        if key != b"\x1b":
            return key.decode()
        if not select.select([self._fd], [], [], 0.1)[0]:
            return "escape"
        if os.read(self._fd, 1) not in (b"[", b"O"):
            return "escape"
        if not select.select([self._fd], [], [], 0.1)[0]:
            return "escape"
        return {b"A": "up", b"B": "down", b"C": "right", b"D": "left"}.get(os.read(self._fd, 1), "escape")


def _run_selection_page(page: _SelectionPage):
    console = Console()
    with _RawTerminal() as terminal:
        with Live(
            get_renderable=lambda: build_selection_renderable(page),
            console=console,
            screen=True,
            refresh_per_second=12,
            vertical_overflow="crop",
        ):
            while True:
                key = terminal.read_key()
                if key == "escape":
                    return _SELECTION_BACK
                action_start = len(page.options)
                if key == "up":
                    if action_start:
                        page.cursor = action_start - 1 if page.cursor >= action_start else max(0, page.cursor - 1)
                    continue
                if key == "down":
                    if action_start:
                        if page.cursor < action_start - 1:
                            page.cursor += 1
                        elif page.cursor == action_start - 1:
                            page.cursor = action_start
                    continue
                if key == "left" and page.cursor >= action_start:
                    page.cursor = action_start
                    continue
                if key == "right" and page.cursor >= action_start:
                    page.cursor = action_start + 1
                    continue
                if key != "enter":
                    continue
                if page.cursor < action_start:
                    option = page.options[page.cursor]
                    if page.mode == "single":
                        page.selected = {option}
                    elif option in page.selected:
                        page.selected.remove(option)
                    else:
                        page.selected.add(option)
                    continue
                if page.cursor == action_start + 1:
                    return _SELECTION_BACK
                if page.mode == "notice":
                    return True
                if not page.selected:
                    page.notice = "Choose at least one item"
                    continue
                if page.mode == "single":
                    return next(option for option in page.options if option in page.selected)
                return tuple(option for option in page.options if option in page.selected)


def build_selection_renderable(page: _SelectionPage):
    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(Text(""))
    body.add_row(Text(page.detail, style=MUTED_TEXT_STYLE))
    body.add_row(Rule(style=PANEL_BORDER_STYLE))
    body.add_row(Text(""))
    if page.options:
        body.add_row(_selection_options(page))
    if page.notice:
        body.add_row(Text(""))
        body.add_row(Text(page.notice, style="bold red"))
    body.add_row(Text(""))
    actions = Table.grid(padding=(0, 1))
    actions.add_column(no_wrap=True)
    actions.add_column(no_wrap=True)
    primary_action = "Try Again" if page.mode == "notice" else "Continue"
    actions.add_row(
        Text(primary_action, style=FOCUSED_TEXT_STYLE if page.cursor == len(page.options) else ACTION_TEXT_STYLE),
        Text("Cancel", style=FOCUSED_TEXT_STYLE if page.cursor == len(page.options) + 1 else ACTION_TEXT_STYLE),
    )
    body.add_row(actions)
    return Group(
        Text(VEHICLE_ASCII, style=MUTED_TEXT_STYLE),
        Text(""),
        Panel(body, border_style=PANEL_BORDER_STYLE, title="StreetWorld", style=PANEL_TEXT_STYLE),
        Text("Ctrl-C Exit StreetWorld", style=ACTION_TEXT_STYLE),
    )


def _selection_options(page: _SelectionPage) -> Table:
    visible = 12
    start = max(0, min(page.cursor - visible // 2, len(page.options) - visible))
    options = page.options[start:start + visible]
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(ratio=1)
    for index, option in enumerate(options, start=start):
        focused = index == page.cursor
        selected = option in page.selected
        style = (
            f"bold {FOCUSED_TEXT_STYLE}"
            if focused and selected
            else FOCUSED_TEXT_STYLE
            if focused
            else "bold " + PANEL_TEXT_STYLE
            if selected
            else PANEL_TEXT_STYLE
        )
        table.add_row(Text(option, style=style, overflow="ellipsis", no_wrap=True))
    return table


class TuiRuntimeState:
    """A lock-protected state store read by Rich while gRPC handlers update it."""

    def __init__(self, backend: str, scene_queue: Sequence[str]) -> None:
        self._lock = threading.Lock()
        self._backend = backend
        self._queue = list(scene_queue)
        self._total = len(scene_queue)
        self._completed = 0
        self._scene_completed = False
        self._status = "initializing"
        self._scene: str | None = None
        self._timestamp_us: int | None = None
        self._speed_mps: float | None = None
        self._steering: float | None = None
        self._throttle: float | None = None
        self._brake: float | None = None
        self._termination_reason: str | None = None
        self._scene_metrics: dict[str, float] | None = None
        self._aggregate_metrics: dict[str, float] | None = None
        self._message: str | None = None
        self._failure: Exception | None = None

    def mark_waiting(self) -> None:
        with self._lock:
            self._status = "waiting"

    def begin_reset(self) -> None:
        with self._lock:
            self._status = "reset"
            self._timestamp_us = None
            self._speed_mps = None
            self._steering = None
            self._throttle = None
            self._brake = None
            self._termination_reason = None
            self._scene_metrics = None
            self._message = None

    def record_reset(self, scene: str, pending_queue: Sequence[str], info: Mapping[str, Any], obs: Mapping[str, Any]) -> None:
        with self._lock:
            self._scene = scene
            self._queue = list(pending_queue)
            self._scene_completed = False
            self._timestamp_us = _timestamp(info)
            self._speed_mps = _speed(obs)

    def record_step(
        self,
        info: Mapping[str, Any],
        obs: Mapping[str, Any],
        terminated: bool,
        truncated: bool,
        scene_metrics: Mapping[str, float] | None,
        aggregate_metrics: Mapping[str, float] | None,
    ) -> None:
        with self._lock:
            self._status = "finished" if terminated or truncated else "running"
            self._timestamp_us = _timestamp(info)
            self._speed_mps = _speed(obs)
            self._steering = float(info["steering"])
            longitudinal = float(info["throttle_brake"])
            self._throttle = max(longitudinal, 0.0)
            self._brake = max(-longitudinal, 0.0)
            if terminated or truncated:
                self._termination_reason = _reason(info, terminated, truncated)
                self._scene_metrics = dict(scene_metrics) if scene_metrics is not None else None
                self._aggregate_metrics = dict(aggregate_metrics) if aggregate_metrics is not None else None
                if not self._scene_completed:
                    self._completed += 1
                    self._scene_completed = True

    def record_exhausted(self) -> None:
        with self._lock:
            self._status = "finished"
            self._message = "No more scenarios"

    def mark_finished(self, message: str | None = None) -> None:
        with self._lock:
            self._status = "finished"
            if message is not None:
                self._message = message

    def record_failure(self, error: Exception) -> None:
        with self._lock:
            self._failure = error

    def failure(self) -> Exception | None:
        with self._lock:
            return self._failure

    def snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            return RuntimeSnapshot(
                status=self._status,
                backend=self._backend,
                scene=self._scene,
                queue=tuple(self._queue),
                completed=self._completed,
                total=self._total,
                timestamp_us=self._timestamp_us,
                speed_mps=self._speed_mps,
                steering=self._steering,
                throttle=self._throttle,
                brake=self._brake,
                termination_reason=self._termination_reason,
                scene_metrics=dict(self._scene_metrics) if self._scene_metrics is not None else None,
                aggregate_metrics=dict(self._aggregate_metrics) if self._aggregate_metrics is not None else None,
                message=self._message,
            )


class LifecycleAwareEnv:
    """Expose environment lifecycle events to the TUI without changing its RPC API."""

    def __init__(self, env: Any, state: TuiRuntimeState, scene_queue: Sequence[str]) -> None:
        self._env = env
        self._state = state
        self._scene_queue = list(scene_queue)
        self._next_scene = 0

    def reset(self, *args: Any, **kwargs: Any) -> Any:
        self._state.begin_reset()
        try:
            obs, info = self._env.reset(*args, **kwargs)
        except LookupError as exc:
            if str(exc) == "No more scenarios to evaluate.":
                self._state.record_exhausted()
            else:
                self._state.record_failure(exc)
            raise
        except Exception as exc:
            self._state.record_failure(exc)
            raise

        scene = str(info.get("scene_name") or self._scene_queue[self._next_scene])
        self._next_scene += 1
        self._state.record_reset(scene, self._scene_queue[self._next_scene:], info, obs)
        return obs, info

    def step(self, action: Sequence[float]) -> Any:
        try:
            obs, reward, terminated, truncated, info = self._env.step(action)
        except Exception as exc:
            self._state.record_failure(exc)
            raise
        scene_metrics, aggregate_metrics = self._metrics(bool(terminated or truncated))
        self._state.record_step(
            info,
            obs,
            bool(terminated),
            bool(truncated),
            scene_metrics,
            aggregate_metrics,
        )
        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        self._env.close()

    def _metrics(self, completed: bool) -> tuple[Mapping[str, float] | None, Mapping[str, float] | None]:
        if not completed:
            return None, None
        tracker = getattr(self._env, "metric_tracker", None)
        completed_metrics = getattr(tracker, "completed_scene_metrics", None)
        if not completed_metrics:
            return None, None
        scene_metrics = completed_metrics[-1]
        aggregate_metrics = self._env.get_average_metric()
        return scene_metrics, aggregate_metrics


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
    title, content = _runtime_content(snapshot)
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


def _runtime_content(snapshot: RuntimeSnapshot) -> tuple[str | None, Table]:
    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    if snapshot.status == "initializing":
        body.add_row(_queue_table(snapshot.queue, snapshot.completed + 1))
        return "Scenarios to Run", body
    if snapshot.status == "waiting":
        body.add_row(_queue_table(snapshot.queue, snapshot.completed + 1))
        return "Scenarios to Run", body
    if snapshot.status == "reset":
        return None, body

    if snapshot.status == "running":
        body.add_row(_runtime_fields(snapshot))
        return "", body
    if snapshot.message == "No more scenarios":
        if snapshot.aggregate_metrics is not None:
            body.add_row(_metric_table("Average Metrics", snapshot.aggregate_metrics))
        return "", body
    if snapshot.termination_reason is not None:
        body.add_row(Text(f"Termination: {snapshot.termination_reason}", style=PANEL_TEXT_STYLE))
    if snapshot.scene_metrics is not None:
        body.add_row(_metric_table("Scene Metrics", snapshot.scene_metrics))
    if snapshot.message is not None:
        body.add_row(Text(snapshot.message, style=SUCCESS_TEXT_STYLE))
    return "", body


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
    for metric in ("NC", "DAC", "TTC", "COM", "RC", "ProgressSpeed"):
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


def _timestamp(info: Mapping[str, Any]) -> int | None:
    timestamp = info.get("relative_timestamp")
    return int(timestamp) if timestamp is not None else None


def _speed(obs: Mapping[str, Any]) -> float | None:
    states = obs.get("states")
    if not isinstance(states, Mapping):
        return None
    if states.get("ego_velo") is not None:
        return float(states["ego_velo"])
    velocity = states.get("linear_velocity")
    if velocity is None:
        velocity = states.get("velocity")
    if velocity is None:
        return None
    values = list(velocity)
    if not values:
        return None
    return math.hypot(float(values[0]), float(values[1])) if len(values) > 1 else abs(float(values[0]))


def _reason(info: Mapping[str, Any], terminated: bool, truncated: bool) -> str:
    reason = info.get("reason")
    if reason is not None:
        return str(getattr(reason, "name", reason))
    if truncated:
        return "truncated"
    if terminated:
        return "terminated"
    return "unknown"
