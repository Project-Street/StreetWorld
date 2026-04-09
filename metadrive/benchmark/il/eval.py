from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from metadrive.benchmark.il.dataset import ILSceneDataset, collate_list, split_records
from metadrive.benchmark.il.models import (
    build_uniad_input,
    build_uniad_trainable,
    build_vad_input,
    build_vad_trainable,
    predict_uniad_traj,
    predict_vad_traj,
)
from metadrive.benchmark.il.scene_io import discover_scene_configs, load_scene_from_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate planning-only IL model")
    parser.add_argument("--model", choices=["uniad", "vad"], required=True)
    parser.add_argument("--scene-config-dir", type=str, default=str(Path(__file__).resolve().parents[3] / "scene_configs"))
    parser.add_argument("--ad-root", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument(
        "--future-step-stride",
        type=int,
        default=0,
        help="GT stride in 0.1s pose steps. 0 means auto=5 (0.5s) for both UniAD and VAD.",
    )
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--train-ratio", type=float, default=0.9)
    return parser.parse_args()


def compute_sample_metrics(pred_xy: torch.Tensor, target_xy: np.ndarray, target_mask: np.ndarray) -> tuple[float, float]:
    target = torch.from_numpy(target_xy).to(device=pred_xy.device, dtype=torch.float32)
    mask = torch.from_numpy(target_mask).to(device=pred_xy.device, dtype=torch.float32) > 0.5
    t = target.shape[0]
    pred = pred_xy[:t, :2]
    dist = torch.linalg.norm(pred - target, dim=-1)
    if mask.any():
        ade = float(dist[mask].mean().item())
        fde = float(dist[mask][-1].item())
    else:
        ade = 0.0
        fde = 0.0
    return ade, fde


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("Evaluation currently requires CUDA.")
    device = torch.device("cuda")

    scenes = [load_scene_from_config(p) for p in discover_scene_configs(Path(args.scene_config_dir))]
    stride = int(args.future_step_stride)
    if stride <= 0:
        stride = 5
    _, val_records = split_records(
        scenes,
        train_ratio=float(args.train_ratio),
        horizon=int(args.horizon),
        future_step_stride=stride,
        seed=42,
    )
    dataset = ILSceneDataset(
        scenes=scenes,
        horizon=int(args.horizon),
        future_step_stride=stride,
        indices=val_records,
    )
    loader = DataLoader(dataset, batch_size=int(args.batch_size), shuffle=False, num_workers=int(args.workers), collate_fn=collate_list)

    if args.model == "uniad":
        model, _ = build_uniad_trainable(Path(args.config), Path(args.checkpoint), Path(args.ad_root), device)
    else:
        model, _ = build_vad_trainable(Path(args.config), Path(args.checkpoint), Path(args.ad_root), device)
    model.eval()

    ades = []
    fdes = []
    with torch.no_grad():
        for batch in loader:
            for sample in batch:
                if args.model == "uniad":
                    raw = build_uniad_input(sample, cameras=set(sample["obs"].keys()))
                    pred = predict_uniad_traj(model, raw)
                else:
                    raw = build_vad_input(sample)
                    pred, _ = predict_vad_traj(model, raw)
                ade, fde = compute_sample_metrics(pred, sample["target_xy"], sample["target_mask"])
                ades.append(ade)
                fdes.append(fde)

    print(f"Eval samples: {len(ades)}")
    print(f"ADE: {float(np.mean(ades) if ades else 0.0):.6f}")
    print(f"FDE: {float(np.mean(fdes) if fdes else 0.0):.6f}")


if __name__ == "__main__":
    main()
