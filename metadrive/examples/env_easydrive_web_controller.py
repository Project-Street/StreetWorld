#!/usr/bin/env python
"""
Run every EasyDrive scenario with browser WASD control.
"""

import argparse
import os
import time

from easydrive.models.scenes.simulator_interface import SimulatorInterface
from metadrive.config import Config
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.envs.interactive_env import make_interactive_env


InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)


def list_scene_ids(scene_config_directory: str) -> list[str]:
    return [
        os.path.join(scene_config_directory, config_file)
        for config_file in sorted(os.listdir(scene_config_directory))
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EasyDrive scenarios with WebUI manual control")
    parser.add_argument("-c", "--scene-config-directory", required=True, help="Scenario config directory")
    parser.add_argument("--web-host", default="127.0.0.1", help="WebUI bind address")
    parser.add_argument("--web-port", type=int, default=8080, help="WebUI port")
    parser.add_argument("--video-output-dir", default="videos", help="Directory for env video recordings")
    args = parser.parse_args()

    config = Config(
        {
            "scene_ids": list_scene_ids(args.scene_config_directory),
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
    env = InteractiveScenarioEnv(SimulatorInterface(), config)
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
