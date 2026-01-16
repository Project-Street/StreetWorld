#!/usr/bin/env python
"""
This script demonstrates how to use the environment where traffic and road map are loaded from Waymo dataset.
"""
import argparse
from metadrive.constants import HELP_MESSAGE
from metadrive.engine.asset_loader import AssetLoader
from metadrive.envs.scenario_env import ScenarioEnv
from sim_interface import SharpVideoSimulatorInterface as SimulatorInterface
# from easydrive.models.scenes.simulator_interface import SimulatorInterface
from metadrive.viewer.viewer import Viewer

from drive_with_streetstudio import GaussianFrameRecorder
from metadrive.policy.replay_policy import ReplayPolicy
import numpy as np
import math
import cv2
# import imageio
# import os
# import shutil
RENDER_MESSAGE = {
    "Quit": "ESC",
    "Switch perspective": "Q or B",
    "Reset Episode": "R",
    "Keyboard Control": "W,A,S,D",
    "Start Visualizer Server": "O",
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reactive_traffic", action="store_true")
    parser.add_argument("--waymo", action="store_true")
    parser.add_argument("--add_sensor", action="store_true")
    parser.add_argument("-c", "--scene_config_directory", type=str)
    parser.add_argument('--host', type=str, default='localhost', help='Server IP')
    parser.add_argument('--port', type=int, default=56789, help='Server port')
    args = parser.parse_args()
    asset_path = AssetLoader.asset_path
    use_waymo = args.waymo
    print(HELP_MESSAGE)

    cfg = {
        "scene_config_directory": args.scene_config_directory,
        "physics_world_step_size": 20, # Why?, actual step is 100
        "actor_config": {
            "policy": ReplayPolicy,
        },
    }

    gaussian_recorder = GaussianFrameRecorder(output_path='./driving.mp4', fps=10)
    print(f"Gaussian render video will be saved to: ./driving.mp4")

    if args.add_sensor:
        additional_cfg = {
            'image_observation': True,
        }
        cfg.update(additional_cfg)
    
    model = SimulatorInterface()

    env = ScenarioEnv(model, cfg)
    obs, _ = env.reset()

    # Start visualizer server when 'o' key is pressed
    # viser = Viewer(1080, 1920, mode='local', host=args.host, port=args.port)
    action = [0, 0]

    for i in range(1, 50):
        print(f"Step {i}")
        o, r, tm, tc, info = env.step(action)
        gaussian_recorder.update_frame(o)
        if tm or tc:
            env.reset()
            action = [0, 0]
            continue

        # if viser.is_running():
        obs_img, obs_info = o
        print(obs_img.keys(), obs_info.keys())
        print(obs_info['ego_pos'], obs_info['command'])
            # o_for_vis = obs_img['camera_0'] #o['gaussian']['FRONT'][-1]
        #     # turn_signal = o['navigation']['turn_signal']
        #     # print('[Turn Signal] ', turn_signal)
            # action = viser.run(o_for_vis)

    # env.close()
    # viser.shutdown()
    gaussian_recorder.save_video()