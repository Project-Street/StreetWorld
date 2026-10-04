from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def parse_camera_models(rig: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    models: Dict[str, Dict[str, Any]] = {}
    for camera_uid, calib in rig["camera_calibrations"].items():
        name = calib.get("logical_sensor_name") or camera_uid
        models[name] = {
            "camera_uid": camera_uid,
            "type": calib["camera_model"]["type"],
            "parameters": calib["camera_model"]["parameters"],
        }
    return models


def _scale_ftheta_params(params: Dict[str, Any], resolution_scale: float) -> None:
    if params.get("angle_to_pixeldist_poly") is not None:
        params["angle_to_pixeldist_poly"] = [
            float(v) * resolution_scale for v in params["angle_to_pixeldist_poly"]
        ]
    if params.get("pixeldist_to_angle_poly") is not None:
        params["pixeldist_to_angle_poly"] = [
            float(v) / (resolution_scale ** idx) if idx > 0 else float(v)
            for idx, v in enumerate(params["pixeldist_to_angle_poly"])
        ]
    if params.get("linear_cde") is not None:
        params["linear_cde"] = [float(v) * resolution_scale for v in params["linear_cde"]]


def _scale_camera_models(
    camera_models: Dict[str, Dict[str, Any]],
    resolution_scale: float,
) -> Dict[str, Dict[str, Any]]:
    if resolution_scale == 1.0:
        return camera_models

    scaled_models: Dict[str, Dict[str, Any]] = {}
    for name, model in camera_models.items():
        params = copy.deepcopy(model["parameters"])
        if "resolution" in params:
            width, height = params["resolution"]
            params["resolution"] = [int(width * resolution_scale), int(height * resolution_scale)]
        if "principal_point" in params:
            cx, cy = params["principal_point"]
            params["principal_point"] = [float(cx) * resolution_scale, float(cy) * resolution_scale]
        for key in ("fx", "fy", "focal_length_x", "focal_length_y", "focal_length"):
            if key in params and params[key] is not None:
                params[key] = float(params[key]) * resolution_scale
        if model["type"] == "ftheta":
            _scale_ftheta_params(params, resolution_scale)
        scaled_models[name] = {
            "camera_uid": model["camera_uid"],
            "type": model["type"],
            "parameters": params,
        }
    return scaled_models


def _build_k_from_camera_model(camera_model: Dict[str, Any]) -> Tuple[np.ndarray, float, float, float, float]:
    params = camera_model["parameters"]
    cx, cy = params["principal_point"]
    if camera_model["type"] == "pinhole":
        fx = params.get("fx") or params.get("focal_length_x") or params.get("focal_length")
        fy = params.get("fy") or params.get("focal_length_y") or params.get("focal_length")
        if fx is None or fy is None:
            raise ValueError("Pinhole camera_model missing fx/fy fields")
    else:
        fx = 1.0
        fy = 1.0
    k = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64)
    return k, float(fx), float(fy), float(cx), float(cy)


