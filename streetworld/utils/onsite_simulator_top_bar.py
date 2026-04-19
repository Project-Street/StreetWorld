import math
from typing import Any

import numpy as np
from rich.console import Group
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


PANEL_BORDER_STYLE = "#D97941"
PANEL_TEXT_STYLE = "white"
CHECKED_STYLE = "#00B0F0"
MUTED_TEXT_STYLE = "#CFCFCF"
SUCCESS_TEXT_STYLE = "green"
BOOTSTRAP_ASCII = "\n".join(
    [
        "   ______",
        "  /|_||_\\\\`.__",
        " (   _    _ _\\\\",
        " =`-(_)--(_)-'",
    ]
)


def _checkbox(label: str, checked: bool) -> Text:
    box_style = CHECKED_STYLE if checked else PANEL_TEXT_STYLE
    return Text.assemble(
        ("[✓] " if checked else "[ ] ", box_style),
        (label, PANEL_TEXT_STYLE),
    )


class LauncherTopBarState:
    def __init__(self, grpc_host: str, grpc_port: int, onsite_dir: str, scene_config_directory: str, gui: bool):
        self.grpc_host = grpc_host
        self.grpc_port = grpc_port
        self.onsite_dir = onsite_dir
        self.scene_config_directory = scene_config_directory
        self.gui = gui
        self.bootstrap_checks = [False, False, False, False]
        self.preparing_text = None
        self.preparing_messages = []
        self.preparing_progress = None
        self.show_spinner = False
        self.session_id = None
        self.scene_name = None
        self.timestamp_us = None
        self.speed_mps = None
        self.action_text = None
        self.state_text = "IDLE"
        self.stage = "bootstrap"

    def mark_renderer_interface_ready(self):
        self.bootstrap_checks[0] = True

    def mark_scenario_env_ready(self):
        self.bootstrap_checks[1] = True

    def mark_onsite_switch_ready(self):
        self.bootstrap_checks[2] = True

    def mark_onsite_daemon_ready(self):
        self.bootstrap_checks[3] = True

    def mark_actor_prepared(self, session_id: str, scene_name: str):
        self.stage = "preparing"
        self.session_id = session_id
        self.scene_name = scene_name
        self.preparing_text = f"Preparing {scene_name}"
        self.preparing_messages = []
        self.preparing_progress = None
        self.show_spinner = True

    def mark_simulation_started(self):
        self.stage = "running"
        self.show_spinner = False

    def mark_finished(self, state_text: str):
        self.stage = "finished"
        self.scene_name = "n/a"
        self.timestamp_us = None
        self.speed_mps = None
        self.action_text = "n/a"
        self.state_text = state_text
        self.preparing_progress = None
        self.show_spinner = False

    def update_runtime(self, timestamp_us: int, speed_mps: float | None, action_text: str, state_text: str):
        self.timestamp_us = timestamp_us
        self.speed_mps = speed_mps
        self.action_text = action_text
        self.state_text = state_text

    def push_preparing_message(self, message: str):
        self.preparing_messages.append(str(message))
        if len(self.preparing_messages) > 5:
            self.preparing_messages = self.preparing_messages[-5:]

    def set_preparing_progress(self, message: str):
        self.preparing_progress = str(message)

    def snapshot(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "grpc_host": self.grpc_host,
            "grpc_port": self.grpc_port,
            "onsite_dir": self.onsite_dir,
            "scene_config_directory": self.scene_config_directory,
            "gui": self.gui,
            "bootstrap_checks": list(self.bootstrap_checks),
            "preparing_text": self.preparing_text,
            "preparing_messages": list(self.preparing_messages),
            "preparing_progress": self.preparing_progress,
            "show_spinner": self.show_spinner,
            "session_id": self.session_id,
            "scene_name": self.scene_name,
            "timestamp_us": self.timestamp_us,
            "speed_mps": self.speed_mps,
            "action_text": self.action_text,
            "state_text": self.state_text,
        }


