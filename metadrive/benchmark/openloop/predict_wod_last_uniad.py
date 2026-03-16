import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[5]
STREETWORLD_ROOT = REPO_ROOT / "submodules" / "StreetWorld"

if STREETWORLD_ROOT.exists() and str(STREETWORLD_ROOT) not in sys.path:
    sys.path.insert(0, str(STREETWORLD_ROOT))

CAMERA_MAP = [
    ("camera_0", 0),  # FRONT
    ("camera_1", 1),  # FRONT_LEFT
    ("camera_2", 2),  # FRONT_RIGHT
    ("camera_3", 6),  # REAR
    ("camera_4", 5),  # REAR_LEFT
    ("camera_5", 7),  # REAR_RIGHT
]

CAMERA_MAP_NUSEC = [
    ("camera_0", 0),  # FRONT
    ("camera_1", 1),  # FRONT_LEFT
    ("camera_2", 2),  # FRONT_RIGHT
    ("camera_3", 3),  # REAR
    ("camera_4", 4),  # REAR_LEFT
    ("camera_5", 5),  # REAR_RIGHT
]

IMG_NORM_CFG = {
    "mean": np.array([103.530, 116.280, 123.675]),
    "std": np.array([1.0, 1.0, 1.0]),
    "to_rgb": False,
}

INTENT_TO_COMMAND = {
    1: 2,  # GO_STRAIGHT
    2: 1,  # GO_LEFT
    3: 0,  # GO_RIGHT
}


def repo_root() -> Path:
    return REPO_ROOT


def streetworld_root() -> Path:
    return STREETWORLD_ROOT


def default_uniad_config() -> dict:
    uniad_root = STREETWORLD_ROOT / "UniAD_SIM"
    return {
        "config_path": uniad_root / "projects" / "configs" / "stage2_e2e" / "base_e2e.py",
        "checkpoint_path": uniad_root / "ckpts" / "uniad_base_e2e.pth",
        "device": "cuda:0",
        "AD_root": uniad_root,
    }


