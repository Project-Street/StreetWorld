import argparse
import json
import logging
import os
import sys
import warnings
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm
from torch.nn.utils import parametrize
from torch.nn.utils.parametrize import is_parametrized

from mmcv import Config  # type: ignore[import-not-found]
from mmcv.cnn import fuse_conv_bn  # type: ignore[import-not-found]
from mmcv.parallel import MMDataParallel  # type: ignore[import-not-found]
from mmcv.runner import load_checkpoint, wrap_fp16_model  # type: ignore[import-not-found]
from mmdet3d.models import build_model  # type: ignore[import-not-found]


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

INTENT_TO_COMMAND = {
    1: 2,  # GO_STRAIGHT
    2: 1,  # GO_LEFT
    3: 0,  # GO_RIGHT
}


def default_vad_config() -> dict:
    vad_root = STREETWORLD_ROOT / "VAD"
    return {
        "config_path": vad_root / "projects" / "configs" / "VAD" / "VAD_base_e2e.py",
        "checkpoint_path": vad_root / "ckpts" / "VAD_base.pth",
        "device": "cuda:0",
    }


def _resolve_attention_module(attn, decoder_name: str, layer_idx: int, attn_idx: int):
    if hasattr(attn, "in_proj_weight"):
        return attn
    nested = getattr(attn, "attn", None)
    if nested is not None and hasattr(nested, "in_proj_weight"):
        return nested
    raise ValueError(
        f"Unsupported attention wrapper at {decoder_name}.layers[{layer_idx}].attentions[{attn_idx}]"
    )


def _register_lora_on_attention(attn, rank: int, alpha: float, dropout: float) -> int:
    from rl_framework.common.policy_network import LoRAParametrization

    if is_parametrized(attn, "in_proj_weight"):
        return 0
    embed_dim = attn.embed_dim
    slice_map = {
        "q": (0, embed_dim),
        "k": (embed_dim, 2 * embed_dim),
        "v": (2 * embed_dim, 3 * embed_dim),
    }
    enabled_slices = (slice_map["q"], slice_map["v"])

    attn.in_proj_weight.requires_grad = False
    if hasattr(attn, "in_proj_bias") and attn.in_proj_bias is not None:
        attn.in_proj_bias.requires_grad = False
    attn.out_proj.weight.requires_grad = False
    if attn.out_proj.bias is not None:
        attn.out_proj.bias.requires_grad = False

    in_lora = LoRAParametrization(
        attn.in_proj_weight.shape[1],
        attn.in_proj_weight.shape[0],
        rank=rank,
        alpha=alpha,
        dropout=dropout,
        enabled_slices=enabled_slices,
    ).to(attn.in_proj_weight.device)
    parametrize.register_parametrization(attn, "in_proj_weight", in_lora)
    mask = in_lora.row_mask.view(-1)
    assert mask[embed_dim: 2 * embed_dim].abs().sum() == 0, "LoRA mask must not modify K projection"
    return 1


def _inject_vad_lora(model, rank: int = 8, alpha: float = 8.0, dropout: float = 0.0) -> int:
    model_impl = model.module if hasattr(model, "module") else model
    if not hasattr(model_impl, "pts_bbox_head"):
        raise ValueError("VAD model must have pts_bbox_head")
    head = model_impl.pts_bbox_head
    total = 0
    for decoder_name, decoder in (
        ("ego_agent_decoder", getattr(head, "ego_agent_decoder", None)),
        ("ego_map_decoder", getattr(head, "ego_map_decoder", None)),
    ):
        if decoder is None:
            raise ValueError(f"pts_bbox_head missing {decoder_name}")
        layers = getattr(decoder, "layers", None)
        if layers is None:
            raise ValueError(f"{decoder_name} has no `layers` attribute")
        for layer_idx, layer in enumerate(layers):
            attentions = getattr(layer, "attentions", None)
            if attentions is None:
                raise ValueError(f"{decoder_name}.layers[{layer_idx}] has no `attentions`")
            for attn_idx, attn in enumerate(attentions):
                core_attn = _resolve_attention_module(attn, decoder_name, layer_idx, attn_idx)
                total += _register_lora_on_attention(core_attn, rank=rank, alpha=alpha, dropout=dropout)
    return total