def _bootstrap_panel(snapshot: dict[str, Any]) -> Panel:
    bootstrap_complete = all(snapshot["bootstrap_checks"])

    checks = Table.grid(expand=True)
    checks.add_column(ratio=1)
    checks.add_column(ratio=1)
    checks.add_row(
        _checkbox("gaussian renderer", snapshot["bootstrap_checks"][0]),
        _checkbox("simulator env", snapshot["bootstrap_checks"][1]),
    )
    checks.add_row(
        _checkbox("onsite switch", snapshot["bootstrap_checks"][2]),
        _checkbox("onsite daemon", snapshot["bootstrap_checks"][3]),
    )

    info = Table.grid(expand=True)
    info.add_column(ratio=1)
    info.add_row(Text(f"onsite_dir: {snapshot['onsite_dir']}", style=MUTED_TEXT_STYLE))
    info.add_row(Text(f"scene_config_directory: {snapshot['scene_config_directory']}", style=MUTED_TEXT_STYLE))
    info.add_row(Text(f"gui: {snapshot['gui']}", style=MUTED_TEXT_STYLE))

    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(Text(""))
    body.add_row(checks)
    body.add_row(Text(""))
    body.add_row(Text("─" * 74, style=PANEL_BORDER_STYLE))
    body.add_row(Text(""))
    body.add_row(info)
    body.add_row(Text(""))
    body.add_row(Text("initialization complete", style=SUCCESS_TEXT_STYLE) if bootstrap_complete else Text(""))

    panel = Panel(body, title="Initialization", border_style=PANEL_BORDER_STYLE, style=PANEL_TEXT_STYLE)
    return Group(
        Text(BOOTSTRAP_ASCII, style=MUTED_TEXT_STYLE),
        Text(""),
        Text(" StreetWorld", style="bold white"),
        Text(""),
        panel,
    )


def _preparing_panel(snapshot: dict[str, Any]) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_row(Text(f"session: {snapshot['session_id'] or '-'}", style=PANEL_TEXT_STYLE))
    spinner = Spinner("dots", text=Text(snapshot["preparing_text"] or "-", style=PANEL_TEXT_STYLE), style=PANEL_TEXT_STYLE)
    table.add_row(spinner if snapshot["show_spinner"] else Text(snapshot["preparing_text"] or "-", style=PANEL_TEXT_STYLE))
    if snapshot["preparing_messages"]:
        table.add_row(Text(""))
        for message in snapshot["preparing_messages"]:
            table.add_row(Text(f"• {message}", style=MUTED_TEXT_STYLE))
    if snapshot["preparing_progress"]:
        table.add_row(Text(""))
        table.add_row(Text(snapshot["preparing_progress"], style=MUTED_TEXT_STYLE))
    return Panel(table, title="Preparing", border_style=PANEL_BORDER_STYLE, style=PANEL_TEXT_STYLE)


def _status_panel(snapshot: dict[str, Any], title: str) -> Panel:
    meta_table = Table.grid(expand=True)
    meta_table.add_column(ratio=1)
    meta_table.add_column(ratio=1)
    meta_table.add_row(
        Text(f"scene: {snapshot['scene_name'] or 'n/a'}", style=PANEL_TEXT_STYLE),
        Text(f"state: {snapshot['state_text'] or '-'}", style=PANEL_TEXT_STYLE),
    )
    speed_text = "n/a" if snapshot["speed_mps"] is None else f"{snapshot['speed_mps']:.2f} m/s"
    meta_table.add_row(
        Text(
            f"timestamp: {snapshot['timestamp_us'] if snapshot['timestamp_us'] is not None else 'n/a'}",
            style=PANEL_TEXT_STYLE,
        ),
        Text(f"speed: {speed_text}", style=PANEL_TEXT_STYLE),
    )
    action_text = Text(
        f"action: {snapshot['action_text'] or 'n/a'}",
        style=PANEL_TEXT_STYLE,
        no_wrap=True,
        overflow="ellipsis",
    )
    body = Table.grid(expand=True)
    body.add_column(ratio=1)
    body.add_row(meta_table)
    body.add_row(action_text)
    return Panel(body, title=title, border_style=PANEL_BORDER_STYLE, style=PANEL_TEXT_STYLE)


def build_top_bar_renderable(snapshot: dict[str, Any]):
    if snapshot["stage"] == "bootstrap":
        return _bootstrap_panel(snapshot)
    if snapshot["stage"] == "preparing":
        return _preparing_panel(snapshot)
    if snapshot["stage"] == "finished":
        return _status_panel(snapshot, "Finished")
    return _status_panel(snapshot, "Running")


def build_launcher_renderable(snapshot: dict[str, Any], log_path: str):
    return Group(
        build_top_bar_renderable(snapshot),
        Text(f"Logs saved to {log_path}", style="dim"),
    )


def update_top_bar_runtime(state: LauncherTopBarState, info: dict[str, Any], action, obs: dict[str, Any], sim_state_name: str):
    steer = float(action[0]) if action is not None else 0.0
    throttle_brake = float(action[1]) if action is not None else 0.0
    speed = None
    vehicle_state = obs.get("states") or {}
    velocity = vehicle_state.get("velocity")
    if velocity is not None:
        vel = np.asarray(velocity, dtype=np.float64).reshape(-1)
        speed = float(math.hypot(vel[0], vel[1])) if vel.size >= 2 else float(abs(vel[0])) if vel.size == 1 else None

    state.update_runtime(
        timestamp_us=int(info["relative_timestamp"]),
        speed_mps=speed,
        action_text=f"steer={steer:.3f} throttle_brake={throttle_brake:.3f}",
        state_text=str(sim_state_name),
    )
