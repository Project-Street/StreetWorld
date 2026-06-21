#!/usr/bin/env python
"""
gRPC server for EasyDrive-style ScenarioEnv environment with browser WebUI.

This server wraps ScenarioEnv and exposes a gRPC interface
for remote reinforcement learning training. The WebUI is read-only.

Usage:
    python -m metadrive.examples.env_server_easydrive \\
        -c /path/to/scene_config_directory \\
        --host 0.0.0.0 \\
        --port 50052
"""

import argparse
import asyncio
import base64
import concurrent.futures
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import grpc
import numpy as np
from google.protobuf import struct_pb2

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.gaussian_obs import GaussianObservation
from metadrive.obs.observation_base import DefaultObservation, DummyObservation
from metadrive.utils.image_layout import compose_image_layout
from metadrive.gui.video_exporter import VideoExporter
from easydrive.models.scenes.simulator_interface import SimulatorInterface

try:
    import torch
except Exception:  # pragma: no cover - torch may be unavailable in lightweight runtime
    torch = None

# Import generated protobuf modules
import metadrive.grpc.streetworld_grpc.service_pb2 as service_pb2
import metadrive.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc
import metadrive.grpc.streetworld_grpc.common_pb2 as common_pb2


class WebUIState:
    def __init__(
        self,
        history_size: int = 200,
        jpeg_quality: int = 85,
        max_image_edge: int = 1200,
    ):
        self.history_size = int(history_size)
        self.jpeg_quality = int(jpeg_quality)
        self.max_image_edge = int(max_image_edge)
        self.timestamp_history: list[int] = []
        self.speed_history: list[float] = []
        self.angular_velocity_history: list[float] = []
        self._lock = threading.Lock()
        self._snapshot: Optional[dict[str, Any]] = None
        self._sequence = 0
        self._metrics: Optional[dict[str, dict[str, float]]] = None
        self._metrics_sequence = 0
        self._take_over_action: Optional[list[float]] = None

    def _append_history(self, container: list, value: Any) -> None:
        container.append(value)
        if len(container) > self.history_size:
            del container[0]

    def draw(self, image: np.ndarray, states: dict[str, Any], info: Any, action: Any) -> None:
        if len(action) != 2:
            raise ValueError(f"Expected action with length 2, got {len(action)}")

        velocity = np.asarray(states["linear_velocity"], dtype=np.float32).reshape(-1)
        if velocity.shape[0] < 2:
            raise ValueError(f"Expected linear_velocity with at least 2 values, got shape {velocity.shape}")
        angular_velocity = np.asarray(states["angular_velocity"], dtype=np.float32).reshape(-1)
        if angular_velocity.shape[0] < 3:
            raise ValueError(f"Expected angular_velocity with at least 3 values, got shape {angular_velocity.shape}")

        timestamp = int(info["relative_timestamp"])
        speed = float(np.linalg.norm(velocity[:2]))
        yaw_rate = float(angular_velocity[2])
        image = self._resize_image_for_webui(image)
        jpeg_quality = self.get_jpeg_quality()
        ok, encoded = cv2.imencode(
            ".jpg",
            cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
            [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
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
            return self._sequence, self._snapshot

    def metrics_snapshot(self) -> tuple[int, Optional[dict[str, dict[str, Any]]]]:
        with self._lock:
            if self._metrics is None:
                return self._metrics_sequence, None
            return self._metrics_sequence, {name: dict(values) for name, values in self._metrics.items()}

    def get_jpeg_quality(self) -> int:
        with self._lock:
            return self.jpeg_quality

    def update_jpeg_quality(self, send_elapsed_s: float, frame_interval_s: Optional[float]) -> None:
        if frame_interval_s is None or frame_interval_s <= 0.0:
            return
        ratio = send_elapsed_s / frame_interval_s
        with self._lock:
            if ratio > 1.0:
                self.jpeg_quality = max(30, int(self.jpeg_quality / ratio))
            elif ratio < 0.5:
                self.jpeg_quality = min(95, self.jpeg_quality + 1)

    def _resize_image_for_webui(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        max_edge = max(height, width)
        if max_edge <= self.max_image_edge:
            return image
        scale = self.max_image_edge / max_edge
        resized_size = (round(width * scale), round(height * scale))
        return cv2.resize(image, resized_size, interpolation=cv2.INTER_AREA)

    def set_policy_metric(self, metric: dict[str, float]) -> None:
        with self._lock:
            self._metrics = {"policy": {str(key): self._json_metric_value(value) for key, value in metric.items()}}
            self._metrics_sequence += 1

    def set_take_over_action(self, action: Optional[list[float]]) -> None:
        with self._lock:
            if action is None:
                self._take_over_action = None
                return
            if len(action) != 2:
                raise ValueError(f"Expected takeover action with length 2, got {len(action)}")
            self._take_over_action = [float(action[0]), float(action[1])]

    def get_take_over_action(self) -> Optional[list[float]]:
        with self._lock:
            if self._take_over_action is None:
                return None
            return list(self._take_over_action)

    def clear(self) -> None:
        with self._lock:
            self.timestamp_history.clear()
            self.speed_history.clear()
            self.angular_velocity_history.clear()
            self._snapshot = None
            self._sequence += 1
            self._metrics = None
            self._metrics_sequence += 1

    def flush_episode(self, _scene_name: str) -> None:
        with self._lock:
            self.timestamp_history.clear()
            self.speed_history.clear()
            self.angular_velocity_history.clear()

    def shutdown(self) -> None:
        return

    @staticmethod
    def _json_metric_value(value: Any) -> float | str:
        value = float(value)
        if np.isfinite(value):
            return value
        return str(value)


class EnvServicer(service_pb2_grpc.EnvServiceServicer):
    """
    gRPC service for ScenarioEnv environment.

    Provides Reset and Step RPCs for remote control.
    """

    def __init__(self, config: dict, video_output_dir: str):
        """
        Initialize servicer with environment configuration.

        Args:
            config: Environment configuration dict
        """
        self.config = config
        # Initialize model/env once and only reset episode state on Reset().
        self.model: SimulatorInterface = SimulatorInterface()
        self.env: ScenarioEnv = ScenarioEnv(self.model, self.config)
        video_fps = 1e6 / (
            float(self.env.config["physics_world_step_size"]) * float(self.env.config["decision_repeat"])
        )
        self.webui_state = WebUIState()
        self.video_exporter = VideoExporter(output_dir=video_output_dir, fps=video_fps)
        self._lock = threading.Lock()
        self._current_scene = None

    def Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse:
        """
        Reset the environment.

        Args:
            request: ResetRequest
            context: gRPC context

        Returns:
            ResetResponse with initial observation and reset info.
        """
        with self._lock:
            # Keep fields for protocol compatibility; they are ignored by easydrive server mode.
            _ = request
            if self.video_exporter.has_frames:
                self.video_exporter.flush_episode(str(self.env.scene_name))
            self.webui_state.clear()
            try:
                obs, reset_info = self.env.reset()
            except LookupError as exc:
                metric = self.env.get_average_metric()
                self.webui_state.set_policy_metric(metric)
                return service_pb2.ResetResponse(
                    status=True,
                    message=str(exc),
                    observation=common_pb2.Observation(),
                    StepInfo=self._dict_to_struct({"eval_done": True, "metric": metric}),
                )
            scene_name = str(self.env.scene_name)
            self._current_scene = scene_name
            reset_info = dict(reset_info) if isinstance(reset_info, dict) else {}
            reset_info.setdefault("scene_name", scene_name)

            return service_pb2.ResetResponse(
                status=False,
                message="",
                observation=self._serialize_observation(obs),
                StepInfo=self._dict_to_struct(reset_info)
            )

    def Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse:
        """
        Execute one environment step.

        Args:
            request: StepRequest with action array [steering, throttle]
            context: gRPC context

        Returns:
            StepResponse with reward, done flags, observation, and step info
        """
        with self._lock:
            if self.env is None:
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Environment not initialized. Call Reset first.")
                return service_pb2.StepResponse(
                    status=True,
                    message="Environment not initialized. Call Reset first.",
                    observation=common_pb2.Observation(),
                    reward=0.0,
                    terminated=False,
                    truncated=True,
                    StepInfo=self._dict_to_struct({})
                )

            # Extract action from request
            action = list(request.action)  # [steering, throttle]
            take_over_action = self.webui_state.get_take_over_action()
            if take_over_action is not None:
                action = take_over_action

            # Step environment
            obs, reward, terminated, truncated, info = self.env.step(action)
            image = compose_image_layout(obs["gaussian"]["image"], self.env.config["image_layout"])
            states = obs["states"]
            self.webui_state.draw(image=image, states=states, info=info, action=action)
            self.video_exporter.draw(image=image, states=states, info=info, action=action)
            if terminated or truncated:
                self.webui_state.flush_episode(str(self.env.scene_name))
                self.video_exporter.flush_episode(str(self.env.scene_name))
            return service_pb2.StepResponse(
                status=False,
                message="",
                observation=self._serialize_observation(obs),
                reward=float(reward),
                terminated=bool(terminated),
                truncated=bool(truncated),
                StepInfo=self._dict_to_struct(info)
            )


    def _serialize_observation(self, obs: Any) -> common_pb2.Observation:
        """
        Serialize environment observation to protobuf Observation.

        Rules:
        1) AssemblyObservation: gaussian -> images_observation, remaining dict -> other_observation
        2) GaussianObservation: gaussian -> images_observation
        3) Other observations: all payload -> other_observation
        4) Dummy/Default observations: raise error
        """
        observer = self.env.agent_managers["actor"].observer

        if isinstance(observer, AssemblyObservation):
            assembly_obs = dict(obs)
            gaussian_obs = assembly_obs.pop("gaussian")
            images = self._serialize_gaussian_images(gaussian_obs["image"], gaussian_obs["camera_info"])
            return common_pb2.Observation(
                images_observation=images,
                other_observation=self._dict_to_struct(assembly_obs),
            )

        if isinstance(observer, GaussianObservation):
            images = self._serialize_gaussian_images(obs["image"], obs["camera_info"])
            return common_pb2.Observation(images_observation=images)

        if isinstance(observer, (DummyObservation, DefaultObservation)):
            raise ValueError("DummyObservation and DefaultObservation are not supported in streetworld grpc mode.")

        return common_pb2.Observation(
            other_observation=self._dict_to_struct(obs),
        )

    def _serialize_gaussian_images(
        self,
        gaussian_images: Dict[str, np.ndarray],
        camera_info: Dict[str, Dict[str, Any]],
    ) -> List[common_pb2.CameraImage]:
        """
        Serialize gaussian observation image + camera_info to CameraImage.
        """
        images = []
        for cam_name, stacked in gaussian_images.items():
            frame = stacked[-1] if stacked.ndim == 4 else stacked
            images.append(
                common_pb2.CameraImage(
                    camera_name=cam_name,
                    image_data=frame.tobytes(),
                    camera_info=self._dict_to_struct(camera_info[cam_name]),
                )
            )
        return images

    def _to_builtin(self, value: Any) -> Any:
        """
        Convert nested numpy-containing structures to protobuf-Struct-compatible python types.
        """
        if isinstance(value, dict):
            return {str(k): self._to_builtin(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._to_builtin(v) for v in value]
        if isinstance(value, np.ndarray):
            return self._to_builtin(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        if torch is not None and isinstance(value, torch.Tensor):
            return self._to_builtin(value.detach().cpu().tolist())
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    def _dict_to_struct(self, data: Any) -> struct_pb2.Struct:
        """
        Convert arbitrary dict-like payload to protobuf Struct.
        """
        payload = self._to_builtin(data)
        if not isinstance(payload, dict):
            payload = {"__payload__": payload}
        struct = struct_pb2.Struct()
        struct.update(payload)
        return struct

    def close(self) -> None:
        if self.video_exporter.has_frames:
            self.video_exporter.flush_episode(str(self.env.scene_name))
        self.webui_state.shutdown()
        self.video_exporter.shutdown()
        self.env.close()


def create_web_app(webui_state: WebUIState):
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse
    from pydantic import BaseModel

    class TakeOverActionRequest(BaseModel):
        action: Optional[list[float]]

    app = FastAPI()
    index_path = Path(__file__).resolve().parents[1] / "gui" / "web" / "index.html"

    @app.get("/")
    async def index():
        return FileResponse(index_path, headers={"Cache-Control": "no-store"})

    @app.post("/take_over_action")
    async def take_over_action(request: TakeOverActionRequest):
        webui_state.set_take_over_action(request.action)
        return {"status": "ok"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        last_sequence = -1
        last_metrics_sequence = -1
        last_frame_send_started_at = time.perf_counter()
        waiting_sent = False
        try:
            while True:
                metrics_sequence, metrics = webui_state.metrics_snapshot()
                if metrics_sequence != last_metrics_sequence:
                    await websocket.send_json({"type": "metrics", "metrics": metrics})
                    last_metrics_sequence = metrics_sequence

                snapshot = webui_state.snapshot()
                if snapshot is None:
                    if not waiting_sent:
                        await websocket.send_json({"type": "waiting", "metrics": metrics})
                        waiting_sent = True
                    await asyncio.sleep(0.05)
                    continue

                waiting_sent = False
                sequence, payload = snapshot
                if sequence != last_sequence:
                    send_started_at = time.perf_counter()
                    frame_interval_s = send_started_at - last_frame_send_started_at
                    
                    await websocket.send_json({"type": "frame", "snapshot": payload})
                    webui_state.update_jpeg_quality(time.perf_counter() - send_started_at, frame_interval_s)
                    last_frame_send_started_at = send_started_at
                    last_sequence = sequence
                await asyncio.sleep(0.02)
        except WebSocketDisconnect:
            webui_state.set_take_over_action(None)
            return

    return app


def serve(
    scene_config_directory: str = "",
    random_scenario: bool = True,
    host: str = "0.0.0.0",
    port: int = 50052,
    web_host: str = "127.0.0.1",
    web_port: int = 8080,
    max_workers: int = 10,
    video_output_dir: str = "videos",
) -> None:
    """
    Start gRPC server.

    Args:
        scene_config_directory: Scenario config directory
        host: Server bind address
        port: Server port
        max_workers: Max concurrent RPC handlers
    """
    import uvicorn

    config = {
        "scene_config_directory": scene_config_directory,
        "random_scenario": random_scenario,
    }
    servicer = EnvServicer(config, video_output_dir=video_output_dir)
    app = create_web_app(servicer.webui_state)
    servicer.env.eval()

    server = grpc.server(
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ('grpc.max_send_message_length', 200 * 1024 * 1024),  # 200 MB
            ('grpc.max_receive_message_length', 200 * 1024 * 1024),
        ]
    )

    service_pb2_grpc.add_EnvServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"EasyDrive ScenarioEnv gRPC server started on {host}:{port}")
    print(f"EasyDrive WebUI started on http://{web_host}:{web_port}")
    print(f"Scene config directory: {scene_config_directory}")
    print(f"Image layout: {servicer.env.config['image_layout']}")
    print(f"Video output directory: {video_output_dir}")
    print("Press Ctrl+C to stop...")

    try:
        uvicorn.run(app, host=web_host, port=web_port)
    finally:
        server.stop(0)
        servicer.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="EasyDrive ScenarioEnv gRPC server with browser WebUI"
    )
    parser.add_argument(
        "-c", "--scene_config_directory",
        type=str,
        required=True,
        help="Scenario config directory"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server bind address (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="gRPC server port (default: 50052)"
    )
    parser.add_argument(
        "--web-host",
        type=str,
        default="127.0.0.1",
        help="WebUI bind address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="WebUI port (default: 8080)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Max concurrent RPC handlers (default: 10)"
    )
    parser.add_argument(
        "--ordered-scenario",
        action="store_true",
        help="Use ordered (sequential) scenarios instead of random sampling"
    )
    parser.add_argument(
        "--video-output-dir",
        type=str,
        default="videos",
        help="Directory for env video recordings (default: videos)"
    )
    args = parser.parse_args()

    if not os.path.isdir(args.scene_config_directory):
        print(f"Error: scene_config_directory not found: {args.scene_config_directory}")
        return 1

    serve(
        scene_config_directory=args.scene_config_directory,
        random_scenario=not args.ordered_scenario,
        host=args.host,
        port=args.port,
        web_host=args.web_host,
        web_port=args.web_port,
        max_workers=args.max_workers,
        video_output_dir=args.video_output_dir,
    )

    return 0


if __name__ == "__main__":
    exit(main())