def create_vad(vad_config: dict, add_lora: bool = False):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    uniad_ft = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    vad_root = os.path.join(uniad_ft, "VAD")

    config_path = vad_config["config_path"]
    checkpoint_path = vad_config["checkpoint_path"]
    device = vad_config["device"]
    warnings.filterwarnings("ignore")

    try:
        from mmdet.core.bbox.match_costs.builder import MATCH_COST  # type: ignore[import-not-found]
        from mmdet.models.builder import LOSSES  # type: ignore[import-not-found]

        if hasattr(MATCH_COST, "_module_dict") and "DiceCost" in MATCH_COST._module_dict:
            del MATCH_COST._module_dict["DiceCost"]
            LOGGER.info("Cleared DiceCost from MATCH_COST")

        if hasattr(LOSSES, "_module_dict") and "DiceLoss" in LOSSES._module_dict:
            del LOSSES._module_dict["DiceLoss"]
            LOGGER.info("Cleared DiceLoss from LOSSES")

    except Exception as exc:
        LOGGER.warning("Registry cleanup failed: %s", exc)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")

    if vad_root not in sys.path:
        sys.path.insert(0, vad_root)

    original_cwd = os.getcwd()
    config_path_abs = os.path.abspath(config_path)
    checkpoint_path_abs = os.path.abspath(checkpoint_path)

    try:
        os.chdir(vad_root)
        config_rel_path = os.path.relpath(config_path_abs, vad_root)
        cfg = Config.fromfile(config_rel_path)

        if cfg.get("custom_imports", None):
            from mmcv.utils import import_modules_from_strings  # type: ignore[import-not-found]

            import_modules_from_strings(**cfg["custom_imports"])

        if hasattr(cfg, "plugin") and cfg.plugin:
            import importlib

            if hasattr(cfg, "plugin_dir"):
                plugin_dir = cfg.plugin_dir
                module_dir = os.path.dirname(plugin_dir).split("/")
            else:
                module_dir = os.path.dirname(config_rel_path).split("/")
            module_path = module_dir[0]
            for part in module_dir[1:]:
                module_path = module_path + "." + part
            importlib.import_module(module_path)

        if cfg.get("cudnn_benchmark", False):
            torch.backends.cudnn.benchmark = True

        cfg.model.pretrained = None
        cfg.model.train_cfg = None
        model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))

        fp16_cfg = cfg.get("fp16", None)
        if fp16_cfg is not None:
            wrap_fp16_model(model)

        if add_lora:
            injected = _inject_vad_lora(model)
            LOGGER.info("LoRA enabled for VAD decoders (modules injected: %s)", injected)

        checkpoint = load_checkpoint(model, checkpoint_path_abs, map_location="cpu")
        model = fuse_conv_bn(model)

        if "CLASSES" in checkpoint.get("meta", {}):
            model.CLASSES = checkpoint["meta"]["CLASSES"]
        if "PALETTE" in checkpoint.get("meta", {}):
            model.PALETTE = checkpoint["meta"]["PALETTE"]

        device_ids = [int(device.split(":")[1])]
        model = MMDataParallel(model, device_ids=device_ids).eval()
        return model
    finally:
        os.chdir(original_cwd)


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


def _series_value(values, idx: int, default: float = 0.0) -> float:
    if not values:
        return float(default)
    idx = max(0, min(idx, len(values) - 1))
    return float(values[idx])


def build_temporal_obs_infos(metadata: dict, cam_params: dict, scene_token: str, temporal_frames: int) -> list[dict]:
    past_states = metadata.get("past_states", {}) or {}
    pos_x = list(past_states.get("pos_x") or [])
    pos_y = list(past_states.get("pos_y") or [])
    vel_x = list(past_states.get("vel_x") or [])
    vel_y = list(past_states.get("vel_y") or [])
    accel_x = list(past_states.get("accel_x") or [])
    accel_y = list(past_states.get("accel_y") or [])

    intent = metadata.get("intent", {}) or {}
    intent_id = int(intent.get("id", 0))
    command = INTENT_TO_COMMAND.get(intent_id, 2)

    n = max(len(pos_x), len(pos_y), len(vel_x), len(vel_y), len(accel_x), len(accel_y), 1)
    first = max(0, n - temporal_frames)
    indices = list(range(first, n))
    while len(indices) < temporal_frames:
        indices.insert(0, indices[0])

    infos: list[dict] = []
    dt = 0.25
    for i, idx in enumerate(indices):
        prev_idx = indices[max(i - 1, 0)]
        next_idx = indices[min(i + 1, len(indices) - 1)]
        dx = _series_value(pos_x, next_idx) - _series_value(pos_x, prev_idx)
        dy = _series_value(pos_y, next_idx) - _series_value(pos_y, prev_idx)
        yaw = float(np.arctan2(dy, dx)) if (abs(dx) + abs(dy)) > 1e-6 else 0.0

        infos.append(
            {
                "ego_rot": np.array([0.0, 0.0, yaw], dtype=np.float32),
                "ego_pos": np.array([_series_value(pos_x, idx), _series_value(pos_y, idx), 0.0], dtype=np.float32),
                "linear_velocity": np.array([_series_value(vel_x, idx), _series_value(vel_y, idx), 0.0], dtype=np.float32),
                "linear_acceleration": np.array([_series_value(accel_x, idx), _series_value(accel_y, idx), 0.0], dtype=np.float32),
                "angular_velocity": np.zeros(3, dtype=np.float32),
                "command": command,
                "relative_timestamp": float((idx - (n - 1)) * dt),
                "scene_token": scene_token,
                "cam_params": cam_params,
            }
        )
    return infos


