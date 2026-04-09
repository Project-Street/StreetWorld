from __future__ import annotations

import argparse
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.distributed as dist
from tqdm.auto import tqdm
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler
from torch.utils.tensorboard import SummaryWriter

from metadrive.benchmark.il.config import ILConfig
from metadrive.benchmark.il.dataset import ILSceneDataset, collate_list, split_records
from metadrive.benchmark.il.debug_vis import save_debug_visuals
from metadrive.benchmark.il.models import (
    build_uniad_input,
    build_uniad_trainable,
    build_vad_input,
    build_vad_trainable,
    predict_uniad_traj,
    predict_vad_traj,
    # predict_vad_traj_with_prev,
    set_planning_train_mode,
    unwrap_model,
)
from metadrive.benchmark.il.render_cache import ensure_scene_cache
from metadrive.benchmark.il.scene_io import discover_scene_configs, load_scene_from_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Planning-only IL for UniAD/VAD")
    parser.add_argument("--model", choices=["uniad", "vad"], required=True)
    parser.add_argument(
        "--scene-config-dir",
        type=str,
        default=str(Path(__file__).resolve().parents[3] / "scene_configs"),
    )
    parser.add_argument("--output-dir", type=str, default=str(Path(__file__).resolve().parent / "outputs"))
    parser.add_argument("--ad-root", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--checkpoint", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument(
        "--future-step-stride",
        type=int,
        default=0,
        help="GT stride in 0.1s pose steps. 0 means auto=5 (0.5s) for both UniAD and VAD.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.9)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force-render", action="store_true")
    parser.add_argument("--early-signal-distance", type=float, default=10.0)
    parser.add_argument("--turn-inradius-threshold", type=float, default=15.0)
    parser.add_argument("--debug-save-vis", action="store_true", help="Save debug camera/BEV images during training")
    parser.add_argument("--debug-vis-dir", type=str, default="", help="Output directory for debug visuals")
    parser.add_argument("--debug-vis-steps", type=int, default=100, help="Save one debug sample every N global steps")
    parser.add_argument(
        "--debug-bev-render",
        type=str,
        default="traj",
        choices=["none", "traj", "output"],
        help="Reserved for compatibility with benchmark clients' BEV options",
    )
    return parser.parse_args()


def to_config(args: argparse.Namespace) -> ILConfig:
    stride = int(args.future_step_stride)
    if stride <= 0:
        stride = 5
    return ILConfig(
        model_type=args.model,
        scene_config_dir=Path(args.scene_config_dir),
        output_dir=Path(args.output_dir),
        ad_root=Path(args.ad_root),
        config_path=Path(args.config),
        checkpoint_path=Path(args.checkpoint),
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        workers=int(args.workers),
        lr=float(args.lr),
        weight_decay=float(args.weight_decay),
        horizon=int(args.horizon),
        future_step_stride=stride,
        train_ratio=float(args.train_ratio),
        seed=int(args.seed),
        force_render=bool(args.force_render),
        early_signal_distance=float(args.early_signal_distance),
        turn_inradius_threshold=float(args.turn_inradius_threshold),
        debug_save_vis=bool(args.debug_save_vis),
        debug_vis_dir=Path(args.debug_vis_dir) if args.debug_vis_dir else (Path(args.output_dir) / "debug_vis"),
        debug_vis_steps=max(1, int(args.debug_vis_steps)),
        debug_bev_render=str(args.debug_bev_render),
    )


def setup_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def setup_distributed() -> Tuple[bool, int, int, torch.device]:
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    distributed = world_size > 1
    if distributed:
        dist.init_process_group(backend="nccl", init_method="env://")
        rank = dist.get_rank()
        local_rank = int(os.environ.get("LOCAL_RANK", "0"))
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
        return True, rank, world_size, device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return False, 0, 1, device


def reduce_scalar(value: torch.Tensor, distributed: bool) -> float:
    if not distributed:
        return float(value.item())
    x = value.detach().clone()
    dist.all_reduce(x, op=dist.ReduceOp.SUM)
    x /= dist.get_world_size()
    return float(x.item())


