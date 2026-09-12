from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from trajdata import VectorMap
from trajdata.dataset_specific.xodr.vector_map_export import populate_vector_map_from_xodr

from .official_grpc_client import NurecOfficialGrpcClient
from .nurec_parser import (
    compute_sim_world_to_xodr_map,
    parse_camera_params,
    parse_tracking_data_for_export,
)

logger = logging.getLogger(__name__)
_NO_EXTRA = object()
_DEFAULT_PINHOLE_LOGICAL_ID = "camera_front_tele_30fov"
_DEFAULT_NUREC_ROOT = Path(__file__).resolve().parents[3] / "data/processed/benchmark/NuRec/sample_set/25.07_release"


class SimulatorInterface:
    def __init__(
        self,
        nurec_root: str | Path = _DEFAULT_NUREC_ROOT,
        zNear: float = 0.0001,
        zFar: float = 1000.0,
        grpc_host: str = "localhost",
        grpc_port: int = 8080,
        grpc_timeout_s: float = 600.0,
        resolution_scale: float = 1.0,
    ) -> None:
        self.zNear = zNear
        self.zFar = zFar
        self.resolution_scale = resolution_scale
        self._nurec_root = Path(nurec_root).expanduser().resolve()
        if not self._nurec_root.is_dir():
            raise FileNotFoundError(f"NuRec release root does not exist: {self._nurec_root}")
        self._grpc = NurecOfficialGrpcClient(host=grpc_host, port=grpc_port, timeout_s=grpc_timeout_s)
        self._cached_ts: Optional[int] = None
        self._cached_object_poses: Dict[str, np.ndarray] = {}
        self._scene_cfgs: Dict[str, Dict[str, Any]] = {}
        self._scene_model: Optional[Dict[str, Any]] = None

    def load_metadata(
        self, scene_id: str | Path
    ) -> Tuple[
        list[int],
        Dict[str, Dict[str, Any]],
        Dict[int, list[list[float]]],
        Dict[str, Dict[str, Any]],
        str,
        list[list[float]],
    ]:
        cfg = self._load_cfg(scene_id)
        self._scene_cfgs[cfg["scene_id"]] = cfg

        rig = json.loads(Path(cfg["rig_trajectories_path"]).read_text(encoding="utf-8"))
        sim_world_to_map = compute_sim_world_to_xodr_map(
            rig_data=rig,
            xodr_path=Path(cfg["map_path"]),
        )
        camera_params, _ = parse_camera_params(rig, resolution_scale=self.resolution_scale)

        traj = rig["rig_trajectories"][0]
        timestamps = [int(ts) for ts in traj["T_rig_world_timestamps_us"]]
        poses = np.asarray(traj["T_rig_worlds"], dtype=np.float64)
        ego_poses = {
            int(ts): (sim_world_to_map @ pose).tolist()
            for ts, pose in sorted(zip(timestamps, poses), key=lambda item: int(item[0]))
        }
        timestamp_range = [int(min(timestamps)), int(max(timestamps))]

        tracks = json.loads(Path(cfg["sequence_tracks_path"]).read_text(encoding="utf-8"))
        tracking = parse_tracking_data_for_export(tracks, sim_world_to_map)
        tracking_data: Dict[str, Dict[str, Any]] = {}
        for obj_id, obj in tracking.items():
            tracking_data[str(obj_id)] = {
                "poses": {
                    int(ts): np.asarray(pose, dtype=np.float64).reshape(4, 4).tolist()
                    for ts, pose in obj["poses"].items()
                },
                "size": obj["size"],
                "type": obj["type"],
            }

        return (
            timestamp_range,
            camera_params,
            ego_poses,
            tracking_data,
            cfg["ground_mesh_path"],
            sim_world_to_map.tolist(),
        )

    def load_model(self, scene_id: str | Path) -> VectorMap:
        cfg = self._scene_cfgs[str(self._resolve_scene_root(scene_id))]
        rig = json.loads(Path(cfg["rig_trajectories_path"]).read_text(encoding="utf-8"))
        sim_world_to_map = compute_sim_world_to_xodr_map(
            rig_data=rig,
            xodr_path=Path(cfg["map_path"]),
        )
        self._scene_model = {
            "scene_id": cfg["render_scene_id"],
            "sim_world_to_map": sim_world_to_map,
            "map_to_sim_world": np.linalg.inv(sim_world_to_map),
        }
        self._cached_object_poses = {}

        vector_map = VectorMap(f"xodr:{cfg['scene_uuid']}")
        populate_vector_map_from_xodr(
            vector_map,
            Path(cfg["map_path"]).read_text(encoding="utf-8"),
        )
        vector_map.compute_search_indices()
        return vector_map

    def update_scene(self, timestamp: int, object_poses: Dict[str, Any]) -> None:
        self._cached_ts = int(timestamp)
        if self._scene_model is None:
            raise RuntimeError("Scene model is not initialized. load_model() must be called before update_scene().")

        object_poses_render: Dict[str, np.ndarray] = {}
        map_to_sim_world = self._scene_model["map_to_sim_world"]
        for object_id, pose in object_poses.items():
            pose_np = np.asarray(pose)
            object_poses_render[str(object_id)] = map_to_sim_world @ pose_np
        self._cached_object_poses = object_poses_render

    def render(self, K: Any, H: int, W: int, extrinsics: Any, extra: Any = _NO_EXTRA) -> Any:
        if self._cached_ts is None:
            raise ValueError("render() called before update_scene(); timestamp is required")
        if self._scene_model is None:
            raise RuntimeError("Scene model is not initialized. load_model() must be called before render().")

        k_mat = np.asarray(K, dtype=np.float64)
        if k_mat.shape != (3, 3):
            raise ValueError(f"K must have shape (3, 3), got {k_mat.shape}")

        map_to_camera = np.asarray(extrinsics, dtype=np.float64)

        sim_world_to_camera = map_to_camera @ self._scene_model["sim_world_to_map"]
        sensor_pose = NurecOfficialGrpcClient.pose_from_matrix(np.linalg.inv(sim_world_to_camera))
        dynamic_objects = [
            NurecOfficialGrpcClient.dynamic_object_from_matrix(track_id, pose)
            for track_id, pose in self._cached_object_poses.items()
        ]

        if extra is _NO_EXTRA:
            return self._grpc.render_pinhole_rgb(
                scene_id=self._scene_model["scene_id"],
                camera_name=_DEFAULT_PINHOLE_LOGICAL_ID,
                K=k_mat,
                height=int(H),
                width=int(W),
                timestamp_us=int(self._cached_ts),
                sensor_pose=sensor_pose,
                dynamic_objects=dynamic_objects,
            )
        if extra.get("type") == "ftheta":
            return self._grpc.render_ftheta_rgb(
                scene_id=self._scene_model["scene_id"],
                camera_name=extra["logical_id"],
                extra=extra,
                height=int(H),
                width=int(W),
                timestamp_us=int(self._cached_ts),
                sensor_pose=sensor_pose,
                dynamic_objects=dynamic_objects,
            )
        if extra.get("type") not in (None, "pinhole"):
            raise ValueError(f"Unsupported camera extra.type: {extra['type']}")
        return self._grpc.render_pinhole_rgb(
            scene_id=self._scene_model["scene_id"],
            camera_name=extra["logical_id"],
            K=k_mat,
            height=int(H),
            width=int(W),
            timestamp_us=int(self._cached_ts),
            sensor_pose=sensor_pose,
            dynamic_objects=dynamic_objects,
        )

    def close(self) -> None:
        self._grpc.close()

    def _resolve_scene_root(self, scene_id: str | Path) -> Path:
        scene_path = Path(scene_id)
        parts = scene_path.parts
        if (
            scene_path.is_absolute()
            or not parts
            or not parts[0].startswith("Batch")
            or not parts[0][len("Batch"):].isdigit()
            or any(part in (".", "..") for part in parts)
        ):
            raise ValueError(
                f"scene_id must be a relative NuRec path beginning with Batch<digits>, got {scene_id!r}"
            )
        return self._nurec_root.joinpath(scene_path)

    def _load_cfg(self, scene_id: str | Path) -> Dict[str, Any]:
        scene_root = self._resolve_scene_root(scene_id)
        usdz_paths = sorted(scene_root.glob("*.usdz"))
        if len(usdz_paths) != 1:
            raise ValueError(f"Expected exactly one .usdz file under scene_id={scene_root}, got {len(usdz_paths)}")

        scene_uuid = usdz_paths[0].stem
        scene_dir = scene_root / scene_uuid
        if not scene_dir.is_dir():
            raise FileNotFoundError(f"Extracted NuRec scene directory not found: {scene_dir}")

        return {
            "scene_id": str(scene_root),
            "render_scene_id": f"clipgt-{scene_uuid}",
            "scene_uuid": scene_uuid,
            "scene_dir": str(scene_dir),
            "rig_trajectories_path": str(scene_dir / "rig_trajectories.json"),
            "sequence_tracks_path": str(scene_dir / "sequence_tracks.json"),
            "map_path": str(scene_dir / "map.xodr"),
            "ground_mesh_path": str(scene_dir / "mesh_ground.ply"),
        }