def load_scene_temporal(
    scene_dir: Path,
    camera_source: str,
    nuscenes_path: Path,
    temporal_frames: int,
):
    obs_img_last, cam_params, metadata = load_scene(scene_dir, camera_source, nuscenes_path)
    temporal_frames = max(1, int(temporal_frames))

    if camera_source != "nuscenes":
        return [obs_img_last for _ in range(temporal_frames)], cam_params, metadata

    camera_map = CAMERA_MAP_NUSEC
    nuscenes_root = scene_dir / "nuscenes"
    frame_dirs = []
    if nuscenes_root.exists():
        frame_dirs = sorted([p for p in nuscenes_root.iterdir() if p.is_dir() and p.name.startswith("frame_")])

    if not frame_dirs:
        return [obs_img_last for _ in range(temporal_frames)], cam_params, metadata

    if len(frame_dirs) >= temporal_frames:
        frame_dirs = frame_dirs[-temporal_frames:]
    else:
        frame_dirs = [frame_dirs[0]] * (temporal_frames - len(frame_dirs)) + frame_dirs

    obs_frames = []
    for frame_dir in frame_dirs:
        obs_img = {}
        for cam_name, cam_id in camera_map:
            jpg_path = frame_dir / f"{cam_id:04d}.jpg"
            png_path = frame_dir / f"{cam_id:04d}.png"
            if jpg_path.exists():
                image_path = jpg_path
            elif png_path.exists():
                image_path = png_path
            else:
                raise FileNotFoundError(f"Missing rendered temporal image in {frame_dir} for cam {cam_id:04d}")
            obs_img[cam_name] = np.array(Image.open(image_path).convert("RGB"))
        obs_frames.append(obs_img)

    return obs_frames, cam_params, metadata


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
        description="Run VAD on WOD last-frame data and write JSON predictions."
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
        help="Path to VAD config (defaults to StreetWorld VAD config)",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Path to VAD checkpoint (defaults to StreetWorld VAD checkpoint)",
    )
    parser.add_argument(
        "--device",
        default="cuda:0",
        help="Device string for VAD (must be CUDA for current dataparser)",
    )
    parser.add_argument(
        "--output_name",
        default="vad_predictions.json",
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
        help="Inject LoRA parametrizations into VAD decoders",
    )
    parser.add_argument(
        "--temporal_frames",
        type=int,
        default=3,
        help="Number of sequential frames for warm-up (final frame is used for output)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not torch.cuda.is_available():
        raise RuntimeError("VAD dataparser uses CUDA tensors; CUDA is required.")

    from rl_framework.vad.dataparser import get_vad_img_norm_cfg, parse_vad_obs
    from rl_framework.vad.trajectory import decode_ego_future_traj

    vad_config = default_vad_config()
    if args.config:
        vad_config["config_path"] = Path(args.config)
    if args.checkpoint:
        vad_config["checkpoint_path"] = Path(args.checkpoint)
    vad_config["device"] = args.device

    LOGGER.info("Loading VAD model...")
    model = create_vad(vad_config, add_lora=bool(args.add_lora))
    model.eval()

    input_dir = Path(args.input_dir)
    if args.scene_id:
        scene_dirs = [input_dir / args.scene_id]
    else:
        scene_dirs = sorted([p for p in input_dir.iterdir() if p.is_dir()])

    img_norm_cfg = get_vad_img_norm_cfg()
    predictions = []
    for scene_dir in tqdm(scene_dirs):
        obs_frames, cam_params, metadata = load_scene_temporal(
            scene_dir,
            args.camera_source,
            Path(args.nuscenes_camera_path),
            temporal_frames=args.temporal_frames,
        )
        scene_id = metadata.get("scene_id") or scene_dir.name
        frame_id = int(metadata.get("frame_id", 0))
        frame_name = build_frame_name(scene_id, frame_id)
        scene_token = str(scene_id)

        obs_infos = build_temporal_obs_infos(
            metadata,
            cam_params,
            scene_token=scene_token,
            temporal_frames=len(obs_frames),
        )

        last_result = None
        last_raw_data = None
        with torch.no_grad():
            for obs_img, obs_info in zip(obs_frames, obs_infos):
                raw_data = parse_vad_obs(obs_img, obs_info, set(), img_norm_cfg)
                raw_data["img"] = [raw_data["img"]]
                last_raw_data = raw_data
                last_result = model(return_loss=False, rescale=True, return_bbox=True, **raw_data)

        if last_result is None or last_raw_data is None:
            raise RuntimeError(f"No inference result produced for scene: {scene_id}")

        pts_bbox = last_result[0]["pts_bbox"]
        plan_traj = decode_ego_future_traj(
            pts_bbox["ego_fut_preds"],
            ego_fut_cmd=pts_bbox.get("ego_fut_cmd", last_raw_data.get("ego_fut_cmd")),
            fallback_cmd=last_raw_data.get("command"),
            cumulative=True,
        )

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
