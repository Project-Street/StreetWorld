import gymnasium as gym
import numpy as np
from scipy.spatial.transform import Rotation as SCR

from metadrive.obs.observation_base import BaseObservation


class StateObservation(BaseObservation):
    """
    Simple state observation returning a dict with:
    - position: [x, y]
    - velocity: [vx, vy]
    """

    def __init__(self, config=None):
        super().__init__(config or {})
        self.controller = None
        # Generous bounds for meters and m/s
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
        })

    def observe(self):
        dt = self.controller.physics_world.dt

        ego_r = SCR.from_matrix(self.controller.transform[:3, :3]).as_euler('XYZ', degrees=False)
        ego_t = self.controller.transform[:3, 3]
        velo = float(self.controller.speed)
        steer = float(self.controller.steering * np.deg2rad(self.controller.max_steering))

        linear_vel = np.asarray(self.controller.velocity, dtype=np.float32)[:2]
        prev_vel_xy = np.asarray(self.controller.last_velocity, dtype=np.float32)[:2]
        linear_acc_xy = (linear_vel - prev_vel_xy) / dt /5
        linear_acc = np.zeros(3, dtype=np.float32)
        linear_acc[:2] = linear_acc_xy
        accel = float(np.linalg.norm(linear_acc_xy))

        angular_vel = np.zeros(3, dtype=np.float32)
        angular_vel[2] = float(self.controller.angular_velocity)

        return {
            'ego_pos': ego_t.tolist(),
            'ego_rot': ego_r.tolist(),
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