def load_camera_params(scene_dir: Path, camera_source: str, nuscenes_path: Path):
    if camera_source == "nuscenes":
        if not nuscenes_path.exists():
            raise FileNotFoundError(f"Missing NuScenes camera params: {nuscenes_path}")
        cameras = np.load(nuscenes_path)
    else:
        camera_path = scene_dir / "camera.npz"
        if not camera_path.exists():
            raise FileNotFoundError(f"Missing camera params: {camera_path}")
        cameras = np.load(camera_path)

    intrinsics = cameras["intrinsics"]
    extrinsics = cameras["extrinsics"]

    axes_transformation = np.array([
        [0, -1, 0, 0],
        [0, 0, -1, 0],
        [1, 0, 0, 0],
        [0, 0, 0, 1]
    ])

    if camera_source != "nuscenes":
        extrinsics = np.linalg.inv(np.linalg.inv(
                np.array([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) @ 
                np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
            ) @ extrinsics @ np.linalg.inv(axes_transformation)) # Axis transformation & convert to ego-to-camera

    return intrinsics, extrinsics


def load_scene(scene_dir: Path, camera_source: str, nuscenes_path: Path):
    with (scene_dir / "e2e.json").open("r", encoding="utf-8") as f:
        metadata = json.load(f)

    intrinsics, extrinsics = load_camera_params(scene_dir, camera_source, nuscenes_path)

    obs_img = {}
    cam_params = {}
    camera_map = CAMERA_MAP_NUSEC if camera_source == "nuscenes" else CAMERA_MAP
    for cam_name, cam_id in camera_map:
        cam_dir = scene_dir / f"{cam_id:04d}"
        jpg_path = cam_dir / "last.jpg"
        png_path = cam_dir / "last.png"
        if camera_source == "nuscenes":
            jpg_path = scene_dir / "nuscenes" / f"{cam_id:04d}.jpg"
            png_path = scene_dir / "nuscenes" / f"{cam_id:04d}.png"

        if jpg_path.exists():
            image_path = jpg_path
        elif png_path.exists():
            image_path = png_path
        else:
            raise FileNotFoundError(f"Missing last frame image in {cam_dir}")

        image = np.array(Image.open(image_path).convert("RGB"))
        obs_img[cam_name] = image

        idx = cam_id - 1
        if idx >= intrinsics.shape[0] or idx >= extrinsics.shape[0]:
            raise IndexError(
                f"Camera index {idx} out of bounds for intrinsics/extrinsics shapes "
                f"{intrinsics.shape} / {extrinsics.shape}"
            )
        cam_params[cam_name] = {
            "K": intrinsics[idx].astype(np.float32),
            "ego2camera": extrinsics[idx].astype(np.float32),
        }

    return obs_img, cam_params, metadata


def build_obs_info(metadata: dict, cam_params: dict, frame_name: str) -> dict:
    past_states = metadata.get("past_states", {}) or {}
    vel_x = _last_or_zero(past_states.get("vel_x"))
    vel_y = _last_or_zero(past_states.get("vel_y"))
    accel_x = _last_or_zero(past_states.get("accel_x"))
    accel_y = _last_or_zero(past_states.get("accel_y"))

    intent = metadata.get("intent", {}) or {}
    intent_id = int(intent.get("id", 0))
    command = INTENT_TO_COMMAND.get(intent_id, 2)

    return {
        "ego_rot": np.zeros(3, dtype=np.float32),
        "ego_pos": np.zeros(3, dtype=np.float32),
        "linear_velocity": np.array([vel_x, vel_y, 0.0], dtype=np.float32),
        "linear_acceleration": np.array([accel_x, accel_y, 0.0], dtype=np.float32),
        "angular_velocity": np.zeros(3, dtype=np.float32),
        "command": command,
        "relative_timestamp": 0.0,
        "scene_token": frame_name,
        "cam_params": cam_params,
    }


def _last_or_zero(values):
    if not values:
        return 0.0
    return float(values[-1])


def build_frame_name(scene_id: str, frame_id: int) -> str:
    return f"{scene_id}-{frame_id:03d}"


def normalize_traj(
    plan_traj: np.ndarray,
    src_dt: float = 0.5,
    dst_dt: float = 0.25,
    dst_horizon: float = 5.0,
) -> np.ndarray:
    if plan_traj.ndim != 2 or plan_traj.shape[1] < 2:
        raise ValueError(f"plan_traj must be (N, 2+), got {plan_traj.shape}")
    if src_dt <= 0 or dst_dt <= 0:
        raise ValueError("src_dt and dst_dt must be positive")

    xy = plan_traj[:, :2]
    target_len = int(round(dst_horizon / dst_dt))
    if xy.shape[0] < 2:
        padded = np.repeat(xy[:1], target_len, axis=0)
        return padded.astype(np.float32)

    src_times = np.arange(xy.shape[0], dtype=np.float32) * src_dt
    dst_times = np.arange(1, target_len + 1, dtype=np.float32) * dst_dt

    def interp_extrap(values: np.ndarray) -> np.ndarray:
        interp = np.interp(dst_times, src_times, values)
        if dst_times[-1] > src_times[-1]:
            denom = src_times[-1] - src_times[-2]
            slope = (values[-1] - values[-2]) / denom if denom != 0 else 0.0
            mask = dst_times > src_times[-1]
            interp[mask] = values[-1] + slope * (dst_times[mask] - src_times[-1])
        return interp

    x = interp_extrap(xy[:, 0])
    y = interp_extrap(xy[:, 1])
    return np.stack([x, y], axis=1).astype(np.float32)


def main():
    parser = argparse.ArgumentParser(
        description="Run UniAD on WOD last-frame data and write JSON predictions."
    )
    parser.add_argument(
        "--input_dir",
        default=str(REPO_ROOT / "data" / "WOD-E2E-test-last"),
        help="Root directory for WOD last-frame data",
    )
    parser.add_argument(
        "--output_dir",
        default=str(REPO_ROOT / "submodules" / "ml-sharp" / "wod-test" / "output"),
        help="Output directory for JSON predictions",
    )
    parser.add_argument(
        "--scene_id",
        default=None,
        help="Optional scene id to process a single scene",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to UniAD config (defaults to StreetWorld UniAD_SIM config)",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Path to UniAD checkpoint (defaults to StreetWorld UniAD_SIM checkpoint)",
    )
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="Device string for UniAD (must be CUDA for current dataparser)",
    )
    parser.add_argument(
        "--output_name",
        default="uniad_predictions.json",
        help="File name for JSON predictions",
    )
    parser.add_argument(
        "--camera_source",
        choices=("waymo", "nuscenes"),
        default="waymo",
        help="Camera params source: waymo (scene dir) or nuscenes (global npz)",
    )
    parser.add_argument(
        "--nuscenes_camera_path",
        default=str(REPO_ROOT / "submodules" / "ml-sharp" / "nuscenes_camera_info.npz"),
        help="Path to NuScenes camera params npz",
    )
    parser.add_argument(
        "--add-lora",
        action="store_true",
        help="Inject LoRA parametrizations into UniAD planning head",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not torch.cuda.is_available():
        raise RuntimeError("UniAD dataparser uses CUDA tensors; CUDA is required.")

    from rl_framework.uniad.loader import create_uniad  # type: ignore[import-not-found]
    from rl_framework.uniad.dataparser import parse_raw  # type: ignore[import-not-found]

    uniad_config = default_uniad_config()
    if args.config:
        uniad_config["config_path"] = Path(args.config)
    if args.checkpoint:
        uniad_config["checkpoint_path"] = Path(args.checkpoint)
    uniad_config["device"] = args.device

    LOGGER.info("Loading UniAD model...")
    model = create_uniad(uniad_config, add_lora=bool(args.add_lora))
    model.eval()

    input_dir = Path(args.input_dir)
    if args.scene_id:
        scene_dirs = [input_dir / args.scene_id]
    else:
        scene_dirs = sorted([p for p in input_dir.iterdir() if p.is_dir()])

    predictions = []
    for scene_dir in tqdm(scene_dirs):
        obs_img, cam_params, metadata = load_scene(
            scene_dir,
            args.camera_source,
            Path(args.nuscenes_camera_path),
        )
        scene_id = metadata.get("scene_id") or scene_dir.name
        frame_id = int(metadata.get("frame_id", 0))
        frame_name = build_frame_name(scene_id, frame_id)

        obs_info = build_obs_info(metadata, cam_params, frame_name)
        camera_names = [name for name, _ in CAMERA_MAP]
        raw_data = parse_raw(obs_img, obs_info, camera_names, IMG_NORM_CFG)
        raw_data.pop('raw_imgs', None)

        dt = 0.5
        prev_pos = obs_info["ego_pos"] - obs_info["linear_velocity"] * dt
        if hasattr(model, "module") and hasattr(model.module, "prev_frame_info"):
            model.module.prev_frame_info["prev_pos"] = prev_pos
        # TODO: Model history info
        with torch.no_grad():
            result = model(return_loss=False, rescale=True, **raw_data)
        plan_traj = result[0]["planning"]["result_planning"]["sdc_traj"][0]
        plan_traj = plan_traj.detach().cpu().numpy()
        
        # x = y, y = -x
        plan_traj[:, [0, 1]] = plan_traj[:, [1, 0]]
        plan_traj[:, 1] = -plan_traj[:, 1]

        traj_xy = normalize_traj(plan_traj, src_dt=0.5, dst_dt=0.25, dst_horizon=5.0)
        
        predictions.append(
            {
                "frame_name": frame_name,
                "scene_id": scene_id,
                "frame_id": frame_id,
                "pos_x": traj_xy[:, 0].astype(float).tolist(),
                "pos_y": traj_xy[:, 1].astype(float).tolist(),
            }
        )

        # LOGGER.info("Predicted %s", frame_name)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / args.output_name
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump({"predictions": predictions}, fp, indent=2, ensure_ascii=True)
    LOGGER.info("Wrote JSON predictions to %s", output_path)


if __name__ == "__main__":
    main()
