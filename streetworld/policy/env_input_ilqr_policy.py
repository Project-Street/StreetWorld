import numpy as np

from streetworld.policy.env_input_policy import EnvInputPolicy
from streetworld.utils.ilqr.lqr_solver import ILQRWarmStartParameters, ILQRSolver, ILQRSolverParameters


def smooth_1d(arr, kernel_size=5):
    if kernel_size == 5:
        kernel = np.array([1, 4, 6, 4, 1], dtype=np.float32)
    else:
        kernel = np.ones(kernel_size, dtype=np.float32)
    kernel = kernel / kernel.sum()

    pad = kernel_size // 2
    arr_pad = np.pad(arr, (pad, pad), mode="edge")
    return np.convolve(arr_pad, kernel, mode="valid").astype(np.float32)


class EnvInputILQRPolicy(EnvInputPolicy):
    """Track relative input waypoints with iLQR."""

    def __init__(self, step_manager, config=None, enable_expert=True):
        super().__init__(step_manager, config, enable_expert)
        self.smooth = self.config["smooth"]
        self.max_acceleration = self.config["max_acceleration"]
        self.trajectory_dt = self.config["trajectory_dt"]
        # TODO: control_dt must equal physics_world_step_size * decision_repeat. Other values currently cause a bug.
        self.control_dt = self.config["control_dt"]
        self.control_dt_us = round(self.control_dt * 1e6)
        if self.control_dt_us % self.step_manager.step_size != 0:
            raise ValueError(f"control_dt={self.control_dt} must be an integer multiple of physical step ")
        self._cached_waypoints = None
        self._cached_transform = None
        self._last_control_timestamp = None
        self._warm_start_params = ILQRWarmStartParameters(
            k_velocity_error_feedback=0.5,
            k_steering_angle_error_feedback=0.1,
            lookahead_distance_lateral_error=15.0,
            k_lateral_error=0.1,
            jerk_penalty_warm_start_fit=1e-4,
            curvature_rate_penalty_warm_start_fit=1e-2,
        )

    def reset(self, controller, seed, state, init_state, **kwargs):
        super().reset(controller, seed, state, init_state, **kwargs)

        self.max_steering_angle = np.deg2rad(self.controller.max_steering.item())
        self.wheelbase = self.controller.FRONT_WHEELBASE + self.controller.REAR_WHEELBASE
        self._solver_params = ILQRSolverParameters(
            discretization_time=self.control_dt,
            state_cost_diagonal_entries=[1.0, 8.0, 15.0, 2.0, 1.0],
            input_cost_diagonal_entries=[1.5, 5.0],
            state_trust_region_entries=[1.0, 1.0, 1.0, 1.0, 1.0],
            input_trust_region_entries=[1.0, 1.0],
            max_ilqr_iterations=100,
            convergence_threshold=1e-6,
            max_solve_time=0.1,
            max_acceleration=self.max_acceleration,
            max_steering_angle=self.max_steering_angle,
            max_steering_angle_rate=np.inf,
            min_velocity_linearization=0.01,
            wheelbase=self.wheelbase,
        )
        self._cached_waypoints = None
        self._cached_transform = self._xy_transform()
        self._last_control_timestamp = self.step_manager.current_timestamp

    def _xy_transform(self):
        transform = self.controller.transform
        return transform[np.ix_([0, 1, 3], [0, 1, 3])]

    def __set_cached_waypoints(self, waypoints):
        waypoints = waypoints.reshape(-1, 2)
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

    def __update_cached_waypoints(self):
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
            self.__set_cached_waypoints(action)
        elif current_timestamp - self._last_control_timestamp >= self.control_dt_us:
            self.__update_cached_waypoints()
            self._cached_waypoints = self._cached_waypoints[1:]
        else:
            return self.last_action

        control_dt = self.control_dt
        plan_xy = self._cached_waypoints

        plan = np.zeros((len(plan_xy) + 1, 5), dtype=np.float32)
        plan[1:, :2] = plan_xy
        headings = np.zeros(len(plan_xy), dtype=np.float32)
        for index in range(len(plan_xy)):
            if index == 0:
                delta = plan_xy[min(1, len(plan_xy) - 1)] - plan_xy[0]
            elif index == len(plan_xy) - 1:
                delta = plan_xy[-1] - plan_xy[-2]
            else:
                delta = plan_xy[index + 1] - plan_xy[index - 1]
            headings[index] = np.arctan2(delta[1], delta[0])
        plan[1:, 2] = headings

        segment_dist = np.linalg.norm(np.diff(plan_xy, axis=0), axis=1)
        ref_speed = np.zeros(len(plan_xy), dtype=np.float32)
        ego_speed = self.controller.speed
        ref_speed[0] = max(ego_speed, segment_dist[0] / control_dt if len(segment_dist) else ego_speed)
        if len(segment_dist):
            ref_speed[1:] = segment_dist / control_dt
            ref_speed = smooth_1d(ref_speed, kernel_size=5)
        plan[1:, 3] = ref_speed

        ego_steer = self.controller.steering * self.max_steering_angle
        curvature = np.zeros(len(plan_xy), dtype=np.float32)
        for index in range(1, len(plan_xy)):
            curvature[index] = (headings[index] - headings[index - 1]) / max(segment_dist[index - 1], 1e-3)
        steer_profile = np.arctan(
            np.clip(curvature * self.wheelbase, -np.tan(self.max_steering_angle), np.tan(self.max_steering_angle))
        )
        if len(plan_xy) > 1:
            steer_profile = smooth_1d(steer_profile, kernel_size=5)
        plan[1:, 4] = np.clip(steer_profile, -self.max_steering_angle, self.max_steering_angle)
        plan[0, 3] = ego_speed
        plan[0, 4] = ego_steer

        current_state = np.array([0.0, 0.0, 0.0, ego_speed, ego_steer], dtype=np.float32)
        solutions = ILQRSolver(self._solver_params, self._warm_start_params).solve(current_state, plan)
        acceleration, steering_rate = solutions[-1].input_trajectory[0]
        steering = np.clip(
            ego_steer + steering_rate * self.control_dt, -self.max_steering_angle, self.max_steering_angle,
        ) / self.max_steering_angle
        throttle_brake = np.clip(acceleration / self.max_acceleration, -1.0, 1.0)
        self.last_action = (steering, throttle_brake)
        self._last_control_timestamp = current_timestamp
        self.action_info = {"action": self.last_action}
        return self.last_action
