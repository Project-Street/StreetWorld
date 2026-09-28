#!/usr/bin/env python3
"""
Run closed-loop ScenarioEnv simulation with an expert-trajectory iLQR policy.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from st_renderer import SimulatorInterface

from metadrive.config import Config
from metadrive.constants import HELP_MESSAGE
from metadrive.envs.interactive_env import make_interactive_env
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.policy.expert_ilqr_policy import ExpertILQRPolicy


InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)


EXPERT_CONFIG = {
    "actor_config": {
        "policy": ExpertILQRPolicy,
        "policy_config": {
            "trajectory_dt": 0.1,
            "control_dt": 0.1,
            "trajectory_steps": 30,
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Closed-loop expert-following ScenarioEnv driver")
    parser.add_argument("--scene_config_directory", type=str, required=True)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--warmup-step", type=int, default=None)
    parser.add_argument("--gui", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gui-image-key", type=str, default="FRONT")
    args = parser.parse_args()

    print(HELP_MESSAGE)
    scene_config_directory = Path(args.scene_config_directory).resolve()
    scene_ids = [str(path) for path in sorted(scene_config_directory.glob("*.yaml"))]

    model = SimulatorInterface()
    config = Config(EXPERT_CONFIG)
    config.merge_from(
        {
            "scene_ids": scene_ids,
            "random_scenario": False,
            "eval_mode": True,
            "actor_config": {"warmup_step": args.warmup_step},
            "gui": args.gui,
            "gui_image_key": args.gui_image_key,
        }
    )
    env = InteractiveScenarioEnv(model, config)

    try:
        while env.data_manager.remain_queue:
            _, info = env.reset()
            print(
                f"scene={info['scene_name']} trajectory_dt={EXPERT_CONFIG['actor_config']['policy_config']['trajectory_dt']:.3f}s "
                f"trajectory_steps={EXPERT_CONFIG['actor_config']['policy_config']['trajectory_steps']}"
            )

            reward_sum = 0.0
            for step_idx in range(1, args.max_steps + 1):
                _, reward, terminated, truncated, info = env.step(None)
                reward_sum += reward

                if terminated or truncated:
                    print(
                        f"episode finished at step={step_idx} ts={info['current_timestamp']} "
                        f"reason={info['reason']}"
                    )
                    break

            print(f"reward_sum={reward_sum:.6f}")
    finally:
        env.close()


if __name__ == "__main__":
    main()
