import inspect
from typing import Dict, Any

import gymnasium as gym
import numpy as np

from metadrive.obs.observation_base import BaseObservation
from scipy.spatial.transform import Rotation as SCR


class AssemblyObservation(BaseObservation):
    """
    Compose multiple observers and return a dict of their observations.

    Config format example (under actor_config.observer_config):
      {
        'gaussian': {
            'observer_class': GaussianObservation,
            'clip_rgb': False,
            'stack_size': 3,
          },
        'navigation': {
            'observer_class': NavigationObservation,
            'navigating_type': 'destination_following',
          }
      }

    AssemblyObservation.reset(...) forwards only the kwargs accepted by each
    sub-observer's reset signature, so you can pass a superset of inputs
    (e.g., controller, render_fn, camera_params, trajdata_map, init_state,
    state, collector, seed, etc.) without worrying about per-observer kwargs.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config or {})
        # name -> instance
        self._observers: Dict[str, BaseObservation] = {}
        self._obs_cls = {}
        for name, sub_cfg in (config or {}).items():
            # Support both 'observer_class' and a common misspelling 'obsever_class'
            cls = sub_cfg.get("observer_class")
            if cls is None:
                raise ValueError(f"observer_class missing for sub-observer '{name}'")
            sub_cfg.pop("observer_class", None)
            self._observers[name] = cls(sub_cfg)
            self._obs_cls[name] = cls

    def reset(self, **kwargs):
        for obs in self._observers.values():
            obs.reset(**kwargs)

    @property
    def observation_space(self):
        spaces = {}
        for name, obs in self._observers.items():
            sub_space = obs.observation_space
            # Wrap plain dicts of spaces into gym.spaces.Dict
            if isinstance(sub_space, dict):
                spaces[name] = gym.spaces.Dict(sub_space)
            else:
                spaces[name] = sub_space
        return gym.spaces.Dict(spaces)

    def observe(self):
        ret = {}
        for name, obs in self._observers.items():
            ret[name] = obs.observe()

        obs_gaussian = ret.get('gaussian', {})
        obs_img = obs_gaussian.get('image', {})
        camera_info = obs_gaussian.get('camera_info', {})

        obs_state = ret.get('states', {})

        obs_nav = ret.get('navigation', {})
        turn_signal = obs_nav.get('turn_signal', 0)
        if turn_signal == -1:
            command = 0
        elif turn_signal == 1:
            command = 1
        else:
            command = 2

        expert_path = obs_nav.get('waypoints', None)

        ego_pos = obs_state.get('ego_pos', np.zeros(3, dtype=np.float32))
        ego_rot = obs_state.get('ego_rot', np.zeros(3, dtype=np.float32))
        R_ego2world = SCR.from_euler('XYZ', ego_rot).as_matrix().astype(np.float32)
        for cam_name, cam_params in camera_info.items():
            R_world_cam = cam_params['ego2camera'][:3, :3] @ R_ego2world.T
            t_world_cam = cam_params['ego2camera'][:3, 3] -  R_world_cam @ ego_pos
            w2c = np.eye(4, dtype=np.float32)
            w2c[:3, :3] = R_world_cam
            w2c[:3, 3] = t_world_cam
            camera_info[cam_name]['w2c'] = w2c

        obs_info = {
            'ego_pos': ego_pos,
            'ego_rot': ego_rot,
            'ego_velo': obs_state.get('ego_velo', 0.0),
            'ego_steer': obs_state.get('ego_steer', 0.0),
            'accelerate': obs_state.get('accelerate', 0.0),
            'steer_rate': obs_state.get('steer_rate', 0.0),
            'timestamp': obs_state.get('timestamp', 0.0),
            'linear_velocity': obs_state.get('linear_velocity', np.zeros(3, dtype=np.float32)),
            'linear_acceleration': obs_state.get('linear_acceleration', np.zeros(3, dtype=np.float32)),
            'angular_velocity': obs_state.get('angular_velocity', np.zeros(3, dtype=np.float32)),
            'command': command,
            'cam_params': camera_info,
            'expert_path': expert_path
        }
        
        return (obs_img, obs_info)

    def destroy(self):
        super().destroy()
        for obs in self._observers.values():
            obs.destroy()
        self._observers.clear()
