#!/usr/bin/env python
"""
OpenEMMA gRPC client for StreetStudio environment.

Mirrors diffusiondrive_client flow: reset -> receive observation ->
run OpenEMMA inference -> parse action -> step.
"""

import argparse
import os
import re
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import cv2
import grpc
import numpy as np

from grpc_client import GrpcClient
from grpc_obs_adapter import unpack_ad_observation
from metrics import MetricsRecorder
from openemma_client_stub import OpenEMMAClient, OpenEMMAClientConfig

os.environ["no_proxy"] = "127.0.0.1,localhost"


def _latest_frame(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 4:
        return frame[-1]
    return frame


def _save_frame(image: np.ndarray, out_path: str) -> None:
    if image.ndim != 3:
        raise ValueError(f"Expected HxWxC image, got shape: {image.shape}")
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    cv2.imwrite(out_path, bgr)


def _parse_action(text: str) -> Tuple[float, float]:
    numbers = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)
    if len(numbers) < 2:
        return 0.0, 0.0
    steer = float(numbers[0])
    accel = float(numbers[1])
    return steer, accel


def _command_to_text(command: Optional[int]) -> str:
    mapping = {
        0: "turn right",
        1: "turn left",
        2: "go straight",
    }
    return mapping.get(int(command), "unknown") if command is not None else "unknown"


def _build_prompt(frame_count: int, frame_interval_s: float, command: Optional[int]) -> str:
    turn_signal = _command_to_text(command)
    return (
        f"You are driving a car. These are {frame_count} front-camera frames "
        f"spaced {frame_interval_s:.2f}s apart (oldest to newest). "
        f"The navigation turn signal suggests: {turn_signal}. "
        "Return two numbers only: steer and accel. "
        "Steer in range [-1, 1], accel in range [-1, 1]."
    )


def _select_camera(obs_img: Dict[str, np.ndarray], camera_name: str) -> np.ndarray:
    if camera_name in obs_img:
        return _latest_frame(obs_img[camera_name])
    if obs_img:
        key = sorted(obs_img.keys())[0]
        return _latest_frame(obs_img[key])
    raise KeyError("No camera images in observation.")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenEMMA gRPC client for StreetStudio")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=50052)
    parser.add_argument("--transforms", type=str, default="")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--model-path", type=str, required=True)
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--api-key", type=str, default=None)
    parser.add_argument("--camera", type=str, default="camera_0")
    parser.add_argument("--infer-every", type=int, default=1)
    parser.add_argument("--temp-dir", type=str, default="/tmp/openemma_frames")
    parser.add_argument("--frame-count", type=int, default=5)
    parser.add_argument("--frame-interval", type=float, default=0.5)
    args = parser.parse_args()

    client = GrpcClient(host=args.host, port=args.port)
    os.makedirs(args.temp_dir, exist_ok=True)

    openemma = OpenEMMAClient(
        OpenEMMAClientConfig(
            model_path=args.model_path,
            device=args.device,
            api_key=args.api_key,
        )
    )

    try:
        episode_index = 0
        total_reward = 0.0
        metrics_recorder = MetricsRecorder()
        collision_scenes = set()
        while True:
            try:
                if episode_index == 0:
                    obs, _reset_info = client.reset(transforms_json_path="full_reset,sequential")
                else:
                    obs, _reset_info = client.reset(transforms_json_path=args.transforms)
            except grpc.RpcError as exc:
                if exc.code() == grpc.StatusCode.OUT_OF_RANGE:
                    print("All scenarios exhausted, stopping.")
                    break
                raise

            episode_index += 1
            obs_img, obs_info, _navigation, _surrounding = unpack_ad_observation(obs)
            action = [0.0, 0.0]
            frame_paths: Deque[str] = deque(maxlen=max(1, args.frame_count))
            reward_sum = 0.0
            last_info = None

            for step in range(1, args.steps + 1):
                frame = _select_camera(obs_img, args.camera)
                image_path = os.path.join(args.temp_dir, f"frame_{episode_index:03d}_{step:06d}.png")
                _save_frame(frame, image_path)
                frame_paths.append(image_path)

                if step % args.infer_every == 0 and len(frame_paths) >= args.frame_count:
                    prompt = _build_prompt(args.frame_count, args.frame_interval, obs_info.get("command"))
                    result = openemma.infer(prompt, list(frame_paths))
                    steer, accel = _parse_action(result)
                    action = [steer, accel]
                    print(f"LLM action: steer={steer:.4f}, accel={accel:.4f}")

                obs, reward, terminated, truncated, info = client.step(action)
                last_info = info
                reward_sum += reward
                total_reward += reward
                metrics_recorder.update(info)
                obs_img, obs_info, _navigation, _surrounding = unpack_ad_observation(obs)
                if step % 10 == 0:
                    print(f"Step {step}: reward={reward:.2f}")

                if terminated or truncated:
                    print(f"Episode finished at step {step}")
                    print(f"Scene: {info.get('scene_name')}")
                    break
            if last_info and last_info.get("collision"):
                collision_scenes.add(last_info.get("scene_name"))
                print(f"Collision detected in scene: {last_info.get('scene_name')}")
            metrics_recorder.end_episode(last_info)
            print(f"Episode {episode_index} reward: {reward_sum:.2f}")
            metrics_so_far = metrics_recorder.summary()
            print(
                "Metrics so far: "
                f"collision={metrics_so_far.get('collision_ratio', 0.0):.3f}, "
                f"out_of_road={metrics_so_far.get('out_of_road_ratio', 0.0):.3f}, "
                f"lag_warn={metrics_so_far.get('lag_warn_ratio', 0.0):.3f}, "
                f"lag_dist={metrics_so_far.get('avg_lag_distance', 0.0):.3f}, "
                f"lag_deficit={metrics_so_far.get('avg_lag_deficit', 0.0):.3f}, "
                f"pos_dev={metrics_so_far.get('avg_position_deviation', 0.0):.3f}, "
                f"heading_err={metrics_so_far.get('avg_heading_error', 0.0):.3f}"
            )
        print(f"Total reward: {total_reward:.2f}")
        final_metrics = metrics_recorder.summary()
        print(
            "Final metrics: "
            f"collision={final_metrics.get('collision_ratio', 0.0):.3f}, "
            f"out_of_road={final_metrics.get('out_of_road_ratio', 0.0):.3f}, "
            f"lag_warn={final_metrics.get('lag_warn_ratio', 0.0):.3f}, "
            f"lag_dist={final_metrics.get('avg_lag_distance', 0.0):.3f}, "
            f"lag_deficit={final_metrics.get('avg_lag_deficit', 0.0):.3f}, "
            f"pos_dev={final_metrics.get('avg_position_deviation', 0.0):.3f}, "
            f"heading_err={final_metrics.get('avg_heading_error', 0.0):.3f}"
        )
        print(f"Collision scenes: {collision_scenes}")
    finally:
        client.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
