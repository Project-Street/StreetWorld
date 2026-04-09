from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np
import torch
from mmcv import Config
from mmcv.cnn import fuse_conv_bn
from mmcv.runner import load_checkpoint, wrap_fp16_model
from mmdet3d.models import build_model

STREETWORLD_ROOT = Path(__file__).resolve().parents[3]
if str(STREETWORLD_ROOT) not in sys.path:
    sys.path.insert(0, str(STREETWORLD_ROOT))

from rl_framework.common.mmcv_utils import cleanup_mmcv_registries
from rl_framework.uniad.dataparser import parse_uniad_obs
# from rl_framework.vad.trajectory import decode_ego_future_traj
from rl_framework.vad.dataparser import get_vad_img_norm_cfg, parse_vad_obs


def _import_plugin_from_cfg(cfg: Config, config_rel_path: str) -> None:
    if not getattr(cfg, "plugin", False):
        return
    if hasattr(cfg, "plugin_dir"):
        module_dir = os.path.dirname(cfg.plugin_dir)
    else:
        module_dir = os.path.dirname(config_rel_path)
    module_path = module_dir.replace("/", ".").replace("\\", ".").strip(".")
    if module_path:
        importlib.import_module(module_path)


def _cleanup_vad_registries() -> None:
    try:
        from mmdet.core.bbox.match_costs.builder import MATCH_COST

        if hasattr(MATCH_COST, "_module_dict") and "DiceCost" in MATCH_COST._module_dict:
            del MATCH_COST._module_dict["DiceCost"]
    except Exception:
        pass

    try:
        from mmdet.models.builder import LOSSES

        if hasattr(LOSSES, "_module_dict") and "DiceLoss" in LOSSES._module_dict:
            del LOSSES._module_dict["DiceLoss"]
    except Exception:
        pass


def _load_model(config_path: Path, checkpoint_path: Path, ad_root: Path, device: torch.device):
    cleanup_mmcv_registries()
    config_path_abs = config_path.resolve()
    checkpoint_path_abs = checkpoint_path.resolve()
    ad_root_abs = ad_root.resolve()
    if str(ad_root_abs) not in sys.path:
        sys.path.insert(0, str(ad_root_abs))

    original_cwd = os.getcwd()
    try:
        os.chdir(str(ad_root_abs))
        config_rel_path = os.path.relpath(str(config_path_abs), str(ad_root_abs))
        cfg = Config.fromfile(config_rel_path)

        if cfg.get("custom_imports", None):
            from mmcv.utils import import_modules_from_strings

            import_modules_from_strings(**cfg["custom_imports"])

        _import_plugin_from_cfg(cfg, config_rel_path)

        cfg.model.pretrained = None
        cfg.model.train_cfg = None
        model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))

        fp16_cfg = cfg.get("fp16", None)
        if fp16_cfg is not None:
            wrap_fp16_model(model)

        load_checkpoint(model, str(checkpoint_path_abs), map_location="cpu")
        model = fuse_conv_bn(model)
        model.to(device)
        return model
    finally:
        os.chdir(original_cwd)


def _set_trainable(module: torch.nn.Module, trainable_names: Iterable[str]) -> int:
    allow = tuple(trainable_names)
    for _, p in module.named_parameters():
        p.requires_grad = False
    trainable = 0
    for name, p in module.named_parameters():
        if any(name.startswith(prefix) for prefix in allow):
            p.requires_grad = True
            trainable += p.numel()
    return trainable


def _set_mode_with_prefixes(module: torch.nn.Module, trainable_prefixes: Iterable[str]) -> None:
    prefixes = tuple(trainable_prefixes)
    module.eval()
    for name, sub in module.named_modules():
        if any(name == p or name.startswith(p + ".") for p in prefixes):
            sub.train()


def unwrap_model(model: torch.nn.Module) -> torch.nn.Module:
    return model.module if hasattr(model, "module") else model


def build_uniad_trainable(config_path: Path, checkpoint_path: Path, ad_root: Path, device: torch.device):
    trainable_prefixes = ["planning_head"]
    model = _load_model(config_path, checkpoint_path, ad_root, device)
    trainable = _set_trainable(model, trainable_prefixes)
    setattr(model, "_il_trainable_prefixes", trainable_prefixes)
    _set_mode_with_prefixes(model, trainable_prefixes)
    return model, trainable


