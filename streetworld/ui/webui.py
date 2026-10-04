from __future__ import annotations

import asyncio
import base64
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

import cv2
from fastapi import WebSocket


class WebUI:
    def __init__(
        self,
        host: str,
        port: int,
        history_size: int,
        jpeg_quality: int,
        max_image_edge: int,
    ) -> None:
        self._host = host
        self._port = port
        self._history_size = history_size
        self._jpeg_quality = jpeg_quality
        self._max_image_edge = max_image_edge
        self._lock = threading.Lock()
        self._timestamp_history: list[int] = []
        self._speed_history: list[float] = []
        self._angular_velocity_history: list[float] = []
        self._snapshot_data: Optional[dict[str, Any]] = None
        self._sequence = 0
        self._metrics: list[dict[str, Any]] = []
        self._take_over_action: Optional[list[float]] = None
        self._server = None
        self._thread = None

    def start(self) -> None:
        import uvicorn

        self._server = uvicorn.Server(uvicorn.Config(self._create_app(), host=self._host, port=self._port))
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        print(f"EasyDrive WebUI started on http://{self._host}:{self._port}")

    def reset(self) -> None:
        with self._lock:
            self._timestamp_history.clear()
            self._speed_history.clear()
            self._angular_velocity_history.clear()
            self._snapshot_data = None
            self._sequence += 1

    def action_for_step(self, action: Any) -> Any:
        with self._lock:
            take_over_action = self._take_over_action
            self._take_over_action = None
            return list(take_over_action) if take_over_action is not None else action

    def publish(self, payload: dict[str, Any]) -> None:
        image = payload["image"]
        angular_velocity = float(payload["angular_velocity"])
        height, width = image.shape[:2]
        max_edge = max(height, width)
        if max_edge > self._max_image_edge:
            scale = self._max_image_edge / max_edge
            image = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        with self._lock:
            jpeg_quality = self._jpeg_quality
        ok, encoded = cv2.imencode(
            ".jpg",
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
        )
        if not ok:
            raise RuntimeError("Failed to encode WebUI image as JPEG")

        with self._lock:
            self._timestamp_history.append(payload["timestamp"])
            self._speed_history.append(payload["speed"])
            self._angular_velocity_history.append(angular_velocity)
            if len(self._timestamp_history) > self._history_size:
                del self._timestamp_history[0]
                del self._speed_history[0]
                del self._angular_velocity_history[0]
            self._sequence += 1
            self._snapshot_data = {
                "image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
                "timestamp": payload["timestamp"],
                "steering": payload["steering"],
                "throttle_brake": payload["throttle_brake"],
                "speed": payload["speed"],
                "angular_velocity": angular_velocity,
                "timestamp_history": list(self._timestamp_history),
                "speed_history": list(self._speed_history),
                "angular_velocity_history": list(self._angular_velocity_history),
            }

    def complete_episode(self, aggregate_metrics: Mapping[str, float] | None) -> None:
        with self._lock:
            if aggregate_metrics is not None:
                self._metrics.append({"manual": aggregate_metrics})
            self._timestamp_history.clear()
            self._speed_history.clear()
            self._angular_velocity_history.clear()

    def close(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=5.0)

    def _set_take_over_action(self, action: Any) -> None:
        with self._lock:
            if action is None:
                self._take_over_action = None
                return
            if len(action) != 2:
                raise ValueError(f"Expected takeover action with length 2, got {len(action)}")
            self._take_over_action = [float(action[0]), float(action[1])]

    def _create_app(self):
        from fastapi import FastAPI, WebSocketDisconnect
        from fastapi.responses import FileResponse

        app = FastAPI()
        index_path = Path(__file__).resolve().parent / "web" / "index.html"

        @app.get("/")
        async def index():
            return FileResponse(index_path, headers={"Cache-Control": "no-store"})

        @app.post("/take_over_action")
        async def take_over_action(request: dict):
            self._set_take_over_action(request["action"])
            return {"status": "ok"}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            last_sequence = -1
            last_frame_send_started_at = time.perf_counter()
            waiting_sent = False
            try:
                while True:
                    with self._lock:
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
                            with self._lock:
                                if ratio > 1.0:
                                    self._jpeg_quality = max(30, int(self._jpeg_quality / ratio))
                                elif ratio < 0.5:
                                    self._jpeg_quality = min(95, self._jpeg_quality + 1)
                        last_frame_send_started_at = send_started_at
                        last_sequence = sequence
                    await asyncio.sleep(0.02)
            except WebSocketDisconnect:
                self._set_take_over_action(None)
                return

        return app
