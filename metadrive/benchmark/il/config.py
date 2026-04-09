from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ILConfig:
    model_type: str
    scene_config_dir: Path
    output_dir: Path
    ad_root: Path
    config_path: Path
    checkpoint_path: Path
    epochs: int
    batch_size: int
    workers: int
    lr: float
    weight_decay: float
    horizon: int
    future_step_stride: int
    train_ratio: float
    seed: int
    force_render: bool
    early_signal_distance: float
    turn_inradius_threshold: float
    debug_save_vis: bool
    debug_vis_dir: Path
    debug_vis_steps: int
    debug_bev_render: str