def build_vad_trainable(config_path: Path, checkpoint_path: Path, ad_root: Path, device: torch.device):
    _cleanup_vad_registries()
    model = _load_model(config_path, checkpoint_path, ad_root, device)

    prefixes = [
        "pts_bbox_head.ego_agent_decoder",
        "pts_bbox_head.ego_map_decoder",
        "pts_bbox_head.ego_fut_decoder",
        "pts_bbox_head.ego_agent_pos_mlp",
        "pts_bbox_head.ego_map_pos_mlp",
        "pts_bbox_head.ego_query",
    ]
    trainable = _set_trainable(model, prefixes)
    setattr(model, "_il_trainable_prefixes", prefixes)
    _set_mode_with_prefixes(model, prefixes)
    return model, trainable


def set_planning_train_mode(model: torch.nn.Module) -> None:
    model_impl = unwrap_model(model)
    prefixes = getattr(model_impl, "_il_trainable_prefixes", None)
    if prefixes is None:
        model_impl.train()
        return
    _set_mode_with_prefixes(model_impl, prefixes)


def build_uniad_input(sample: dict, cameras) -> Dict[str, object]:
    img_norm_cfg = {
        "mean": np.array([103.530, 116.280, 123.675], dtype=np.float32),
        "std": np.array([1.0, 1.0, 1.0], dtype=np.float32),
        "to_rgb": False,
    }
    raw = parse_uniad_obs(sample["obs"], sample["info"], sorted(cameras), img_norm_cfg)
    # UniAD forward_test does not accept auxiliary visualization payloads.
    raw.pop("raw_imgs", None)
    return raw


def build_vad_input(sample: dict) -> Dict[str, object]:
    raw = parse_vad_obs(sample["obs"], sample["info"], cameras=None, img_norm_cfg=get_vad_img_norm_cfg())
    # Keep inference payload minimal/compatible with benchmark clients.
    raw.pop("raw_imgs", None)
    return raw


def predict_uniad_traj(
    model: torch.nn.Module,
    raw_data: Dict[str, object],
    return_output: bool = False,
):
    model = unwrap_model(model)
    result = model(return_loss=False, rescale=True, **raw_data)
    uniad_output = result[0]
    traj = uniad_output["planning"]["result_planning"]["sdc_traj"][0]
    if traj.shape[-1] > 2:
        traj = traj[..., :2]
    if return_output:
        return traj, uniad_output
    return traj


def _run_vad_inference(model: torch.nn.Module, raw_data: Dict[str, object]) -> Dict[str, Any]:
    model = unwrap_model(model)
    infer_input = dict(raw_data)
    if not isinstance(infer_input.get("img"), (list, tuple)):
        infer_input["img"] = [infer_input["img"]]

    result = model(return_loss=False, rescale=True, return_bbox=True, **infer_input)
    vad_output = result[0] if isinstance(result, (list, tuple)) and len(result) > 0 else result
    if not isinstance(vad_output, dict):
        raise RuntimeError("Unexpected VAD inference output: expected dict-like payload.")
    return vad_output


def predict_vad_traj(
    model: torch.nn.Module,
    raw_data: Dict[str, object],
    return_output: bool = False,
):
    vad_output = _run_vad_inference(model, raw_data)

    pts_bbox = vad_output.get("pts_bbox")
    out_dict: Dict[str, Any] = pts_bbox if isinstance(pts_bbox, dict) else vad_output
    ego_fut_preds = out_dict.get("ego_fut_preds", None)
    if ego_fut_preds is None:
        raise KeyError("VAD output missing ego_fut_preds for planning trajectory decode.")

    cmd_device = raw_data["ego_fut_cmd"].device
    if not torch.is_tensor(ego_fut_preds):
        ego_fut_preds = torch.as_tensor(ego_fut_preds, device=cmd_device, dtype=torch.float32)
    else:
        ego_fut_preds = ego_fut_preds.to(device=cmd_device, dtype=torch.float32)
    if ego_fut_preds.ndim == 4:
        ego_fut_preds = ego_fut_preds[0]
    if ego_fut_preds.ndim != 3:
        raise RuntimeError(f"Unexpected ego_fut_preds shape: {tuple(ego_fut_preds.shape)}")

    cmd_vec = raw_data["ego_fut_cmd"][0, 0, 0]
    cmd_idx = int(torch.argmax(cmd_vec).item())
    traj = ego_fut_preds[cmd_idx].cumsum(dim=-2)
    if not return_output:
        return traj, cmd_vec

    if isinstance(vad_output.get("pts_bbox"), dict):
        vad_output["pts_bbox"].setdefault("ego_fut_cmd", cmd_vec)
    else:
        vad_output.setdefault("ego_fut_cmd", cmd_vec)
    return traj, cmd_vec, vad_output
