from __future__ import annotations

import argparse
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Any

import torch


def _extract_state_dict(ckpt: Any) -> OrderedDict:
    if isinstance(ckpt, OrderedDict):
        return ckpt

    if not isinstance(ckpt, dict):
        raise TypeError(f"Unsupported checkpoint type: {type(ckpt)}")

    if "state_dict" in ckpt and isinstance(ckpt["state_dict"], (dict, OrderedDict)):
        return OrderedDict(ckpt["state_dict"])

    if "model_state_dict" in ckpt and isinstance(ckpt["model_state_dict"], (dict, OrderedDict)):
        return OrderedDict(ckpt["model_state_dict"])

    # Fallback: treat dict itself as state_dict if tensor-like values are present.
    if ckpt and all(hasattr(v, "shape") for v in ckpt.values()):
        return OrderedDict(ckpt)

    raise KeyError("Could not find model weights in checkpoint (expected 'state_dict' or 'model_state_dict').")


def _strip_module_prefix(state_dict: OrderedDict) -> OrderedDict:
    out = OrderedDict()
    for k, v in state_dict.items():
        nk = k[7:] if k.startswith("module.") else k
        out[nk] = v
    return out


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

    if args.mmcv_wrapper:
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
    print(f"[ok] Num parameters: {len(state_dict)}")


if __name__ == "__main__":
    main()
