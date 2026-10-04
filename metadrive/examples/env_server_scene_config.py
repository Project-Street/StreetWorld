#!/usr/bin/env python
"""Serve scenarios supplied by a scene config file or directory."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from metadrive.envs.env_servicer import serve
from metadrive.examples.env_server_easydrive import build_environment, build_parser


BACKENDS = {
    "nuscenes": "easydrive",
    "waymo": "easydrive",
    "nurec": "nurec",
}


def load_scene_ids(scene_config: Path) -> list[str]:
    return scene_config.read_text(encoding="utf-8").splitlines()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.description = "StreetWorld scene-config environment server"
    parser.add_argument("-c", "--scene-config", required=True, type=Path)
    parser.add_argument("--dataset", required=True, choices=tuple(BACKENDS))
    args = parser.parse_args(argv)

    backend = BACKENDS[args.dataset]
    scene_ids = load_scene_ids(args.scene_config.expanduser().resolve())
    env = build_environment(
        backend=backend,
        dataset=args.dataset,
        scene_ids=scene_ids,
        ad_policy_config=args.ad_policy_config,
        nurec_grpc_host=args.nurec_grpc_host,
        nurec_grpc_port=args.nurec_grpc_port,
        nurec_grpc_timeout=args.nurec_grpc_timeout,
        web_host=args.web_host,
        web_port=args.web_port,
        video_output_dir=args.video_output_dir,
        async_mode=args.async_mode,
        tui=False,
    )
    serve(env, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
