# Planning-Only IL (UniAD / VAD)

This folder provides imitation learning warm-start for planning modules only.

## What it does

- Loads scenes from `submodules/StreetWorld/scene_configs/*.yaml`.
- Renders NuScenes camera images once with Gaussian simulator.
- Caches renders under `<tracking_dir>/cache/<scene_name>/...`.
  - Example: if tracking is `/data/scene_001/tracking.json`, cache is `/data/scene_001/cache/<scene_name>/...`.
- Derives driving command with the same turn-signal logic as `metadrive/obs/navigation_obs.py`.
- Trains planning-only parameters (perception frozen) for UniAD or VAD.
- Supports single GPU and multi-GPU DDP (`torchrun`).
- Logs training metrics to TensorBoard.

## Trajectory target alignment

- VAD prediction is offset-based and is decoded with cumulative sum before loss.
- UniAD planning head output is already cumulative trajectory.
- GT interval alignment default is `--future-step-stride=5`, i.e. 0.5s between future points.
  - This matches NuScenes keyframe spacing used by both UniAD and VAD labels.
- You can override via `--future-step-stride` when your scene timing differs.

## Run

If your `c2w_path` npz cannot be loaded due to numpy version mismatch, convert first:

```bash
python -m metadrive.benchmark.il.convert_c2w_to_json --scene-config-dir ./scene_configs
```

You can also write converted path into scene yaml files:

```bash
python -m metadrive.benchmark.il.convert_c2w_to_json --scene-config-dir ./scene_configs --update-scene-config
```

From `submodules/StreetWorld`:

```bash
python -m metadrive.benchmark.il.train \
  --model uniad \
  --ad-root ./UniAD_SIM \
  --config ./UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py \
  --checkpoint ./UniAD_SIM/ckpts/uniad_base_e2e.pth \
  --output-dir ./metadrive/benchmark/il/outputs/uniad_il
```

```bash
python -m metadrive.benchmark.il.train \
  --model vad \
  --ad-root ./VAD \
  --config ./VAD/projects/configs/VAD/VAD_base_e2e.py \
  --checkpoint ./VAD/ckpts/VAD_base.pth \
  --output-dir ./metadrive/benchmark/il/outputs/vad_il
```

Multi-GPU:

```bash
torchrun --nproc_per_node=4 -m metadrive.benchmark.il.train \
  --model uniad \
  --ad-root ./UniAD_SIM \
  --config ./UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py \
  --checkpoint ./UniAD_SIM/ckpts/uniad_base_e2e.pth
```

Debug visual dump (camera + BEV) similar to benchmark clients:

```bash
python -m metadrive.benchmark.il.train \
  --model uniad \
  --ad-root ./UniAD_SIM \
  --config ./UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py \
  --checkpoint ./UniAD_SIM/ckpts/uniad_base_e2e.pth \
  --debug-save-vis \
  --debug-vis-steps 50
```

Images are written to `<output_dir>/debug_vis/` by default.

## TensorBoard

```bash
tensorboard --logdir metadrive/benchmark/il/outputs
```

Key logs:

- `train/loss_total`, `train/ade`, `train/fde`, `train/lr`, `train/grad_norm`
- `val/loss`, `val/ade`, `val/fde`
- `data/cache_hit_ratio`, `data/render_time_sec`

## Convert IL checkpoint for clients

Training saves epoch checkpoints containing optimizer/config metadata. To use a
checkpoint directly in benchmark clients (`uniad_client.py` / `vad_client.py`),
convert it to plain model weights:

```bash
python -m metadrive.benchmark.il.convert_il_checkpoint \
  --input metadrive/benchmark/il/outputs/uniad_il/checkpoints/uniad_epoch_001.pth
```

This writes `<input_stem>_weights.pth` by default, which can be passed to
`--checkpoint` in clients.
