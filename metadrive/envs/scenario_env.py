"""
This environment can load all scenarios exported from other environments via env.export_scenarios()
"""

from typing import Union

import numpy as np
import math

import torch
from metadrive.manager.agent_manager import AgentState
from metadrive.engine.asset_loader import AssetLoader
from metadrive.envs.base_env import BaseEnv
from metadrive.manager.scenario_curriculum_manager import ScenarioCurriculumManager
from metadrive.manager.scenario_data_manager import ScenarioDataManager, ScenarioOnlineDataManager
from metadrive.manager.scenario_map_manager import ScenarioMapManager
from metadrive.manager.agent_manager import AgentManager
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.obs.surrounding_obs import SurroundingObservation
from metadrive.utils.random_utils import get_np_random
from metadrive.utils.math import wrap_to_pi
from metadrive.utils.navigation_utils import nearest_front_index

SCENARIO_ENV_CONFIG = dict(
    # ===== Scenario Config =====
    data_directory=AssetLoader.file_path("nuscenes", unix_style=False),
    start_scenario_index=0,

    # Set num_scenarios=-1 to load all scenarios in the data directory.
    num_scenarios=3,
    sequential_seed=False,  # Whether to set seed (the index of map) sequentially across episodes
    worker_index=0,  # Allowing multi-worker sampling with Rllib
    num_workers=1,  # Allowing multi-worker sampling with Rllib

    # ===== Curriculum Config =====
    curriculum_level=1,  # i.e. set to 5 to split the data into 5 difficulty level
    episodes_to_evaluate_curriculum=None,
    target_success_rate=0.8,

    # ===== Map Config =====
    store_map=True,
    store_data=True,
    need_lane_localization=True,
    no_map=False,
    map_region_size=1024,
    cull_lanes_outside_map=True,

    # ===== Scenario =====
    no_traffic=False,  # nothing will be generated including objects/pedestrian/vehicles
    no_static_vehicles=False,  # static vehicle will be removed
    no_light=False,  # no traffic light
    reactive_traffic=False,  # turn on to enable idm traffic
    filter_overlapping_car=True,  # If in one frame a traffic vehicle collides with ego car, it won't be created.
    default_vehicle_in_traffic=False,
    skip_missing_light=True,
    static_traffic_object=True,
    show_sidewalk=False,
    even_sample_vehicle_class=None,  # Deprecated.

    # ===== Reward Scheme =====
    position_deviation_threshold=2,
    position_penalty_gain=0.2,
    position_penalty_max=0.25,
    heading_deviation_threshold=0.1,
    heading_penalty_weight=0.5,
    heading_penalty_max=0.5,
    position_improve_weight=0.2,
    heading_improve_weight=0.2,
    progress_reward_weight=2.0,
    reverse_penalty_weight=1.0,
    lag_warn_distance=6.0,
    lag_warn_penalty=0.1,
    lag_fail_distance=15.0,
    progress_deviation_weight=0.1,
    progress_match_tolerance=0.2,
    progress_match_decay=2.0,
    ttc_safe_horizon=4.0,
    ttc_warn_horizon=2.0,
    ttc_mid_penalty_weight=0.5,
    ttc_high_penalty_weight=0.8,
    ttc_safe_bonus_weight=0.2,
    ttc_safe_bonus_min_speed=0.5,
    ttc_safe_bonus_min_progress=0.05,
    living_cost=0.05,
    anti_stall_window=30,
    enable_anti_stall_truncation=True,

    # ===== Cost Scheme =====
    crash_vehicle_cost=1.0,
    crash_object_cost=1.0,
    out_of_road_cost=1.0,
    crash_human_cost=1.0,

    # ===== Termination Scheme =====
    out_of_route_done=False,
    crash_vehicle_done=False,
    crash_object_done=False,
    crash_human_done=False,
    relax_out_of_road_done=True,

    # ===== Collision Reward =====
    collision_penalty_weight=50.0,

    # ===== Episode Bonus =====
    success_bonus=75.0,
    max_step=300,
)



