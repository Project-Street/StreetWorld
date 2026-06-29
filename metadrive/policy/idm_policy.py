import math
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np

from metadrive.component.vehicle.PID_controller import PIDController
from metadrive.policy.base_policy import BasePolicy
from metadrive.type import MetaDriveType


class IDMRouteInitializationError(RuntimeError):
    pass


class IDMLaneRuntimeError(RuntimeError):
    pass


@dataclass
class EgoState:
    position: np.ndarray
    heading_theta: float
    heading: np.ndarray
    velocity: np.ndarray
    speed: float
    speed_km_h: float


@dataclass
class ObjectState:
    name: str
    position: np.ndarray
    velocity: np.ndarray
    heading_theta: float
    size: Sequence[float]
    obj_type: str
    lane: Optional[object] = None
    lane_s: Optional[float] = None
    lane_lat: Optional[float] = None
    lane_relation_cache: Optional[Dict[str, Tuple[str, object, float]]] = None

    @property
    def speed(self) -> float:
        return float(np.linalg.norm(self.velocity[:2]))

    @property
    def speed_km_h(self) -> float:
        return self.speed * 3.6

    @property
    def velocity_km_h(self) -> np.ndarray:
        return self.velocity[:2] * 3.6


@dataclass
class FrontBackObjects:
    front_objs: List[Optional[ObjectState]]
    back_objs: List[Optional[ObjectState]]
    front_dist: List[Optional[float]]
    back_dist: List[Optional[float]]

    def left_lane_exist(self):
        return self.front_dist[0] is not None

    def right_lane_exist(self):
        return self.front_dist[2] is not None

    def has_front_object(self):
        return self.front_objs[1] is not None

    def has_back_object(self):
        return self.back_objs[1] is not None

    def has_left_front_object(self):
        return self.front_objs[0] is not None

    def has_left_back_object(self):
        return self.back_objs[0] is not None

    def has_right_front_object(self):
        return self.front_objs[2] is not None

    def has_right_back_object(self):
        return self.back_objs[2] is not None

    def front_object(self):
        return self.front_objs[1]

    def left_front_object(self):
        return self.front_objs[0]

    def right_front_object(self):
        return self.front_objs[2]

    def back_object(self):
        return self.back_objs[1]

    def left_back_object(self):
        return self.back_objs[0]

    def right_back_object(self):
        return self.back_objs[2]

    def left_front_min_distance(self):
        assert self.left_lane_exist(), "left lane doesn't exist"
        return self.front_dist[0]

    def right_front_min_distance(self):
        assert self.right_lane_exist(), "right lane doesn't exist"
        return self.front_dist[2]

    def front_min_distance(self):
        return self.front_dist[1]

    def left_back_min_distance(self):
        assert self.left_lane_exist(), "left lane doesn't exist"
        return self.back_dist[0]

    def right_back_min_distance(self):
        assert self.right_lane_exist(), "right lane doesn't exist"
        return self.back_dist[2]

    def back_min_distance(self):
        return self.back_dist[1]


