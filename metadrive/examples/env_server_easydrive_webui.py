#!/usr/bin/env python
"""
EasyDrive ScenarioEnv gRPC server with a browser WebUI.

Policy processes still drive the environment through the gRPC Reset/Step API.
The WebUI is read-only: it displays the same payload used by the existing GUI
without sending actions back to the simulator.

Usage:
    python -m metadrive.examples.env_server_easydrive_webui \
        -c /path/to/scene_config_directory \
        --port 8080
"""

import argparse
import asyncio
import base64
import concurrent.futures
import os
import threading
from pathlib import Path
from typing import Any, Optional

import cv2
import grpc
import numpy as np

from metadrive.examples.env_server_easydrive import EnvServicer as BaseEnvServicer
import metadrive.grpc.streetworld_grpc.common_pb2 as common_pb2
import metadrive.grpc.streetworld_grpc.service_pb2 as service_pb2
import metadrive.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc


class WebUILockGUI:
    """GUI-compatible shared state for the WebUI reader."""

    def __init__(self, image_key: str, history_size: int = 200, jpeg_quality: int = 85):
        self.image_key = image_key
        self.history_size = int(history_size)
        self.jpeg_quality = int(jpeg_quality)
        self.timestamp_history: list[int] = []
        self.speed_history: list[float] = []
        self.angular_velocity_history: list[float] = []
        self._lock = threading.Lock()
        self._snapshot: Optional[dict[str, Any]] = None
        self._sequence = 0
        self._metrics: Optional[dict[str, dict[str, float]]] = None
        self._metrics_sequence = 0

    def _append_history(self, container: list, value: Any) -> None:
        container.append(value)
        if len(container) > self.history_size:
            del container[0]

    def draw(self, obs: Any, info: Any, action: Any) -> None:
        if len(action) != 2:
            raise ValueError(f"Expected action with length 2, got {len(action)}")

        gaussian = obs["gaussian"]
        states = obs["states"]
        image_stack = gaussian["image"][self.image_key]
        if image_stack.ndim != 4 or image_stack.shape[0] <= 0:
            raise ValueError(f"Invalid image stack shape for {self.image_key}: {image_stack.shape}")

        image = self._ensure_uint8_rgb(image_stack[-1])
        velocity = np.asarray(states["linear_velocity"], dtype=np.float32).reshape(-1)
        if velocity.shape[0] < 2:
            raise ValueError(f"Expected linear_velocity with at least 2 values, got shape {velocity.shape}")
        angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32).reshape(-1)
        if angular_velocity.shape[0] < 3:
            raise ValueError(f"Expected angular_velocity with at least 3 values, got shape {angular_velocity.shape}")

        timestamp = int(info["relative_timestamp"])
        speed = float(np.linalg.norm(velocity[:2]))
        yaw_rate = float(angular_velocity[2])
        ok, encoded = cv2.imencode(
            ".jpg",
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if not ok:
            raise RuntimeError("Failed to encode WebUI image as JPEG")

        with self._lock:
            self._append_history(self.timestamp_history, timestamp)
            self._append_history(self.speed_history, speed)
            self._append_history(self.angular_velocity_history, yaw_rate)
            self._sequence += 1
            self._snapshot = {
                "image": "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii"),
                "timestamp": timestamp,
                "steering": float(action[0]),
                "throttle_brake": float(action[1]),
                "speed": speed,
                "angular_velocity": yaw_rate,
                "timestamp_history": list(self.timestamp_history),
                "speed_history": list(self.speed_history),
                "angular_velocity_history": list(self.angular_velocity_history),
            }

    def snapshot(self) -> Optional[tuple[int, dict[str, Any]]]:
        with self._lock:
            if self._snapshot is None:
                return None
            return self._sequence, dict(self._snapshot)

    def metrics_snapshot(self) -> tuple[int, Optional[dict[str, dict[str, Any]]]]:
        with self._lock:
            if self._metrics is None:
                return self._metrics_sequence, None
            return self._metrics_sequence, {name: dict(values) for name, values in self._metrics.items()}

    def set_policy_metric(self, metric: dict[str, float]) -> None:
        with self._lock:
            self._metrics = {"policy": {str(key): self._json_metric_value(value) for key, value in metric.items()}}
            self._metrics_sequence += 1

    def clear(self) -> None:
        with self._lock:
            self.timestamp_history.clear()
            self.speed_history.clear()
            self.angular_velocity_history.clear()
            self._snapshot = None
            self._sequence += 1
            self._metrics = None
            self._metrics_sequence += 1

    def flush_episode(self, scene_name: str) -> None:
        del scene_name
        with self._lock:
            self.timestamp_history.clear()
            self.speed_history.clear()
            self.angular_velocity_history.clear()

    def shutdown(self) -> None:
        return

    @staticmethod
    def _ensure_uint8_rgb(image: np.ndarray) -> np.ndarray:
        image = np.asarray(image)
        if image.dtype != np.uint8:
            image = np.clip(image, 0, 255).astype(np.uint8)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected RGB image with shape (H, W, 3), got {image.shape}")
        return np.ascontiguousarray(image)

    @staticmethod
    def _json_metric_value(value: Any) -> float | str:
        value = float(value)
        if np.isfinite(value):
            return value
        return str(value)


