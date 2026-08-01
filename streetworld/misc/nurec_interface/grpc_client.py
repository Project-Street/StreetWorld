from __future__ import annotations

from typing import Any, Dict, Optional

import grpc

from .simple_nurec_grpc import render_pb2, render_pb2_grpc


class NurecGrpcClient:
    max_message_length = 256 * 1024 * 1024  # 256 MB
    def __init__(self, host: str = "localhost", port: int = 50051, timeout_s: float = 120.0) -> None:
        self._timeout_s = timeout_s
        target = f"{host}:{port}"
        options = (
            ("grpc.enable_http_proxy", 0),
            
            ("grpc.max_send_message_length", self.max_message_length),
            ("grpc.max_receive_message_length", self.max_message_length),
            
        )
        self._channel = grpc.insecure_channel(target, options=options)
        self._stub = render_pb2_grpc.RenderServiceStub(self._channel)

    def render(
        self,
        camera_to_world: list[float],
        fx: float,
        fy: float,
        cx: float,
        cy: float,
        width: int,
        height: int,
        camera_model: Optional[str] = None,
        ftheta_params: Optional[Dict[str, Any]] = None,
        time_s: Optional[float] = None,
    ) -> render_pb2.RenderResponse:
        camera_kwargs: Dict[str, Any] = {
            "camera_to_world": camera_to_world,
            "fx": float(fx),
            "fy": float(fy),
            "cx": float(cx),
            "cy": float(cy),
            "width": int(width),
            "height": int(height),
        }
        if time_s is not None:
            camera_kwargs["time"] = float(time_s)
        if camera_model:
            camera_kwargs["camera_model"] = camera_model
        if ftheta_params:
            camera_kwargs["ftheta_params"] = render_pb2.FThetaParams(
                reference_poly=ftheta_params.get("reference_poly", ""),
                pixeldist_to_angle_poly=ftheta_params.get("pixeldist_to_angle_poly", []),
                angle_to_pixeldist_poly=ftheta_params.get("angle_to_pixeldist_poly", []),
                max_angle=float(ftheta_params.get("max_angle", 0.0)),
                linear_cde=ftheta_params.get("linear_cde", []),
            )
        request = render_pb2.RenderRequest(camera=render_pb2.CameraParams(**camera_kwargs))
        return self._stub.Render(request, timeout=self._timeout_s)

    def set_traffic_pose(self, tracks_id: list[str], poses_4x4: list[float]) -> render_pb2.TrafficPoseResponse:
        request = render_pb2.TrafficPoseRequest(
            tracks_id=[str(track_id) for track_id in tracks_id],
            poses_4x4=poses_4x4,
        )
        return self._stub.SetTrafficPose(request, timeout=self._timeout_s)

    def load_model(self, ckpt_path: str) -> render_pb2.LoadModelResponse:
        request = render_pb2.LoadModelRequest(ckpt_path=str(ckpt_path))
        return self._stub.LoadModel(request, timeout=self._timeout_s)

    def close(self) -> None:
        if self._channel is None:
            return
        self._channel.close()
        self._channel = None
        self._stub = None
