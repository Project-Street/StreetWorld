"""
This environment can load all scenarios exported from other environments via env.export_scenarios()
"""

from typing import Union

import numpy as np
import math

from metadrive.manager.agent_manager import AgentState
from metadrive.engine.asset_loader import AssetLoader
from metadrive.envs.base_env import BaseEnv
from metadrive.manager.scenario_data_manager import ScenarioOnlineDataManager
from metadrive.manager.agent_manager import AgentManager
from metadrive.obs.assembly_obs import AssemblyObservation
from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.obs.surrounding_obs import SurroundingObservation
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
    position_deviation_threshold=1.5,
    position_penalty_gain=0.5,
    position_penalty_max=1.0,
    heading_deviation_threshold=0.05,
    heading_penalty_weight=0.3,
    progress_reward_weight=1.0,
    reverse_penalty_weight=0.5,
    progress_deviation_weight=1.0,
    ttc_safe_horizon=4.0,
    ttc_warn_horizon=2.0,
    ttc_mid_penalty_weight=0.5,
    ttc_high_penalty_weight=1.5,
    ttc_safe_bonus_weight=0.2,
    comfort_accel_weight=0.1,
    comfort_heading_weight=0.05,
    comfort_accel_threshold=1.5,
    comfort_heading_threshold=0.1,
    comfort_bonus_factor=0.5,

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
    collision_penalty_weight=3.0,
)



