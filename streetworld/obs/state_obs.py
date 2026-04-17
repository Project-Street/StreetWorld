import gymnasium as gym
import numpy as np

from streetworld.obs.observation_base import BaseObservation


class StateObservation(BaseObservation):
    def __init__(self, config=None):
        super().__init__(config or {})
        self.controller = None

    def reset(self, controller, seed=None, **kwargs):
        self.controller = controller

    @property
    def observation_space(self):
        return gym.spaces.Dict({
            "transform": gym.spaces.Box(-1e6, 1e6, shape=(4, 4), dtype=np.float32),
            "position": gym.spaces.Box(-1e6, 1e6, shape=(3,), dtype=np.float32),
            "velocity": gym.spaces.Box(-1e3, 1e3, shape=(3,), dtype=np.float32),
            "acceleration": gym.spaces.Box(-1e4, 1e4, shape=(3,), dtype=np.float32),
            "heading_theta": gym.spaces.Box(-np.pi, np.pi, shape=(), dtype=np.float32),
            "angular_velocity": gym.spaces.Box(-1e3, 1e3, shape=(), dtype=np.float32),
            "angular_acceleration": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
            "size": gym.spaces.Box(0.0, 1e3, shape=(3,), dtype=np.float32),
            "type": gym.spaces.Text(max_length=64),
            "steering_wheel_angle": gym.spaces.Box(-1e3, 1e3, shape=(), dtype=np.float32),
            "steering_wheel_speed": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
            "left_directive_wheel_angle": gym.spaces.Box(-1e3, 1e3, shape=(), dtype=np.float32),
            "right_directive_wheel_angle": gym.spaces.Box(-1e3, 1e3, shape=(), dtype=np.float32),
            "throttle_brake": gym.spaces.Box(-1.0, 1.0, shape=(), dtype=np.float32),
            "longitudinal_acceleration": gym.spaces.Box(-1e4, 1e4, shape=(2,), dtype=np.float32),
            "front_left_wheel_speed": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
            "front_right_wheel_speed": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
            "rear_left_wheel_speed": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
            "rear_right_wheel_speed": gym.spaces.Box(-1e5, 1e5, shape=(), dtype=np.float32),
        })

    def observe(self):
        return {
            "transform": np.asarray(self.controller.transform, dtype=np.float32),
            "position": np.asarray(self.controller.position, dtype=np.float32),
            "velocity": np.asarray(self.controller.velocity, dtype=np.float32),
            "acceleration": np.asarray(self.controller.acceleration, dtype=np.float32),
            "heading_theta": float(self.controller.heading_theta),
            "angular_velocity": float(self.controller.angular_velocity),
            "angular_acceleration": float(self.controller.angular_acceleration),
            "size": np.asarray(
                [self.controller.LENGTH, self.controller.WIDTH, self.controller.HEIGHT], dtype=np.float32
            ),
            "type": str(self.controller.metadrive_type),
            "steering_wheel_angle": float(self.controller.get_steering_wheel_angle()),
            "steering_wheel_speed": float(self.controller.get_steering_wheel_speed()),
            "left_directive_wheel_angle": float(self.controller.get_wheel_steering_angle_rad(0)),
            "right_directive_wheel_angle": float(self.controller.get_wheel_steering_angle_rad(1)),
            "throttle_brake": float(self.controller.throttle_brake),
            "longitudinal_acceleration": np.asarray(self.controller.get_longitudinal_acceleration(), dtype=np.float32),
            "front_left_wheel_speed": float(self.controller.get_wheel_speed(0)),
            "front_right_wheel_speed": float(self.controller.get_wheel_speed(1)),
            "rear_left_wheel_speed": float(self.controller.get_wheel_speed(2)),
            "rear_right_wheel_speed": float(self.controller.get_wheel_speed(3)),
        }

    def destroy(self):
        self.controller = None
        super().destroy()
