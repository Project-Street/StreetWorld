import numpy as np

from streetworld.policy.env_input_ilqr_policy import EnvInputILQRPolicy


class ExpertILQRPolicy(EnvInputILQRPolicy):
    """Track the recorded expert trajectory with iLQR."""

    def __init__(self, step_manager, config=None, enable_expert=True):
        config = dict(config)
        config["smooth"] = False
        config["max_acceleration"] = 3.2
        super().__init__(step_manager, config, enable_expert)
        self.trajectory_steps = int(self.config.get("trajectory_steps", 10))
        if self.trajectory_steps < 1:
            raise ValueError("trajectory_steps must be positive")
        self._expert_path = None
        self._expert_timestamps = None
        self._arrived = False

    def reset(self, controller, seed, state, init_state, **kwargs):
        super().reset(controller, seed, state, init_state, **kwargs)
        valid_timestamps = [timestamp for timestamp in sorted(state) if state[timestamp]["valid"]]
        if len(valid_timestamps) == 0:
            raise ValueError("ExpertILQRPolicy requires at least one valid expert point")
        expert_timestamps = np.asarray(valid_timestamps, dtype=np.int64)
        self.terminate_timestamp = int(expert_timestamps[-1])
        expert_points = np.asarray(
            [state[timestamp]["position"][:2] for timestamp in valid_timestamps],
            dtype=np.float32,
        )
        trajectory_dt_us = round(self.trajectory_dt * 1e6)
        if trajectory_dt_us < 1:
            raise ValueError("trajectory_dt must be at least one microsecond")
        resample_timestamps = np.arange(
            expert_timestamps[0],
            expert_timestamps[-1],
            trajectory_dt_us,
            dtype=np.int64,
        )
        resample_timestamps = np.append(resample_timestamps, expert_timestamps[-1])
        self._expert_timestamps = resample_timestamps
        self._arrived = False
        self._expert_path = np.column_stack(
            (
                np.interp(resample_timestamps, expert_timestamps, expert_points[:, 0]),
                np.interp(resample_timestamps, expert_timestamps, expert_points[:, 1]),
            )
        ).astype(np.float32)

    def act(self, action=None, *args, **kwargs):
        front_idx = int(np.searchsorted(self._expert_timestamps, self.step_manager.current_timestamp, side="right"))
        future_path = self._expert_path[front_idx:]
        ego_xy = np.asarray(self.controller.position, dtype=np.float32)[:2]
        heading_vec = np.asarray(self.controller.heading, dtype=np.float32)[:2]
        if len(future_path) == 0 or not np.any((future_path - ego_xy) @ heading_vec >= 0.0):
            self._arrived = True
            return self.last_action

        expert_waypoints = future_path[: self.trajectory_steps]
        if len(expert_waypoints) == 1:
            expert_waypoints = np.vstack((expert_waypoints, expert_waypoints))
        world_to_ego = np.linalg.inv(self._xy_transform())
        expert_waypoints = np.column_stack(
            (expert_waypoints, np.ones(len(expert_waypoints), dtype=np.float32))
        )
        relative_waypoints = (world_to_ego @ expert_waypoints.T).T[:, :2].astype(np.float32)
        return super().act(relative_waypoints, *args, **kwargs)

    @property
    def is_arrive(self):
        return self._arrived or self.step_manager.current_timestamp >= self.terminate_timestamp