class ScenarioEnv(BaseEnv):
    @classmethod
    def default_config(cls):
        config = super(ScenarioEnv, cls).default_config()
        config.update(SCENARIO_ENV_CONFIG)
        return config

    def __init__(self, model, config=None):
        super(ScenarioEnv, self).__init__(model, config)
        self._last_speed = None
        self._last_accel = None
        self._last_steer = None
        self._last_progress_value = None
        self._last_progress_idx = None
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
            self.logger.info(msg("arrive_dest"), extra={"log_once": True})
        elif state_info == AgentState.OUT_OF_ROAD:
            done = True
            self.logger.info(msg("out_of_road"), extra={"log_once": True})
        elif state_info == AgentState.OUT_OF_STEP:
            done = True
            self.logger.info(msg("out_of_step of object"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_HUMAN:
            done = True
            self.logger.info(msg("crash human"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_VEHICLE:
            done = True
            self.logger.info(msg("crash vehicle"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_OBJECT:
            done = True
            self.logger.info(msg("crash object"), extra={"log_once": True})
        elif state_info == AgentState.CRASH_WORLD:
            done = True
            self.logger.info(msg("crash background"), extra={"log_once": True})
        elif is_max_step:
            state_info = AgentState.OUT_OF_STEP
            done = True
            self.logger.info(msg("max step"), extra={"log_once": True})

        # # log data to curriculum manager
        # self.engine.curriculum_manager.log_episode(
        #     done_info[TerminationState.SUCCESS], vehicle.navigation.route_completion
        # )

        return done, {'reason': state_info}

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

    def reset(self, seed: Union[None, int] = None):
        self._last_speed = None
        self._last_accel = None
        self._last_steer = None
        self._last_progress_value = None
        self._last_progress_idx = None
        return super().reset(seed=seed)

    def reward_function(self):
        """Return reward composed of collision, positional, heading, and smoothness terms."""
        actor_manager = self.agent_managers['actor']
        state = actor_manager.state
        vehicle = getattr(actor_manager, "controller", None)
        nav = self._get_navigation_observer()

        step_info = dict()
        components = dict()
        collision_states = {
            AgentState.CRASH_VEHICLE,
            AgentState.CRASH_HUMAN,
            AgentState.CRASH_OBJECT,
            AgentState.CRASH_WORLD,
            AgentState.OUT_OF_ROAD,
        }
        step_info["collision"] = int(state in collision_states)
        collision_reward = 0.0
        if state in collision_states:
            collision_reward = -float(self.config.get("collision_penalty_weight", 3.0))
        components["collision_reward"] = collision_reward

        # ===== Expert reference =====
        expert_state = None
        ego_xy = None
        path_xy = None
        idx = None
        if nav is not None and vehicle is not None and hasattr(nav, "get_reference_state"):
            path_xy = getattr(nav, "_path_xy", None)
            if path_xy is not None and len(path_xy) > 0:
                ego_xy = nav._vehicle_xy(vehicle)
                heading_vec = nav._ego_heading_vec(vehicle)
                idx = nearest_front_index(path_xy, ego_xy, heading_vec)
                idx = int(np.clip(idx, 0, len(path_xy) - 1))
                expert_state = nav.get_reference_state(idx)

        step_info["expert_available"] = 1 if expert_state else 0

        # ===== Positional deviation =====
        position_reward = 0.0
        if expert_state and expert_state.get("position") is not None and ego_xy is not None:
            expert_pos = np.asarray(expert_state["position"], dtype=np.float32)
            deviation = float(np.linalg.norm(ego_xy - expert_pos))
            threshold = max(self.config.get("position_deviation_threshold", 1.5), 1e-3)
            if deviation > threshold:
                gain = float(self.config.get("position_penalty_gain", 0.5))
                max_penalty = float(self.config.get("position_penalty_max", 1.0))
                position_reward = -min(max_penalty, gain * (deviation - threshold))
            step_info["position_deviation"] = deviation
            step_info["position_threshold"] = threshold
        else:
            step_info["position_deviation"] = None
            step_info["position_threshold"] = None
        components["position_reward"] = position_reward

        # ===== Heading deviation =====
        heading_reward = 0.0
        ego_heading = float(getattr(vehicle, "heading_theta", 0.0)) if vehicle is not None else 0.0
        if expert_state and expert_state.get("heading_theta") is not None:
            expert_heading = float(expert_state["heading_theta"])
            heading_err = abs(ego_heading - expert_heading)
            heading_threshold = max(float(self.config.get("heading_deviation_threshold", 0.05)), 1e-6)
            if heading_err > heading_threshold:
                heading_reward = -float(self.config.get("heading_penalty_weight", 0.3)) * (heading_err - heading_threshold)
            step_info["heading_error"] = heading_err
            step_info["heading_threshold"] = heading_threshold
        else:
            step_info["heading_error"] = None
            step_info["heading_threshold"] = None
        components["heading_reward"] = heading_reward

        # ===== Safety: TTC shaping =====
        ttc_reward = 0.0
        ttc_safe = float(self.config.get("ttc_safe_horizon", 4.0))
        ttc_warn = float(self.config.get("ttc_warn_horizon", 2.0))
        w_mid = float(self.config.get("ttc_mid_penalty_weight", 0.5))
        w_high = float(self.config.get("ttc_high_penalty_weight", 1.5))
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
        components["ttc_reward"] = ttc_reward
        step_info["ttc"] = min_ttc

        # ===== Comfort & Smoothness =====
        ego_speed = float(vehicle.speed) if vehicle is not None and hasattr(vehicle, "speed") else 0.0
        dt = float(0.1)
        speed_delta = 0.0 if self._last_speed is None else ego_speed - self._last_speed
        accel = speed_delta / max(dt, 1e-3)
        current_heading = float(getattr(vehicle, "heading_theta", 0.0)) if vehicle is not None else 0.0
        heading_rate = 0.0
        if self._last_steer is not None:
            heading_rate = (current_heading - self._last_steer) / max(dt, 1e-3)
        w_accel = float(self.config.get("comfort_accel_weight", 0.1))
        w_heading = float(self.config.get("comfort_heading_weight", 0.05))
        accel_thresh = float(self.config.get("comfort_accel_threshold", 1.5))
        heading_thresh = float(self.config.get("comfort_heading_threshold", 0.1))
        comfort_bonus_factor = float(self.config.get("comfort_bonus_factor", 0.5))
        comfort_reward = 0.0
        accel_mag = abs(accel)
        heading_rate_mag = abs(heading_rate)
        if accel_mag > accel_thresh:
            comfort_reward -= w_accel * (accel_mag - accel_thresh)
        else:
            comfort_reward += w_accel * comfort_bonus_factor * (1.0 - accel_mag / max(accel_thresh, 1e-3))
        if heading_rate_mag > heading_thresh:
            comfort_reward -= w_heading * (heading_rate_mag - heading_thresh)
        else:
            comfort_reward += w_heading * comfort_bonus_factor * (1.0 - heading_rate_mag / max(heading_thresh, 1e-3))
        components["comfort_reward"] = comfort_reward
        step_info["accel"] = accel
        step_info["heading_rate"] = heading_rate
        self._last_speed = ego_speed
        self._last_steer = current_heading

        # ===== Progress along route =====
        progress_reward = 0.0
        progress_weight = float(self.config.get("progress_reward_weight", 1.0))
        reverse_weight = float(self.config.get("reverse_penalty_weight", 0.5))

        valid_path = path_xy is not None and len(path_xy) >= 2
        valid_ego = ego_xy is not None

        if valid_path and valid_ego:
            path_cumlen = getattr(nav, "_path_cumlen", None) if nav else None
            progress_val, best_idx = self._project_progress_along_path(
                ego_xy, path_xy, path_cumlen, self._last_progress_idx
            )

            if progress_val is not None:
                if self._last_progress_value is None:
                    self._last_progress_value = progress_val
                    self._last_progress_idx = best_idx

                delta = progress_val - self._last_progress_value

                if delta > 1e-3:
                    progress_reward = progress_weight * delta
                    deviation = 0.0
                    if expert_state and expert_state.get("position") is not None and ego_xy is not None:
                        expert_pos = np.asarray(expert_state["position"], dtype=np.float32)
                        deviation = float(np.linalg.norm(ego_xy - expert_pos))
                    alpha = float(self.config.get("progress_deviation_weight", 1.0))
                    if deviation > 1e-4 and alpha > 0:
                        progress_reward *= math.exp(-alpha * deviation)
                elif delta < -1e-3:
                    progress_reward = -reverse_weight * abs(delta)

                self._last_progress_value = progress_val
                self._last_progress_idx = best_idx
        
        else:
            self._last_progress_value = None
            self._last_progress_idx = None

        if state in collision_states and progress_reward > 0:
            progress_reward = 0.0

        components["progress_reward"] = progress_reward
        step_info["progress"] = progress_reward / progress_weight if progress_weight > 1e-6 else 0.0

        total_reward = sum(components.values())
        for name, value in components.items():
            step_info[name] = value

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
            k = 15
            lo = max(0, last_idx - k)
            hi = min(N, last_idx + k)
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
            return None, None
        return best_progress, best_idx

    def _get_surrounding_observer(self):
        actor_observer = getattr(self.agent_managers['actor'], "observer", None)
        if isinstance(actor_observer, SurroundingObservation):
            return actor_observer
        if isinstance(actor_observer, AssemblyObservation):
            surrounding = actor_observer._observers.get("surrounding") if hasattr(actor_observer, "_observers") else None
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
    def close(self):
        """Close the environment and clean up resources."""
        if hasattr(self, "engine") and self.engine is not None:
            self.engine.close()
            
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
