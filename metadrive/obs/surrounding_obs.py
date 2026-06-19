import math
import numpy as np
import torch
from typing import Any, Dict

from metadrive.obs.observation_base import BaseObservation

class SurroundingObservation(BaseObservation):
    """
    Collect surrounding dynamic objects.

    observe() returns a dict: {object_id: state_dict}.
    - position: [x, y, z]
    - velocity: [vx, vy, vz]
    - size: [length, width, height]
    """

    def __init__(self, config):
        super().__init__(config)
        self.coordinate_mode = self.config["coordinate_mode"]
        self.ignore_dist = self.config.get("ignore_dist")
        if self.ignore_dist is not None:
            self.ignore_dist = float(self.ignore_dist)
        self.collector = None
        self.controller = None

    def reset(self, collector, controller, **kwargs):
        self.collector = collector
        self.controller = controller

    @property
    def observation_space(self):
        # Variable-size list; return a placeholder Box to satisfy interface.
        import gymnasium as gym
        return gym.spaces.Box(-np.inf, np.inf, shape=(1,), dtype=np.float32)

    def observe(self):
        objs: Dict[str, Dict[str, Any]] = self.collector()  # dict[name] -> sampled data

        ego_T = self.controller.transform
        ego_T_inv = np.linalg.inv(ego_T)
        ego_R_inv = ego_T_inv[:3, :3]
        ego_heading = self.controller.heading_theta

        candidates = [
            (name, ctrl)
            for name, ctrl in objs.items()
            if ctrl["controller"] is not self.controller
        ]
        if self.ignore_dist is not None and candidates:
            ego_position = torch.as_tensor(self.controller.position, dtype=torch.float32, device="cuda")
            position_tensor = torch.tensor(
                [ctrl["position"] for _, ctrl in candidates],
                dtype=torch.float32,
                device="cuda",
            )
            distance_square = torch.sum((position_tensor - ego_position) ** 2, dim=1)
            keep_indices = torch.nonzero(distance_square <= self.ignore_dist ** 2).flatten().cpu().tolist()
            candidates = [candidates[i] for i in keep_indices]

        surrounding = {}
        for name, ctrl in candidates:
            if self.coordinate_mode == "agent":
                transform = ctrl["transform"]
                transform_out = ego_T_inv @ transform
                pos = transform_out[:3, 3]
                velocity = ego_R_inv @ ctrl["velocity"]
                acceleration = ego_R_inv @ ctrl["acceleration"]
                heading_theta = self._wrap_pi(ctrl["heading_theta"] - ego_heading)
            else:
                transform_out = ctrl["transform"]
                pos = ctrl["position"]
                velocity = ctrl["velocity"]
                acceleration = ctrl["acceleration"]
                heading_theta = ctrl["heading_theta"]

            surrounding[name] = {
                "transform": transform_out,
                "position": pos,
                "velocity": velocity,
                "acceleration": acceleration,
                "heading_theta": float(heading_theta),
                "angular_velocity": ctrl["angular_velocity"],
                "angular_acceleration": ctrl["angular_acceleration"],
                "size": ctrl["size"],
                "type": ctrl["type"]
            }

        return surrounding

    @staticmethod
    def _wrap_pi(a):
        return (a + math.pi) % (2 * math.pi) - math.pi

    def destroy(self):
        super().destroy()
        self.collector = None
        self.controller = None
