import numpy as np

from metadrive.policy.env_input_policy import EnvInputPolicy
from metadrive.utils.PID import PIDController


def smooth_1d(arr, kernel_size=5):
    if kernel_size == 5:
        kernel = np.array([1, 4, 6, 4, 1], dtype=np.float32)
    else:
        kernel = np.ones(kernel_size, dtype=np.float32)
    kernel = kernel / kernel.sum()

    pad = kernel_size // 2
    arr_pad = np.pad(arr, (pad, pad), mode="edge")
    return np.convolve(arr_pad, kernel, mode="valid").astype(np.float32)


class EnvInputPIDPolicy(EnvInputPolicy):
    """Track relative input waypoints with PID control."""

    def __init__(self, step_manager, config=None, enable_expert=True):
        super().__init__(step_manager, config, enable_expert)
        self.smooth = self.config["smooth"]
        self.trajectory_dt = self.config["trajectory_dt"]
        # TODO: control_dt must equal physics_world_step_size * decision_repeat. Other values currently cause a bug.
        self.control_dt = self.config["control_dt"]
        self.turn_controller_params = self.config["turn_controller"]
        self.speed_controller_params = self.config["speed_controller"]
        self.control_dt_us = round(self.control_dt * 1e6)
        if self.control_dt_us % self.step_manager.step_size != 0:
            raise ValueError(f"control_dt={self.control_dt} must be an integer multiple of physical step")
        self._cached_waypoints = None
        self._cached_transform = None
        self._last_control_timestamp = None
        self._turn_controller = PIDController(*self.turn_controller_params)
        self._speed_controller = PIDController(*self.speed_controller_params)

    def reset(self, controller, seed, state, init_state, **kwargs):
        super().reset(controller, seed, state, init_state, **kwargs)
        self._cached_waypoints = None
        self._cached_transform = self._xy_transform()
        self._last_control_timestamp = self.step_manager.current_timestamp
        self._turn_controller = PIDController(*self.turn_controller_params)
        self._speed_controller = PIDController(*self.speed_controller_params)

    def _xy_transform(self):
        transform = self.controller.transform
        return transform[np.ix_([0, 1, 3], [0, 1, 3])]

    def _set_cached_waypoints(self, waypoints):
        waypoints = np.asarray(waypoints, dtype=np.float32).reshape(-1, 2)
        t_orig = np.arange(1, len(waypoints) + 1, dtype=np.float32) * self.trajectory_dt
        t_ref = np.concatenate(([0.0], t_orig))
        x_forward_ref = np.concatenate(([0.0], waypoints[:, 0]))
        y_left_ref = np.concatenate(([0.0], waypoints[:, 1]))
        if self.smooth:
            x_forward_ref = smooth_1d(x_forward_ref, kernel_size=5)
            y_left_ref = smooth_1d(y_left_ref, kernel_size=5)
        t_new = np.arange(self.control_dt, t_orig[-1] + 1e-6, self.control_dt, dtype=np.float32)
        self._cached_waypoints = np.column_stack(
            (np.interp(t_new, t_ref, x_forward_ref), np.interp(t_new, t_ref, y_left_ref))
        ).astype(np.float32)
        self._cached_transform = self._xy_transform()

    def _update_cached_waypoints(self):
        current_transform = self._xy_transform()
        cached_to_current = np.linalg.inv(current_transform) @ self._cached_transform
        homogeneous_waypoints = np.column_stack(
            (self._cached_waypoints, np.ones(len(self._cached_waypoints), dtype=np.float32))
        )
        self._cached_waypoints = (cached_to_current @ homogeneous_waypoints.T).T[:, :2].astype(np.float32)
        self._cached_transform = current_transform

    def act(self, action, *args, **kwargs):
        if action is None:
            return 0.0, 0.0

        current_timestamp = self.step_manager.current_timestamp
        if self.step_manager.key_step:
            self._set_cached_waypoints(action)
        elif current_timestamp - self._last_control_timestamp >= self.control_dt_us:
            self._update_cached_waypoints()
            self._cached_waypoints = self._cached_waypoints[1:]
        else:
            return self.last_action

        aim = (self._cached_waypoints[0] + self._cached_waypoints[1]) * 0.5
        # Waypoints are [forward, left], and positive MetaDrive steering turns left.
        u = np.arctan2(aim[1], aim[0]) / (np.pi * 0.5)
        steering = np.clip(self._turn_controller.step(u), -1.0, 1.0)

        desired_speed = np.linalg.norm(self._cached_waypoints[1] - self._cached_waypoints[0]) / self.control_dt
        speed_error = np.clip(desired_speed - self.controller.speed, 0.0, 0.25)
        throttle = np.clip(self._speed_controller.step(speed_error), 0.0, 0.75)
        brake = self.controller.speed / desired_speed > 1.2
        throttle_brake = -1.0 if brake else throttle

        self.last_action = (steering, throttle_brake)
        self._last_control_timestamp = current_timestamp
        self.action_info = {"action": self.last_action}
        return self.last_action
