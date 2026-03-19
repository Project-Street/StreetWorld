from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import yaml

from metadrive.misc.nurec_interface.grpc_client import NurecGrpcClient
from metadrive.misc.nurec_interface.nurec_parser import (
    compute_sim_world_to_xodr_map,
    export_one_scene,
    generate_corrected_xodr,
    parse_camera_params,
    parse_world_to_nre,
)
from metadrive.utils.logger import get_log_timestamp

logger = logging.getLogger(__name__)


class SimulatorInterface:
    _NUREC_HF_REPO_ID = "nvidia/PhysicalAI-Autonomous-Vehicles-NuRec"
    _NUREC_HF_BASE_PATH = "sample_set/25.07_release"

    def __init__(
        self,
        zNear: float = 0.0001,
        zFar: float = 1000.0,
        grpc_host: str = "localhost",
        grpc_port: int = 9001,
        grpc_timeout_s: float = 60.0,
        resolution_scale: float = 1.0,
        camera_model_type: str = "ftheta",
    ) -> None:
        self.zNear = zNear
        self.zFar = zFar
        self.resolution_scale = resolution_scale
        self._grpc_host = str(grpc_host)
        self._grpc_port = int(grpc_port)
        self._local_server_proc: Optional[subprocess.Popen] = None
        self._simple_nurec_log_fp = None

        camera_model_type = str(camera_model_type).lower()
        if camera_model_type not in {"pinhole", "ftheta"}:
            raise ValueError(f"camera_model_type must be 'pinhole' or 'ftheta', got: {camera_model_type}")
        self._camera_model_type = camera_model_type

        self._maybe_start_local_nurec_server()

        self._grpc = NurecGrpcClient(host=grpc_host, port=grpc_port, timeout_s=grpc_timeout_s)
        self._cached_ts: Optional[int] = None
        self._scene_model: Optional[Dict[str, Any]] = None

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        normalized = host.strip().lower()
        if normalized in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            return socket.gethostbyname(normalized).startswith("127.")
        except OSError:
            return False

    @staticmethod
    def _is_port_listening(host: str, port: int, timeout_s: float = 0.2) -> bool:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout_s):
                return True
        except OSError:
            return False

    def _maybe_start_local_nurec_server(self) -> None:
        if not self._is_loopback_host(self._grpc_host):
            return
        if self._is_port_listening(self._grpc_host, self._grpc_port):
            return

        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = get_log_timestamp()
        _simple_nurec_log_path = log_dir / f"simple-nurec_{ts}.log"
        self._simple_nurec_log_fp = _simple_nurec_log_path.open("a", encoding="utf-8", buffering=1)

        self._local_server_proc = subprocess.Popen(
            [
                "simple-nurec",
                "server",
                "--host",
                self._grpc_host,
                "--port",
                str(self._grpc_port),
            ],
            stdout=self._simple_nurec_log_fp,
            stderr=subprocess.STDOUT,
        )
        logger.info(
            "Started simple-nurec server pid=%s, log=%s",
            self._local_server_proc.pid,
            _simple_nurec_log_path,
        )

        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self._is_port_listening(self._grpc_host, self._grpc_port):
                return
            if self._local_server_proc.poll() is not None:
                raise RuntimeError(
                    f"simple-nurec server exited early (code={self._local_server_proc.returncode})"
                )
            time.sleep(0.1)
        raise RuntimeError(f"simple-nurec server did not start listening on {self._grpc_host}:{self._grpc_port} within timeout")

    def load_metadata(
        self, cfg_path: str | Path
    ) -> Tuple[str, Any, list[int], Dict[str, Dict[str, Any]], Dict[int, list[list[float]]], Dict[str, Dict[str, Any]], Optional[str]]:
        cfg_path = Path(cfg_path)
        self._ensure_scene_config(cfg_path)
        cfg = self._load_cfg(cfg_path)
        rig = json.loads(Path(cfg["rig_trajectories_path"]).read_text(encoding="utf-8"))
        camera_params, _ = parse_camera_params(rig, resolution_scale=self.resolution_scale)
        ego_raw = json.loads(Path(cfg["ego_pose_path"]).read_text(encoding="utf-8"))
        ego_poses = {
            int(ts): np.asarray(pose, dtype=np.float64).reshape(4, 4).tolist()
            for ts, pose in ego_raw.items()
        }
        timestamps = sorted(ego_poses.keys())
        timestamp_range = [int(min(timestamps)), int(max(timestamps))]
        traj_raw = json.loads(Path(cfg["trajectory_path"]).read_text(encoding="utf-8"))
        tracking_data: Dict[str, Dict[str, Any]] = {}
        for obj_id, obj in traj_raw.items():
            if not isinstance(obj, dict) or "local2world" not in obj:
                continue
            tracking_data[str(obj_id)] = {
                "poses": {int(ts): np.asarray(pose, dtype=np.float64).reshape(4, 4).tolist()
                          for ts, pose in obj["local2world"].items()},
                "size": obj.get("size", [4.5, 2.0, 1.5]),
                "type": obj.get("type", "vehicle"),
            }
        bk_ground_model_path = None
        print(f"loaded {cfg['scene_name']}.")
        return (
            cfg["scene_name"],
            cfg,
            timestamp_range,
            camera_params,
            ego_poses,
            tracking_data,
            bk_ground_model_path,
        )

    def _ensure_scene_config(self, cfg_path: Path) -> None:
        if cfg_path.exists():
            return
        scene_name = cfg_path.stem
        m = re.fullmatch(r"(\d+)_(\d+)", scene_name)
        if not m:
            raise FileNotFoundError(f"Scene config not found: {cfg_path}")
        logger.warning("Scene not found. Downloading now: scene=%s cfg=%s", scene_name, cfg_path)
        self._download_and_generate_scene(
            scene_name=scene_name,
            batch_num=int(m.group(1)),
            scene_index=int(m.group(2)),
            scene_cfg_dir=cfg_path.parent,
        )
        logger.warning("Scene download completed: scene=%s. Please restart the job on http://www.zjvts.cn/#/job/listr.", scene_name)

    def _download_and_generate_scene(self, scene_name: str, batch_num: int, scene_index: int, scene_cfg_dir: Path) -> None:
        repo_id = self._NUREC_HF_REPO_ID
        target_path = self._NUREC_HF_BASE_PATH
        batch_name = f"Batch{int(batch_num):04d}"
        token = os.getenv("HF_TOKEN")
        if not token:
            raise RuntimeError("Missing HF_TOKEN; cannot auto-download NuRec scene")

        try:
            from huggingface_hub import HfApi, hf_hub_download
        except ImportError as exc:
            raise ImportError("huggingface_hub is required for auto scene download") from exc

        api = HfApi()
        files = api.list_repo_files(repo_id=repo_id, repo_type="dataset", token=token)
        batch_prefix = f"{target_path}/{batch_name}/"
        usdz_files = [p for p in files if p.startswith(batch_prefix) and p.endswith(".usdz")]
        by_uuid: Dict[str, str] = {Path(relpath).stem: relpath for relpath in usdz_files}

        ordered_scene_ids = sorted(by_uuid.keys())
        if scene_index < 1 or scene_index > len(ordered_scene_ids):
            raise RuntimeError(
                f"Scene index out of range for batch {batch_num}: index={scene_index}, total={len(ordered_scene_ids)}"
            )
        scene_uuid = ordered_scene_ids[scene_index - 1]
        relpath = by_uuid[scene_uuid]

        data_root = Path("data")
        nurec_root = data_root / "nurec"
        trajectory_root = data_root / "trajectory"
        nurec_root.mkdir(parents=True, exist_ok=True)
        trajectory_root.mkdir(parents=True, exist_ok=True)
        scene_cfg_dir.mkdir(parents=True, exist_ok=True)

        local_usdz = Path(
            hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=relpath,
                token=token,
                local_dir=str(nurec_root),
            )
        )
        scene_root = local_usdz.parent
        scene_dir = scene_root / scene_uuid
        with zipfile.ZipFile(local_usdz, "r") as zf:
            zf.extractall(scene_dir)
        local_usdz.unlink()
        generate_corrected_xodr(scene_dir)

        pose_dir = trajectory_root / scene_name
        export_one_scene(scene_dir, pose_dir)

        cwd_root = Path.cwd()
        cfg = {
            "scene_name": scene_name,
            "scene_uuid": scene_uuid,
            # Keep generated yaml paths root-relative (e.g. data/...) to avoid fragile ../../ traversal.
            "scene_root": os.path.relpath(scene_root, cwd_root),
            "pose_data_path": os.path.relpath(pose_dir, cwd_root),
            "ego_pose_path": os.path.relpath(pose_dir / "ego_pose.json", cwd_root),
            "trajectory_path": os.path.relpath(pose_dir / "trajectory.json", cwd_root),
        }
        out_yaml = scene_cfg_dir / f"{scene_name}.yaml"
        out_yaml.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False), encoding="utf-8")

    def load_model(self, cfg: Any) -> None:
        rig = json.loads(Path(cfg["rig_trajectories_path"]).read_text(encoding="utf-8"))
        world_to_nre = np.asarray(parse_world_to_nre(rig), dtype=np.float64)
        sim_world_to_map = compute_sim_world_to_xodr_map(
            rig_data=rig,
            xodr_path=Path(cfg["map_path"]),
        )
        _, camera_models = parse_camera_params(rig, resolution_scale=self.resolution_scale)
        self._scene_model = {
            "world_to_nre": world_to_nre,
            "nre_to_world": np.linalg.inv(world_to_nre),
            "sim_world_to_map": sim_world_to_map,
            "map_to_sim_world": np.linalg.inv(sim_world_to_map),
            "camera_models": camera_models,
        }
        self._grpc.load_model(cfg["ckpt_path"])
        return None

    def update_scene(self, timestamp: int, object_poses: Dict[str, Any]) -> None:
        self._cached_ts = int(timestamp)
        if self._scene_model is None:
            raise RuntimeError("Scene model is not initialized. load_model() must be called before update_scene().")
        tracks_id: list[str] = []
        poses_4x4: list[float] = []
        for object_id, pose in object_poses.items():
            pose_np = np.array(pose, dtype=np.float64)
            if pose_np.shape != (4, 4):
                raise ValueError(f"Object {object_id} pose must have shape (4, 4), got {pose_np.shape}")
            if not np.isfinite(pose_np).all():
                raise ValueError(f"Object {object_id} pose contains non-finite values")
            # Exported trajectories are map coordinates; convert back to sim world here.
            pose_np = self._scene_model["map_to_sim_world"] @ pose_np
            pose_np = self._scene_model["world_to_nre"] @ pose_np
            tracks_id.append(str(object_id))
            poses_4x4.extend(pose_np.reshape(-1).tolist())
        response = self._grpc.set_traffic_pose(tracks_id=tracks_id, poses_4x4=poses_4x4)
        if not response.success:
            raise RuntimeError(f"SetTrafficPose failed: {response.error_message}")

    def render(self, K: Any, H: int, W: int, extrinsics: Any) -> np.ndarray:
        if self._cached_ts is None:
            raise ValueError("render() called before update_scene(); timestamp is required")
        if self._scene_model is None:
            raise RuntimeError("Scene model is not initialized. load_model() must be called before render().")
        k_mat = np.array(K, dtype=np.float64)
        fx = float(k_mat[0, 0])
        fy = float(k_mat[1, 1])
        cx = float(k_mat[0, 2])
        cy = float(k_mat[1, 2])

        world_to_camera = np.array(extrinsics, dtype=np.float64)
        # Input extrinsics are world->camera in map coordinates.
        # Convert map->camera to sim_world->camera to cancel export-time map transform.
        world_to_camera = world_to_camera @ self._scene_model["sim_world_to_map"]
        # Keep the original world->NRE conversion for renderer camera pose.
        nre_to_camera = world_to_camera @ self._scene_model["nre_to_world"]
        camera_to_world = np.linalg.inv(nre_to_camera)[:3, :4].reshape(-1).tolist()

        camera_model_type = self._camera_model_type
        if camera_model_type == "ftheta":
            ftheta_model = self._find_camera_model_by_type("ftheta")
            ftheta_params = ftheta_model["parameters"] if ftheta_model is not None else None
        elif camera_model_type == "pinhole":
            ftheta_params = None
        else:
            raise ValueError(f"Unsupported camera_model_type: {camera_model_type}")

        response = self._grpc.render(
            camera_to_world=camera_to_world,
            fx=fx,
            fy=fy,
            cx=cx,
            cy=cy,
            width=int(W),
            height=int(H),
            camera_model=camera_model_type,
            ftheta_params=ftheta_params,
            time_s=float(self._cached_ts) / 1_000_000.0,
        )
        if not response.success:
            raise RuntimeError(f"Render failed: {response.error_message}")
        rgb = np.frombuffer(response.rgb_image.rgb_data, dtype=np.uint8)
        rgb = rgb.reshape((response.rgb_image.height, response.rgb_image.width, 3))
        return rgb

    def _find_camera_model_by_type(self, model_type: str) -> Optional[Dict[str, Any]]:
        if self._scene_model is None:
            return None
        for model in self._scene_model["camera_models"].values():
            if model.get("type") == model_type:
                return model
        return None

    @staticmethod
    def _load_cfg(cfg_path: Path) -> Dict[str, Any]:
        data = yaml.safe_load(cfg_path.read_text())

        scene_root = (Path.cwd() / Path(data["scene_root"])).resolve()
        scene_dir = scene_root / str(data["scene_uuid"])

        ego_pose_path = (Path.cwd() / Path(data["ego_pose_path"])).resolve()
        trajectory_path = (Path.cwd() / Path(data["trajectory_path"])).resolve()

        data["scene_root"] = str(scene_root)
        data["rig_trajectories_path"] = str(scene_dir / "rig_trajectories.json")
        data["sequence_tracks_path"] = str(scene_dir / "sequence_tracks.json")
        data["map_path"] = str(scene_dir / "map.xodr")
        data["ckpt_path"] = str(scene_dir / "checkpoint.ckpt")
        data["ego_pose_path"] = str(ego_pose_path)
        data["trajectory_path"] = str(trajectory_path)
        return data
