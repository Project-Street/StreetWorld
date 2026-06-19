from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Sequence

import cv2
import matplotlib
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from metadrive.utils.image_to_video import image_list_to_video

matplotlib.use("Agg")

logger = logging.getLogger(__name__)


def extract_video_payload(image: np.ndarray, states: dict[str, Any], info: Any, action: Sequence[float]):
    if len(action) != 2:
        raise ValueError(f"Expected action with length 2, got {len(action)}")

    velocity = np.asarray(states["linear_velocity"], dtype=np.float32).reshape(-1)
    speed = float(np.linalg.norm(velocity[:2]))
    angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32).reshape(-1)
    if angular_velocity.shape[0] < 3:
        raise ValueError(f"Expected angular_velocity with at least 3 values, got shape {angular_velocity.shape}")
    yaw_rate = float(angular_velocity[2])
    timestamp = int(info["relative_timestamp"])

    return {
        "image": image,
        "timestamp": timestamp,
        "steering": float(action[0]),
        "throttle_brake": float(action[1]),
        "speed": speed,
        "angular_velocity": yaw_rate,
    }


def _draw_bar(canvas: np.ndarray, origin: tuple[int, int], size: tuple[int, int], value: float, label: str) -> None:
    x, y = origin
    w, h = size
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (40, 40, 40), thickness=-1)
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (220, 220, 220), thickness=2)
    center_x = x + w // 2
    fill_x = int(center_x + np.clip(value, -1.0, 1.0) * (w // 2))
    left = min(center_x, fill_x)
    right = max(center_x, fill_x)
    cv2.rectangle(canvas, (left, y), (right, y + h), (60, 180, 255), thickness=-1)
    cv2.putText(
        canvas,
        f"{label}: {value:+.3f}",
        (x + 12, y + h - 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )


def _draw_history_plot(
    timestamps: Sequence[int | float],
    values: Sequence[float],
    side_px: int,
    ylabel: str,
) -> np.ndarray:
    fig = Figure(figsize=(side_px / 100.0, side_px / 100.0), dpi=100)
    fig.patch.set_facecolor("#121212")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#121212")

    if len(timestamps) >= 2 and len(values) >= 2:
        ax.plot(timestamps, values, color="#50dc78", linewidth=2.0)

    for spine in ax.spines.values():
        spine.set_color("#8a8a8a")
    ax.tick_params(colors="#ffffff", labelsize=7)
    ax.set_xlabel("timestamp", color="#ffffff", fontsize=8)
    ax.set_ylabel(ylabel, color="#ffffff", fontsize=8)
    ax.grid(color="#3a3a3a", linewidth=0.6, alpha=0.8)
    fig.subplots_adjust(left=0.22, right=0.96, bottom=0.20, top=0.94)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba(), dtype=np.uint8)
    return np.ascontiguousarray(rgba[..., :3])


def compose_video_frame(
    payload: dict[str, Any],
    timestamp_history: Sequence[int | float],
    speed_history: Sequence[float],
    angular_velocity_history: Sequence[float],
) -> np.ndarray:
    image = payload["image"]
    image_h, image_w = image.shape[:2]
    plot_side = image_h // 2
    output_w = image_w + plot_side

    left = image.copy()
    bar_height = max(44, image_h // 14)
    bar_margin = max(12, image_h // 40)
    bar_width = (image_w - bar_margin * 3) // 2
    bar_y = image_h - bar_margin - bar_height
    _draw_bar(left, (bar_margin, bar_y), (bar_width, bar_height), payload["steering"], "steering")
    _draw_bar(
        left,
        (bar_margin * 2 + bar_width, bar_y),
        (bar_width, bar_height),
        payload["throttle_brake"],
        "throttle_brake",
    )

    speed_plot = _draw_history_plot(timestamp_history, speed_history, plot_side, "speed")
    angular_plot = _draw_history_plot(timestamp_history, angular_velocity_history, plot_side, "angular_velocity")
    right = np.vstack([speed_plot, angular_plot])
    height_diff = image_h - right.shape[0]
    if height_diff > 0:
        pad = np.repeat(right[-1:], height_diff, axis=0)
        right = np.vstack([right, pad])
    elif height_diff < 0:
        right = right[:image_h]

    frame = np.zeros((image_h, output_w, 3), dtype=np.uint8)
    frame[:, :image_w] = left
    frame[:, image_w:] = right
    return frame


class VideoExporter:
    def __init__(
        self,
        history_size: int = 200,
        output_dir: str = "videos",
        fps: float = 40.0,
    ):
        self.history_size = int(history_size)
        self.output_dir = Path(output_dir)
        self.fps = float(fps)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp_history: list[int] = []
        self.speed_history: list[float] = []
        self.angular_velocity_history: list[float] = []
        self.episode_frames: list[np.ndarray] = []

    @property
    def has_frames(self) -> bool:
        return len(self.episode_frames) > 0

    def _append_history(self, container: list, value) -> None:
        container.append(value)
        if len(container) > self.history_size:
            del container[0]

    def draw(self, image: np.ndarray, states: dict[str, Any], info: Any, action: Sequence[float]) -> None:
        payload = extract_video_payload(image, states, info, action)
        self._append_history(self.timestamp_history, payload["timestamp"])
        self._append_history(self.speed_history, payload["speed"])
        self._append_history(self.angular_velocity_history, payload["angular_velocity"])
        frame = compose_video_frame(payload, self.timestamp_history, self.speed_history, self.angular_velocity_history)
        self.episode_frames.append(frame)

    def flush_episode(self, scene_name: str) -> None:
        if self.episode_frames:
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.output_dir / f"{current_time}_{scene_name}.mp4"
            image_list_to_video(str(output_path), self.episode_frames, code="mp4v", fps=self.fps)
            logger.info("Exported video for scene %s to %s.", scene_name, output_path)
        self.episode_frames.clear()
        self.timestamp_history.clear()
        self.speed_history.clear()
        self.angular_velocity_history.clear()

    def shutdown(self) -> None:
        return
