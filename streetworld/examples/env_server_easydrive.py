#!/usr/bin/env python
"""Serve EasyDrive or NuRec scenarios through the StreetWorld gRPC API."""

from __future__ import annotations

import argparse
from typing import Sequence

from streetworld.config import Config
from streetworld.configs.autovla_config import AUTOVLA_CONFIG
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S
from streetworld.configs.epona_config import EPONA_CONFIG
from streetworld.configs.nurec_config import NUREC_CONFIG
from streetworld.configs.openemma_config import OPENEMMA_CONFIG
from streetworld.configs.transfuser_config import TRANSFUSER_CONFIG
from streetworld.envs.env_servicer import serve
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.misc.nurec_interface.simulator_interface import SimulatorInterface as NurecSimulatorInterface
from streetworld.ui.scene_selector import select_catalog_scenes


InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
AD_POLICY_CONFIGS = {
    "autovla": AUTOVLA_CONFIG,
    "epona": EPONA_CONFIG,
    "openemma": OPENEMMA_CONFIG,
    "transfuser": TRANSFUSER_CONFIG,
    "latent_transfuser": TRANSFUSER_CONFIG,
}


def build_environment(
    *,
    backend: str,
    dataset: str,
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
        "backend": backend,
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
        from st_renderer import SimulatorInterface

        config = Config(DEFAULT_POLICY_CONFIG_0_5S)
        config.merge_from(AD_POLICY_CONFIGS.get(ad_policy_config, {}))
        config.merge_from(config_values)
        return InteractiveScenarioEnv(SimulatorInterface(dataset), config)
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
    parser.add_argument("--host", default="127.0.0.1", help="StreetWorld gRPC bind address")
    parser.add_argument("--port", type=int, default=50052, help="StreetWorld gRPC bind port")
    parser.add_argument("--web-host", default="127.0.0.1", help="WebUI bind address")
    parser.add_argument("--web-port", type=int, default=18080, help="WebUI bind port")
    parser.add_argument("--ad-policy-config", type=str.lower, default="default")
    parser.add_argument("--video-output-dir", default="videos", help="Directory for environment video recordings")
    parser.add_argument("--async-mode", action="store_true", help="Run simulation in fixed-period asynchronous mode")
    parser.add_argument("--nurec-grpc-host", default="127.0.0.1", help="NuRec renderer address")
    parser.add_argument("--nurec-grpc-port", type=int, default=8080, help="NuRec renderer port")
    parser.add_argument("--nurec-grpc-timeout", type=float, default=600.0, help="NuRec renderer timeout in seconds")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        selection = select_catalog_scenes()
    except KeyboardInterrupt:
        return 130
    backend = selection.backend
    dataset = selection.dataset.lower()
    scene_ids = list(selection.scenes)

    env = build_environment(
        backend=backend,
        dataset=dataset,
        scene_ids=scene_ids,
        ad_policy_config=args.ad_policy_config,
        nurec_grpc_host=args.nurec_grpc_host,
        nurec_grpc_port=args.nurec_grpc_port,
        nurec_grpc_timeout=args.nurec_grpc_timeout,
        web_host=args.web_host,
        web_port=args.web_port,
        video_output_dir=args.video_output_dir,
        async_mode=args.async_mode,
        tui=True,
    )
    serve(env, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
