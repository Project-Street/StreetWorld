"""
Utility functions for parsing StreetStudio format (transforms.json).

This module provides functions to convert StreetStudio data format
to the format required by StreetWorld ScenarioDataManager.
"""

import numpy as np
from scipy.spatial.transform import Rotation
from typing import Union


class SceneTransform:
    """3D scene transformation helper for coordinate system conversion.

    Handles transformations between normalized dataset coordinates and real-world coordinates.
    The transformation order is: [origin] -> rotation -> translation -> scaling -> [target].
    """

    def __init__(self, rotation: Union[list, np.ndarray], translation: Union[list, np.ndarray], scaling: float):
        """
        Initialize SceneTransform.

        Args:
            rotation: 3x3 rotation matrix
            translation: 3D translation vector
            scaling: uniform scaling factor
        """
        self.rotation = np.array(rotation, dtype=np.float32)
        self.translation = np.array(translation, dtype=np.float32)
        self.scaling = float(scaling)
        self.inv_rotation = np.linalg.inv(self.rotation)

    def apply_position(self, position, reverse: bool = False):
        """Transform 3D positions.

        Args:
            position: Position array of shape (..., 3).
            reverse: If True, apply inverse transformation. Default is False.

        Returns:
            Transformed positions with same shape as input.
        """
        if reverse:
            position = position / self.scaling
            position = (position - self.translation) @ self.inv_rotation.T
        else:
            position = position @ self.rotation.T + self.translation
            position = position * self.scaling
        return position

    def apply_vector(self, vec, reverse: bool = False):
        """Transform 3D vectors (no translation applied).

        Args:
            vec: Vector array of shape (..., 3).
            reverse: If True, apply inverse transformation. Default is False.

        Returns:
            Transformed vectors with same shape as input.
        """
        if reverse:
            vec = vec @ self.inv_rotation.T / self.scaling
        else:
            vec = vec @ self.rotation.T * self.scaling
        return vec

    def apply_extrinsic(self, extrinsic, reverse: bool = False):
        """Transform extrinsic camera matrices.

        Applies transformation to both rotation and translation components,
        keeping the matrix orthonormal.

        Args:
            extrinsic: Extrinsic matrix or batch of matrices, shape (..., 4, 4).
            reverse: If True, apply inverse transformation. Default is False.

        Returns:
            Transformed extrinsic matrix with same shape as input.
        """
        # Extract rotation and translation from extrinsic matrix
        R = extrinsic[..., :3, :3]
        t = extrinsic[..., :3, 3]

        # Apply transformations using existing methods
        # For rotation matrix: apply vector transformation to each column, then normalize
        R_new = self.apply_vector(R, reverse=reverse)
        R_new = R_new / np.linalg.norm(R_new, axis=-2, keepdims=True)

        # For translation vector: apply position transformation directly
        t_new = self.apply_position(t, reverse=reverse)

        # Construct new extrinsic matrix with same shape as input
        extrinsic_new = extrinsic.copy()
        extrinsic_new[..., :3, :3] = R_new
        extrinsic_new[..., :3, 3] = t_new
        return extrinsic_new


def quat_trans_to_matrix(quaternion, translation):
    """Convert quaternion (w,x,y,z) and translation to 4x4 transform matrix

    Args:
        quaternion: list or array of [w, x, y, z] (scalar-first format)
        translation: list or array of [x, y, z]

    Returns:
        4x4 numpy array transformation matrix
    """
    rot = Rotation.from_quat(quaternion, scalar_first=True).as_matrix()
    matrix = np.eye(4)
    matrix[:3, :3] = rot
    matrix[:3, 3] = translation
    return matrix


def sec_to_us(timestamp_sec):
    """Convert seconds to microseconds (integer)

    Args:
        timestamp_sec: float, timestamp in seconds

    Returns:
        int, timestamp in microseconds
    """
    return int(timestamp_sec * 1_000_000)


def us_to_sec(timestamp_us):
    """Convert microseconds to seconds (float)

    Args:
        timestamp_us: int, timestamp in microseconds

    Returns:
        float, timestamp in seconds
    """
    return timestamp_us / 1_000_000.0