def extract_target(sample: dict, device: torch.device) -> Tuple[torch.Tensor, torch.Tensor]:
    target = torch.from_numpy(sample["target_xy"]).to(device=device, dtype=torch.float32)
    mask = torch.from_numpy(sample["target_mask"]).to(device=device, dtype=torch.float32)
    return target, mask


def compute_losses(pred_xy: torch.Tensor, target_xy: torch.Tensor, mask: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    t = target_xy.shape[0]
    pred = pred_xy[:t, :2]
    diff = pred - target_xy
    l2 = torch.linalg.norm(diff, dim=-1)
    valid = mask > 0.5
    if valid.any():
        ade = l2[valid].mean()
        fde = l2[valid][-1]
        loss = ade
    else:
        ade = torch.zeros((), device=pred.device, dtype=pred.dtype)
        fde = torch.zeros((), device=pred.device, dtype=pred.dtype)
        loss = ade
    return loss, ade, fde


def load_scenes(cfg: ILConfig) -> List:
    configs = discover_scene_configs(cfg.scene_config_dir)
    if not configs:
        raise FileNotFoundError(f"No scene config found in: {cfg.scene_config_dir}")
    return [load_scene_from_config(p) for p in configs]


def ensure_caches(scenes: List, rank: int, distributed: bool, force_render: bool, writer: SummaryWriter | None) -> None:
    cache_stats = []
    if rank == 0:
        for scene in scenes:
            stats = ensure_scene_cache(scene, force=force_render)
            cache_stats.append(stats)
            print(
                f"[cache] {scene.scene_name}: rendered={int(stats['rendered'])} "
                f"skipped={int(stats['skipped'])} hit={stats['cache_hit_ratio']:.3f}"
            )

        if writer and cache_stats:
            writer.add_scalar("data/cache_hit_ratio", float(np.mean([s["cache_hit_ratio"] for s in cache_stats])), 0)
            writer.add_scalar("data/render_time_sec", float(np.sum([s["elapsed_sec"] for s in cache_stats])), 0)

    if distributed:
        dist.barrier()


def make_model(cfg: ILConfig, device: torch.device):
    if cfg.model_type == "uniad":
        model, trainable = build_uniad_trainable(cfg.config_path, cfg.checkpoint_path, cfg.ad_root, device)
    else:
        model, trainable = build_vad_trainable(cfg.config_path, cfg.checkpoint_path, cfg.ad_root, device)
    if trainable <= 0:
        raise RuntimeError("No trainable parameters selected for planning-only IL")
    return model, trainable


def batch_forward(
    model,
    batch: List[dict],
    cfg: ILConfig,
    device: torch.device,
    rank: int = 0,
    global_step: int = -1,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    total_loss = torch.zeros((), device=device)
    total_ade = 0.0
    total_fde = 0.0
    count = 0
    debug_enabled = (
        cfg.debug_save_vis
        and rank == 0
        and global_step >= 0
        and (global_step % cfg.debug_vis_steps == 0)
    )
    debug_saved = False

    for sample_idx, sample in enumerate(batch):
        target_xy, target_mask = extract_target(sample, device)
        uniad_output = None
        vad_output = None
        if cfg.model_type == "uniad":
            warmup_obs = sample.get("warmup_obs", [])
            warmup_info = sample.get("warmup_info", [])
            if len(warmup_obs) == len(warmup_info) and len(warmup_obs) > 0:
                for wo, wi in zip(warmup_obs, warmup_info):
                    warmup_sample = {
                        "obs": wo,
                        "info": wi,
                    }
                    warmup_raw = build_uniad_input(warmup_sample, cameras=set(wo.keys()))
                    warmup_raw.pop("raw_imgs", None)
                    with torch.no_grad():
                        _ = predict_uniad_traj(model, warmup_raw)
            raw_data = build_uniad_input(sample, cameras=set(sample["obs"].keys()))
            raw_data.pop("raw_imgs", None)
            if debug_enabled and not debug_saved and sample_idx == 0 and cfg.debug_bev_render == "output":
                pred, uniad_output = predict_uniad_traj(model, raw_data, return_output=True)
            else:
                pred = predict_uniad_traj(model, raw_data)
        else:
            warmup_obs = sample.get("warmup_obs", [])
            warmup_info = sample.get("warmup_info", [])
            if len(warmup_obs) == len(warmup_info) and len(warmup_obs) > 0:
                for wo, wi in zip(warmup_obs, warmup_info):
                    warmup_sample = {
                        "obs": wo,
                        "info": wi,
                    }
                    warmup_raw = build_vad_input(warmup_sample)
                    warmup_raw.pop("raw_imgs", None)
                    with torch.no_grad():
                        _ = predict_vad_traj(model, warmup_raw)
            raw_data = build_vad_input(sample)
            raw_data.pop("raw_imgs", None)
            if debug_enabled and not debug_saved and sample_idx == 0 and cfg.debug_bev_render == "output":
                pred, _, vad_output = predict_vad_traj(model, raw_data, return_output=True)
            else:
                pred, _ = predict_vad_traj(model, raw_data)
        if sample['info']['relative_timestamp'] < 0.3:
            # Ensures temporal info
            continue
        loss, ade, fde = compute_losses(pred, target_xy, target_mask)

        if debug_enabled and not debug_saved and sample_idx == 0:
            pred_np = pred.detach().cpu().numpy()
            save_debug_visuals(
                sample=sample,
                pred_traj=pred_np,
                out_dir=cfg.debug_vis_dir,
                step=global_step,
                model_type=cfg.model_type,
                bev_render_mode=cfg.debug_bev_render,
                uniad_output=uniad_output,
                vad_output=vad_output,
                prefix=f"{cfg.model_type}_train",
            )
            debug_saved = True

        total_loss = total_loss + loss
        total_ade += float(ade.detach().item())
        total_fde += float(fde.detach().item())
        count += 1
    
    if count == 0:
        zero = torch.zeros((), device=device, requires_grad=True)
        return zero, {"ade": 0.0, "fde": 0.0}

    total_loss = total_loss / max(1, count)
    metrics = {
        "ade": total_ade / max(1, count),
        "fde": total_fde / max(1, count),
    }
    return total_loss, metrics


def evaluate(model, loader: DataLoader, cfg: ILConfig, device: torch.device) -> Dict[str, float]:
    model.eval()
    losses, ades, fdes = [], [], []
    with torch.no_grad():
        for batch in loader:
            loss, metrics = batch_forward(model, batch, cfg, device)
            losses.append(float(loss.item()))
            ades.append(metrics["ade"])
            fdes.append(metrics["fde"])
    model.train()
    return {
        "loss": float(np.mean(losses) if losses else 0.0),
        "ade": float(np.mean(ades) if ades else 0.0),
        "fde": float(np.mean(fdes) if fdes else 0.0),
    }


def main() -> None:
    args = parse_args()
    cfg = to_config(args)
    distributed, rank, world_size, device = setup_distributed()
    if device.type != "cuda":
        raise RuntimeError("IL training currently requires CUDA because UniAD/VAD dataparser uses CUDA tensors.")
    setup_seed(cfg.seed + rank)

    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    tb_dir = cfg.output_dir / "tensorboard"
    ckpt_dir = cfg.output_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    writer = SummaryWriter(str(tb_dir)) if rank == 0 else None

    scenes = load_scenes(cfg)
    ensure_caches(scenes, rank=rank, distributed=distributed, force_render=cfg.force_render, writer=writer)

    train_records, val_records = split_records(
        scenes,
        train_ratio=cfg.train_ratio,
        horizon=cfg.horizon,
        future_step_stride=cfg.future_step_stride,
        seed=cfg.seed,
    )
    train_dataset = ILSceneDataset(
        scenes=scenes,
        horizon=cfg.horizon,
        future_step_stride=cfg.future_step_stride,
        indices=train_records,
        early_signal_distance=cfg.early_signal_distance,
        turn_inradius_threshold=cfg.turn_inradius_threshold,
    )
    val_dataset = ILSceneDataset(
        scenes=scenes,
        horizon=cfg.horizon,
        future_step_stride=cfg.future_step_stride,
        indices=val_records,
        early_signal_distance=cfg.early_signal_distance,
        turn_inradius_threshold=cfg.turn_inradius_threshold,
    )

    train_sampler = DistributedSampler(train_dataset, num_replicas=world_size, rank=rank, shuffle=True) if distributed else None
    val_sampler = DistributedSampler(val_dataset, num_replicas=world_size, rank=rank, shuffle=False) if distributed else None

    train_loader = DataLoader(
        train_dataset,
        batch_size=cfg.batch_size,
        sampler=train_sampler,
        shuffle=(train_sampler is None),
        num_workers=cfg.workers,
        pin_memory=torch.cuda.is_available(),
        collate_fn=collate_list,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=cfg.batch_size,
        sampler=val_sampler,
        shuffle=False,
        num_workers=cfg.workers,
        pin_memory=torch.cuda.is_available(),
        collate_fn=collate_list,
    )

    model, trainable = make_model(cfg, device)
    if distributed:
        model = DDP(model, device_ids=[device.index] if device.type == "cuda" else None, find_unused_parameters=True)

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=cfg.lr, weight_decay=cfg.weight_decay)

    if rank == 0:
        print(f"[il] model={cfg.model_type} trainable_params={trainable} train_samples={len(train_dataset)} val_samples={len(val_dataset)}")

    best_val = float("inf")
    global_step = 0
    for epoch in range(cfg.epochs):
        if train_sampler is not None:
            train_sampler.set_epoch(epoch)

        set_planning_train_mode(model)
        epoch_iter = tqdm(
            train_loader,
            desc=f"Epoch {epoch + 1}/{cfg.epochs}",
            leave=False,
            disable=(rank != 0),
            dynamic_ncols=True,
        )
        for batch in epoch_iter:
            optimizer.zero_grad(set_to_none=True)
            loss, train_metrics = batch_forward(model, batch, cfg, device, rank=rank, global_step=global_step)
            loss.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_(params, max_norm=35.0)
            optimizer.step()

            loss_val = reduce_scalar(loss.detach(), distributed)
            ade_val = train_metrics["ade"]
            fde_val = train_metrics["fde"]

            if writer and rank == 0:
                writer.add_scalar("train/loss_total", loss_val, global_step)
                writer.add_scalar("train/loss_traj", loss_val, global_step)
                writer.add_scalar("train/ade", ade_val, global_step)
                writer.add_scalar("train/fde", fde_val, global_step)
                writer.add_scalar("train/lr", float(optimizer.param_groups[0]["lr"]), global_step)
                writer.add_scalar("train/grad_norm", float(grad_norm), global_step)

            if rank == 0:
                epoch_iter.set_postfix(
                    loss=f"{loss_val:.4f}",
                    ade=f"{ade_val:.3f}",
                    fde=f"{fde_val:.3f}",
                )
            global_step += 1

        val_stats = evaluate(model, val_loader, cfg, device) if len(val_dataset) > 0 else {"loss": 0.0, "ade": 0.0, "fde": 0.0}
        val_loss_tensor = torch.tensor(val_stats["loss"], device=device)
        val_loss = reduce_scalar(val_loss_tensor, distributed)

        if writer and rank == 0:
            writer.add_scalar("val/loss", val_loss, epoch)
            writer.add_scalar("val/ade", val_stats["ade"], epoch)
            writer.add_scalar("val/fde", val_stats["fde"], epoch)

        if rank == 0:
            ckpt_epoch = ckpt_dir / f"{cfg.model_type}_epoch_{epoch + 1:03d}.pth"
            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": unwrap_model(model).state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "config": vars(cfg),
                },
                ckpt_epoch,
            )

            ckpt_last = ckpt_dir / f"{cfg.model_type}_last.pth"
            torch.save(unwrap_model(model).state_dict(), ckpt_last)
            if val_loss < best_val:
                best_val = val_loss
                ckpt_best = ckpt_dir / f"{cfg.model_type}_best.pth"
                torch.save(unwrap_model(model).state_dict(), ckpt_best)
            print(
                f"[epoch {epoch+1}/{cfg.epochs}] val_loss={val_loss:.4f} "
                f"val_ADE={val_stats['ade']:.4f} val_FDE={val_stats['fde']:.4f}"
            )

    if writer:
        writer.close()

    if distributed:
        dist.barrier()
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
