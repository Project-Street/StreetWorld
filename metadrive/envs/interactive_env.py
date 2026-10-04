from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from metadrive.configs.interactive_env_config import INTERACTIVE_ENV_CONFIG
from metadrive.ui.tui import TUI
from metadrive.ui.video_exporter import VideoExporter
from metadrive.ui.webui import WebUI


TRAJECTORY_HEIGHT_BELOW_EGO_M = 1.0
TRAJECTORY_COLOR_RGB = (64, 255, 64)


def _draw_projected_trajectory(image: np.ndarray, trajectory: np.ndarray, camera_info: Mapping[str, Any]) -> None:
    k = np.asarray(camera_info["K"], dtype=np.float32)
    if k.shape != (3, 3):
        raise ValueError(f"Camera K must be 3x3, got {k.shape}")
    e2c = np.asarray(camera_info["ego2camera"], dtype=np.float32)
    if e2c.shape != (4, 4):
        raise ValueError(f"Camera ego2camera must be 4x4, got {e2c.shape}")

    x_forward = trajectory[:, 0]
    y_left = trajectory[:, 1]
    z_up = np.full_like(x_forward, -TRAJECTORY_HEIGHT_BELOW_EGO_M)
    ego_points = np.stack([x_forward, y_left, z_up], axis=1)
    camera_points = (e2c[:3, :3] @ ego_points.T + e2c[:3, 3:4]).T
    camera_points = camera_points[camera_points[:, 2] > 1e-6]
    if not camera_points.size:
        return

    pixels = (k @ (camera_points / camera_points[:, 2:3]).T).T
    height, width = image.shape[:2]
    visible = (pixels[:, 0] >= 0) & (pixels[:, 0] < width) & (pixels[:, 1] >= 0) & (pixels[:, 1] < height)
    points = np.rint(pixels[visible, :2]).astype(np.int32)
    if not len(points):
        return
    for point in points:
        cv2.circle(image, tuple(point), radius=2, color=TRAJECTORY_COLOR_RGB, thickness=-1, lineType=cv2.LINE_AA)
    if len(points) > 1:
        cv2.polylines(image, [points], isClosed=False, color=TRAJECTORY_COLOR_RGB, thickness=2, lineType=cv2.LINE_AA)


