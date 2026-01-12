#!/usr/bin/env python
"""
Example script demonstrating how to use StreetStudioScenarioEnv.

This script loads a scenario from a StreetStudio transforms.json file
and runs the simulation with keyboard control.
"""

import argparse
from metadrive.envs.streetstudio_scenario_env import StreetStudioScenarioEnv
from metadrive.constants import HELP_MESSAGE


def main():
    parser = argparse.ArgumentParser(description="Run StreetWorld with StreetStudio data")
    parser.add_argument(
        "--transforms",
        type=str,
        required=True,
        help="Path to transforms.json file from StreetStudio"
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Enable rendering"
    )
    args = parser.parse_args()

    print(HELP_MESSAGE)
    print(f"Loading StreetStudio scenario from: {args.transforms}")

    # Configure environment
    config = {
        "transforms_json_path": args.transforms,
        # Use a simple observation config for keyboard control
        "use_render": args.render,
        "manual_control": True,
        "num_scenarios": 1,
    }

    # Create environment
    env = StreetStudioScenarioEnv(config)

    try:
        # Reset environment
        obs, info = env.reset()
        print("Environment loaded successfully!")
        print(f"Scene: {env.data_manager.idx2scene[0]}")
        print(f"Timestamp range: {env.data_manager.metadata[env.data_manager.idx2scene[0]]['timestamp_range']}")

        # Run simulation
        action = [0, 0]  # [throttle/brake, steering]
        for i in range(10000):
            o, r, tm, tc, info = env.step(action)

            if tm or tc:
                print(f"Episode finished at step {i}")
                env.reset()
                action = [0, 0]
                continue

            # Print progress every 100 steps
            if i % 100 == 0:
                print(f"Step {i}, reward: {r:.2f}")

    except KeyboardInterrupt:
        print("\nSimulation stopped by user")
    finally:
        env.close()
        print("Environment closed")


if __name__ == "__main__":
    main()
