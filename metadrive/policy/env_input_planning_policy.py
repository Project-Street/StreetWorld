"""
Reference:
- Adapted from:
  - https://github.com/Bharath2/iLQR/blob/main/examples/pendulum.py
  - https://github.com/Bharath2/iLQR/blob/main/examples/vehicle_control.py
- Upstream iLQR utilities are vendored in metadrive.utils.ilqr from Bharath2/iLQR.
"""

import math

import numpy as np
import sympy as sp

from metadrive.policy.env_input_policy import EnvInputPolicy
from metadrive.utils.ilqr import Bounded, Cost, Dynamics, GetSyms, iLQR
from metadrive.utils.navigation_utils import nearest_front_index


def _wrap_to_pi(angle):
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def _vehicle_kinematics(state, action):
    px, py, heading, vel, steer = state
    accel, steer_vel = action
    return sp.Matrix(
        [
            vel * sp.cos(heading),
            vel * sp.sin(heading),
            vel * sp.tan(steer),
            accel,
            steer_vel,
        ]
    )


class EnvInputPlanningPolicy(EnvInputPolicy):
    def __init__(self, step_manager, config=None, enable_expert=True):
        super().__init__(step_manager, config, enable_expert)
        self.lookahead_index = int(self.config.get("planning_lookahead_index", 3))
        self.control_dt = float(self.config.get("planning_control_dt", 0.1))
        self.horizon = int(self.config.get("planning_horizon", 12))
        self.max_iters = int(self.config.get("planning_max_iters", 8))
        self.action_weight = float(self.config.get("planning_action_weight", 0.1))
        self.terminal_factor = float(self.config.get("planning_terminal_factor", 5.0))
        self.max_accel = float(self.config.get("planning_max_accel", 1.0))
        self.max_steer_vel = float(self.config.get("planning_max_steer_vel", 0.5))

        self._us_init = np.zeros((self.horizon, 2), dtype=np.float64)
        self._dynamics = self._build_dynamics()

    def _build_dynamics(self):
        state, action = GetSyms(5, 2)
        state_dot = _vehicle_kinematics(state, action)
        return Dynamics.SymContinuous(state_dot, state, action, dt=self.control_dt)

    def act(self, action, *args, **kwargs):
        waypoint = np.asarray(action, dtype=np.float32)
        if waypoint.ndim != 2 or waypoint.shape[1] != 2:
            raise ValueError(f"Waypoint input must have shape [N, 2], got {waypoint.shape}.")
        if len(waypoint) < 2:
            return 0.0, 0.0

        ego_xy = np.array([self.controller.position[0], self.controller.position[1]], dtype=np.float64)
        heading_vec = np.array([self.controller.heading[0], self.controller.heading[1]], dtype=np.float64)
        heading_norm = np.linalg.norm(heading_vec)
        if heading_norm < 1e-6:
            raise ValueError("Controller heading vector norm is zero.")
        heading_vec /= heading_norm

        rel_all = waypoint - ego_xy[None, :]
        if not np.any((rel_all @ heading_vec) >= 0.0):
            return 0.0, -1.0

        front_idx = int(nearest_front_index(waypoint, ego_xy.astype(np.float32), heading_vec.astype(np.float32)))
        target_idx = min(front_idx + self.lookahead_index, len(waypoint) - 1)
        ref_idx = max(target_idx - 1, 0)

        target_point = waypoint[target_idx].astype(np.float64)
        ref_point = waypoint[ref_idx].astype(np.float64)
        segment = target_point - ref_point
        segment_norm = np.linalg.norm(segment)
        if segment_norm < 1e-6:
            raise ValueError("Waypoint path segment norm is zero.")

        desired_heading = math.atan2(segment[1], segment[0])
        ego_heading = float(self.controller.heading_theta)
        heading_error = _wrap_to_pi(desired_heading - ego_heading)
        steer = float(self.controller.get_steering_wheel_angle())
        speed_m_s = float(self.controller.speed_km_h) / 3.6
        max_steer = math.radians(float(self.controller.max_steering))

        x0 = np.array(
            [
                ego_xy[0],
                ego_xy[1],
                ego_heading,
                speed_m_s,
                steer,
            ],
            dtype=np.float64,
        )
        state, action_syms = GetSyms(5, 2)
        px, py, heading, vel, steer_state = state
        accel, steer_vel = action_syms
        L = (px - target_point[0])**2 + (py - target_point[1])**2
        L += (heading - desired_heading)**2 + (vel - speed_m_s)**2
        L += self.action_weight * accel**2 + self.action_weight * steer_vel**2
        L += Bounded(action_syms, high=[self.max_accel, self.max_steer_vel], low=[-self.max_accel, -self.max_steer_vel])
        L += Bounded([steer_state], high=[max_steer], low=[-max_steer])
        Lf = self.terminal_factor * ((px - target_point[0])**2 + (py - target_point[1])**2 + (heading - desired_heading)**2)
        Lf += (vel - speed_m_s)**2
        cost = Cost.Symbolic(L, Lf, state, action_syms)
        controller = iLQR(self._dynamics, cost)
        _, us, _ = controller.fit(x0, self._us_init.copy(), maxiters=self.max_iters, early_stop=True)
        self._us_init[:-1] = us[1:]
        self._us_init[-1] = us[-1]

        throttle_brake = float(np.clip(us[0, 0], -1.0, 1.0))
        next_steer = steer + us[0, 1] * self.control_dt
        steering = float(np.clip(next_steer / max_steer, -1.0, 1.0))
        right_vec = np.array([heading_vec[1], -heading_vec[0]], dtype=np.float64)
        lateral_error = float(np.dot(target_point - ego_xy, right_vec))

        self.action_info = {
            "lateral_error": lateral_error,
            "heading_error": float(heading_error),
        }
        return steering, throttle_brake
