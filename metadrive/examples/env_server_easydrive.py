#!/usr/bin/env python
"""
CLI entry for the EasyDrive environment server.
"""

import argparse
import copy
import concurrent.futures
import os

import grpc
from easydrive.models.scenes.simulator_interface import SimulatorInterface
from metadrive.configs.autovla_config import AUTOVLA_CONFIG
from metadrive.configs.diffusiondrive_config import DIFFUSIONDRIVE_CONFIG
from metadrive.configs.openemma_config import OPENEMMA_CONFIG
from metadrive.configs.opendrivevla_config import OPENDRIVEVLA_CONFIG
from metadrive.configs.stp3_config import STP3_CONFIG
from metadrive.configs.transfuser_config import TRANSFUSER_CONFIG
from metadrive.configs.uniad_config import UNIAD_CONFIG
from metadrive.configs.vad_config import VAD_CONFIG
from metadrive.config import Config
from metadrive.envs.env_servicer import EnvServicer
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.envs.web_env import make_web_env
import metadrive.grpc.streetworld_grpc.service_pb2_grpc as service_pb2_grpc


WebScenarioEnv = make_web_env(ScenarioEnv)
AD_POLICY_CONFIGS = {
    "autovla": AUTOVLA_CONFIG,
    "default": {},
    "diffusiondrive": DIFFUSIONDRIVE_CONFIG,
    "openemma": OPENEMMA_CONFIG,
    "opendrivevla": OPENDRIVEVLA_CONFIG,
    "stp3": STP3_CONFIG,
    "uniad": UNIAD_CONFIG,
    "vad": VAD_CONFIG,
    "transfuser": TRANSFUSER_CONFIG,
}


def resolve_ad_policy_config(name: str) -> dict:
    name = str(name).strip().lower()
    if name not in AD_POLICY_CONFIGS:
        valid = ", ".join(sorted(AD_POLICY_CONFIGS))
        raise ValueError(f"Unknown AD policy config {name!r}. Valid options: {valid}")
    return AD_POLICY_CONFIGS[name]


def list_scene_ids(scene_config_directory: str) -> list[str]:
    return [
        os.path.join(scene_config_directory, config_file)
        for config_file in sorted(os.listdir(scene_config_directory))
    ]


def serve(
    scene_config_directory: str = "",
    random_scenario: bool = True,
    ad_policy_config: str = "default",
    host: str = "0.0.0.0",
    port: int = 50052,
    web_host: str = "127.0.0.1",
    web_port: int = 8080,
    max_workers: int = 10,
    video_output_dir: str = "videos",
) -> None:
    scene_ids = list_scene_ids(scene_config_directory)
    config = Config(copy.deepcopy(resolve_ad_policy_config(ad_policy_config)))
    config.merge_from(
        {
            "scene_ids": scene_ids,
            "random_scenario": random_scenario,
            "web_host": web_host,
            "web_port": web_port,
            "video_output_dir": video_output_dir,
        }
    )
    env = WebScenarioEnv(SimulatorInterface(), config)
    server = grpc.server(
        concurrent.futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_send_message_length", 200 * 1024 * 1024),
            ("grpc.max_receive_message_length", 200 * 1024 * 1024),
        ],
    )
    service_pb2_grpc.add_EnvServiceServicer_to_server(EnvServicer(env), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    print(f"EasyDrive ScenarioEnv gRPC server started on {host}:{port}")
    print(f"Scene config directory: {scene_config_directory}")
    print(f"AD policy config: {ad_policy_config}")
    print(f"Video output directory: {video_output_dir}")
    print("Press Ctrl+C to stop...")
    try:
        server.wait_for_termination()
    finally:
        server.stop(0)
        env.close()


def main():
    parser = argparse.ArgumentParser(description="EasyDrive ScenarioEnv gRPC server with browser WebUI")
    parser.add_argument(
        "-c", "--scene_config_directory",
        type=str,
        required=True,
        help="Scenario config directory",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Server bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=50052,
        help="gRPC server port (default: 50052)",
    )
    parser.add_argument(
        "--web-host",
        type=str,
        default="127.0.0.1",
        help="WebUI bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="WebUI port (default: 8080)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=10,
        help="Max concurrent RPC handlers (default: 10)",
    )
    parser.add_argument(
        "--ordered-scenario",
        action="store_true",
        help="Use ordered scenarios instead of random sampling",
    )
    parser.add_argument(
        "--ad-policy-config",
        type=str.lower,
        default="default",
        choices=sorted(AD_POLICY_CONFIGS),
        help="AD policy observation/config preset used by the EasyDrive server",
    )
    parser.add_argument(
        "--video-output-dir",
        type=str,
        default="videos",
        help="Directory for env video recordings (default: videos)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.scene_config_directory):
        print(f"Error: scene_config_directory not found: {args.scene_config_directory}")
        return 1

    serve(
        scene_config_directory=args.scene_config_directory,
        random_scenario=not args.ordered_scenario,
        ad_policy_config=args.ad_policy_config,
        host=args.host,
        port=args.port,
        web_host=args.web_host,
        web_port=args.web_port,
        max_workers=args.max_workers,
        video_output_dir=args.video_output_dir,
    )
    return 0


if __name__ == "__main__":
    exit(main())
