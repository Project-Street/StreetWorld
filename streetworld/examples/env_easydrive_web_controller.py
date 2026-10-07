#!/usr/bin/env python
"""
Run selected EasyDrive scenarios with browser WASD control.
"""

import argparse
import time
from typing import Sequence

from st_renderer import SimulatorInterface
from streetworld.config import Config
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.ui.scene_selector import select_catalog_scenes


InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run EasyDrive scenarios with WebUI manual control")
    parser.add_argument("--web-host", default="127.0.0.1", help="WebUI bind address")
    parser.add_argument("--web-port", type=int, default=8080, help="WebUI port")
    parser.add_argument("--video-output-dir", default="videos", help="Directory for env video recordings")
    args = parser.parse_args(argv)
    selection = select_catalog_scenes(datasets=("nuScenes", "Waymo"))

    config = Config(
        {
            "scene_ids": list(selection.scenes),
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
    env = InteractiveScenarioEnv(SimulatorInterface(selection.dataset.lower()), config)
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
