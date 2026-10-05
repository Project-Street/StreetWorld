from __future__ import annotations

from typing import Any, Iterable, Sequence

import cv2
import grpc
import numpy as np

from submodules.nurec_interface.nre.grpc.protos import common_pb2, sensorsim_pb2, sensorsim_pb2_grpc


class NurecOfficialGrpcClient:
    max_message_length = 256 * 1024 * 1024

    def __init__(self, host: str = "localhost", port: int = 8080, timeout_s: float = 120.0) -> None:
        self._timeout_s = float(timeout_s)
        options = (
            ("grpc.enable_http_proxy", 0),
            ("grpc.max_send_message_length", self.max_message_length),
            ("grpc.max_receive_message_length", self.max_message_length),
        )
        self._channel = grpc.insecure_channel(f"{host}:{int(port)}", options=options)
        self._stub = sensorsim_pb2_grpc.SensorsimServiceStub(self._channel)

    @staticmethod
    def _pinhole_camera_spec(
        camera_name: str,
        K: np.ndarray,
        height: int,
        width: int,
    ) -> sensorsim_pb2.CameraSpec:
        return sensorsim_pb2.CameraSpec(
            logical_id=str(camera_name),
            resolution_h=int(height),
            resolution_w=int(width),
            shutter_type=sensorsim_pb2.GLOBAL,
            opencv_pinhole_param=sensorsim_pb2.OpenCVPinholeCameraParam(
                principal_point_x=float(K[0, 2]),
                principal_point_y=float(K[1, 2]),
                focal_length_x=float(K[0, 0]),
                focal_length_y=float(K[1, 1]),
                radial_coeffs=[0.0] * 6,
                tangential_coeffs=[0.0] * 2,
                thin_prism_coeffs=[0.0] * 4,
            ),
        )

    @staticmethod
    def _ftheta_camera_spec(extra: dict) -> sensorsim_pb2.CameraSpec:
        if extra["type"] != "ftheta":
            raise ValueError(f"extra.type must be 'ftheta', got: {extra['type']}")
        params = extra["parameters"]
        cx, cy = params["principal_point"]
        reference_poly = {
            "PIXELDIST_TO_ANGLE": sensorsim_pb2.FthetaCameraParam.PIXELDIST_TO_ANGLE,
            "ANGLE_TO_PIXELDIST": sensorsim_pb2.FthetaCameraParam.ANGLE_TO_PIXELDIST,
        }[params["reference_poly"]]
        ftheta_param = sensorsim_pb2.FthetaCameraParam(
            principal_point_x=float(cx),
            principal_point_y=float(cy),
            reference_poly=reference_poly,
            pixeldist_to_angle_poly=[float(v) for v in params["pixeldist_to_angle_poly"]],
            angle_to_pixeldist_poly=[float(v) for v in params["angle_to_pixeldist_poly"]],
            max_angle=float(params["max_angle"]),
        )
        if params.get("linear_cde") is not None:
            linear_cde = params["linear_cde"]
            if len(linear_cde) != 3:
                raise ValueError(f"ftheta linear_cde must have 3 values, got {len(linear_cde)}")
            ftheta_param.linear_cde.CopyFrom(
                sensorsim_pb2.LinearCde(
                    linear_c=float(linear_cde[0]),
                    linear_d=float(linear_cde[1]),
                    linear_e=float(linear_cde[2]),
                )
            )
        camera_kwargs = {}
        intrinsics_width, intrinsics_height = params["resolution"]
        if params.get("external_distortion_parameters") is not None:
            distortion_params = params["external_distortion_parameters"]
            distortion_reference_poly = {
                "FORWARD": sensorsim_pb2.BivariateWindshieldModelParameters.FORWARD,
                "BACKWARD": sensorsim_pb2.BivariateWindshieldModelParameters.BACKWARD,
            }[distortion_params["reference_poly"]]
            camera_kwargs["bivariate_windshield_model_param"] = sensorsim_pb2.BivariateWindshieldModelParameters(
                reference_poly=distortion_reference_poly,
                horizontal_poly=[float(v) for v in distortion_params["horizontal_poly"]],
                vertical_poly=[float(v) for v in distortion_params["vertical_poly"]],
                horizontal_poly_inverse=[float(v) for v in distortion_params["horizontal_poly_inverse"]],
                vertical_poly_inverse=[float(v) for v in distortion_params["vertical_poly_inverse"]],
            )
        return sensorsim_pb2.CameraSpec(
            logical_id=str(extra["logical_id"]),
            resolution_h=int(intrinsics_height),
            resolution_w=int(intrinsics_width),
            shutter_type=sensorsim_pb2.GLOBAL,
            ftheta_param=ftheta_param,
            **camera_kwargs,
        )

    def render_batch_rgb(
        self,
        *,
        scene_id: str,
        cameras: Sequence[dict[str, Any]],
        timestamp_us: int,
        dynamic_objects: Iterable[sensorsim_pb2.DynamicObject],
    ) -> list[np.ndarray]:
        dynamic_objects = list(dynamic_objects)
        items = []
        for camera in cameras:
            height = int(camera["height"])
            width = int(camera["width"])
            extra = camera["extra"]
            camera_name = str(camera["camera_name"])
            if extra is None:
                camera_intrinsics = self._pinhole_camera_spec(camera_name, camera["K"], height, width)
            elif extra.get("type") == "ftheta":
                camera_intrinsics = self._ftheta_camera_spec(extra)
            elif extra.get("type") in (None, "pinhole"):
                camera_intrinsics = self._pinhole_camera_spec(camera_name, camera["K"], height, width)
            else:
                raise ValueError(f"Unsupported camera extra.type: {extra['type']}")
            request = sensorsim_pb2.RGBRenderRequest(
                scene_id=str(scene_id),
                resolution_h=height,
                resolution_w=width,
                camera_intrinsics=camera_intrinsics,
                frame_start_us=int(timestamp_us),
                frame_end_us=int(timestamp_us) + 1,
                sensor_pose=sensorsim_pb2.PosePair(
                    start_pose=camera["sensor_pose"], end_pose=camera["sensor_pose"]
                ),
                dynamic_objects=dynamic_objects,
                image_format=sensorsim_pb2.JPEG,
                image_quality=95.0,
                insert_ego_mask=False,
            )
            items.append(sensorsim_pb2.BatchRGBRenderRequestItem(camera_name=camera_name, request=request))

        response = self._stub.batch_render_rgb(
            sensorsim_pb2.BatchRGBRenderRequest(items=items),
            timeout=self._timeout_s,
        )
        return [
            self._decode_rgb(item.result.image_bytes, camera["height"], camera["width"])
            for item, camera in zip(response.items, cameras)
        ]

    @staticmethod
    def _decode_rgb(image_bytes: bytes, height: int, width: int) -> np.ndarray:
        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("NuRec render_rgb returned undecodable image bytes")
        expected_shape = (int(height), int(width), 3)
        if bgr.shape != expected_shape:
            raise ValueError(f"NuRec render_rgb returned shape {bgr.shape}, expected {expected_shape}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return rgb

    @staticmethod
    def pose_pair_from_matrix(matrix: np.ndarray) -> sensorsim_pb2.PosePair:
        pose = NurecOfficialGrpcClient.pose_from_matrix(matrix)
        return sensorsim_pb2.PosePair(start_pose=pose, end_pose=pose)

    @staticmethod
    def dynamic_object_from_matrix(track_id: str, matrix: np.ndarray) -> sensorsim_pb2.DynamicObject:
        return sensorsim_pb2.DynamicObject(
            track_id=str(track_id),
            pose_pair=NurecOfficialGrpcClient.pose_pair_from_matrix(matrix),
        )

    @staticmethod
    def pose_from_matrix(matrix: np.ndarray) -> common_pb2.Pose:
        mat = np.asarray(matrix, dtype=np.float64)
        if mat.shape != (4, 4):
            raise ValueError(f"Pose matrix must have shape (4, 4), got {mat.shape}")
        quat = _rotation_matrix_to_quat_wxyz(mat[:3, :3])
        return common_pb2.Pose(
            vec=common_pb2.Vec3(
                x=float(mat[0, 3]),
                y=float(mat[1, 3]),
                z=float(mat[2, 3]),
            ),
            quat=common_pb2.Quat(
                w=float(quat[0]),
                x=float(quat[1]),
                y=float(quat[2]),
                z=float(quat[3]),
            ),
        )

    def close(self) -> None:
        if self._channel is None:
            return
        self._channel.close()
        self._channel = None
        self._stub = None


def _rotation_matrix_to_quat_wxyz(rotation: np.ndarray) -> np.ndarray:
    rot = np.asarray(rotation, dtype=np.float64)
    trace = float(np.trace(rot))
    if trace > 0.0:
        scale = np.sqrt(trace + 1.0) * 2.0
        quat = np.array(
            [
                0.25 * scale,
                (rot[2, 1] - rot[1, 2]) / scale,
                (rot[0, 2] - rot[2, 0]) / scale,
                (rot[1, 0] - rot[0, 1]) / scale,
            ],
            dtype=np.float64,
        )
    elif rot[0, 0] > rot[1, 1] and rot[0, 0] > rot[2, 2]:
        scale = np.sqrt(1.0 + rot[0, 0] - rot[1, 1] - rot[2, 2]) * 2.0
        quat = np.array(
            [
                (rot[2, 1] - rot[1, 2]) / scale,
                0.25 * scale,
                (rot[0, 1] + rot[1, 0]) / scale,
                (rot[0, 2] + rot[2, 0]) / scale,
            ],
            dtype=np.float64,
        )
    elif rot[1, 1] > rot[2, 2]:
        scale = np.sqrt(1.0 + rot[1, 1] - rot[0, 0] - rot[2, 2]) * 2.0
        quat = np.array(
            [
                (rot[0, 2] - rot[2, 0]) / scale,
                (rot[0, 1] + rot[1, 0]) / scale,
                0.25 * scale,
                (rot[1, 2] + rot[2, 1]) / scale,
            ],
            dtype=np.float64,
        )
    else:
        scale = np.sqrt(1.0 + rot[2, 2] - rot[0, 0] - rot[1, 1]) * 2.0
        quat = np.array(
            [
                (rot[1, 0] - rot[0, 1]) / scale,
                (rot[0, 2] + rot[2, 0]) / scale,
                (rot[1, 2] + rot[2, 1]) / scale,
                0.25 * scale,
            ],
            dtype=np.float64,
        )
    norm = np.linalg.norm(quat)
    if norm == 0.0:
        raise ValueError("Rotation matrix produced a zero-length quaternion")
    return quat / norm