def parse_instances_data(instances_data):
    """Parse instances_data from transforms.json into tracking_data format

    Args:
        instances_data: dict from transforms.json, format:
            {
                uid: {
                    "is_rigid": bool,
                    "size": [l, w, h],
                    "traj_data": {
                        "timestamps": [ts1, ts2, ...],
                        "translations": {ts: [x, y, z]},
                        "quaternions": {ts: [w, x, y, z]}
                    }
                }
            }

    Returns:
        tracking_data: dict format:
            {
                uid: {
                    "size": [l, w, h],
                    "type": "vehicle" | "pedestrian",
                    "poses": {us: 4x4_matrix}
                }
            }
    """
    tracking_data = {}
    for uid, data in instances_data.items():
        tracking_data[uid] = {
            "size": data["size"],
            "type": "vehicle" if data["is_rigid"] else "pedestrian",
            "poses": {},
        }

        traj = data["traj_data"]
        for ts in traj["timestamps"]:
            # Convert timestamp to string for dict lookup (JSON keys are strings)
            ts_key = str(ts)
            trans = traj["translations"][ts_key]
            quat = traj["quaternions"][ts_key]
            tracking_data[uid]["poses"][sec_to_us(ts)] = quat_trans_to_matrix(quat, trans)

    return tracking_data


class GRPCRenderClient:
    """gRPC client for remote StreetStudio rendering.

    This client handles communication with a remote gRPC rendering server,
    including coordinate transformation (real -> normalized) and time scaling.
    """

    def __init__(self, server_url: str, dataset_transforms: dict):
        """
        Initialize gRPC render client.

        Args:
            server_url: gRPC server address (e.g., "localhost:50051")
            dataset_transforms: dict with 'rotation', 'translation', 'scaling' keys
        """
        self.server_url = server_url
        self.transform = SceneTransform(**dataset_transforms)
        self._channel = None
        self._stub = None

    def _get_stub(self):
        """Lazy load gRPC stub."""
        if self._stub is None:
            import grpc
            from streetstudio_grpc import render_pb2_grpc

            # Increase max receive message size to 100MB to handle large images
            self._channel = grpc.insecure_channel(
                self.server_url,
                options=[
                    ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                ],
            )
            self._stub = render_pb2_grpc.RenderServiceStub(self._channel)
        return self._stub

    def render(self, K, H, W, extrinsics, timestamp_us: int = 0):
        """
        Render via gRPC.

        Args:
            K: 3x3 camera intrinsic matrix (torch.Tensor or np.ndarray)
            H: image height (int)
            W: image width (int)
            extrinsics: 4x4 camera-to-world matrix in real coordinate system (torch.Tensor or np.ndarray)
            timestamp_us: timestamp in microseconds (int)

        Returns:
            np.ndarray: RGB image (H, W, 3), dtype=np.uint8

        Raises:
            RuntimeError: If gRPC render fails
        """
        from streetstudio_grpc import render_pb2

        # Convert to numpy if needed
        if hasattr(K, "cpu"):
            K = K.cpu().numpy()
        if hasattr(extrinsics, "cpu"):
            extrinsics = extrinsics.cpu().numpy()
        else:
            K = np.array(K)
            extrinsics = np.array(extrinsics)

        # Transform c2w extrinsics from real to normalized coordinate system
        # reverse=True: real -> normalized (inverse of dataset_transforms)
        extrinsics_norm = self.transform.apply_extrinsic(extrinsics, reverse=False)

        # Time scaling: dataset_time_sec * 0.1 = renderer_time
        render_time = timestamp_us / 1_000_000 * 0.1

        # Build gRPC request
        # extrinsics_norm is camera-to-world (4x4), convert to (3x4) for gRPC API
        extrinsics_norm[0:3, 1:3] *= -1 # OpenCV -> OpenGL
        camera_to_world = extrinsics_norm[:3, :].flatten().tolist()


        request = render_pb2.RenderRequest(
            camera=render_pb2.CameraParams(
                camera_to_world=camera_to_world,
                fx=float(K[0, 0]),
                fy=float(K[1, 1]),
                cx=float(K[0, 2]),
                cy=float(K[1, 2]),
                width=int(W),
                height=int(H),
                time=float(render_time),
            )
        )

        # Call gRPC
        stub = self._get_stub()
        response = stub.Render(request)

        if not response.success:
            raise RuntimeError(f"Render failed: {response.error_message}")

        # Parse response
        rgb = np.frombuffer(response.rgb_image.rgb_data, dtype=np.uint8)
        rgb = rgb.reshape(response.rgb_image.height, response.rgb_image.width, 3)
        return rgb

    def close(self):
        """Close gRPC channel."""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
            self._stub = None
