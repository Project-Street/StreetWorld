"""Scenario reward calculation and episode diagnostics."""

import math

import numpy as np

from streetworld.manager.agent_manager import AgentState
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.utils.math import wrap_to_pi


class RewardCalculator:
    def __init__(self):
        self.reset()

    def reset(self):
        self._last_progress_value = None
        self._last_progress_idx = None
        self._episode_reward_sums = dict(
            progress=0.0,
            ttc=0.0,
            heading=0.0,
            position=0.0,
            living_cost=0.0,
            success_bonus=0.0,
        )
        self._episode_counters = dict(
            stall_steps=0,
            ttc_warn_steps=0,
            collision=False,
        )

    def compute(self, env):
        """Calculate reward from the environment and this calculator's episode history."""
        actor_manager = env.actor_manager
        vehicle = actor_manager.controller
        state = actor_manager.state
        config = env.config
        navigation = self._get_navigation_observer(env)

        step_info = dict()
        diag_info = dict()
        collision_states = {
            AgentState.CRASH_VEHICLE,
            AgentState.CRASH_HUMAN,
            AgentState.CRASH_OBJECT,
            AgentState.CRASH_WORLD,
            AgentState.OUT_OF_ROAD,
        }
        collision = state in collision_states
        step_info["collision"] = int(collision)
        collision_reward = 0.0
        if collision:
            collision_reward = -float(config["collision_penalty_weight"])
        success_bonus = 0.0
        if state == AgentState.SUCCESS:
            success_bonus = float(config["success_bonus"])

        progress, progress_idx, deviation = self._project_progress_along_path(
            navigation._NavigationObservation__vehicle_xy(vehicle), navigation._path_xy, navigation._path_cumlen,
            self._last_progress_idx,
        )
        progress_delta = 0.0 if self._last_progress_value is None else progress - self._last_progress_value
        self._last_progress_value = progress
        self._last_progress_idx = progress_idx
        expert_state = navigation.get_reference_state(progress_idx)
        step_info["expert_available"] = 1 if expert_state else 0
        ego_speed = vehicle.speed
        diag_info["speed"] = ego_speed

        # ===== Positional deviation =====
        position_reward = 0.0
        position_threshold = None
        if deviation is not None:
            position_threshold = max(config["position_deviation_threshold"], 1e-3)
            if deviation > position_threshold:
                gain = float(config["position_penalty_gain"])
                max_penalty = float(config["position_penalty_max"])
                position_reward = -min(max_penalty, gain * (deviation - position_threshold))
        step_info["position_deviation"] = deviation
        step_info["position_threshold"] = position_threshold
        diag_info["deviation"] = deviation

        # ===== Heading deviation =====
        heading_reward = 0.0
        heading_penalty_max = float(config["heading_penalty_max"])
        ego_heading = vehicle.heading_theta
        if expert_state and expert_state.get("heading_theta") is not None:
            expert_heading = float(expert_state["heading_theta"])
            heading_err = abs(wrap_to_pi(ego_heading - expert_heading))
            heading_threshold = max(float(config["heading_deviation_threshold"]), 1e-6)
            if heading_err > heading_threshold:
                heading_reward = -float(config["heading_penalty_weight"]) * (heading_err - heading_threshold)
            if heading_penalty_max > 0.0:
                heading_reward = max(-heading_penalty_max, heading_reward)
            step_info["heading_error"] = heading_err
            step_info["heading_threshold"] = heading_threshold
        else:
            step_info["heading_error"] = None
            step_info["heading_threshold"] = None

        # ===== Progress along route =====
        progress_forward = 0.0
        reverse_component = 0.0
        progress_reward = 0.0
        progress_weight = float(config["progress_reward_weight"])
        reverse_weight = float(config["reverse_penalty_weight"])

        if progress_delta > 1e-3:
            progress_forward = progress_weight * progress_delta
            alpha = float(config["progress_deviation_weight"])
            if deviation > 1e-4 and alpha > 0:
                progress_forward *= math.exp(-alpha * deviation)
        elif progress_delta < -1e-3:
            reverse_component = -reverse_weight * abs(progress_delta)

        if collision and progress_forward > 0:
            progress_forward = 0.0

        progress_reward = progress_forward + reverse_component
        step_info["progress"] = progress_reward / progress_weight if progress_weight > 1e-6 else 0.0
        diag_info["progress_delta"] = progress_delta
        denom = progress_weight * progress_delta + 1e-8
        if denom <= 0:
            progress_ratio = 0.0
        else:
            progress_ratio = progress_forward / denom
        step_info["progress_ratio"] = float(progress_ratio)
        diag_info["progress_ratio"] = float(progress_ratio)
        step_info["ego_speed"] = ego_speed
        step_info["collision_count"] = int(self._episode_counters["collision"])

        # ===== Safety: TTC shaping (with gating on stall) =====
        ttc_reward = 0.0
        ttc_safe = float(config["ttc_safe_horizon"])
        ttc_warn = float(config["ttc_warn_horizon"])
        w_mid = float(config["ttc_mid_penalty_weight"])
        w_high = float(config["ttc_high_penalty_weight"])
        w_safe_bonus = float(config["ttc_safe_bonus_weight"])
        min_ttc = self._compute_min_ttc(vehicle, env._BaseEnv__collect_all_object())
        if min_ttc is not None:
            if min_ttc <= ttc_warn:
                penalty = (ttc_warn - min_ttc) / max(ttc_warn, 1e-3)
                ttc_reward = -w_high * np.clip(penalty, 0.0, 1.0)
            elif min_ttc < ttc_safe:
                penalty = (ttc_safe - min_ttc) / max(ttc_safe - ttc_warn, 1e-3)
                ttc_reward = -w_mid * np.clip(penalty, 0.0, 1.0)
            else:
                bonus = (min_ttc - ttc_safe) / max(ttc_safe, 1e-3)
                ttc_reward = w_safe_bonus * np.clip(bonus, 0.0, 1.0)
        diag_info["ttc"] = min_ttc
        step_info["ttc"] = min_ttc

        v_min = float(config["ttc_safe_bonus_min_speed"])
        progress_min = float(config["ttc_safe_bonus_min_progress"])
        stalled = ego_speed <= v_min and progress_delta <= progress_min
        if ttc_reward > 0.0 and stalled:
            ttc_reward = 0.0
        diag_info["stalled"] = stalled
        # ===== Living cost =====
        living_cost = float(config["living_cost"])

        # ===== Episode stats bookkeeping =====
        self._episode_reward_sums["progress"] += progress_reward
        self._episode_reward_sums["ttc"] += ttc_reward
        self._episode_reward_sums["heading"] += heading_reward
        self._episode_reward_sums["position"] += position_reward
        self._episode_reward_sums["living_cost"] += living_cost
        self._episode_reward_sums["success_bonus"] += success_bonus
        if collision:
            self._episode_counters["collision"] = True
        if min_ttc is not None and min_ttc <= ttc_warn:
            self._episode_counters["ttc_warn_steps"] += 1
        if stalled:
            self._episode_counters["stall_steps"] += 1

        reward_components = {
            "living_cost": living_cost,
            "progress": progress_forward,
            "reverse": reverse_component,
            "ttc": ttc_reward,
            "position": position_reward,
            "heading": heading_reward,
            "collision": collision_reward,
            "success_bonus": success_bonus,
        }
        total_reward = sum(reward_components.values())
        reward_components["total"] = total_reward

        step_info["reward_components"] = reward_components
        step_info["diag"] = diag_info
        step_info["step_reward"] = total_reward
        step_info["stalled"] = stalled

        return total_reward, step_info

    def episode_info(self):
        return {
            "ep_sum_progress": self._episode_reward_sums["progress"],
            "ep_sum_ttc": self._episode_reward_sums["ttc"],
            "ep_sum_heading": self._episode_reward_sums["heading"],
            "ep_sum_position": self._episode_reward_sums["position"],
            "ep_sum_living_cost": self._episode_reward_sums["living_cost"],
            "ep_sum_success_bonus": self._episode_reward_sums["success_bonus"],
            "ep_stall_steps_count": self._episode_counters["stall_steps"],
            "ep_ttc_warning_steps_count": self._episode_counters["ttc_warn_steps"],
            "collision_happened": int(self._episode_counters["collision"]),
        }

    @staticmethod
    def _compute_min_ttc(vehicle, objects):
        transform_inv = np.linalg.inv(vehicle.transform)
        rotation = transform_inv[:3, :3]
        velocity = np.asarray(vehicle.velocity)
        ego_velocity_xy = (rotation @ np.array([velocity[0], velocity[1], 0.0], dtype=np.float32))[:2]
        min_ttc = None
        for obj in objects.values():
            if obj["controller"] is vehicle:
                continue
            relative_position = np.asarray((transform_inv @ obj["transform"])[:2, 3], dtype=np.float32)
            velocity = np.asarray(obj["velocity"], dtype=np.float32).reshape(-1)
            if len(velocity) < 2:
                raise ValueError("Object velocity must contain at least two values.")
            relative_velocity = (
                rotation @ np.array([velocity[0], velocity[1], 0.0], dtype=np.float32)
            )[:2] - ego_velocity_xy
            distance = float(np.linalg.norm(relative_position))
            if distance < 1e-3:
                return 0.0
            closing_speed = -float(np.dot(relative_velocity, relative_position / distance))
            if closing_speed <= 1e-3:
                continue
            ttc = distance / closing_speed
            if min_ttc is None or ttc < min_ttc:
                min_ttc = ttc
        return min_ttc

    @staticmethod
    def _get_navigation_observer(env):
        observer = env.actor_manager.observer
        if isinstance(observer, AssemblyObservation):
            observer = observer._observers["navigation"]
        if not isinstance(observer, NavigationObservation):
            raise TypeError("Scenario reward requires a NavigationObservation.")
        return observer

    def _project_progress_along_path(self, position, path_xy, path_cumlen, last_idx):
        if len(path_xy) < 2:
            raise ValueError("Navigation route must contain at least two points.")
        pts = np.asarray(path_xy, dtype=np.float32)
        if len(path_cumlen) != len(pts):
            raise ValueError("Navigation route and cumulative lengths must have equal lengths.")
        N = len(pts) - 1
        if last_idx is None:
            seg_range = range(0, N)
        else:
            k_low = 5
            k_high = 50
            lo = max(0, last_idx - k_low)
            hi = min(N, last_idx + k_high)
            seg_range = range(lo, hi)

        best_progress = None
        best_dist = np.inf
        best_idx = None
        pos = np.asarray(position, dtype=np.float32)

        for idx in seg_range:
            p0 = pts[idx]
            p1 = pts[idx + 1]
            seg = p1 - p0
            seg_len = np.linalg.norm(seg)
            if seg_len < 1e-6:
                continue
            t = float(np.dot(pos - p0, seg) / (seg_len ** 2))
            t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
            proj = p0 + t * seg
            dist = np.linalg.norm(pos - proj)
            if dist < best_dist:
                base = float(path_cumlen[idx])
                best_progress = base + t * seg_len
                best_dist = dist
                best_idx = idx

        if best_progress is None:
            raise ValueError("Navigation route has no nonzero-length segment.")
        return best_progress, best_idx, best_dist

    def _get_reference_direction(self, path_xy, idx):
        if path_xy is None or idx is None or len(path_xy) < 2:
            return None

        if idx < len(path_xy) - 1:
            ref_idx0 = idx
            ref_idx1 = idx + 1
        elif idx > 0:
            ref_idx0 = idx - 1
            ref_idx1 = idx
        else:
            return None

        target_vec = path_xy[ref_idx1] - path_xy[ref_idx0]
        norm = np.linalg.norm(target_vec)
        if norm < 1e-6:
            return None
        return target_vec / norm
