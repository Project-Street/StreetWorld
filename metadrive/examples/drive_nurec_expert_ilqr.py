#!/usr/bin/env python3
"""
Run closed-loop ScenarioEnv simulation with actions computed from the full expert
trajectory through iLQR.

The expert trajectory is loaded once from ScenarioDataManager at reset time.
Each env step slices a future 3-second expert window at the env step cadence
and uses it as the iLQR reference path for the next control action.
"""

from __future__ import annotations

import argparse
import math
from collections import OrderedDict

import numpy as np

from metadrive.constants import HELP_MESSAGE
from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.misc.nurec_interface.simulator_interface import SimulatorInterface
from metadrive.policy.env_input_planning_policy import EnvInputPlanningPolicy



def _build_expert_cache(env: ScenarioEnv) -> OrderedDict[int, dict]:
    scenario_data = env.data_manager.get_current_scenario_data()
    actor_states = scenario_data["agent_state"]["actor"]
    return OrderedDict(sorted((int(ts), state) for ts, state in actor_states.items()))


def _future_waypoints(
    expert_cache: OrderedDict[int, dict],
    *,
    current_timestamp: int,
    control_dt_us: int,
    future_seconds: float,
) -> np.ndarray:
    future_horizon_us = int(round(float(future_seconds) * 1_000_000.0))
    horizon_steps = future_horizon_us / control_dt_us
    if not math.isclose(horizon_steps, round(horizon_steps), rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(
            f"future_seconds={future_seconds} is not divisible by env step "
            f"{control_dt_us / 1_000_000.0:.6f}s"
        )
    horizon_steps = int(round(horizon_steps))
    if horizon_steps < 2:
        raise ValueError("future_seconds must contain at least two control points")

    timestamps = [current_timestamp + control_dt_us * step for step in range(1, horizon_steps + 1)]
    missing = [ts for ts in timestamps if ts not in expert_cache]
    if missing:
        raise KeyError(
            f"Expert trajectory does not contain required timestamps for current step. "
            f"first_missing={missing[0]}"
        )

    return np.asarray([expert_cache[ts]["position"][:2] for ts in timestamps], dtype=np.float32)


def _build_policy(env: ScenarioEnv, control_dt_s: float, lookahead_index: int) -> EnvInputPlanningPolicy:
    policy = EnvInputPlanningPolicy(
        env.step_manager,
        config={
            "discrete_action": False,
            "action_check": False,
            "discrete_steering_dim": 5,
            "discrete_throttle_dim": 5,
            "planning_control_dt": control_dt_s,
            "planning_lookahead_index": int(lookahead_index),
        },
    )
    policy.controller = env.actor_controller
    return policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Closed-loop expert-following ScenarioEnv driver")
    parser.add_argument("--nurec-root", type=str, required=True)
    parser.add_argument("--scene_config_directory", type=str, required=True)
    parser.add_argument("--scene_name", type=str, default=None)
    parser.add_argument("--grpc-host", type=str, default="localhost")
    parser.add_argument("--grpc-port", type=int, default=9001)
    parser.add_argument("--grpc-timeout", type=float, default=60.0)
    parser.add_argument("--future-seconds", type=float, default=3.0)
    parser.add_argument("--lookahead-index", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--gui", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--gui-image-key", type=str, default="FRONT")
    args = parser.parse_args()

    print(HELP_MESSAGE)
    model = SimulatorInterface(nurec_root=args.nurec_root)
    env = ScenarioEnv(
        model,
        {
            "scene_config_directory": args.scene_config_directory,
            "gui": args.gui,
            "gui_image_key": args.gui_image_key,
        },
    )

    try:
        obs, info = env.reset(scene_name=args.scene_name)
        del obs

        expert_cache = _build_expert_cache(env)
        control_dt_us = int(env.config["physics_world_step_size"] * env.config["decision_repeat"])
        control_dt_s = control_dt_us * 1e-6
        policy = _build_policy(env, control_dt_s=control_dt_s, lookahead_index=args.lookahead_index)

        print(
            f"scene={info['scene_name']} env_dt={control_dt_s:.3f}s "
            f"future={args.future_seconds:.1f}s expert_points={len(expert_cache)}"
        )

        reward_sum = 0.0
        last_expert_ts = next(reversed(expert_cache))

        for step_idx in range(1, args.max_steps + 1):
            current_timestamp = int(info["current_timestamp"])
            if current_timestamp + int(round(args.future_seconds * 1_000_000.0)) > last_expert_ts:
                print(
                    f"stop: not enough future expert trajectory for {args.future_seconds:.1f}s "
                    f"window at timestamp={current_timestamp}"
                )
                break

            future_waypoints = _future_waypoints(
                expert_cache,
                current_timestamp=current_timestamp,
                control_dt_us=control_dt_us,
                future_seconds=args.future_seconds,
            )
            action = policy.act(future_waypoints)
            _, reward, terminated, truncated, info = env.step(action)
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
