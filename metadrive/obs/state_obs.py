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
        self._last_timestamp = None
        # Generous bounds for meters and m/s
        self._pos_low = -1e6
        self._pos_high = 1e6
        self._vel_low = -1e3
        self._vel_high = 1e3

    def reset(self, controller, seed=None, **kwargs):
        self.controller = controller
        self._last_timestamp = None

    @property
    def observation_space(self):
        return gym.spaces.Dict({
            'position': gym.spaces.Box(self._pos_low, self._pos_high, shape=(2,), dtype=np.float32),
            'velocity': gym.spaces.Box(self._vel_low, self._vel_high, shape=(2,), dtype=np.float32),
        })

    def observe(self):
        ego_r = SCR.from_matrix(self.controller.transform[:3, :3]).as_euler('XYZ', degrees=False)
        ego_t = self.controller.transform[:3, 3]
        velo = float(self.controller.speed)
        steer = float(self.controller.steering * np.deg2rad(self.controller.max_steering))
        accel = float(self.controller.accelerate)
        steer_rate = float(self.controller.steer_rate)
        timestamp = float(self.controller.timestamp - 0.1)
        dt = 0.1
        if self._last_timestamp is not None:
            dt_candidate = timestamp - self._last_timestamp
            if dt_candidate > 1e-4:
                dt = dt_candidate
        self._last_timestamp = timestamp

        vel_xy = np.asarray(getattr(self.controller, 'velocity', np.zeros(2, dtype=np.float32)), dtype=np.float32)
        linear_vel = np.zeros(3, dtype=np.float32)
        linear_vel[:2] = vel_xy

        prev_vel_xy = np.asarray(getattr(self.controller, 'last_velocity', vel_xy), dtype=np.float32)
        linear_acc_xy = (vel_xy - prev_vel_xy) / dt
        linear_acc = np.zeros(3, dtype=np.float32)
        linear_acc[:2] = linear_acc_xy

        angular_vel = np.zeros(3, dtype=np.float32)
        angular_vel[2] = float(getattr(self.controller, 'angular_velocity', 0.0))

        return {
            'ego_pos': ego_t.tolist(),
            'ego_rot': ego_r.tolist(),
            'ego_velo': velo,
            'ego_steer': steer,
            'accelerate': accel,
            'steer_rate': steer_rate,
            'timestamp': timestamp,
            'linear_velocity': linear_vel,
            'linear_acceleration': linear_acc,
            'angular_velocity': angular_vel,
        }

    def destroy(self):
        self.controller = None
        super().destroy()