def parse_camera_params(
    rig: Dict[str, Any],
    resolution_scale: float = 1.0,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    if resolution_scale <= 0:
        raise ValueError("resolution_scale must be > 0")
    camera_params: Dict[str, Dict[str, Any]] = {}
    camera_models_raw = parse_camera_models(rig)
    camera_models = _scale_camera_models(camera_models_raw, resolution_scale=resolution_scale)
    for camera_name, model in camera_models_raw.items():
        model_scaled = camera_models[camera_name]
        camera_uid = model["camera_uid"]
        calib = rig["camera_calibrations"][camera_uid]
        t_sensor_rig = np.array(calib["T_sensor_rig"], dtype=np.float64)
        ego2camera = np.linalg.inv(t_sensor_rig)
        k, fx, fy, cx, cy = _build_k_from_camera_model(model)
        if resolution_scale != 1.0:
            k = k.copy()
            k[0, 0] *= resolution_scale
            k[1, 1] *= resolution_scale
            k[0, 2] *= resolution_scale
            k[1, 2] *= resolution_scale
            fx *= resolution_scale
            fy *= resolution_scale
            cx *= resolution_scale
            cy *= resolution_scale
        width, height = model_scaled["parameters"]["resolution"]
        parsed_params = {
            "K": k.tolist(),
            "H": int(height),
            "W": int(width),
            "ego2camera": ego2camera.tolist(),
            "fx": fx,
            "fy": fy,
            "cx": cx,
            "cy": cy,
            "extra": {
                "type": model_scaled["type"],
                "logical_id": camera_name,
            },
        }
        if model_scaled["type"] == "ftheta":
            parsed_params["extra"]["parameters"] = copy.deepcopy(model["parameters"])
        camera_params[camera_name] = parsed_params
    return camera_params, camera_models


def parse_world_to_nre(rig: Dict[str, Any]) -> np.ndarray:
    return np.asarray(rig["world_to_nre"]["matrix"], dtype=np.float64)


def compute_sim_world_to_xodr_map(rig_data: Dict[str, Any], xodr_path: Path) -> np.ndarray:
    from trajdata.dataset_specific.xodr.geo_transform import get_t_rig_enu_from_ecef

    xodr_xml = xodr_path.read_text(encoding="utf-8")
    t_world_base = np.asarray(rig_data["T_world_base"], dtype=np.float64)
    return np.asarray(get_t_rig_enu_from_ecef(t_world_base, xodr_xml), dtype=np.float64)


def parse_tracking_data_for_export(
    tracks: Dict[str, Any],
    t_sim_world_to_xodr_map: np.ndarray,
) -> Dict[str, Dict[str, Any]]:
    if not tracks:
        return {}
    chunk_key = next(iter(tracks))
    tracks_data = tracks[chunk_key]["tracks_data"]
    cuboid_data = tracks[chunk_key]["cuboidtracks_data"]
    track_ids = tracks_data["tracks_id"]
    labels = tracks_data["tracks_label_class"]
    timestamps_list = tracks_data["tracks_timestamps_us"]
    poses_list = tracks_data["tracks_poses"]
    sizes = cuboid_data["cuboids_dims"]
    tracking: Dict[str, Dict[str, Any]] = {}
    for idx, track_id in enumerate(track_ids):
        obj_id = str(track_id)
        size = sizes[idx]
        raw_obj_type = str(labels[idx])
        obj_type_key = raw_obj_type.lower()
        obj_type = {
            "automobile": "vehicle",
            "trailer": "vehicle",
            "heavy_truck": "vehicle",
            "other_vehicle": "vehicle",
            "bus": "vehicle",
            "person": "pedestrian",
            "bicycle": "cyclist",
            "stroller": "pedestrian",
        }.get(obj_type_key, obj_type_key)
        if obj_type not in ("vehicle", "pedestrian", "cyclist"):
            logger.warning(
                "Drop unsupported NuRec object type: track_id=%s, type=%s",
                obj_id,
                raw_obj_type,
            )
            continue
        pose_map: Dict[int, List[List[float]]] = {}
        for ts, pose in zip(timestamps_list[idx], poses_list[idx]):
            x, y, z, qx, qy, qz, qw = pose
            mat = np.eye(4, dtype=np.float64)
            mat[:3, :3] = _quat_xyzw_to_matrix(qx, qy, qz, qw)
            mat[:3, 3] = [x, y, z]
            mat = t_sim_world_to_xodr_map @ mat
            pose_map[int(ts)] = mat.tolist()
        tracking[obj_id] = {"poses": pose_map, "size": size, "type": obj_type}
    return tracking


def _quat_xyzw_to_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    quat = np.array([qw, qx, qy, qz], dtype=np.float64)
    norm = np.linalg.norm(quat)
    if norm == 0.0:
        raise ValueError("Quaternion has zero length")
    qw, qx, qy, qz = quat / norm
    return np.array(
        [
            [1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qz * qw), 2.0 * (qx * qz + qy * qw)],
            [2.0 * (qx * qy + qz * qw), 1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qx * qw)],
            [2.0 * (qx * qz - qy * qw), 2.0 * (qy * qz + qx * qw), 1.0 - 2.0 * (qx * qx + qy * qy)],
        ],
        dtype=np.float64,
    )