class IDMPolicy(BasePolicy):
    """IDM using trajdata VectorMap lanes and state/surrounding observations."""

    TAU_ACC = 0.6
    TAU_HEADING = 0.3
    TAU_LATERAL = 0.8
    MAX_STEERING_ANGLE = np.pi / 3

    DISTANCE_WANTED = 3.0
    TIME_WANTED = 1.5
    DELTA = 10.0

    LANE_CHANGE_FREQ = 50
    LANE_CHANGE_SPEED_INCREASE = 10.0
    SAFE_LANE_CHANGE_DISTANCE = 15.0
    MAX_LONG_DIST = 30.0
    MAX_SPEED = 100.0

    NORMAL_SPEED = 30.0
    CREEP_SPEED = 5.0

    ACC_FACTOR = 2.0
    DEACC_FACTOR = 3.0

    DEFAULT_LANE_WIDTH = 3.5
    DEST_REGION_RADIUS = 2.0

    def __init__(self, step_manager, config=None):
        super().__init__(step_manager, config or {})
        self.disable_idm_deceleration = bool(self.config.get("disable_idm_deceleration", False))
        self.enable_lane_change = bool(self.config.get("enable_lane_change", True))
        self.target_speed = float(self.config.get("normal_speed", self.NORMAL_SPEED))
        self.normal_speed = float(self.config.get("normal_speed", self.NORMAL_SPEED))
        self.creep_speed = float(self.config.get("creep_speed", self.CREEP_SPEED))
        self.lane_width = float(self.config.get("lane_width", self.DEFAULT_LANE_WIDTH))
        self.max_long_dist = float(self.config.get("max_long_dist", self.MAX_LONG_DIST))
        self.safe_lane_change_distance = float(
            self.config.get("safe_lane_change_distance", self.SAFE_LANE_CHANGE_DISTANCE)
        )
        self.lane_change_speed_increase = float(
            self.config.get("lane_change_speed_increase", self.LANE_CHANGE_SPEED_INCREASE)
        )

        self.heading_pid = PIDController(1.7, 0.01, 3.5)
        self.lateral_pid = PIDController(0.3, 0.002, 0.05)
        self.overtake_timer = 0
        self.stop_start_overtake_blocked = False
        self.routing_target_lane = None
        self.available_routing_index_range = None
        self.route_lane_ids: List[str] = []
        self.route_road_ids: List[str] = []
        self.route_road_cursor = 0
        self.trajdata_map = None
        self.last_action = [0.0, 0.0]

    def reset(self, controller, seed, state, init_state, trajdata_map=None, **kwargs):
        super().reset(controller=controller, seed=seed, state=state, init_state=init_state, **kwargs)
        if controller.metadrive_type != MetaDriveType.VEHICLE:
            raise ValueError("IDMPolicy can only control vehicle agents.")
        if trajdata_map is None:
            raise ValueError("IDMPolicy requires trajdata_map from ScenarioMapManager.")

        self.trajdata_map = trajdata_map
        spawn_position = np.asarray(init_state["spawn_position"], dtype=np.float32)
        spawn_yaw = float(init_state["spawn_yaw"])
        self.heading_pid.reset()
        self.lateral_pid.reset()
        self.target_speed = self.normal_speed
        self.routing_target_lane = None
        self.available_routing_index_range = None
        self.route_road_cursor = 0
        self.stop_start_overtake_blocked = False
        self.route_lane_ids = []
        self.route_road_ids = []
        if not self.static:
            start_lane = self._lane_for_pose(spawn_position, spawn_yaw, route_initialization=True)
            target_lane = self._target_lane_from_trajectory(state)
            self.route_road_ids = self._build_route_road_ids(
                self._road_id_for_lane(start_lane),
                self._road_id_for_lane(target_lane),
            )
        self.overtake_timer = int(self.np_random.randint(0, self.LANE_CHANGE_FREQ))
        self.last_action = [0.0, 0.0]

    def act(self, observation, *args, **kwargs):
        if observation is None:
            raise ValueError("IDMPolicy requires observation with states and surrounding.")
        if "states" not in observation or "surrounding" not in observation:
            raise KeyError("IDMPolicy act() only accepts observation['states'] and observation['surrounding'].")

        ego = self._parse_ego_state(observation["states"])
        surrounding = self._parse_surrounding(observation["surrounding"])
        try:
            current_lane = self._current_lane(ego)
        except IDMLaneRuntimeError:
            action = [0.0, 0.0]
            self.last_action = action
            self.action_info["action"] = action
            self.action_info["acceleration"] = 0.0
            self.action_info["target_lane"] = None
            self.action_info["route_roads"] = self.route_road_ids
            self.action_info["route_road_cursor"] = self.route_road_cursor
            self.action_info["current_road"] = None
            self.action_info["next_road"] = self._next_route_road_id()
            self.action_info["target_speed"] = self.target_speed
            self.action_info["idm_out_of_road"] = True
            return action
        self._advance_route_cursor(current_lane)
        current_ref_lanes = self._current_ref_lanes(current_lane)
        next_ref_lanes = self._next_ref_lanes(current_ref_lanes)
        next_route_road_id = self._next_route_road_id()

        success = self._move_to_next_road(current_lane, current_ref_lanes)
        if success and self.enable_lane_change:
            front_obj, front_dist, steering_target_lane = self._lane_change_policy(
                ego, surrounding, current_ref_lanes, next_ref_lanes, next_route_road_id
            )
        else:
            surrounding_objects = self._find_front_back_objects(
                ego, surrounding, self.routing_target_lane
            )
            front_obj = surrounding_objects.front_object()
            front_dist = surrounding_objects.front_min_distance()
            steering_target_lane = self.routing_target_lane

        steering = self._steering_control(ego, steering_target_lane)
        acceleration = self._acceleration(ego, front_obj, front_dist)
        throttle_brake = self._throttle_brake_control(acceleration)
        action = [steering, throttle_brake]
        self.last_action = action
        self.action_info["action"] = action
        self.action_info["acceleration"] = acceleration
        self.action_info["target_lane"] = steering_target_lane.id
        self.action_info["route_roads"] = self.route_road_ids
        self.action_info["route_road_cursor"] = self.route_road_cursor
        self.action_info["current_road"] = self._road_id_for_lane(current_lane)
        self.action_info["next_road"] = next_route_road_id
        self.action_info["target_speed"] = self.target_speed
        self.action_info["idm_out_of_road"] = False
        return action

    def _parse_ego_state(self, state_obs) -> EgoState:
        pos = np.asarray(state_obs["ego_pos"], dtype=np.float32)
        velocity = np.asarray(state_obs["linear_velocity"], dtype=np.float32)
        heading_theta = float(state_obs["heading_theta"])
        heading = np.asarray([math.cos(heading_theta), math.sin(heading_theta)], dtype=np.float32)
        speed = float(state_obs["ego_velo"])
        return EgoState(pos, heading_theta, heading, velocity, speed, speed * 3.6)

    def _parse_surrounding(self, surrounding_obs) -> List[ObjectState]:
        ret = []
        for name, obj in surrounding_obs.items():
            obj_state = ObjectState(
                name=name,
                position=np.asarray(obj["position"], dtype=np.float32),
                velocity=np.asarray(obj["velocity"], dtype=np.float32),
                heading_theta=float(obj["heading_theta"]),
                size=obj["size"],
                obj_type=obj["type"],
            )
            obj_state.lane_relation_cache = {}
            ret.append(obj_state)
        return ret

    def _lane_for_pose(self, xyz, heading_theta=None, route_initialization=False):
        heading = 0.0 if heading_theta is None else float(heading_theta)
        xyzh = np.asarray([float(xyz[0]), float(xyz[1]), float(xyz[2]), heading], dtype=np.float32)
        lanes = self.trajdata_map.get_current_lane(xyzh, max_heading_error=np.inf)
        if len(lanes) == 0:
            error_cls = IDMRouteInitializationError if route_initialization else IDMLaneRuntimeError
            raise error_cls(
                f"IDMPolicy cannot find current lane for {self.controller.name}: "
                f"pos={xyzh[:3].tolist()} heading={heading:.6f}."
            )
        return lanes[0]

    def _current_lane(self, ego: EgoState):
        return self._lane_for_pose(ego.position, ego.heading_theta)

    def _target_lane_from_trajectory(self, trajectory):
        if len(trajectory) == 0:
            raise IDMRouteInitializationError(f"IDMPolicy cannot build route from empty trajectory for {self.controller.name}.")
        state = trajectory[max(trajectory.keys())]
        return self._lane_for_pose(state["position"], float(state["heading_theta"]), route_initialization=True)

    def _build_route_road_ids(self, start_road_id: str, target_road_id: str) -> List[str]:
        route = self._road_bfs(start_road_id, target_road_id)
        if route is None:
            raise IDMRouteInitializationError(
                f"IDMPolicy road route is disconnected: {start_road_id} -> {target_road_id}."
            )
        return route

    def _road_bfs(self, start_road_id: str, target_road_id: str) -> Optional[List[str]]:
        if start_road_id == target_road_id:
            return [start_road_id]

        queue = deque([(start_road_id, [start_road_id])])
        visited: Set[str] = {start_road_id}
        while queue:
            road_id, path = queue.popleft()
            for next_road_id in sorted(self._successor_road_ids(road_id)):
                if next_road_id in visited:
                    continue
                next_path = path + [next_road_id]
                if next_road_id == target_road_id:
                    return next_path
                visited.add(next_road_id)
                queue.append((next_road_id, next_path))
        return None

    def _successor_road_ids(self, road_id: str) -> Set[str]:
        return set(self._road_for_road_id(road_id).next_roads)

    def _advance_route_cursor(self, current_lane):
        current_road_id = self._road_id_for_lane(current_lane)
        for idx in range(self.route_road_cursor, len(self.route_road_ids)):
            if self.route_road_ids[idx] == current_road_id:
                self.route_road_cursor = idx
                return

    def _move_to_next_road(self, current_lane, current_ref_lanes):
        if self.routing_target_lane is None:
            self.routing_target_lane = current_lane
            return self._lane_in_group(self.routing_target_lane, current_ref_lanes)

        if not self._lane_in_group(self.routing_target_lane, current_ref_lanes):
            for lane in current_ref_lanes:
                if self._has_connection(self.routing_target_lane, lane):
                    self.routing_target_lane = lane
                    return True
            return False

        return True

    def _lane_change_policy(
        self,
        ego: EgoState,
        surrounding: List[ObjectState],
        current_ref_lanes,
        next_ref_lanes,
        next_route_road_id,
    ):
        surrounding_objects = self._find_front_back_objects(
            ego, surrounding, self.routing_target_lane, current_ref_lanes
        )
        self.available_routing_index_range = self._route_available_lane_indices(current_ref_lanes, next_route_road_id)
        routing_idx = self._lane_group_index(self.routing_target_lane, current_ref_lanes)

        def lane_change(front_obj, front_dist, target_lane):
            self.routing_target_lane = target_lane
            return front_obj, front_dist, target_lane

        def lane_follow():
            self.target_speed = self.normal_speed
            self.overtake_timer += 1
            return surrounding_objects.front_object(), surrounding_objects.front_min_distance(), self.routing_target_lane

        routing_target_idx = self._routing_lane_change_target_index(
            routing_idx, self.available_routing_index_range
        )
        if routing_target_idx is not None:
            if routing_target_idx < routing_idx:
                target_lane = current_ref_lanes[routing_idx - 1]
                if (
                    surrounding_objects.left_back_min_distance() < self.safe_lane_change_distance
                    or surrounding_objects.left_front_min_distance() < 5.0
                ):
                    self.target_speed = self.creep_speed
                    return surrounding_objects.front_object(), surrounding_objects.front_min_distance(), self.routing_target_lane
                self.target_speed = self.normal_speed
                return lane_change(surrounding_objects.left_front_object(), surrounding_objects.left_front_min_distance(), target_lane)

            target_lane = current_ref_lanes[routing_idx + 1]
            if (
                surrounding_objects.right_back_min_distance() < self.safe_lane_change_distance
                or surrounding_objects.right_front_min_distance() < 5.0
            ):
                self.target_speed = self.creep_speed
                return surrounding_objects.front_object(), surrounding_objects.front_min_distance(), self.routing_target_lane
            self.target_speed = self.normal_speed
            return lane_change(surrounding_objects.right_front_object(), surrounding_objects.right_front_min_distance(), target_lane)

        if (
            not self._stop_start_blocks_overtake(ego)
            and abs(ego.speed_km_h - self.normal_speed) > 3.0
            and surrounding_objects.has_front_object()
            and abs(surrounding_objects.front_object().speed_km_h - self.normal_speed) > 3.0
            and self.overtake_timer > self.LANE_CHANGE_FREQ
        ):
            front_speed = surrounding_objects.front_object().speed_km_h
            left_front_speed = None
            right_front_speed = None
            if (
                surrounding_objects.left_lane_exist()
                and surrounding_objects.left_front_min_distance() > self.safe_lane_change_distance
                and surrounding_objects.left_back_min_distance() > self.safe_lane_change_distance
            ):
                left_front_speed = (
                    surrounding_objects.left_front_object().speed_km_h
                    if surrounding_objects.has_left_front_object()
                    else self.MAX_SPEED
                )
            if (
                surrounding_objects.right_lane_exist()
                and surrounding_objects.right_front_min_distance() > self.safe_lane_change_distance
                and surrounding_objects.right_back_min_distance() > self.safe_lane_change_distance
            ):
                right_front_speed = (
                    surrounding_objects.right_front_object().speed_km_h
                    if surrounding_objects.has_right_front_object()
                    else self.MAX_SPEED
                )

            if left_front_speed is not None and left_front_speed - front_speed > self.lane_change_speed_increase:
                expect_lane_idx = routing_idx - 1
                if expect_lane_idx in self.available_routing_index_range:
                    return lane_change(
                        surrounding_objects.left_front_object(),
                        surrounding_objects.left_front_min_distance(),
                        current_ref_lanes[expect_lane_idx],
                    )
            if right_front_speed is not None and right_front_speed - front_speed > self.lane_change_speed_increase:
                expect_lane_idx = routing_idx + 1
                if expect_lane_idx in self.available_routing_index_range:
                    return lane_change(
                        surrounding_objects.right_front_object(),
                        surrounding_objects.right_front_min_distance(),
                        current_ref_lanes[expect_lane_idx],
                    )

        return lane_follow()

    def _stop_start_blocks_overtake(self, ego: EgoState) -> bool:
        if ego.speed_km_h <= self.creep_speed:
            self.stop_start_overtake_blocked = True
        elif ego.speed_km_h >= self.normal_speed - 3.0:
            self.stop_start_overtake_blocked = False
        return self.stop_start_overtake_blocked

    def _current_ref_lanes(self, current_lane):
        if len(self.route_road_ids) == 0:
            raise RuntimeError(f"IDMPolicy has no navigation route for {self.controller.name}.")

        current_route_road_id = self.route_road_ids[self.route_road_cursor]
        if self._road_id_for_lane(current_lane) == current_route_road_id:
            return self._lane_group(current_lane)
        return self._ref_lanes_for_route_road(current_route_road_id)

    def _next_ref_lanes(self, current_ref_lanes):
        next_road_id = self._next_route_road_id()
        if next_road_id is None:
            return None
        return self._ref_lanes_for_route_road(next_road_id, current_ref_lanes)

    def _next_route_road_id(self) -> Optional[str]:
        next_route_index = self.route_road_cursor + 1
        if next_route_index >= len(self.route_road_ids):
            return None
        return self.route_road_ids[next_route_index]

    def _ref_lanes_for_route_road(self, road_id: str, previous_ref_lanes=None):
        candidate_lanes = self._lanes_for_road(road_id)
        if len(candidate_lanes) == 0:
            raise RuntimeError(f"IDMPolicy route road {road_id} has no lanes.")

        if previous_ref_lanes is None:
            return self._lane_group(candidate_lanes[0])
        connected = [
            lane for lane in candidate_lanes
            if any(self._has_connection(prev_lane, lane) for prev_lane in previous_ref_lanes)
        ]
        if len(connected) == 0:
            raise RuntimeError(f"IDMPolicy route road {road_id} is not connected from current reference lanes.")
        return self._lane_group(self._nearest_lane_to_group(connected, previous_ref_lanes))

    def _route_available_lane_indices(self, current_ref_lanes, next_road_id: Optional[str]) -> List[int]:
        if next_road_id is None:
            return [idx for idx in range(len(current_ref_lanes))]
        indices = [
            idx for idx, lane in enumerate(current_ref_lanes)
            if self._lane_can_reach_road(lane, next_road_id)
        ]
        if len(indices) == 0:
            current_road_id = self._road_id_for_lane(current_ref_lanes[0])
            raise RuntimeError(
                f"IDMPolicy current road {current_road_id} has no lane connected to next road {next_road_id}."
            )
        return indices

    @staticmethod
    def _routing_lane_change_target_index(routing_idx: int, available_indices: Sequence[int]) -> Optional[int]:
        if routing_idx in available_indices:
            return None
        if routing_idx > available_indices[-1]:
            return routing_idx - 1
        if routing_idx < available_indices[0]:
            return routing_idx + 1
        return min(available_indices, key=lambda idx: abs(idx - routing_idx))

    def _lane_can_reach_road(self, lane, road_id: str) -> bool:
        return any(self._road_id_for_lane_id(next_lane_id) == road_id for next_lane_id in lane.next_lanes)

    def _lane_group(self, lane):
        road = self._road_for_road_id(self._road_id_for_lane(lane))
        lanes = [self._lane_by_id(lane_id) for lane_id in road.lane_ids]
        return sorted(
            lanes,
            key=lambda candidate: self._project_to_lane(lane, self._lane_midpoint(candidate))[1],
            reverse=True,
        )

    @staticmethod
    def _lane_in_group(lane, lanes) -> bool:
        return any(candidate.id == lane.id for candidate in lanes)

    @staticmethod
    def _lane_group_index(lane, lanes) -> int:
        for idx, candidate in enumerate(lanes):
            if candidate.id == lane.id:
                return idx
        raise ValueError(f"Lane {lane.id} is not in current_ref_lanes.")

    @staticmethod
    def _has_connection(prev_lane, next_lane) -> bool:
        return next_lane.id in prev_lane.next_lanes or prev_lane.id in next_lane.prev_lanes

    def _center_distance(self, lane_a, lane_b):
        a = self._lane_points(lane_a)
        b = self._lane_points(lane_b)
        return float(np.linalg.norm(a[len(a) // 2] - b[len(b) // 2]))

    def _nearest_lane_to_group(self, candidate_lanes, ref_lanes):
        return min(
            candidate_lanes,
            key=lambda lane: min(self._center_distance(lane, ref_lane) for ref_lane in ref_lanes),
        )

    def _lane_midpoint(self, lane) -> np.ndarray:
        points = self._lane_points(lane)
        return points[len(points) // 2]

    def _road_for_road_id(self, road_id: str):
        return self.trajdata_map.get_road(road_id)

    def _road_id_for_lane(self, lane) -> Optional[str]:
        return self._road_id_for_lane_id(lane.id)

    def _road_id_for_lane_id(self, lane_id: str) -> Optional[str]:
        road = self.trajdata_map.road_for_lane(lane_id)
        if road is None:
            raise KeyError(f"Lane {lane_id} has no containing road in trajdata map.")
        return road.id

    def _lane_by_id(self, lane_id: str):
        return self.trajdata_map.get_road_lane(lane_id)

    def _lanes_for_road(self, road_id: str):
        road = self._road_for_road_id(road_id)
        return [self._lane_by_id(lane_id) for lane_id in sorted(road.lane_ids)]

    def _find_front_back_objects(self, ego: EgoState, objects: Sequence[ObjectState], target_lane, ref_lanes=None):
        if ref_lanes is not None:
            idx = self._lane_group_index(target_lane, ref_lanes)
            left_lane = ref_lanes[idx - 1] if idx > 0 else None
            right_lane = ref_lanes[idx + 1] if idx + 1 < len(ref_lanes) else None
        else:
            left_lane = None
            right_lane = None
        lanes = [left_lane, target_lane, right_lane]
        front_objs: List[Optional[ObjectState]] = [None, None, None]
        back_objs: List[Optional[ObjectState]] = [None, None, None]
        front_dist: List[Optional[float]] = [self.max_long_dist if lane is not None else None for lane in lanes]
        back_dist: List[Optional[float]] = [self.max_long_dist if lane is not None else None for lane in lanes]
        ego_s = [self._project_to_lane(lane, ego.position)[0] if lane is not None else None for lane in lanes]
        found_front_in_current_lane = [False, False, False]
        found_back_in_current_lane = [False, False, False]

        for i, lane in enumerate(lanes):
            if lane is None:
                continue
            assert front_dist[i] is not None and back_dist[i] is not None
            for obj in objects:
                lane_relation = self._object_lane_relation(lane, obj)
                if lane_relation is None:
                    continue
                if lane_relation == "next" and found_front_in_current_lane[i]:
                    continue
                if lane_relation == "prev" and found_back_in_current_lane[i]:
                    continue
                center_longitudinal = self._relative_longitudinal(lane, ego_s[i], obj, lane_relation)
                if center_longitudinal is None:
                    continue
                longitudinal_clearance = self._longitudinal_clearance(center_longitudinal, obj)
                if center_longitudinal > 0.0 and longitudinal_clearance < front_dist[i]:
                    front_dist[i] = longitudinal_clearance
                    front_objs[i] = obj
                    if lane_relation == "same":
                        found_front_in_current_lane[i] = True
                elif center_longitudinal < 0.0 and longitudinal_clearance < back_dist[i]:
                    back_dist[i] = longitudinal_clearance
                    back_objs[i] = obj
                    if lane_relation == "same":
                        found_back_in_current_lane[i] = True

        return FrontBackObjects(front_objs, back_objs, front_dist, back_dist)

    def _object_lane_relation(self, lane, obj: ObjectState):
        if obj.lane_relation_cache is None:
            obj.lane_relation_cache = {}
        if lane.id not in obj.lane_relation_cache:
            relation = self._object_lane_relation_by_box(lane, obj)
            if relation is not None:
                obj.lane_relation_cache[lane.id] = relation
        relation = obj.lane_relation_cache.get(lane.id)
        if relation is not None:
            relation_name, relation_lane, lane_s = relation
            obj.lane = relation_lane
            obj.lane_s = lane_s
            obj.lane_lat = 0.0
            return relation_name
        return None

    def _object_lane_relation_by_box(self, lane, obj: ObjectState):
        for candidate_lane, relation in (
            (lane, "same"),
            *[(self._lane_by_id(lane_id), "next") for lane_id in lane.next_lanes],
            *[(self._lane_by_id(lane_id), "prev") for lane_id in lane.prev_lanes],
        ):
            lane_s = self._object_s_on_lane_by_box(candidate_lane, obj)
            if lane_s is not None:
                return relation, candidate_lane, lane_s
        return None

    def _object_s_on_lane_by_box(self, lane, obj: ObjectState) -> Optional[float]:
        lane_length = self._lane_length(lane)
        inside_s = []
        for corner in self._object_bottom_corners(obj):
            s, lat, _ = self._project_to_lane(lane, corner)
            if 0.0 <= s <= lane_length and abs(lat) <= self.lane_width * 0.5:
                inside_s.append(s)
        if not inside_s:
            return None
        center_s, _, _ = self._project_to_lane(lane, obj.position)
        return float(np.clip(center_s, min(inside_s), max(inside_s)))

    def _object_bottom_corners(self, obj: ObjectState) -> np.ndarray:
        size = np.asarray(obj.size, dtype=np.float32).reshape(-1)
        if size.shape[0] < 2:
            raise ValueError(f"Object {obj.name} size must contain length and width, got {obj.size}.")
        half_length = float(size[0]) * 0.5
        half_width = float(size[1]) * 0.5
        forward = np.asarray([math.cos(obj.heading_theta), math.sin(obj.heading_theta)], dtype=np.float32)
        left = np.asarray([-forward[1], forward[0]], dtype=np.float32)
        center = np.asarray(obj.position, dtype=np.float32)[:2]
        return np.asarray(
            [
                center + forward * half_length + left * half_width,
                center + forward * half_length - left * half_width,
                center - forward * half_length - left * half_width,
                center - forward * half_length + left * half_width,
            ],
            dtype=np.float32,
        )

    def _relative_longitudinal(self, lane, ego_s: float, obj: ObjectState, relation: str):
        if relation == "same":
            return obj.lane_s - ego_s
        if relation == "next":
            return self._lane_length(lane) - ego_s + obj.lane_s
        if relation == "prev":
            return -(ego_s + self._lane_length(obj.lane) - obj.lane_s)
        return None

    def _longitudinal_clearance(self, center_longitudinal: float, obj: ObjectState) -> float:
        obj_size = np.asarray(obj.size, dtype=np.float32).reshape(-1)
        half_length_sum = 0.5 * (float(self.controller.LENGTH) + float(obj_size[0]))
        return max(abs(center_longitudinal) - half_length_sum, 0.0)

    def _steering_control(self, ego: EgoState, target_lane) -> float:
        long, lat, _ = self._project_to_lane(target_lane, ego.position)
        lane_heading = self._heading_at_s(target_lane, long + 1.0)
        steering_angle = self.heading_pid.get_result(-self._wrap_to_pi(lane_heading - ego.heading_theta))
        steering_angle += self.lateral_pid.get_result(lat)
        return self._normalize_steering(steering_angle)

    def _acceleration(self, ego: EgoState, front_obj: Optional[ObjectState], dist_to_front: Optional[float]) -> float:
        target_speed = max(self.target_speed / 3.6, 1e-3)
        acceleration = self.ACC_FACTOR * (1.0 - np.power(max(ego.speed, 0.0) / target_speed, self.DELTA))
        if front_obj is not None and not self.disable_idm_deceleration:
            if dist_to_front is None:
                raise ValueError("front object exists but dist_to_front is None")
            speed_diff = self._desired_gap(ego, front_obj) / self._not_zero(dist_to_front)
            acceleration -= self.ACC_FACTOR * (speed_diff ** 2)
        return float(acceleration)

    def _desired_gap(self, ego: EgoState, front_obj: ObjectState) -> float:
        ab = self.ACC_FACTOR * self.DEACC_FACTOR
        dv = float(np.dot(ego.velocity[:2] - front_obj.velocity[:2], ego.heading))
        return self.DISTANCE_WANTED + ego.speed * self.TIME_WANTED + ego.speed * dv / (2.0 * math.sqrt(ab))

    def _normalize_steering(self, steering_angle: float) -> float:
        max_steering = math.radians(float(self.controller.max_steering))
        return float(np.clip(steering_angle / max_steering, -1.0, 1.0))

    def _throttle_brake_control(self, acceleration: float) -> float:
        if acceleration >= 0.0:
            throttle_brake = acceleration / self._controller_max_acceleration()
        else:
            throttle_brake = acceleration / self._controller_max_deceleration()
        return float(np.clip(throttle_brake, -1.0, 1.0))

    def _controller_mass(self) -> float:
        return float(self.controller.MASS)

    def _controller_max_acceleration(self) -> float:
        max_acceleration = 4.0 * float(self.controller.max_engine_force) / self._controller_mass()
        if "max_acceleration" in self.controller.config:
            max_acceleration = min(max_acceleration, float(self.controller.config["max_acceleration"]))
        return max_acceleration

    def _controller_max_deceleration(self) -> float:
        return 4.0 * float(self.controller.max_brake_force) / (
            self._controller_mass() * float(self.controller.TIRE_RADIUS)
        )

    def _lane_points(self, lane) -> np.ndarray:
        return np.asarray(lane.center.xy, dtype=np.float32)

    def _lane_length(self, lane) -> float:
        points = self._lane_points(lane)
        if len(points) < 2:
            return 0.0
        return float(np.linalg.norm(points[1:] - points[:-1], axis=1).sum())

    def _project_to_lane(self, lane, xy) -> Tuple[float, float, int]:
        points = self._lane_points(lane)
        if len(points) < 2:
            raise ValueError(f"Lane {lane.id} has fewer than 2 centerline points.")
        p0 = points[:-1]
        p1 = points[1:]
        seg = p1 - p0
        seg_len = np.linalg.norm(seg, axis=1)
        valid = seg_len > 1e-6
        if not np.any(valid):
            raise ValueError(f"Lane {lane.id} has zero-length centerline.")
        p0 = p0[valid]
        seg = seg[valid]
        seg_len = seg_len[valid]
        rel = np.asarray(xy, dtype=np.float32)[None, :2] - p0
        t = np.clip(np.sum(rel * seg, axis=1) / (seg_len ** 2), 0.0, 1.0)
        proj = p0 + t[:, None] * seg
        dist = np.linalg.norm(np.asarray(xy, dtype=np.float32)[None, :2] - proj, axis=1)
        idx = int(np.argmin(dist))
        cum = np.concatenate([[0.0], np.cumsum(seg_len)])
        tangent = seg[idx] / seg_len[idx]
        lateral_vec = np.asarray(xy, dtype=np.float32)[:2] - proj[idx]
        lateral = float(tangent[0] * lateral_vec[1] - tangent[1] * lateral_vec[0])
        return float(cum[idx] + t[idx] * seg_len[idx]), lateral, idx

    def _heading_at_s(self, lane, s: float) -> float:
        points = self._lane_points(lane)
        seg = points[1:] - points[:-1]
        seg_len = np.linalg.norm(seg, axis=1)
        cum = np.concatenate([[0.0], np.cumsum(seg_len)])
        idx = int(np.searchsorted(cum, np.clip(s, 0.0, cum[-1]), side="right") - 1)
        idx = int(np.clip(idx, 0, len(seg) - 1))
        return float(math.atan2(seg[idx, 1], seg[idx, 0]))

    @staticmethod
    def _wrap_to_pi(angle: float) -> float:
        return (angle + math.pi) % (2 * math.pi) - math.pi

    @staticmethod
    def _not_zero(value: float, eps: float = 1e-5) -> float:
        if abs(value) > eps:
            return value
        return eps if value >= 0 else -eps