def make_interactive_env(env_class):
    class InteractiveEnv(env_class):
        @classmethod
        def default_config(cls):
            config = super(InteractiveEnv, cls).default_config()
            config.merge_from(INTERACTIVE_ENV_CONFIG)
            return config

        def __init__(self, simulator_interface, config=None):
            super().__init__(simulator_interface, config)
            if self.config["tui"]:
                self._tui = TUI(self.config["scene_ids"])
            if self.config["video_output_dir"] is not None:
                video_fps = 1e6 / (
                    float(self.config["physics_world_step_size"]) * float(self.config["decision_repeat"])
                )
                self._video_exporter = VideoExporter(
                    output_dir=self.config["video_output_dir"],
                    fps=video_fps,
                    hud=self.config.get("video_hud", True),
                )
            if self.config["webui"]:
                self._web_ui = WebUI(
                    host=self.config["web_host"],
                    port=int(self.config["web_port"]),
                    history_size=int(self.config["history_size"]),
                    jpeg_quality=int(self.config["jpeg_quality"]),
                    max_image_edge=int(self.config["max_image_edge"]),
                )
            self._project_trajectory_on_camera = self.config["project_trajectory_on_camera"]
            if self.config["eval_mode"]:
                self.eval(order=self.config["eval_order"], repeat_per_scene=self.config["eval_repeat_per_scene"])

            if self.config["webui"]:
                self._web_ui.start()
            if self.config["tui"]:
                self._tui.start()

        def _reset(self, *args, **kwargs):
            if self.config["tui"]:
                self._tui.begin_reset()
            if self.config["video_output_dir"] is not None and self._video_exporter.has_frames:
                self._video_exporter.flush_episode(str(self.scene_id))
            if self.config["webui"]:
                self._web_ui.reset()
            try:
                obs, info = super()._reset(*args, **kwargs)
            except LookupError as error:
                if self.config["tui"] and str(error) == "No more scenarios to evaluate.":
                    self._tui.finish_evaluation()
                raise

            if self.config["tui"]:
                self._tui.record_reset(info, obs["states"])
            return obs, info

        def _step(self, action):
            if self.config["webui"]:
                action = self._web_ui.action_for_step(action)

            obs, reward, terminated, truncated, info = super()._step(action)
            if self.config["webui"] or self.config["tui"] or self.config["video_output_dir"] is not None:
                image_stacks = self._with_projected_trajectory(obs["gaussian"], action)
                image = self._compose_image_layout(image_stacks, self.config["image_layout"])
                payload = self._extract_video_payload(image, obs["states"], info)
                if self.config["webui"]:
                    self._web_ui.publish(payload)
                if self.config["video_output_dir"] is not None:
                    self._video_exporter.draw_payload(payload)
                if self.config["tui"]:
                    self._tui.record_step(
                        info=info,
                        payload=payload,
                        terminated=bool(terminated),
                        truncated=bool(truncated),
                    )
            if terminated or truncated:
                if self.config["tui"]:
                    self._tui.complete_episode(self.metric_tracker)
                if self.config["webui"]:
                    self._web_ui.complete_episode(self.get_average_metric() if not self.data_manager.remain_queue else None)
                if self.config["video_output_dir"] is not None:
                    self._video_exporter.flush_episode(str(self.scene_id))
            return obs, reward, terminated, truncated, info

        @staticmethod
        def _compose_image_layout(
            image_stacks: Mapping[str, np.ndarray],
            layout: Sequence[Sequence[str]],
            pad_value: int = 0,
        ) -> np.ndarray:
            flat_names = [camera_name for row in layout for camera_name in row]
            if not flat_names:
                raise ValueError("image layout must contain at least one camera name")

            images = {}
            for camera_name in flat_names:
                image_stack = np.asarray(image_stacks[camera_name])
                if image_stack.ndim != 4 or image_stack.shape[0] <= 0:
                    raise ValueError(f"Invalid image stack shape for {camera_name}: {image_stack.shape}")
                image = image_stack[-1]
                if image.dtype != np.uint8:
                    image = np.clip(image, 0, 255).astype(np.uint8)
                if image.ndim != 3 or image.shape[2] != 3:
                    raise ValueError(f"Expected RGB image with shape (H, W, 3), got {image.shape}")
                images[camera_name] = np.ascontiguousarray(image)

            max_h = max(image.shape[0] for image in images.values())
            max_w = max(image.shape[1] for image in images.values())
            max_cols = max(len(row) for row in layout)
            if max_cols <= 0:
                raise ValueError("image layout rows must not be empty")

            canvas = np.full((max_h * len(layout), max_w * max_cols, 3), int(pad_value), dtype=np.uint8)
            for row_idx, row in enumerate(layout):
                if not row:
                    raise ValueError("image layout rows must not be empty")
                row_offset_x = ((max_cols - len(row)) * max_w) // 2
                for col_idx, camera_name in enumerate(row):
                    image = images[camera_name]
                    h, w = image.shape[:2]
                    cell_x = row_offset_x + col_idx * max_w
                    cell_y = row_idx * max_h
                    x = cell_x + (max_w - w) // 2
                    y = cell_y + (max_h - h) // 2
                    canvas[y:y + h, x:x + w] = image
            return canvas

        @staticmethod
        def _extract_video_payload(
            image: np.ndarray,
            states: dict[str, Any],
            info: Mapping[str, Any],
        ) -> dict[str, Any]:
            return {
                "image": image,
                "timestamp": info["relative_timestamp"],
                "steering": info["steering"],
                "throttle_brake": info["throttle_brake"],
                "speed": states["ego_velo"],
                "angular_velocity": states["angular_velocity"][2],
            }

        def _with_projected_trajectory(self, gaussian_obs: Mapping[str, Any], action: Any) -> Mapping[str, np.ndarray]:
            if self._project_trajectory_on_camera is None or action is None:
                return gaussian_obs["image"]

            trajectory = np.asarray(action, dtype=np.float32)

            camera_name = self._project_trajectory_on_camera
            image_stacks = dict(gaussian_obs["image"])
            image_stack = np.array(image_stacks[camera_name], copy=True)
            _draw_projected_trajectory(image_stack[-1], trajectory, gaussian_obs["camera_info"][camera_name])
            image_stacks[camera_name] = image_stack
            return image_stacks

        def _close(self):
            if self.config["tui"]:
                self._tui.close()
            if self.config["video_output_dir"] is not None:
                if self._video_exporter.has_frames:
                    self._video_exporter.flush_episode(str(self.scene_id))
                self._video_exporter.shutdown()
            if self.config["webui"]:
                self._web_ui.close()
            super()._close()

    InteractiveEnv.__name__ = f"Interactive{env_class.__name__}"
    InteractiveEnv.__qualname__ = InteractiveEnv.__name__
    InteractiveEnv.__module__ = __name__
    return InteractiveEnv
