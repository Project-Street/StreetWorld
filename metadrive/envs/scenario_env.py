"""
This environment can load all scenarios exported from other environments via env.export_scenarios()
"""

from typing import Union

import numpy as np
import math

import torch
from metadrive.manager.agent_manager import AgentState
from metadrive.configs.default_scenario_config import SCENARIO_ENV_CONFIG
from metadrive.envs.base_env import BaseEnv
from metadrive.manager.scenario_curriculum_manager import ScenarioCurriculumManager
from metadrive.manager.scenario_data_manager import ScenarioDataManager
from metadrive.manager.scenario_map_manager import ScenarioMapManager
from metadrive.manager.agent_manager import AgentManager
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.utils.random_utils import get_np_random
from metadrive.utils.math import wrap_to_pi
from metadrive.utils.navigation_utils import nearest_front_index
from metadrive.envs.scenario_metrics import ScenarioMetricTracker



class ScenarioEnv(BaseEnv):
    @classmethod
    def default_config(cls):
        config = super(ScenarioEnv, cls).default_config()
        config.update(SCENARIO_ENV_CONFIG)
        return config

    def __init__(self, model, config=None):
        super(ScenarioEnv, self).__init__(model, config)
        self.metric_tracker = ScenarioMetricTracker()
        self._reset_reward_trackers()
        if self.config["curriculum_level"] > 1:
            assert self.config["num_scenarios"] % self.config["curriculum_level"] == 0, \
                "Each level should have the same number of scenarios"
            if self.config["num_workers"] > 1:
                num = int(self.config["num_scenarios"] / self.config["curriculum_level"])
                assert num % self.config["num_workers"] == 0
        if self.config["num_workers"] > 1:
            assert self.config["sequential_seed"], \
                "If using > 1 workers, you have to allow sequential_seed for consistency!"

    def _post_process_config(self, config):
        config = super(ScenarioEnv, self)._post_process_config(config)
        return config

    def _init_agent_manager(self):
        return AgentManager(self.config['actor_config'], self.step_manager)

    def done_function(self):
        state_info = self.agent_managers['actor'].state
        is_max_step = self.config["max_step"] is not None and self.episode_lengths >= self.config["max_step"]

        def msg(reason):
            return "Episode ended! Scenario Index: {} Scenario id: {} Reason: {}.".format(
                self.current_seed, self.scene_id, reason
            )
        
        done = False
        if state_info == AgentState.SUCCESS:
            done = True
            self.logger.debug(msg("arrive_dest"), extra={"log_once": True})
        elif state_info == AgentState.OUT_OF_ROAD:
            done = True
            self.logger.debug(msg("out_of_road"), extra={"log_once": True})
        elif state_info == AgentState.OUT_OF_STEP:
            done = True
            self.logger.debug(msg("out_of_step of object"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_HUMAN:
            done = True
            self.logger.debug(msg("crash human"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_VEHICLE:
            done = True
            self.logger.debug(msg("crash vehicle"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_OBJECT:
            done = True
            self.logger.debug(msg("crash object"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_WORLD:
            done = True
            self.logger.debug(msg("crash background"), extra={"log_once": True})
        elif is_max_step:
            state_info = AgentState.OUT_OF_STEP
            done = True
            self.logger.debug(msg("max step"), extra={"log_once": True})

        # # log data to curriculum manager
        # self.engine.curriculum_manager.log_episode(
        #     done_info[TerminationState.SUCCESS], vehicle.navigation.route_completion
        # )

        info = {'reason': state_info}
        if done:
            info.update(
                ep_sum_progress=self._episode_reward_sums.get("progress", 0.0),
                ep_sum_ttc=self._episode_reward_sums.get("ttc", 0.0),
                ep_sum_heading=self._episode_reward_sums.get("heading", 0.0),
                ep_sum_position=self._episode_reward_sums.get("position", 0.0),
                ep_sum_living_cost=self._episode_reward_sums.get("living_cost", 0.0),
                ep_sum_success_bonus=self._episode_reward_sums.get("success_bonus", 0.0),
                ep_stall_steps_count=self._episode_counters.get("stall_steps", 0),
                ep_ttc_warning_steps_count=self._episode_counters.get("ttc_warn_steps", 0),
                collision_happened=int(self._episode_counters.get("collision", False)),
            )
        return done, info

    def cost_function(self):
        actor_mgr = self.agent_managers['actor']
        state = actor_mgr.state

        step_info = dict(num_crash_object=0, num_crash_human=0, num_crash_vehicle=0, num_on_line=0)
        cost = 0

        if state == AgentState.OUT_OF_ROAD:
            cost += self.config["out_of_road_cost"]
        if state == AgentState.CRASH_VEHICLE:
            cost += self.config["crash_vehicle_cost"]
            step_info["crash_vehicle_cost"] = self.config["crash_vehicle_cost"]
            step_info["num_crash_vehicle"] = 1
        if state == AgentState.CRASH_HUMAN:
            cost += self.config["crash_human_cost"]
            step_info["num_crash_human"] = 1
        if state == AgentState.CRASH_OBJECT:
            step_info["num_crash_object"] = 1

        step_info["cost"] = cost
        return cost, step_info

    def reset(self, seed: Union[None, int] = None, scene_id: Union[None, str] = None):
        self._stop_async_step_loop()
        self._reset_reward_trackers()
        obs, info = super().reset(seed=seed, scene_id=scene_id)
        self.metric_tracker.reset(warmup_step=self.agent_managers["actor"].warmup_step)
        self.metric_tracker.update(info, obs, self)
        return obs, info

    def _step(self, actions):
        obs, reward, terminated, truncated, info = super()._step(actions)
        self.metric_tracker.update(info, obs, self)
        if terminated or truncated:
            self.metric_tracker.finalize()
        return obs, reward, terminated, truncated, info

    def get_average_metric(self):
        return self.metric_tracker.get_average_metric()

    def _reset_reward_trackers(self):
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

    def reward_function(self):
        """Return reward composed of collision, positional, heading, TTC, progress, and shaping terms."""
        actor_manager = self.agent_managers['actor']
        state = actor_manager.state
        vehicle = actor_manager.controller
        nav = self._get_navigation_observer()

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
            collision_reward = -float(self.config.get("collision_penalty_weight", 50.0))
        success_bonus = 0.0
        if state == AgentState.SUCCESS:
            success_bonus = float(self.config.get("success_bonus", 50.0))

        # ===== Expert reference =====
        expert_state = None
        ego_xy = None
        path_xy = None
        path_cumlen = None
        if nav is not None:
            path_xy = getattr(nav, "_path_xy", None)
            path_cumlen = getattr(nav, "_path_cumlen", None)
            if path_xy is not None and len(path_xy) > 0:
                ego_xy = nav._vehicle_xy(vehicle)

        best_idx = None
        best_dist = None
        progress_val = None
        valid_path = path_xy is not None and len(path_xy) >= 2
        valid_ego = ego_xy is not None
        if valid_path and valid_ego:
            progress_val, best_idx, best_dist = self._project_progress_along_path(
                ego_xy, path_xy, path_cumlen, self._last_progress_idx
            )

        if best_idx is None and nav is not None and path_xy is not None:
            heading_vec = nav._ego_heading_vec(vehicle)
            idx = nearest_front_index(path_xy, ego_xy, heading_vec) if ego_xy is not None else 0
            best_idx = int(np.clip(idx, 0, len(path_xy) - 1))

        if best_idx is not None and nav is not None and hasattr(nav, "get_reference_state"):
            expert_state = nav.get_reference_state(int(np.clip(best_idx, 0, len(path_xy) - 1)))

        step_info["expert_available"] = 1 if expert_state else 0
        ego_speed = vehicle.speed
        diag_info["speed"] = ego_speed

        # ===== Positional deviation =====
        position_reward = 0.0
        deviation = best_dist
        position_threshold = None
        if deviation is None and expert_state and expert_state.get("position") is not None and ego_xy is not None:
            expert_pos = np.asarray(expert_state["position"], dtype=np.float32)
            deviation = float(np.linalg.norm(ego_xy - expert_pos))
        if deviation is not None:
            position_threshold = max(self.config.get("position_deviation_threshold", 2.0), 1e-3)
            if deviation > position_threshold:
                gain = float(self.config.get("position_penalty_gain", 0.5))
                max_penalty = float(self.config.get("position_penalty_max", 1.0))
                position_reward = -min(max_penalty, gain * (deviation - position_threshold))
        step_info["position_deviation"] = deviation
        step_info["position_threshold"] = position_threshold
        diag_info["deviation"] = deviation

        # ===== Heading deviation =====
        heading_reward = 0.0
        heading_penalty_max = float(self.config.get("heading_penalty_max", 1.0))
        ego_heading = vehicle.heading_theta
        if expert_state and expert_state.get("heading_theta") is not None:
            expert_heading = float(expert_state["heading_theta"])
            heading_err = abs(wrap_to_pi(ego_heading - expert_heading))
            heading_threshold = max(float(self.config.get("heading_deviation_threshold", 0.1)), 1e-6)
            if heading_err > heading_threshold:
                heading_reward = -float(self.config.get("heading_penalty_weight", 0.5)) * (heading_err - heading_threshold)
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
        progress_delta = 0.0
        progress_weight = float(self.config.get("progress_reward_weight", 2.0))
        reverse_weight = float(self.config.get("reverse_penalty_weight", 1.0))

        valid_path = path_xy is not None and len(path_xy) >= 2
        valid_ego = ego_xy is not None

        if valid_path and valid_ego and progress_val is not None:
            if self._last_progress_value is None:
                self._last_progress_value = progress_val
                self._last_progress_idx = best_idx

            delta = progress_val - self._last_progress_value
            progress_delta = delta

            if delta > 1e-3:
                progress_forward = progress_weight * delta
                deviation_for_progress = best_dist if best_dist is not None else deviation or 0.0
                alpha = float(self.config.get("progress_deviation_weight", 1.0))
                if deviation_for_progress > 1e-4 and alpha > 0:
                    progress_forward *= math.exp(-alpha * deviation_for_progress)
            elif delta < -1e-3:
                reverse_component = -reverse_weight * abs(delta)

            self._last_progress_value = progress_val
            self._last_progress_idx = best_idx

        else:
            self._last_progress_value = None
            self._last_progress_idx = None

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
        step_info["collision_count"] = int(self._episode_counters.get("collision", False))

        # ===== Safety: TTC shaping (with gating on stall) =====
        ttc_reward = 0.0
        ttc_safe = float(self.config.get("ttc_safe_horizon", 4.0))
        ttc_warn = float(self.config.get("ttc_warn_horizon", 2.0))
        w_mid = float(self.config.get("ttc_mid_penalty_weight", 0.5))
        w_high = float(self.config.get("ttc_high_penalty_weight", 0.8))
        w_safe_bonus = float(self.config.get("ttc_safe_bonus_weight", 0.2))
        min_ttc = self._compute_min_ttc(vehicle)
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

        v_min = float(self.config.get("ttc_safe_bonus_min_speed", 0.5))
        progress_min = float(self.config.get("ttc_safe_bonus_min_progress", 0.05))
        stalled = ego_speed <= v_min and progress_delta <= progress_min
        if ttc_reward > 0.0 and stalled:
            ttc_reward = 0.0
        diag_info["stalled"] = stalled
        # ===== Living cost =====
        living_cost = float(self.config.get("living_cost", 0.05))

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

    def _compute_min_ttc(self, vehicle):
        objects = self._collect_all_object()
        if not objects:
            return None

        transform_inv = np.linalg.inv(vehicle.transform)
        R_vehicle_world = transform_inv[:3, :3]

        vel_world = np.asarray(vehicle.velocity)
        vel_world3 = np.array([float(vel_world[0]), float(vel_world[1]), 0.0], dtype=np.float32)
        ego_vel_ego = (R_vehicle_world @ vel_world3)[:2]

        min_ttc = None
        for name, obj in objects.items():
            if obj["controller"] is vehicle:
                continue

            obj_transform = obj["transform"]
            rel_transform = transform_inv @ obj_transform
            rel_pos = np.asarray(rel_transform[:2, 3], dtype=np.float32)
            obj_vel_world = np.asarray(obj["velocity"], dtype=np.float32).reshape(-1)
            if obj_vel_world.shape[0] < 2:
                raise ValueError(f"Expected object velocity with at least 2 values, got shape {obj_vel_world.shape}")
            obj_vel_world3 = np.array([float(obj_vel_world[0]), float(obj_vel_world[1]), 0.0], dtype=np.float32)
            rel_vel = (R_vehicle_world @ obj_vel_world3)[:2] - ego_vel_ego
            dist = float(np.linalg.norm(rel_pos))
            if dist < 1e-3:
                return 0.0
            rel_dir = rel_pos / dist
            closing_speed = -float(np.dot(rel_vel, rel_dir))
            if closing_speed <= 1e-3:
                continue
            ttc = dist / closing_speed
            if min_ttc is None or ttc < min_ttc:
                min_ttc = ttc
        return min_ttc

    def _get_navigation_observer(self):
        actor_observer = getattr(self.agent_managers['actor'], "observer", None)
        if isinstance(actor_observer, NavigationObservation):
            return actor_observer
        if isinstance(actor_observer, AssemblyObservation):
            nav = actor_observer._observers.get("navigation") if hasattr(actor_observer, "_observers") else None
            if isinstance(nav, NavigationObservation):
                return nav
        return None
    def _project_progress_along_path(self, position, path_xy, path_cumlen, last_idx):
        if path_xy is None or len(path_xy) < 2:
            return None, None
        pts = np.asarray(path_xy, dtype=np.float32)
        if path_cumlen is None or len(path_cumlen) != len(pts):
            seg_lengths = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
            path_cumlen = np.concatenate(([0.0], np.cumsum(seg_lengths)))
        N = len(pts) - 1
        if N <= 0:
            return None, None
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
                base = float(path_cumlen[idx]) if idx < len(path_cumlen) else 0.0
                best_progress = base + t * seg_len
                best_dist = dist
                best_idx = idx

        if best_progress is None:
            return None, None, None
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

class ScenarioOnlineEnv(ScenarioEnv):
    """
    This environment allow the user to pass in scenario data directly.
    """
    def default_config(cls):
        config = super(ScenarioOnlineEnv, cls).default_config()
        config.update({
            "store_map": False,
        })
        return config

    def __init__(self, config=None):
        super(ScenarioOnlineEnv, self).__init__(config)
        self.lazy_init()

        assert self.config["store_map"] is False, \
            "ScenarioOnlineEnv should not store map. Please set store_map=False in config"

    def _setup(self):
        """Overwrite the data_manager by ScenarioOnlineDataManager"""
        super()._setup()
        self.engine.update_manager("data_manager", ScenarioOnlineDataManager())

    def set_scenario(self, scenario_data):
        """Please call this function before env.reset()"""
        self.engine.data_manager.set_scenario(scenario_data)


class ScenarioWaypointEnv(ScenarioEnv):
    """
    This environment use WaypointPolicy. Even though the environment still runs in 10 HZ, we allow the external
    waypoint generator generates up to 5 waypoints at each step (controlled by config "waypoint_horizon").
    Say at step t, we receive 5 waypoints. Then we will set the agent states for t+1, t+2, t+3, t+4, t+5 if at
    t+1 ~ t+4 no additional waypoints are received. Here is the full timeline:

    step t=0: env.reset(), initial positions/obs are sent out. This corresponds to the t=0 or t=10 in WOMD dataset
    (TODO: we should allow control on the meaning of the t=0)
    step t=1: env.step(), agent receives 5 waypoints, we will record the waypoint sequences. Set agent state for t=1,
        and send out the obs for t=1.
    step t=2: env.step(), it's possible to get action=None, which means the agent will use the cached waypoint t=2,
        and set the agent state for t=2. The obs for t=2 will be sent out. If new waypoints are received, we will \
        instead set agent state to the first new waypoint.
    step t=3: ... continues the loop and receives action=None or new waypoints.
    step t=4: ...
    step t=5: ...
    step t=6: if we only receive action at t=1, and t=2~t=5 are all None, then this step will force to receive
        new waypoints. We will set the agent state to the first new waypoint.

    Most of the functions are implemented in WaypointPolicy.
    """
    @classmethod
    def default_config(cls):
        config = super(ScenarioWaypointEnv, cls).default_config()
        return config

    def _post_process_config(self, config):
        ret = super(ScenarioWaypointEnv, self)._post_process_config(config)
        assert config["set_static"], "Waypoint policy requires set_static=True"
        return ret
