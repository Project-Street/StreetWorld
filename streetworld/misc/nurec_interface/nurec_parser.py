from __future__ import annotations

import copy
import json
import logging
import os
import re
import zipfile
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
import torch
import yaml

from streetworld.utils.trajectory import build_rotation

logger = logging.getLogger(__name__)

_NUREC_SCENE_API_BASE = os.getenv("NUREC_SCENE_API_BASE", "http://101.201.109.161:8000")
_NUREC_SCENE_API_KEY = os.getenv("NUREC_SCENE_API_KEY", "tj2026onsite-track4")

_XODR_HEADER_TAG_RE = re.compile(r"<header\b[^>]*>", re.IGNORECASE | re.DOTALL)
_XODR_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="([^"]*)"')
_XODR_JS_DATE_RE = re.compile(
    r"^[A-Za-z]{3}\s+([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})\s+(\d{2}:\d{2}:\d{2})\s+GMT[+-]\d{4}(?:\s+\(.*\))?$"
)
_XODR_MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}
_XODR_ZERO_SCI = "0.0000000000000000e+00"


def _load_json(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _quat_xyzw_to_matrix(qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
    quat = torch.tensor([qw, qx, qy, qz], dtype=torch.float32)
    rot = build_rotation(quat).numpy()
    return rot


def parse_world_to_nre(rig: Dict[str, Any]) -> np.ndarray:
    return np.array(rig["world_to_nre"]["matrix"], dtype=np.float64)


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
        # angle -> pixel distance scales linearly with pixel size
        params["angle_to_pixeldist_poly"] = [
            float(v) * resolution_scale for v in params["angle_to_pixeldist_poly"]
        ]
    if params.get("pixeldist_to_angle_poly") is not None:
        # pixel distance -> angle: scale r^i coefficients by 1/scale^i
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
        camera_params[camera_name] = {
            "K": k.tolist(),
            "H": int(height),
            "W": int(width),
            "ego2camera": ego2camera.tolist(),
            "fx": fx,
            "fy": fy,
            "cx": cx,
            "cy": cy,
        }
    return camera_params, camera_models


def parse_ego_poses_deprecated(rig: Dict[str, Any]) -> Tuple[Dict[int, List[List[float]]], List[int]]:
    traj = rig["rig_trajectories"][0]
    timestamps = [int(ts) for ts in traj["T_rig_world_timestamps_us"]]
    poses = np.array(traj["T_rig_worlds"], dtype=np.float64)
    world_to_nre = parse_world_to_nre(rig)
    ego_poses: Dict[int, List[List[float]]] = {}
    for ts, pose in zip(timestamps, poses):
        t_rig_nre = world_to_nre @ pose
        ego_poses[ts] = t_rig_nre.tolist()
    return ego_poses, timestamps


def parse_tracking_data_deprecated(
    tracks: Dict[str, Any],
    apply_world_to_nre: bool = False,
    world_to_nre: Optional[np.ndarray] = None,
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
        timestamps = timestamps_list[idx]
        poses = poses_list[idx]
        pose_map: Dict[int, List[float]] = {}
        for ts, pose in zip(timestamps, poses):
            x, y, z, qx, qy, qz, qw = pose
            rot = _quat_xyzw_to_matrix(qx, qy, qz, qw)
            mat = np.eye(4, dtype=np.float64)
            mat[:3, :3] = rot
            mat[:3, 3] = [x, y, z]
            if apply_world_to_nre:
                if world_to_nre is None:
                    raise ValueError("world_to_nre required when apply_world_to_nre=True")
                mat = world_to_nre @ mat
            pose_map[int(ts)] = mat.tolist()
        tracking[obj_id] = {"poses": pose_map, "size": size, "type": obj_type}
    return tracking

def compute_sim_world_to_xodr_map(rig_data: Dict[str, Any], xodr_path: Path) -> np.ndarray:
    from trajdata.dataset_specific.xodr.geo_transform import get_t_rig_enu_from_ecef

    xodr_xml = xodr_path.read_text(encoding="utf-8")
    t_world_base = np.asarray(rig_data["T_world_base"], dtype=np.float64)
    return np.asarray(get_t_rig_enu_from_ecef(t_world_base, xodr_xml), dtype=np.float64)


def _to_xodr_iso_datetime(value: str) -> str:
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", value):
        return value
    match = _XODR_JS_DATE_RE.match(value)
    if not match:
        return value
    month_text, day_text, year_text, hms = match.groups()
    month = _XODR_MONTH_MAP.get(month_text)
    if month is None:
        return value
    return f"{int(year_text):04d}-{month:02d}-{int(day_text):02d}T{hms}"


def generate_corrected_xodr(scene_dir: Path) -> Path:
    src = scene_dir / "map.xodr"
    dst = scene_dir / "corrected_map.xodr"
    if not src.exists():
        raise FileNotFoundError(f"map.xodr not found: {src}")

    text = src.read_text(encoding="utf-8")
    match = _XODR_HEADER_TAG_RE.search(text)
    if not match:
        raise ValueError(f"No <header> tag found in xodr: {src}")

    attrs = dict(_XODR_ATTR_RE.findall(match.group(0)))
    if not attrs:
        raise ValueError(f"No header attributes found in xodr: {src}")

    attrs["date"] = _to_xodr_iso_datetime(attrs.get("date", ""))
    attrs["north"] = _XODR_ZERO_SCI
    attrs["south"] = _XODR_ZERO_SCI
    attrs["east"] = _XODR_ZERO_SCI
    attrs["west"] = _XODR_ZERO_SCI

    ordered_keys = [
        "revMajor",
        "revMinor",
        "name",
        "version",
        "date",
        "vendor",
        "north",
        "south",
        "east",
        "west",
    ]
    parts = []
    for key in ordered_keys:
        if key in attrs:
            parts.append(f'{key}="{attrs[key]}"')
    for key, value in attrs.items():
        if key not in ordered_keys:
            parts.append(f'{key}="{value}"')
    new_header = "<header " + " ".join(parts) + ">"
    corrected_text = text[:match.start()] + new_header + text[match.end():]
    dst.write_text(corrected_text, encoding="utf-8")
    logger.info("Generated corrected xodr: %s", dst)
    return dst


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
            rot = _quat_xyzw_to_matrix(qx, qy, qz, qw)
            mat = np.eye(4, dtype=np.float64)
            mat[:3, :3] = rot
            mat[:3, 3] = [x, y, z]
            mat = t_sim_world_to_xodr_map @ mat
            pose_map[int(ts)] = mat.tolist()
        tracking[obj_id] = {"poses": pose_map, "size": size, "type": obj_type}
    return tracking


def discover_scenes(nurec_path: Path) -> Dict[Path, List[Tuple[str, Path]]]:
    by_batch: Dict[Path, List[Tuple[str, Path]]] = defaultdict(list)
    for root, _, files in os.walk(nurec_path, followlinks=True):
        if "rig_trajectories.json" not in files:
            continue
        scene_dir = (Path(root) / "rig_trajectories.json").parent
        wrapper_dir = scene_dir.parent
        if wrapper_dir.name.startswith("Batch"):
            batch_dir = wrapper_dir
        else:
            batch_dir = wrapper_dir.parent
            if not batch_dir.name.startswith("Batch"):
                continue
            if scene_dir.name != wrapper_dir.name:
                continue
        by_batch[batch_dir].append((scene_dir.name, scene_dir))
    for batch_dir in by_batch:
        by_batch[batch_dir].sort(key=lambda x: x[0])
    return dict(sorted(by_batch.items(), key=lambda x: x[0].name))


def _safe_extract_all(zf: zipfile.ZipFile, out_dir: Path) -> None:
    out_dir_resolved = out_dir.resolve()
    for member in zf.infolist():
        member_path = out_dir / member.filename
        try:
            member_resolved = member_path.resolve()
        except FileNotFoundError:
            member_resolved = member_path.parent.resolve() / member_path.name
        if out_dir_resolved not in (member_resolved, *member_resolved.parents):
            raise ValueError(f"Unsafe archive member path: {member.filename}")
    zf.extractall(out_dir)


def _write_scene_config(scene_name: str, scene_root: Path, pose_dir: Path, scene_cfg_dir: Path) -> Path:
    scene_cfg_dir.mkdir(parents=True, exist_ok=True)
    cwd_root = Path.cwd()
    cfg = {
        "scene_name": scene_name,
        "scene_uuid": scene_name,
        "scene_root": str(scene_root.resolve()),
        "pose_data_path": os.path.relpath(pose_dir, cwd_root),
        "ego_pose_path": os.path.relpath(pose_dir / "ego_pose.json", cwd_root),
        "trajectory_path": os.path.relpath(pose_dir / "trajectory.json", cwd_root),
    }
    out_yaml = scene_cfg_dir / f"{scene_name}.yaml"
    out_yaml.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return out_yaml


def parse_scene_batch_name(scene_name: str) -> str:
    match = re.fullmatch(r"(\d+)_(\d+)", scene_name)
    if match is None:
        raise ValueError(f"scene_name must match <batch>_<scene>, got: {scene_name}")
    return f"Batch{int(match.group(1)):04d}"


def prepare_nurec_scene_data(
    scene_name: str,
    scene_cfg_dir: Path | str,
    nurec_root: Path | str = Path("data/NuRec"),
    trajectory_root: Path | str = Path("data/trajectory"),
    api_base: str = _NUREC_SCENE_API_BASE,
    api_key: str = _NUREC_SCENE_API_KEY,
) -> Path:
    scene_cfg_dir = Path(scene_cfg_dir)
    nurec_root = Path(nurec_root)
    trajectory_root = Path(trajectory_root)
    scene_id = scene_name
    batch_name = parse_scene_batch_name(scene_name)
    api_base = api_base.rstrip("/")
    headers = {"X-API-Key": api_key}

    meta_resp = requests.get(f"{api_base}/api/scenes/{scene_id}/meta", headers=headers, timeout=10)
    meta_resp.raise_for_status()

    download_resp = requests.post(f"{api_base}/api/scenes/{scene_id}/download", headers=headers, timeout=10)
    download_resp.raise_for_status()
    download_data = download_resp.json()

    scene_root = nurec_root / batch_name
    local_usdz = scene_root / f"{scene_name}.usdz"
    scene_dir = scene_root / scene_name

    scene_root.mkdir(parents=True, exist_ok=True)
    trajectory_root.mkdir(parents=True, exist_ok=True)
    scene_cfg_dir.mkdir(parents=True, exist_ok=True)

    total_size = int(download_data.get("size") or 0)
    print(f"Downloading scene {scene_name} -> {local_usdz}")
    with requests.get(download_data["download_url"], stream=True, timeout=60) as resp:
        resp.raise_for_status()
        if total_size <= 0:
            content_length = resp.headers.get("Content-Length")
            if content_length and content_length.isdigit():
                total_size = int(content_length)

        downloaded = 0
        with local_usdz.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = downloaded / total_size * 100.0
                    print(
                        f"\rDownloading {scene_name}: {percent:.1f}% ({downloaded}/{total_size})",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\rDownloading {scene_name}: {downloaded} bytes",
                        end="",
                        flush=True,
                    )
    print()

    scene_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(local_usdz, "r") as zf:
        _safe_extract_all(zf, scene_dir)
    local_usdz.unlink()
    generate_corrected_xodr(scene_dir)

    pose_dir = trajectory_root / scene_name
    export_one_scene(scene_dir, pose_dir)
    return _write_scene_config(scene_name=scene_name, scene_root=scene_root, pose_dir=pose_dir, scene_cfg_dir=scene_cfg_dir)


def export_one_scene(scene_dir: Path, out_dir: Path) -> None:
    rig = _load_json(scene_dir / "rig_trajectories.json")
    t_sim_world_to_xodr_map = compute_sim_world_to_xodr_map(rig, scene_dir / "map.xodr")

    traj = rig["rig_trajectories"][0]
    timestamps = [int(ts) for ts in traj["T_rig_world_timestamps_us"]]
    poses = np.array(traj["T_rig_worlds"], dtype=np.float64)
    ego_pose_out = {
        str(ts): (t_sim_world_to_xodr_map @ pose).tolist()
        for ts, pose in sorted(zip(timestamps, poses), key=lambda x: int(x[0]))
    }

    tracks = _load_json(scene_dir / "sequence_tracks.json")
    tracking = parse_tracking_data_for_export(tracks, t_sim_world_to_xodr_map)

    trajectory_out: Dict[str, Dict[str, Any]] = {}
    for obj_id, obj in tracking.items():
        local2world = {
            str(int(ts)): mat
            for ts, mat in sorted(obj["poses"].items(), key=lambda x: int(x[0]))
        }
        trajectory_out[str(obj_id)] = {
            "type": obj["type"],
            "size": list(obj["size"]),
            "local2world": local2world,
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ego_pose.json").write_text(json.dumps(ego_pose_out, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "trajectory.json").write_text(json.dumps(trajectory_out, ensure_ascii=False, indent=2), encoding="utf-8")
