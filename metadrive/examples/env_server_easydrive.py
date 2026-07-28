#!/usr/bin/env python
"""Serve EasyDrive or NuRec scenarios through the StreetWorld gRPC API."""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Sequence

from metadrive.config import Config
from metadrive.configs.alpamayo_config import ALPAMAYO_CONFIG
from metadrive.configs.autovla_config import AUTOVLA_CONFIG
from metadrive.configs.diffusiondrive_config import DIFFUSIONDRIVE_CONFIG
from metadrive.configs.epona_config import EPONA_CONFIG
from metadrive.configs.genad_config import GENAD_CONFIG
from metadrive.configs.momad_config import MOMAD_CONFIG
from metadrive.configs.nurec_config import NUREC_CONFIG
from metadrive.configs.omnidrive_config import OMNIDRIVE_CONFIG
from metadrive.configs.openemma_config import OPENEMMA_CONFIG
from metadrive.configs.opendrivevla_config import OPENDRIVEVLA_CONFIG
from metadrive.configs.sparsedrive_config import SPARSEDRIVE_CONFIG
from metadrive.configs.stp3_config import STP3_CONFIG
from metadrive.configs.transfuser_config import TRANSFUSER_CONFIG
from metadrive.configs.uniad_config import UNIAD_CONFIG
from metadrive.configs.vad_config import VAD_CONFIG
from metadrive.envs.env_servicer import serve
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.envs.interactive_env import make_interactive_env
from metadrive.examples.easydrive_tui import (
    BACKENDS,
    resolve_scene_config,
    select_catalog_scenes,
)
from metadrive.misc.nurec_interface.simulator_interface import SimulatorInterface as NurecSimulatorInterface


InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
AD_POLICY_CONFIGS = {
    "alpamayo1": ALPAMAYO_CONFIG,
    "alpamayo1_5": ALPAMAYO_CONFIG,
    "autovla": AUTOVLA_CONFIG,
    "default": {},
    "diffusiondrive": DIFFUSIONDRIVE_CONFIG,
    "epona": EPONA_CONFIG,
    "genad": GENAD_CONFIG,
    "momad": MOMAD_CONFIG,
    "omnidrive": OMNIDRIVE_CONFIG,
    "openemma": OPENEMMA_CONFIG,
    "opendrivevla": OPENDRIVEVLA_CONFIG,
    "sparsedrive": SPARSEDRIVE_CONFIG,
    "stp3": STP3_CONFIG,
    "transfuser": TRANSFUSER_CONFIG,
    "uniad": UNIAD_CONFIG,
    "vad": VAD_CONFIG,
}


def resolve_ad_policy_config(name: str) -> dict:
    name = str(name).strip().lower()
    if name not in AD_POLICY_CONFIGS:
        valid = ", ".join(sorted(AD_POLICY_CONFIGS))
        raise ValueError(f"Unknown AD policy config {name!r}. Valid options: {valid}")
    return AD_POLICY_CONFIGS[name]


def build_environment(
    *,
    backend: str,
    scene_ids: Sequence[str],
    ad_policy_config: str,
    nurec_grpc_host: str,
    nurec_grpc_port: int,
    nurec_grpc_timeout: float,
    web_host: str,
    web_port: int,
    video_output_dir: str,
    async_mode: bool,
    tui: bool,
):
    config_values = {
        "scene_ids": list(scene_ids),
        "random_scenario": False,
        "async_mode": async_mode,
        "web_host": web_host,
        "web_port": web_port,
        "video_output_dir": video_output_dir,
        "eval_mode": True,
        "eval_order": True,
        "eval_repeat_per_scene": 1,
        "tui": tui,
    }
    if backend == "easydrive":
        from easydrive.models.scenes.simulator_interface import SimulatorInterface as EasyDriveSimulatorInterface

        config = Config(resolve_ad_policy_config(ad_policy_config))
        config.merge_from(config_values)
        return InteractiveScenarioEnv(EasyDriveSimulatorInterface(), config)
    if backend == "nurec":
        config = Config(config_values)
        config.merge_from(NUREC_CONFIG)
        return InteractiveScenarioEnv(
            NurecSimulatorInterface(
                grpc_host=nurec_grpc_host,
                grpc_port=nurec_grpc_port,
                grpc_timeout_s=nurec_grpc_timeout,
            ),
            config,
        )
    raise ValueError(f"Unknown backend {backend!r}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StreetWorld EasyDrive/NuRec environment server")
    parser.add_argument("-c", "--scene-config", type=Path, help="Scene config directory or YAML list")
    parser.add_argument("--backend", choices=BACKENDS, help="Backend required with --scene-config")
    parser.add_argument("--host", default="127.0.0.1", help="StreetWorld gRPC bind address")
    parser.add_argument("--port", type=int, default=50052, help="StreetWorld gRPC bind port")
    parser.add_argument("--web-host", default="127.0.0.1", help="WebUI bind address")
    parser.add_argument("--web-port", type=int, default=18080, help="WebUI bind port")
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum gRPC handler workers")
    parser.add_argument("--ad-policy-config", type=str.lower, default="default", choices=sorted(AD_POLICY_CONFIGS))
    parser.add_argument("--video-output-dir", default="videos", help="Directory for environment video recordings")
    parser.add_argument("--async-mode", action="store_true", help="Run simulation in fixed-period asynchronous mode")
    parser.add_argument("--no-tui", action="store_true", help="Disable the Rich interface; requires --scene-config")
    parser.add_argument("--nurec-grpc-host", default="127.0.0.1", help="NuRec renderer address")
    parser.add_argument("--nurec-grpc-port", type=int, default=8080, help="NuRec renderer port")
    parser.add_argument("--nurec-grpc-timeout", type=float, default=600.0, help="NuRec renderer timeout in seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.scene_config is None:
        if args.no_tui:
            raise ValueError("--no-tui requires --scene-config.")
        if args.backend is not None:
            raise ValueError("--backend is determined by catalog mode; omit it when --scene-config is omitted.")
        try:
            selection = select_catalog_scenes()
        except KeyboardInterrupt:
            return 130
        backend = selection.backend
        scene_ids = list(selection.scenes)
    else:
        if args.backend is None:
            raise ValueError("--backend is required when --scene-config is supplied.")
        backend = args.backend
        scene_ids = resolve_scene_config(args.scene_config, backend)

    env = build_environment(
        backend=backend,
        scene_ids=scene_ids,
        ad_policy_config=args.ad_policy_config,
        nurec_grpc_host=args.nurec_grpc_host,
        nurec_grpc_port=args.nurec_grpc_port,
        nurec_grpc_timeout=args.nurec_grpc_timeout,
        web_host=args.web_host,
        web_port=args.web_port,
        video_output_dir=args.video_output_dir,
        async_mode=args.async_mode,
        tui=not args.no_tui,
    )
    serve(env, host=args.host, port=args.port, max_workers=args.max_workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
