from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Any, Mapping, Iterable, List

import torch


def _is_tensor_mapping(obj: Any) -> bool:
    return isinstance(obj, Mapping) and len(obj) > 0 and all(torch.is_tensor(v) for v in obj.values())


def _extract_state_dict(ckpt: Any) -> OrderedDict:
    if isinstance(ckpt, OrderedDict):
        return ckpt

    if not isinstance(ckpt, dict):
        raise TypeError(f"Unsupported checkpoint type: {type(ckpt)}")

    state_dict = ckpt.get("state_dict", None)
    model_state_dict = ckpt.get("model_state_dict", None)

    if _is_tensor_mapping(state_dict) and _is_tensor_mapping(model_state_dict):
        # Prefer the richer one when both exist to avoid exporting an adapter-only state_dict.
        if len(model_state_dict) >= len(state_dict):
            return OrderedDict(model_state_dict)
        return OrderedDict(state_dict)

    if _is_tensor_mapping(model_state_dict):
        return OrderedDict(model_state_dict)

    if _is_tensor_mapping(state_dict):
        return OrderedDict(state_dict)

    # Fallback: treat dict itself as state_dict if tensor-like values are present.
    if _is_tensor_mapping(ckpt):
        return OrderedDict(ckpt)

    raise KeyError("Could not find model weights in checkpoint (expected 'state_dict' or 'model_state_dict').")


def _strip_module_prefix(state_dict: OrderedDict) -> OrderedDict:
    out = OrderedDict()
    for k, v in state_dict.items():
        nk = k[7:] if k.startswith("module.") else k
        out[nk] = v
    return out


def _infer_model_type(ckpt: Any, input_path: Path) -> str:
    if isinstance(ckpt, Mapping):
        cfg = ckpt.get("config", None)
        if isinstance(cfg, Mapping):
            mt = cfg.get("model_type", None)
            if isinstance(mt, str) and mt in {"uniad", "vad"}:
                return mt
    name = input_path.name.lower()
    if "uniad" in name:
        return "uniad"
    if "vad" in name:
        return "vad"
    return ""


def _default_trainable_prefixes(model_type: str) -> List[str]:
    if model_type == "uniad":
        return ["planning_head"]
    if model_type == "vad":
        return [
            "pts_bbox_head.ego_agent_decoder",
            "pts_bbox_head.ego_map_decoder",
            "pts_bbox_head.ego_fut_decoder",
            "pts_bbox_head.ego_agent_pos_mlp",
            "pts_bbox_head.ego_map_pos_mlp",
            "pts_bbox_head.ego_query",
        ]
    return []


def _matches_prefix(key: str, prefixes: Iterable[str]) -> bool:
    for p in prefixes:
        if key == p or key.startswith(p + "."):
            return True
    return False


def _merge_with_base(base_state_dict: OrderedDict, il_state_dict: OrderedDict, include_prefixes: Iterable[str]) -> OrderedDict:
    prefixes = tuple(include_prefixes)
    restrict = len(prefixes) > 0
    merged = OrderedDict(base_state_dict)
    updated = 0
    skipped = 0
    filtered = 0
    for k, v in il_state_dict.items():
        if restrict and not _matches_prefix(k, prefixes):
            filtered += 1
            continue
        if k in merged and merged[k].shape == v.shape:
            merged[k] = v
            updated += 1
        else:
            skipped += 1
    if restrict:
        print(f"[info] Merge with base: updated={updated} skipped={skipped} filtered={filtered}")
    else:
        print(f"[info] Merge with base: updated={updated} skipped={skipped}")
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert IL training checkpoint to client-loadable model weights"
    )
    parser.add_argument("--input", type=str, required=True, help="Input checkpoint path")
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Output path (default: <input_stem>_weights.pth)",
    )
    parser.add_argument(
        "--keep-module-prefix",
        action="store_true",
        help="Do not strip leading 'module.' from parameter names",
    )
    parser.add_argument(
        "--mmcv-wrapper",
        action="store_true",
        help="Save as {'state_dict': ... , 'meta': ...} instead of raw state_dict",
    )
    parser.add_argument(
        "--base-checkpoint",
        type=str,
        default="",
        help="Optional full base checkpoint. When provided, converted weights are merged into base weights.",
    )
    parser.add_argument(
        "--trainable-only",
        action="store_true",
        help="When used with --base-checkpoint, only merge known trainable prefixes (e.g., UniAD planning_head).",
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default="",
        choices=["", "uniad", "vad"],
        help="Model type for --trainable-only. Auto-infer if omitted.",
    )
    parser.add_argument(
        "--include-prefix",
        action="append",
        default=[],
        help="Custom key prefix to merge (repeatable). Takes precedence over --trainable-only defaults.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        raise FileNotFoundError(f"Input checkpoint not found: {in_path}")

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = in_path.with_name(f"{in_path.stem}_weights.pth")

    ckpt = torch.load(str(in_path), map_location="cpu")
    state_dict = _extract_state_dict(ckpt)
    if not args.keep_module_prefix:
        state_dict = _strip_module_prefix(state_dict)

    include_prefixes: List[str] = [str(x) for x in args.include_prefix if str(x)]
    if not include_prefixes and args.trainable_only:
        model_type = str(args.model_type).strip() or _infer_model_type(ckpt, in_path)
        include_prefixes = _default_trainable_prefixes(model_type)
        if not include_prefixes:
            raise ValueError(
                "Could not determine trainable prefixes for --trainable-only. "
                "Please pass --model-type {uniad|vad} or explicit --include-prefix."
            )
        print(f"[info] trainable-only prefixes ({model_type}): {include_prefixes}")

    base_payload = None
    if args.base_checkpoint:
        base_path = Path(args.base_checkpoint)
        if not base_path.exists():
            raise FileNotFoundError(f"Base checkpoint not found: {base_path}")
        base_ckpt = torch.load(str(base_path), map_location="cpu")
        base_payload = base_ckpt
        base_state_dict = _extract_state_dict(base_ckpt)
        if not args.keep_module_prefix:
            base_state_dict = _strip_module_prefix(base_state_dict)
        state_dict = _merge_with_base(base_state_dict, state_dict, include_prefixes=include_prefixes)

    if args.base_checkpoint and isinstance(base_payload, Mapping) and "state_dict" in base_payload and isinstance(base_payload["state_dict"], Mapping):
        payload = dict(base_payload)
        payload["state_dict"] = state_dict
        if "meta" not in payload or not isinstance(payload.get("meta"), Mapping):
            payload["meta"] = {}
        payload["meta"] = dict(payload["meta"])
        payload["meta"]["converted_from"] = str(in_path)
    elif args.mmcv_wrapper:
        payload: Dict[str, Any] = {
            "state_dict": state_dict,
            "meta": {"converted_from": str(in_path)},
        }
    else:
        payload = state_dict

    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, str(out_path))

    print(f"[ok] Converted checkpoint: {in_path}")
    print(f"[ok] Saved weights to: {out_path}")
    print(f"[ok] Num tensors: {len(state_dict)}")


if __name__ == "__main__":
    main()
