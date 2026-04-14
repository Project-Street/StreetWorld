import math

import numpy as np

from metadrive.policy.env_input_policy import EnvInputPolicy
from metadrive.utils.ilqr import plan2control


DEFAULT_WHEELBASE = 2.469
DEFAULT_MAX_STEER_RAD = math.radians(40.0)
EPS = 1e-3


def _smooth_1d(values: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    pad = kernel_size // 2
    padded = np.pad(values, (pad, pad), mode="edge")
    kernel = np.ones((kernel_size,), dtype=np.float64) / kernel_size
    return np.convolve(padded, kernel, mode="valid")


def _wrap_to_pi(angle: np.ndarray | float) -> np.ndarray | float:
    return np.arctan2(np.sin(angle), np.cos(angle))


def _build_reference_trajectory(
    *,
    future_waypoints: np.ndarray,
    current_state: np.ndarray,
    control_dt: float,
    wheelbase: float,
    max_steer_rad: float,
) -> np.ndarray:
    ego_xy = current_state[:2]
    ego_heading = current_state[2]
    M = len(future_waypoints)

    reference_trajectory = np.zeros((M + 1, 5), dtype=np.float64)
    reference_trajectory[0] = current_state
    reference_trajectory[1:, :2] = future_waypoints

    headings = np.empty((M,), dtype=np.float64)
    last_heading = ego_heading
    last_position = ego_xy
    for idx in range(M):
        displacement = future_waypoints[idx] - last_position
        if np.linalg.norm(displacement) >= EPS:
            last_heading = math.atan2(displacement[1], displacement[0])
        headings[idx] = last_heading
        last_position = future_waypoints[idx]
    reference_trajectory[1:, 2] = headings

    segment_points = np.vstack((ego_xy, future_waypoints))
    delta_pos = np.diff(segment_points, axis=0)
    segment_dist = np.linalg.norm(delta_pos, axis=1)
    segment_speed = segment_dist / control_dt

    ref_speed = np.zeros((M,), dtype=np.float64)
    ref_speed[:] = segment_speed[:M]
    ref_speed = _smooth_1d(ref_speed, kernel_size=5)
    reference_trajectory[1:, 3] = ref_speed

    curvature = np.zeros((M,), dtype=np.float64)
    curvature[0] = _wrap_to_pi(headings[0] - ego_heading) / max(segment_dist[0], EPS)
    for idx in range(1, M):
        curvature[idx] = _wrap_to_pi(headings[idx] - headings[idx - 1]) / max(segment_dist[idx], EPS)

    tan_limit = np.tan(max_steer_rad)
    steer_profile = np.arctan(np.clip(curvature * wheelbase, -tan_limit, tan_limit))
    steer_profile = _smooth_1d(steer_profile, kernel_size=5)
    steer_profile = np.clip(steer_profile, -max_steer_rad, max_steer_rad)
    reference_trajectory[1:, 4] = steer_profile

    return reference_trajectory


class EnvInputPlanningPolicy(EnvInputPolicy):
    def __init__(self, step_manager, config=None, enable_expert=True):
        super().__init__(step_manager, config, enable_expert)
        self.lookahead_index = int(self.config.get("planning_lookahead_index", 3))
        self.control_dt = float(self.config.get("planning_control_dt", 0.1))
        self.horizon = int(self.config.get("planning_horizon", 12))

    def act(self, action, observation, **kwargs):
        waypoint = np.asarray(action, dtype=np.float64)
        if waypoint.ndim != 2 or waypoint.shape[1] != 2:
            raise ValueError(f"Waypoint input must have shape [N, 2], got {waypoint.shape}")
        if len(waypoint) <= 1:
            return 0.0, 0.0

        states = observation["states"]
        ego_position = np.asarray(states["position"], dtype=np.float64).reshape(-1)
        ego_velocity = np.asarray(states["velocity"], dtype=np.float64).reshape(-1)
        ego_heading = float(states["heading_theta"])
        ego_steer = float(states["steering_wheel_angle"])
        ego_xy = ego_position[:2]
        ego_speed = float(np.linalg.norm(ego_velocity[:2]))

        future_waypoints = waypoint[: self.horizon]
        current_state = np.asarray([ego_xy[0], ego_xy[1], ego_heading, ego_speed, ego_steer], dtype=np.float64)
        reference_trajectory = _build_reference_trajectory(
            future_waypoints=future_waypoints,
            current_state=current_state,
            control_dt=self.control_dt,
            wheelbase=DEFAULT_WHEELBASE,
            max_steer_rad=DEFAULT_MAX_STEER_RAD,
        )

        throttle_brake, steering = plan2control(reference_trajectory, current_state)
        return steering, throttle_brake
