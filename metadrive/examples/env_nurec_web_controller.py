#!/usr/bin/env python
"""
Run two NuRec scenarios with browser WASD control.
"""

import argparse
import time
from pathlib import Path

from metadrive.config import Config
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.envs.web_env import make_web_env
from metadrive.misc.nurec_interface.simulator_interface import SimulatorInterface


NUREC_ROOT = Path(__file__).resolve().parents[2] / "data/processed/benchmark/NuRec/sample_set/25.07_release"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "tmp/nurec_web_controller.yaml"
SCENE_IDS = [
    "Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa",
    "Batch0005/7eaac028-ff62-4f54-9cca-52c8f49ba87e",
    "Batch0004/6db8921b-e103-4cd4-901c-b2726849be7a",
]

WebScenarioEnv = make_web_env(ScenarioEnv)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the selected NuRec scenarios with WebUI manual control")
    parser.add_argument("--grpc-host", default="127.0.0.1", help="NuRec gRPC server address")
    parser.add_argument("--grpc-port", type=int, default=8080, help="NuRec gRPC server port")
    parser.add_argument("--grpc-timeout", type=float, default=600.0, help="NuRec gRPC timeout in seconds")
    parser.add_argument("--web-host", default="127.0.0.1", help="WebUI bind address")
    parser.add_argument("--web-port", type=int, default=8082, help="WebUI bind port")
    parser.add_argument("--video-output-dir", default="videos", help="Directory for env video recordings")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Environment config file")
    args = parser.parse_args()

    config = Config(
        {
            "scene_ids": SCENE_IDS,
            "random_scenario": False,
            "async_mode": True,
            "web_host": args.web_host,
            "web_port": args.web_port,
            "video_output_dir": args.video_output_dir,
            "eval_mode": True,
            "eval_order": True,
            "eval_repeat_per_scene": 1,
        }
    )
    config.merge_from(Config.fromfile(str(args.config)).to_dict())
    env = WebScenarioEnv(
        SimulatorInterface(
            nurec_root=NUREC_ROOT,
            grpc_host=args.grpc_host,
            grpc_port=args.grpc_port,
            grpc_timeout_s=args.grpc_timeout,
        ),
        config,
    )
    decision_period_s = env.config["decision_repeat"] * env.config["physics_world_step_size"] * 1e-6
    try:
        while True:
            env.reset()

            while True:
                _, _, terminated, truncated, _ = env.step([0.0, 0.0])
                if terminated or truncated:
                    if not env.data_manager.remain_queue:
                        while True:
                            time.sleep(1.0)
                    break

    finally:
        env.close()


if __name__ == "__main__":
    raise SystemExit(main())