class ScenarioEnv(BaseEnv):
    @classmethod
    def default_config(cls):
        config = super(ScenarioEnv, cls).default_config()
        config.update(SCENARIO_ENV_CONFIG)
        return config

    def __init__(self, model, config=None):
        super(ScenarioEnv, self).__init__(model, config)
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
                self.current_seed, self.data_manager.current_scenario_id, reason
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

        stall_truncate = False
        if not done and self._stall_truncate_flag:
            state_info = AgentState.OUT_OF_STEP
            done = True
            stall_truncate = True
        if done:
            self._stall_truncate_flag = False
            if stall_truncate:
                self.logger.debug(msg("anti_stall_truncation"), extra={"log_once": True})

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
                anti_stall_truncated=int(stall_truncate),
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

    def reset(self, seed: Union[None, int] = None, scene_id: Union[None, int] = None):
        self._reset_reward_trackers()
        return super().reset(seed=seed, scene_id=scene_id)

    def _reset_reward_trackers(self):
        self._last_progress_value = None
        self._last_progress_idx = None
        self._last_expert_progress_value = None
        self._last_expert_progress_idx = None
        self._last_signed_lateral_error = None
        self._last_signed_heading_error = None
        self._stall_counter = 0
        self._stall_truncate_flag = False
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

    def reward_function_old(self):
        """Return reward composed of collision, positional, heading, TTC, progress, and shaping terms."""
        actor_manager = self.agent_managers['actor']
        state = actor_manager.state
        vehicle = getattr(actor_manager, "controller", None)
        nav = self._get_navigation_observer()

        step_info = dict()
        diag_info = dict()
        collision_states = {
            AgentState.CRASH_VEHICLE,
            AgentState.CRASH_HUMAN,
            AgentState.CRASH_OBJECT,
            AgentState.CRASH_WORLD,
            # AgentState.OUT_OF_ROAD,
        }
        collision = state in collision_states #or state == AgentState.OUT_OF_ROAD
        step_info["collision"] = int(collision)
        collision_reward = 0.0
        if collision:
            collision_reward = -float(self.config.get("collision_penalty_weight", 50.0))
        if state == AgentState.OUT_OF_ROAD:
            collision_reward = -20.0
        success_bonus = 0.0
        if state == AgentState.SUCCESS:
            success_bonus = float(self.config.get("success_bonus", 50.0))

        # ===== Expert reference =====
        expert_state = None
        ego_xy = None
        path_xy = None
        path_cumlen = None
        if nav is not None and vehicle is not None:
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

        if best_idx is None and nav is not None and vehicle is not None and path_xy is not None:
            heading_vec = nav._ego_heading_vec(vehicle)
            idx = nearest_front_index(path_xy, ego_xy, heading_vec) if ego_xy is not None else 0
            best_idx = int(np.clip(idx, 0, len(path_xy) - 1))

        if best_idx is not None and valid_path and path_xy is not None and nav is not None and hasattr(nav, "get_reference_state"):
            path_len = len(path_xy)
            expert_state = nav.get_reference_state(int(np.clip(best_idx, 0, path_len - 1)))

        step_info["expert_available"] = 1 if expert_state else 0

        expert_progress_val = None
        expert_progress_idx = None
        expert_progress_time_val = None
        expert_progress_time_idx = None
        expert_xy_t = None
        expert_xy_t1 = None
        if valid_path and expert_state and expert_state.get("position") is not None:
            expert_xy_t = np.asarray(expert_state["position"], dtype=np.float32)
            expert_progress_val, expert_progress_idx, _ = self._project_progress_along_path(
                expert_xy_t, path_xy, path_cumlen, self._last_expert_progress_idx
            )
            if best_idx is not None and nav is not None and hasattr(nav, "get_reference_state"):
                next_idx = int(np.clip(best_idx + 1, 0, len(path_xy) - 1))
                expert_state_t1 = nav.get_reference_state(next_idx)
                if expert_state_t1 and expert_state_t1.get("position") is not None:
                    expert_xy_t1 = np.asarray(expert_state_t1["position"], dtype=np.float32)

        # Timestamp-aligned expert progress (aligned with ego env step index, not nearest/path index).
        if valid_path and nav is not None and hasattr(nav, "get_reference_state"):
            time_idx = int(np.clip(int(self.episode_lengths), 0, len(path_xy) - 1))
            expert_state_time = nav.get_reference_state(time_idx)
            if expert_state_time and expert_state_time.get("position") is not None:
                expert_xy_time = np.asarray(expert_state_time["position"], dtype=np.float32)
                expert_progress_time_val, expert_progress_time_idx, _ = self._project_progress_along_path(
                    expert_xy_time, path_xy, path_cumlen, self._last_expert_progress_idx
                )
                # Use timestamp-aligned expert displacement for per-step lag penalty when available.
                next_time_idx = int(np.clip(time_idx + 1, 0, len(path_xy) - 1))
                expert_state_time_t1 = nav.get_reference_state(next_time_idx)
                if expert_state_time_t1 and expert_state_time_t1.get("position") is not None:
                    expert_xy_t = expert_xy_time
                    expert_xy_t1 = np.asarray(expert_state_time_t1["position"], dtype=np.float32)

        ego_speed = float(vehicle.speed) if vehicle is not None and hasattr(vehicle, "speed") else 0.0
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
        ego_heading = float(getattr(vehicle, "heading_theta", 0.0)) if vehicle is not None else 0.0
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
        expert_progress_delta = 0.0
        relative_progress_delta = 0.0
        progress_match_factor = 1.0
        progress_weight = float(self.config.get("progress_reward_weight", 2.0))
        reverse_weight = float(self.config.get("reverse_penalty_weight", 1.0))
        match_tolerance = max(float(self.config.get("progress_match_tolerance", 0.2)), 0.0)
        match_decay = max(float(self.config.get("progress_match_decay", 2.0)), 0.0)

        valid_path = path_xy is not None and len(path_xy) >= 2
        valid_ego = ego_xy is not None

        if valid_path and valid_ego and progress_val is not None:
            if self._last_progress_value is None:
                self._last_progress_value = progress_val
                self._last_progress_idx = best_idx
            if expert_progress_val is not None and self._last_expert_progress_value is None:
                self._last_expert_progress_value = expert_progress_val
                self._last_expert_progress_idx = expert_progress_idx

            progress_delta = progress_val - self._last_progress_value
            if expert_progress_val is not None and self._last_expert_progress_value is not None:
                expert_progress_delta = expert_progress_val - self._last_expert_progress_value
            relative_progress_delta = progress_delta - expert_progress_delta

            if expert_progress_val is not None and self._last_expert_progress_value is not None:
                mismatch = max(0.0, abs(relative_progress_delta) - match_tolerance)
                progress_match_factor = math.exp(-match_decay * mismatch)
            else:
                progress_match_factor = 1.0

            if progress_delta > 1e-3:
                progress_forward = progress_weight * progress_delta * progress_match_factor
                deviation_for_progress = best_dist if best_dist is not None else deviation or 0.0
                alpha = float(self.config.get("progress_deviation_weight", 1.0))
                if deviation_for_progress > 1e-4 and alpha > 0:
                    progress_forward *= math.exp(-alpha * deviation_for_progress)
            elif relative_progress_delta < -1e-3:
                reverse_component = -reverse_weight * abs(relative_progress_delta)

            self._last_progress_value = progress_val
            self._last_progress_idx = best_idx
            if expert_progress_val is not None:
                self._last_expert_progress_value = expert_progress_val
                self._last_expert_progress_idx = expert_progress_idx

        else:
            self._last_progress_value = None
            self._last_progress_idx = None
            self._last_expert_progress_value = None
            self._last_expert_progress_idx = None

        if collision and progress_forward > 0:
            progress_forward = 0.0

        progress_reward = progress_forward + reverse_component
        step_info["progress"] = progress_reward / progress_weight if progress_weight > 1e-6 else 0.0
        diag_info["progress_delta"] = progress_delta
        step_info["expert_progress_delta"] = expert_progress_delta
        step_info["relative_progress_delta"] = relative_progress_delta
        step_info["progress_match_factor"] = progress_match_factor
        diag_info["expert_progress_delta"] = expert_progress_delta
        diag_info["relative_progress_delta"] = relative_progress_delta
        diag_info["progress_match_factor"] = progress_match_factor
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
            self._stall_counter += 1
        else:
            self._stall_counter = 0
        if self.config.get("enable_anti_stall_truncation", True):
            stall_window = max(int(self.config.get("anti_stall_window", 25)), 1)
            if self._stall_counter >= stall_window:
                self._stall_truncate_flag = True

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

    def reward_function(self):
        """Simplified reward with collision/pose penalties and progress-lag shaping."""
        actor_manager = self.agent_managers['actor']
        state = actor_manager.state
        vehicle = getattr(actor_manager, "controller", None)
        nav = self._get_navigation_observer()

        step_info = {}
        diag_info = {}

        # ---- Terminal event reward terms ----
        collision_states = {
            AgentState.CRASH_VEHICLE,
            AgentState.CRASH_HUMAN,
            AgentState.CRASH_OBJECT,
            AgentState.CRASH_WORLD,
        }
        collision = state in collision_states
        collision_reward = -float(self.config.get("collision_penalty_weight", 50.0)) if collision else 0.0
        success_bonus = float(self.config.get("success_bonus", 75.0)) if state == AgentState.SUCCESS else 0.0
        step_info["collision"] = int(collision)

        # ---- Fetch path and ego projection ----
        path_xy = None
        path_cumlen = None
        ego_xy = None
        if nav is not None and vehicle is not None:
            path_xy = getattr(nav, "_path_xy", None)
            path_cumlen = getattr(nav, "_path_cumlen", None)
            if path_xy is not None and len(path_xy) > 0:
                ego_xy = nav._vehicle_xy(vehicle)

        valid_path = path_xy is not None and len(path_xy) >= 2
        valid_ego = ego_xy is not None
        best_idx = None
        best_dist = None
        progress_val = None
        if valid_path and valid_ego:
            progress_val, best_idx, best_dist = self._project_progress_along_path(
                ego_xy, path_xy, path_cumlen, self._last_progress_idx
            )

        if best_idx is None and valid_path and nav is not None and vehicle is not None and ego_xy is not None:
            heading_vec = nav._ego_heading_vec(vehicle)
            idx = nearest_front_index(path_xy, ego_xy, heading_vec)
            best_idx = int(np.clip(idx, 0, len(path_xy) - 1))

        # ---- Expert states: nearest-index for pose terms; timestamp-aligned for lag terms ----
        expert_state_near = None
        ref_direction = None
        if valid_path and best_idx is not None and nav is not None and hasattr(nav, "get_reference_state"):
            near_idx = int(np.clip(best_idx, 0, len(path_xy) - 1))
            expert_state_near = nav.get_reference_state(near_idx)
            ref_direction = self._get_reference_direction(path_xy, near_idx)
        step_info["expert_available"] = 1 if expert_state_near else 0

        expert_progress_time_val = None
        expert_progress_time_idx = None
        expert_xy_t = None
        expert_xy_t1 = None
        if valid_path and nav is not None and hasattr(nav, "get_reference_state"):
            base_dt_us = max(int(self.config.get("physics_world_step_size", 1)), 1)
            step_dt_us = int(getattr(self.step_manager, "step_size", base_dt_us))
            expert_stride = max(int(round(step_dt_us / float(base_dt_us))), 1)
            time_idx = int(np.clip(int(self.episode_lengths) * expert_stride, 0, len(path_xy) - 1))
            next_time_idx = int(np.clip(time_idx + expert_stride, 0, len(path_xy) - 1))

            expert_state_t = nav.get_reference_state(time_idx)
            expert_state_t1 = nav.get_reference_state(next_time_idx)

            if expert_state_t and expert_state_t.get("position") is not None:
                expert_xy_t = np.asarray(expert_state_t["position"], dtype=np.float32)
                expert_progress_time_val, expert_progress_time_idx, _ = self._project_progress_along_path(
                    expert_xy_t, path_xy, path_cumlen, self._last_expert_progress_idx
                )
            if expert_state_t1 and expert_state_t1.get("position") is not None:
                expert_xy_t1 = np.asarray(expert_state_t1["position"], dtype=np.float32)

        # ---- Position deviation term ----
        position_reward = 0.0
        deviation = best_dist
        signed_lateral_error = 0.0

        if deviation is None and expert_state_near and expert_state_near.get("position") is not None and ego_xy is not None:
            expert_pos = np.asarray(expert_state_near["position"], dtype=np.float32)
            deviation = float(np.linalg.norm(ego_xy - expert_pos))
            if ref_direction is not None:
                rel = ego_xy - expert_pos
                signed_lateral_error = float(ref_direction[0] * rel[1] - ref_direction[1] * rel[0])
        elif (
            deviation is not None and valid_path and valid_ego and path_xy is not None and
            best_idx is not None and ref_direction is not None
        ):
            ref_idx = int(np.clip(best_idx, 0, len(path_xy) - 1))
            ref_point = np.asarray(path_xy[ref_idx], dtype=np.float32)
            rel = ego_xy - ref_point
            signed_lateral_error = float(ref_direction[0] * rel[1] - ref_direction[1] * rel[0])

        position_threshold = max(float(self.config.get("position_deviation_threshold", 2.0)), 1e-3)
        if deviation is not None and deviation > position_threshold:
            gain = float(self.config.get("position_penalty_gain", 0.2))
            max_penalty = float(self.config.get("position_penalty_max", 0.25))
            position_reward = -min(max_penalty, gain * (deviation - position_threshold))

        if self._last_signed_lateral_error is not None:
            improve = abs(self._last_signed_lateral_error) - abs(signed_lateral_error)
            if improve > 0:
                position_reward += float(self.config.get("position_improve_weight", 0.2)) * improve
        self._last_signed_lateral_error = signed_lateral_error

        if deviation is None:
            deviation = 0.0
        step_info["position_deviation"] = deviation
        step_info["position_threshold"] = position_threshold
        diag_info["deviation"] = deviation
        diag_info["signed_lateral_error"] = signed_lateral_error

        # ---- Heading deviation term ----
        heading_reward = 0.0
        heading_penalty_max = float(self.config.get("heading_penalty_max", 0.5))
        heading_threshold = max(float(self.config.get("heading_deviation_threshold", 0.1)), 1e-6)
        ego_heading = float(getattr(vehicle, "heading_theta", 0.0)) if vehicle is not None else 0.0
        signed_heading_error = 0.0
        heading_err = 0.0

        if expert_state_near and expert_state_near.get("heading_theta") is not None:
            expert_heading = float(expert_state_near["heading_theta"])
            signed_heading_error = float(wrap_to_pi(ego_heading - expert_heading))
            heading_err = abs(signed_heading_error)
            if heading_err > heading_threshold:
                heading_reward = -float(self.config.get("heading_penalty_weight", 0.5)) * (heading_err - heading_threshold)
            if heading_penalty_max > 0.0:
                heading_reward = max(-heading_penalty_max, heading_reward)

        if self._last_signed_heading_error is not None:
            improve = abs(self._last_signed_heading_error) - abs(signed_heading_error)
            if improve > 0:
                heading_reward += float(self.config.get("heading_improve_weight", 0.2)) * improve
        self._last_signed_heading_error = signed_heading_error

        step_info["heading_error"] = heading_err
        step_info["heading_threshold"] = heading_threshold
        diag_info["signed_heading_error"] = signed_heading_error

        # ---- Progress-lag terms ----
        progress_reward = 0.0
        progress_delta = 0.0
        expert_progress_delta = 0.0
        relative_progress_delta = 0.0
        progress_deficit = 0.0
        lag_distance = 0.0

        lag_tolerance = max(float(self.config.get("progress_match_tolerance", 0.2)), 0.0)
        lag_warn_distance = max(float(self.config.get("lag_warn_distance", 6.0)), 0.0)
        lag_warn_penalty = max(float(self.config.get("lag_warn_penalty", 0.1)), 0.0)
        lag_out_of_road_dist = max(float(self.config.get("lag_fail_distance", 15.0)), lag_warn_distance)
        progress_weight = float(self.config.get("progress_reward_weight", 2.0))
        progress_match_factor = 0.0
        lag_warn = 0

        ego_speed = float(vehicle.speed) if vehicle is not None and hasattr(vehicle, "speed") else 0.0
        diag_info["speed"] = ego_speed

        if valid_path and valid_ego and progress_val is not None:
            if self._last_progress_value is None:
                self._last_progress_value = progress_val
                self._last_progress_idx = best_idx

            progress_delta = float(progress_val - self._last_progress_value)

            if expert_xy_t is not None and expert_xy_t1 is not None:
                expert_progress_delta = float(np.linalg.norm(expert_xy_t1 - expert_xy_t))
            elif expert_progress_time_val is not None and self._last_expert_progress_value is not None:
                expert_progress_delta = float(expert_progress_time_val - self._last_expert_progress_value)

            relative_progress_delta = progress_delta - expert_progress_delta
            progress_deficit = max(0.0, expert_progress_delta - progress_delta)
            progress_match_factor = 1.0

            if expert_progress_time_val is not None:
                lag_distance = max(0.0, float(expert_progress_time_val - progress_val))
                if progress_deficit > lag_tolerance and lag_distance > lag_warn_distance:
                    lag_warn = 1
                    progress_reward = -lag_warn_penalty
                if lag_distance >= lag_out_of_road_dist:
                    actor_manager.state = AgentState.OUT_OF_ROAD
                    state = actor_manager.state

            self._last_progress_value = progress_val
            self._last_progress_idx = best_idx
            if expert_progress_time_val is not None:
                self._last_expert_progress_value = expert_progress_time_val
                self._last_expert_progress_idx = expert_progress_time_idx
        else:
            self._last_progress_value = None
            self._last_progress_idx = None
            self._last_expert_progress_value = None
            self._last_expert_progress_idx = None
            self._last_signed_lateral_error = None
            self._last_signed_heading_error = None

        # ---- Aggregate ----
        out_of_road_reward = -20.0 if state == AgentState.OUT_OF_ROAD else 0.0
        reward_components = {
            "living_cost": 0.0,
            "progress": progress_reward,
            "reverse": 0.0,
            "ttc": 0.0,
            "position": position_reward,
            "heading": heading_reward,
            "collision": collision_reward + out_of_road_reward,
            "success_bonus": success_bonus,
        }
        total_reward = sum(reward_components.values())
        reward_components["total"] = total_reward

        # ---- Logging/compat keys ----
        diag_info["progress_delta"] = progress_delta
        diag_info["expert_progress_delta"] = expert_progress_delta
        diag_info["relative_progress_delta"] = relative_progress_delta
        diag_info["progress_match_factor"] = progress_match_factor
        diag_info["progress_deficit"] = progress_deficit
        diag_info["lag_distance"] = lag_distance
        diag_info["lag_warn_distance"] = lag_warn_distance
        diag_info["lag_fail_distance"] = lag_out_of_road_dist
        diag_info["lag_warn"] = lag_warn
        diag_info["expert_progress_time_val"] = expert_progress_time_val if expert_progress_time_val is not None else 0.0
        diag_info["ttc"] = 0.0
        diag_info["stalled"] = 0

        if progress_weight > 1e-6 and progress_delta > 0:
            progress_ratio = progress_reward / (progress_weight * progress_delta + 1e-8)
        else:
            progress_ratio = 0.0
        step_info["progress"] = progress_reward / progress_weight if progress_weight > 1e-6 else 0.0
        step_info["expert_progress_delta"] = expert_progress_delta
        step_info["relative_progress_delta"] = relative_progress_delta
        step_info["progress_match_factor"] = progress_match_factor
        step_info["progress_ratio"] = float(progress_ratio)
        step_info["ego_speed"] = ego_speed
        step_info["collision_count"] = int(self._episode_counters.get("collision", False))
        step_info["ttc"] = 0.0
        step_info["stalled"] = 0
        diag_info["progress_ratio"] = float(progress_ratio)

        self._episode_reward_sums["progress"] += float(progress_reward)
        self._episode_reward_sums["ttc"] += 0.0
        self._episode_reward_sums["position"] += float(position_reward)
        self._episode_reward_sums["heading"] += float(heading_reward)
        self._episode_reward_sums["living_cost"] += 0.0
        self._episode_reward_sums["success_bonus"] += float(success_bonus)
        if collision:
            self._episode_counters["collision"] = True

        self._stall_counter = 0
        self._stall_truncate_flag = False

        step_info["reward_components"] = reward_components
        step_info["diag"] = diag_info
        step_info["step_reward"] = total_reward
        return total_reward, step_info

    def _compute_min_ttc(self, vehicle):
        surrounding_obs = self._get_surrounding_observer()
        if vehicle is None or surrounding_obs is None:
            return None
        surroundings = surrounding_obs.observe()
        if not surroundings:
            return None
        # ego velocity in ego frame
        vel_world = np.array(getattr(vehicle, "velocity", [0.0, 0.0]), dtype=np.float32)
        if vel_world.shape[0] < 2:
            vel_world = np.array([float(vel_world[0]), 0.0], dtype=np.float32)
        vel_world3 = np.array([float(vel_world[0]), float(vel_world[1]), 0.0], dtype=np.float32)
        transform = getattr(vehicle, "transform", None)
        if transform is None:
            return None
        R_world_vehicle = transform[:3, :3]
        R_vehicle_world = np.linalg.inv(R_world_vehicle)
        ego_vel_ego = (R_vehicle_world @ vel_world3)[:2]
        min_ttc = None
        for obj in surroundings:
            rel_pos = np.asarray(obj.get("position", [0.0, 0.0]), dtype=np.float32)
            rel_vel = np.asarray(obj.get("velocity", [0.0, 0.0]), dtype=np.float32) - ego_vel_ego
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
            observers = getattr(actor_observer, "_observers", None)
            nav = observers.get("navigation") if observers else None
            if isinstance(nav, NavigationObservation):
                return nav
        return None
    def _project_progress_along_path(self, position, path_xy, path_cumlen, last_idx):
        if path_xy is None or len(path_xy) < 2:
            return None, None, None
        pts = np.asarray(path_xy, dtype=np.float32)
        if path_cumlen is None or len(path_cumlen) != len(pts):
            seg_lengths = np.linalg.norm(pts[1:] - pts[:-1], axis=1)
            path_cumlen = np.concatenate(([0.0], np.cumsum(seg_lengths)))
        N = len(pts) - 1
        if N <= 0:
            return None, None, None
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

    def _get_surrounding_observer(self):
        actor_observer = getattr(self.agent_managers['actor'], "observer", None)
        if isinstance(actor_observer, SurroundingObservation):
            return actor_observer
        if isinstance(actor_observer, AssemblyObservation):
            observers = getattr(actor_observer, "_observers", None)
            surrounding = observers.get("surrounding") if observers else None
            if isinstance(surrounding, SurroundingObservation):
                return surrounding
        return None

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
    @classmethod
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
