"""Select scenes from dataset catalogs through the terminal interface."""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import yaml
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from metadrive.ui.tui_style import (
    ACTION_TEXT_STYLE,
    FOCUSED_TEXT_STYLE,
    MUTED_TEXT_STYLE,
    PANEL_BORDER_STYLE,
    PANEL_TEXT_STYLE,
    VEHICLE_ASCII,
)


CATALOGS = {
    "nuScenes": ("easydrive", "nuScenes.yaml"),
    "Waymo": ("easydrive", "Waymo.yaml"),
    "NuRec": ("nurec", "NuRec.yaml"),
}
_SELECTION_BACK = object()


@dataclass(frozen=True)
class CatalogSelection:
    dataset: str
    backend: str
    scenes: tuple[str, ...]


@dataclass
class _SelectionPage:
    detail: str
    options: Sequence[str]
    multiple: bool = False
    cursor: int = 0
    selected: set[str] = field(default_factory=set)
    notice: str | None = None


def filter_catalog_scenes(
    catalog: Mapping[str, Mapping[str, Sequence[str]]],
    selected_tags: Mapping[str, Sequence[str]],
) -> list[str]:
    scenes: list[str] | None = None
    for category, tags in catalog.items():
        matched = list(dict.fromkeys(scene for tag in selected_tags[category] for scene in tags[tag]))
        scenes = matched if scenes is None else [scene for scene in scenes if scene in matched]
    return scenes or []


def select_catalog_scenes() -> CatalogSelection:
    """Interactively select a dataset and tags, returning a non-empty queue."""
    dataset_page = _SelectionPage(
        detail="Choose a dataset",
        options=list(CATALOGS),
    )
    while True:
        dataset = _run_selection_page(dataset_page)
        if dataset is _SELECTION_BACK:
            continue

        backend, catalog_filename = CATALOGS[dataset]
        catalog_path = Path(__file__).resolve().parents[2] / "catalog" / catalog_filename
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
        tag_pages = [
            _SelectionPage(
                detail="Choose one or more tags",
                options=list(tags),
                multiple=True,
            )
            for category, tags in catalog.items()
        ]
        tag_index = 0
        while tag_index >= 0:
            if tag_index == len(tag_pages):
                selected_tags = {category: tuple(page.selected) for category, page in zip(catalog, tag_pages, strict=True)}
                scenes = filter_catalog_scenes(catalog, selected_tags)
                if scenes:
                    scene_names = scenes if backend == "nurec" else [Path(scene).stem for scene in scenes]
                    return CatalogSelection(dataset, backend, tuple(scene_names))
                retry = _run_selection_page(
                    _SelectionPage(detail="No scenarios match the selected tags", options=())
                )
                tag_index = len(tag_pages) - 1 if retry is _SELECTION_BACK else 0
                continue

            page = tag_pages[tag_index]
            chosen = _run_selection_page(page)
            if chosen is _SELECTION_BACK:
                tag_index -= 1
            else:
                page.selected = set(chosen)
                tag_index += 1


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
                if key == "up" and action_start:
                    page.cursor = max(0, min(action_start - 1, page.cursor - 1))
                    continue
                if key == "down" and page.cursor < action_start:
                    page.cursor += 1
                    continue
                if key in ("left", "right") and page.cursor >= action_start:
                    page.cursor = action_start + (key == "right")
                    continue
                if key != "enter":
                    continue
                if page.cursor < action_start:
                    option = page.options[page.cursor]
                    if not page.multiple:
                        page.selected = {option}
                    elif option in page.selected:
                        page.selected.remove(option)
                    else:
                        page.selected.add(option)
                    continue
                if page.cursor == action_start + 1:
                    return _SELECTION_BACK
                if not page.options:
                    return True
                if not page.selected:
                    page.notice = "Choose at least one item"
                    continue
                if not page.multiple:
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
        start = max(0, min(page.cursor - 6, len(page.options) - 12))
        options = Table.grid(expand=True, padding=(0, 1))
        options.add_column(ratio=1)
        for index, option in enumerate(page.options[start:start + 12], start=start):
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
            options.add_row(Text(option, style=style, overflow="ellipsis", no_wrap=True))
        body.add_row(options)
    if page.notice:
        body.add_row(Text(""))
        body.add_row(Text(page.notice, style="bold red"))
    body.add_row(Text(""))
    actions = Table.grid(padding=(0, 1))
    actions.add_column(no_wrap=True)
    actions.add_column(no_wrap=True)
    primary_action = "Try Again" if not page.options else "Continue"
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
