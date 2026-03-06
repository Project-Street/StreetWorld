from typing import Dict, Optional, List


class MetricsRecorder:
    """Record inference metrics across episodes."""

    _DT = 0.1

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._episode_count = 0
        self._collision_episodes = 0
        self._out_of_road_episodes = 0

        self._ttc_episode_means: List[float] = []
        self._heading_episode_means: List[float] = []
        self._position_episode_means: List[float] = []
        self._progress_episode_values: List[float] = []
        self._smoothness_episode_means: List[float] = []

        self._reset_episode_accumulators()

    def _reset_episode_accumulators(self) -> None:
        self._episode_ttc_sum = 0.0
        self._episode_ttc_count = 0

        self._episode_heading_sum = 0.0
        self._episode_heading_count = 0

        self._episode_position_sum = 0.0
        self._episode_position_count = 0

        self._episode_progress_sum = 0.0
        self._episode_progress_count = 0
        self._episode_collision = False
        self._episode_out_of_road = False

        self._episode_smoothness_sum = 0.0
        self._episode_smoothness_count = 0
        self._episode_speed_history: List[float] = []

    @staticmethod
    def _safe_float(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def update(self, step_info: Dict) -> None:
        """Update metrics with step_info dict."""
        if not step_info:
            return

        ttc = self._safe_float(step_info.get("ttc"))
        if ttc is not None:
            self._episode_ttc_sum += ttc
            self._episode_ttc_count += 1

        heading_error = self._safe_float(step_info.get("heading_error"))
        if heading_error is not None:
            self._episode_heading_sum += heading_error
            self._episode_heading_count += 1

        position_deviation = self._safe_float(step_info.get("position_deviation"))
        if position_deviation is not None:
            self._episode_position_sum += position_deviation
            self._episode_position_count += 1

        progress_ratio = self._safe_float(step_info.get("progress_ratio"))
        if progress_ratio is not None:
            self._episode_progress_sum += progress_ratio
            self._episode_progress_count += 1

        ego_speed = self._safe_float(step_info.get("ego_speed"))
        if ego_speed is not None:
            self._episode_speed_history.append(ego_speed)
            if len(self._episode_speed_history) > 3:
                self._episode_speed_history.pop(0)
            if len(self._episode_speed_history) == 3:
                v0, v1, v2 = self._episode_speed_history
                second_derivative = (v2 - 2.0 * v1 + v0) / (self._DT ** 2)
                self._episode_smoothness_sum += abs(second_derivative)
                self._episode_smoothness_count += 1

        collision_flag = step_info.get("collision")
        if collision_flag:
            self._episode_collision = True

        reason = step_info.get("reason")
        if reason == "out_of_road":
            self._episode_out_of_road = True

    def end_episode(self, step_info: Optional[Dict] = None) -> None:
        """Finalize the current episode and reset accumulators."""
        if step_info:
            self.update(step_info)

        self._episode_count += 1

        if self._episode_collision:
            self._collision_episodes += 1
        if self._episode_out_of_road:
            self._out_of_road_episodes += 1

        if self._episode_ttc_count > 0:
            self._ttc_episode_means.append(
                self._episode_ttc_sum / float(self._episode_ttc_count)
            )
        if self._episode_heading_count > 0:
            self._heading_episode_means.append(
                self._episode_heading_sum / float(self._episode_heading_count)
            )
        if self._episode_position_count > 0:
            self._position_episode_means.append(
                self._episode_position_sum / float(self._episode_position_count)
            )
        if self._episode_progress_count > 0:
            self._progress_episode_values.append(
                self._episode_progress_sum / float(self._episode_progress_count)
            )
        if self._episode_smoothness_count > 0:
            self._smoothness_episode_means.append(
                self._episode_smoothness_sum / float(self._episode_smoothness_count)
            )

        self._reset_episode_accumulators()

    def _mean(self, values: List[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / float(len(values))

    def summary(self) -> Dict[str, float]:
        """Return aggregated metrics across episodes."""
        episode_count = float(self._episode_count) if self._episode_count > 0 else 1.0

        return {
            "time_to_collision": self._mean(self._ttc_episode_means),
            "collision_ratio": self._collision_episodes / episode_count,
            "out_of_road_ratio": self._out_of_road_episodes / episode_count,
            "avg_position_deviation": self._mean(self._position_episode_means),
            "avg_heading_error": self._mean(self._heading_episode_means),
            "progress_ratio": self._mean(self._progress_episode_values),
            "smoothness": self._mean(self._smoothness_episode_means),
        }