class EnvServicer(BaseEnvServicer):
    """Existing EasyDrive gRPC servicer with WebUILockGUI attached as env.gui."""

    def __init__(self, config: dict[str, Any], webui_lock: WebUILockGUI):
        super().__init__(config)
        self.webui_lock = webui_lock
        self.env.gui = self.webui_lock

    def Reset(self, request, context):
        self.webui_lock.clear()
        try:
            return super().Reset(request, context)
        except LookupError as exc:
            metric = self.env.get_average_metric()
            self.webui_lock.set_policy_metric(metric)
            return service_pb2.ResetResponse(
                status=True,
                message=str(exc),
                observation=common_pb2.Observation(),
                StepInfo=self._dict_to_struct({"eval_done": True, "metric": metric}),
            )

    def close(self) -> None:
        self.env.close()


def create_web_app(webui_lock: WebUILockGUI):
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse

    app = FastAPI()
    index_path = Path(__file__).resolve().parents[1] / "gui" / "web" / "index.html"

    @app.get("/")
    async def index():
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        last_sequence = -1
        last_metrics_sequence = -1
        waiting_sent = False
        try:
            while True:
                metrics_sequence, metrics = webui_lock.metrics_snapshot()
                if metrics_sequence != last_metrics_sequence:
                    await websocket.send_json({"type": "metrics", "metrics": metrics})
                    last_metrics_sequence = metrics_sequence

                snapshot = webui_lock.snapshot()
                if snapshot is None:
                    if not waiting_sent:
                        await websocket.send_json({"type": "waiting", "metrics": metrics})
                        waiting_sent = True
                    await asyncio.sleep(0.05)
                    continue

                waiting_sent = False
                sequence, payload = snapshot
                if sequence != last_sequence:
                    await websocket.send_json({"type": "frame", "snapshot": payload})
                    last_sequence = sequence
                await asyncio.sleep(0.02)
        except WebSocketDisconnect:
            return

    return app


def serve(
    scene_config_directory: str,
    random_scenario: bool = True,
    host: str = "0.0.0.0",
    grpc_port: int = 50052,
    web_host: str = "127.0.0.1",
    web_port: int = 8080,
    max_workers: int = 10,
    image_key: str = "FRONT",
) -> None:
    import uvicorn

    config = {
        "scene_config_directory": scene_config_directory,
        "random_scenario": random_scenario,
    }
    webui_lock = WebUILockGUI(image_key=image_key)
    app = create_web_app(webui_lock)
    servicer = EnvServicer(config=config, webui_lock=webui_lock)
    servicer.env.eval()
    
    grpc_server = grpc.server(
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_send_message_length", 200 * 1024 * 1024),
            ("grpc.max_receive_message_length", 200 * 1024 * 1024),
        ],
    )
    service_pb2_grpc.add_EnvServiceServicer_to_server(servicer, grpc_server)
    grpc_server.add_insecure_port(f"{host}:{grpc_port}")
    grpc_server.start()

    print(f"EasyDrive ScenarioEnv gRPC server started on {host}:{grpc_port}")
    print(f"EasyDrive WebUI started on http://{web_host}:{web_port}")
    print(f"Scene config directory: {scene_config_directory}")
    print(f"WebUI image key: {image_key}")
    print("Press Ctrl+C to stop...")

    try:
        uvicorn.run(app, host=web_host, port=web_port)
    finally:
        grpc_server.stop(0)
        servicer.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="EasyDrive ScenarioEnv gRPC server with browser WebUI")
    parser.add_argument(
        "-c",
        "--scene_config_directory",
        "--scene-config-directory",
        dest="scene_config_directory",
        type=str,
        required=True,
        help="Scenario config directory",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="gRPC server bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--grpc-port",
        type=int,
        default=50052,
        help="gRPC server port for the policy process (default: 50052; optional)",
    )
    parser.add_argument(
        "--web-host",
        type=str,
        default="127.0.0.1",
        help="WebUI bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="WebUI port (default: 8080)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Max concurrent gRPC handlers (default: 10)",
    )
    parser.add_argument(
        "--image-key",
        type=str,
        default="FRONT",
        help="GUI image key to stream (default: FRONT)",
    )
    parser.add_argument(
        "--ordered-scenario",
        action="store_true",
        help="Use ordered (sequential) scenarios instead of random sampling",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.scene_config_directory):
        print(f"Error: scene_config_directory not found: {args.scene_config_directory}")
        return 1

    serve(
        scene_config_directory=args.scene_config_directory,
        random_scenario=not args.ordered_scenario,
        host=args.host,
        grpc_port=args.grpc_port,
        web_host=args.web_host,
        web_port=args.port,
        max_workers=args.max_workers,
        image_key=args.image_key,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
