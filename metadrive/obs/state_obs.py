import gymnasium as gym
import numpy as np
from scipy.spatial.transform import Rotation as SCR

from metadrive.obs.observation_base import BaseObservation


class StateObservation(BaseObservation):
    """
    Simple state observation returning the legacy ego-state fields.
    """

    def __init__(self, config=None):
        super().__init__(config or {})
        self.controller = None
        self._pos_low = -1e6
        self._pos_high = 1e6
        self._vel_low = -1e3
        self._vel_high = 1e3

    def reset(self, controller, seed=None, **kwargs):
        self.controller = controller

    @property
    def observation_space(self):
        return gym.spaces.Dict({
            'position': gym.spaces.Box(self._pos_low, self._pos_high, shape=(2,), dtype=np.float32),
            'velocity': gym.spaces.Box(self._vel_low, self._vel_high, shape=(2,), dtype=np.float32),
            'heading_theta': gym.spaces.Box(-np.pi, np.pi, shape=(), dtype=np.float32),
        })

    def observe(self):
        ego_transform = self.controller.transform
        ego_pos = np.asarray(ego_transform[:3, 3], dtype=np.float32)
        ego_rot = SCR.from_matrix(ego_transform[:3, :3]).as_euler('XYZ', degrees=False).astype(np.float32)
        velo = float(self.controller.speed)
        steer = float(self.controller.get_steering_wheel_angle())

        linear_vel = np.asarray(self.controller.velocity, dtype=np.float32)
        longitudinal_acc = np.asarray(self.controller.get_longitudinal_acceleration(), dtype=np.float32)
        linear_acc = np.zeros(3, dtype=np.float32)
        linear_acc[:2] = longitudinal_acc
        accel = float(np.linalg.norm(linear_acc[:2]))

        angular_vel = np.zeros(3, dtype=np.float32)
        angular_vel[2] = float(self.controller.angular_velocity)

        return {
            'ego_pos': ego_pos,
            'ego_rot': ego_rot,
            'heading_theta': float(self.controller.heading_theta),
            'ego_steer': steer,
            'linear_velocity': linear_vel,
            'ego_velo': velo,
            'linear_acceleration': linear_acc,
            'accelerate': accel,
            'angular_velocity': angular_vel,
        }

    def destroy(self):
        self.controller = None
        super().destroy()
