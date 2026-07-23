import asyncio
import base64
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import cv2
import numpy as np

from metadrive.configs.web_env_config import WEB_ENV_CONFIG
from metadrive.gui.video_exporter import VideoExporter
from metadrive.utils.image_layout import compose_image_layout


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


def make_web_env(env_class):
    class WebEnv(env_class):
        @classmethod
        def default_config(cls):
            config = super(WebEnv, cls).default_config()
            config.merge_from(WEB_ENV_CONFIG)
            return config

        def __init__(self, simulator_interface, config=None):
            super().__init__(simulator_interface, config)
            video_fps = 1e6 / (
                float(self.config["physics_world_step_size"]) * float(self.config["decision_repeat"])
            )
            self._video_exporter = VideoExporter(output_dir=self.config["video_output_dir"], fps=video_fps)
            self._web_host = self.config["web_host"]
            self._web_port = int(self.config["web_port"])
            self._history_size = int(self.config["history_size"])
            self._jpeg_quality = int(self.config["jpeg_quality"])
            self._max_image_edge = int(self.config["max_image_edge"])
            self._project_trajectory_on_camera = self.config["project_trajectory_on_camera"]
            self._timestamp_history: list[int] = []
            self._speed_history: list[float] = []
            self._angular_velocity_history: list[float] = []
            self._web_lock = threading.Lock()
            self._snapshot_data: Optional[dict[str, Any]] = None
            self._sequence = 0
            self._metrics: list[dict[str, Any]] = []
            self._take_over_action: Optional[list[float]] = None
            self._web_server = None
            self._web_thread = None
            if self.config["eval_mode"]:
                self.eval(order=self.config["eval_order"], repeat_per_scene=self.config["eval_repeat_per_scene"])
            print(f"Image layout: {self.config['image_layout']}")
            if self.config["start_web_server"]:
                self._start_web_server()

        def reset(self, *args, **kwargs):
            self._stop_async_step_loop()
            if self._video_exporter.has_frames:
                self._video_exporter.flush_episode(str(self.scene_id))
            with self._web_lock:
                self._timestamp_history.clear()
                self._speed_history.clear()
                self._angular_velocity_history.clear()
                self._snapshot_data = None
                self._sequence += 1
            return super().reset(*args, **kwargs)

        def _step(self, action):
            with self._web_lock:
                if self._take_over_action is not None:
                    action = list(self._take_over_action)

            obs, reward, terminated, truncated, info = super()._step(action)
            gaussian_obs = obs["gaussian"]
            image_stacks = self._with_projected_trajectory(gaussian_obs, action)
            image = compose_image_layout(image_stacks, self.config["image_layout"])
            states = obs["states"]
            self._draw_web_state(image=image, states=states, info=info, action=action)
            self._video_exporter.draw(image=image, states=states, info=info, action=action)
            if terminated or truncated:
                with self._web_lock:
                    if not self.data_manager.remain_queue:
                        self._metrics.append({"manual": self.get_average_metric()})
                    self._timestamp_history.clear()
                    self._speed_history.clear()
                    self._angular_velocity_history.clear()
                self._video_exporter.flush_episode(str(self.scene_id))
            return obs, reward, terminated, truncated, info

        def _with_projected_trajectory(self, gaussian_obs: Mapping[str, Any], action: Any) -> Mapping[str, np.ndarray]:
            if self._project_trajectory_on_camera is None or action is None:
                return gaussian_obs["image"]

            trajectory = np.asarray(action, dtype=np.float32)
            if trajectory.ndim == 1:
                return gaussian_obs["image"]
            if trajectory.ndim != 2 or trajectory.shape[1] != 2:
                raise ValueError(f"Trajectory must have shape (N, 2), got {trajectory.shape}")
            if len(trajectory) < 2:
                return gaussian_obs["image"]

            camera_name = self._project_trajectory_on_camera
            image_stacks = dict(gaussian_obs["image"])
            image_stack = np.array(image_stacks[camera_name], copy=True)
            _draw_projected_trajectory(image_stack[-1], trajectory, gaussian_obs["camera_info"][camera_name])
            image_stacks[camera_name] = image_stack
            return image_stacks

        def _draw_web_state(self, image: np.ndarray, states: dict[str, Any], info: Any, action: Any) -> None:
            steering = info["steering"]
            throttle_brake = info["throttle_brake"]

            velocity = np.asarray(states["linear_velocity"], dtype=np.float32).reshape(-1)
            if velocity.shape[0] < 2:
                raise ValueError(f"Expected linear_velocity with at least 2 values, got shape {velocity.shape}")
            angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32).reshape(-1)
            if angular_velocity.shape[0] < 3:
                raise ValueError(f"Expected angular_velocity with at least 3 values, got shape {angular_velocity.shape}")

            timestamp = int(info["relative_timestamp"])
            speed = float(np.linalg.norm(velocity[:2]))
            yaw_rate = float(angular_velocity[2])
            height, width = image.shape[:2]
            max_edge = max(height, width)
            if max_edge > self._max_image_edge:
                scale = self._max_image_edge / max_edge
                resized_size = (round(width * scale), round(height * scale))
                image = cv2.resize(image, resized_size, interpolation=cv2.INTER_AREA)
            with self._web_lock:
                jpeg_quality = self._jpeg_quality
            ok, encoded = cv2.imencode(
                ".jpg",
                cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
            )
            if not ok:
                raise RuntimeError("Failed to encode WebUI image as JPEG")

            with self._web_lock:
                self._timestamp_history.append(timestamp)
                self._speed_history.append(speed)
                self._angular_velocity_history.append(yaw_rate)
                if len(self._timestamp_history) > self._history_size:
                    del self._timestamp_history[0]
                    del self._speed_history[0]
                    del self._angular_velocity_history[0]
                self._sequence += 1
                self._snapshot_data = {
                    "image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
                    "timestamp": timestamp,
                    "steering": float(steering),
                    "throttle_brake": float(throttle_brake),
                    "speed": speed,
                    "angular_velocity": yaw_rate,
                    "timestamp_history": list(self._timestamp_history),
                    "speed_history": list(self._speed_history),
                    "angular_velocity_history": list(self._angular_velocity_history),
                }

        def _start_web_server(self) -> None:
            import uvicorn

            self._web_server = uvicorn.Server(
                uvicorn.Config(self._create_web_app(), host=self._web_host, port=self._web_port)
            )
            self._web_thread = threading.Thread(target=self._web_server.run, daemon=True)
            self._web_thread.start()
            print(f"EasyDrive WebUI started on http://{self._web_host}:{self._web_port}")

        def _create_web_app(self):
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.responses import FileResponse

            app = FastAPI()
            index_path = Path(__file__).resolve().parents[1] / "gui" / "web" / "index.html"

            @app.get("/")
            async def index():
                return FileResponse(index_path, headers={"Cache-Control": "no-store"})

            @app.post("/take_over_action")
            async def take_over_action(request: dict):
                action = request["action"]
                with self._web_lock:
                    if action is None:
                        self._take_over_action = None
                    else:
                        if len(action) != 2:
                            raise ValueError(f"Expected takeover action with length 2, got {len(action)}")
                        self._take_over_action = [float(action[0]), float(action[1])]
                return {"status": "ok"}

            @app.websocket("/ws")
            async def websocket_endpoint(websocket: WebSocket):
                await websocket.accept()
                last_sequence = -1
                last_frame_send_started_at = time.perf_counter()
                waiting_sent = False
                try:
                    while True:
                        with self._web_lock:
                            snapshot = None if self._snapshot_data is None else (self._sequence, self._snapshot_data)
                            metrics = self._metrics.pop(0) if self._metrics else None
                        if metrics is not None:
                            await websocket.send_json({"type": "metrics", "metrics": metrics})
                        if snapshot is None:
                            if not waiting_sent:
                                await websocket.send_json({"type": "waiting"})
                                waiting_sent = True
                            await asyncio.sleep(0.05)
                            continue

                        waiting_sent = False
                        sequence, payload = snapshot
                        if sequence != last_sequence:
                            send_started_at = time.perf_counter()
                            frame_interval_s = send_started_at - last_frame_send_started_at

                            await websocket.send_json({"type": "frame", "snapshot": payload})
                            if frame_interval_s > 0.0:
                                ratio = (time.perf_counter() - send_started_at) / frame_interval_s
                                with self._web_lock:
                                    if ratio > 1.0:
                                        self._jpeg_quality = max(30, int(self._jpeg_quality / ratio))
                                    elif ratio < 0.5:
                                        self._jpeg_quality = min(95, self._jpeg_quality + 1)
                            last_frame_send_started_at = send_started_at
                            last_sequence = sequence
                        await asyncio.sleep(0.02)
                except WebSocketDisconnect:
                    with self._web_lock:
                        self._take_over_action = None
                    return

            return app

        def close(self):
            self._stop_async_step_loop()
            if self._video_exporter.has_frames:
                self._video_exporter.flush_episode(str(self.scene_id))
            self._video_exporter.shutdown()
            if self._web_server is not None:
                self._web_server.should_exit = True
            if self._web_thread is not None and self._web_thread is not threading.current_thread():
                self._web_thread.join(timeout=5.0)
            super().close()

    WebEnv.__name__ = f"Web{env_class.__name__}"
    WebEnv.__qualname__ = WebEnv.__name__
    WebEnv.__module__ = __name__
    return WebEnv
