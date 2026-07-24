import math

import numpy as np
import gymnasium as gym
from trajdata import VectorMap
from metadrive.obs.observation_base import BaseObservation
from metadrive.base_class.randomizable import Randomizable
from metadrive.utils.navigation_utils import nearest_front_index

lane_follow_length = 200.0

class NavigationObservation(BaseObservation, Randomizable):
    trajdata_map: VectorMap

    def __init__(self, config):
        BaseObservation.__init__(self, config)
        Randomizable.__init__(self, None)
        self.navigating_type = config.get("navigating_type", "expert_following")  # lane_following, expert_following, snap_lane
        self.forecast_type = config.get("forecast_type", "distance")
        self.forecast_value = config.get("forecast_value", 20.0)
        self.carla_style_target = config.get("carla_style_target")
        self.path_interval = config.get("path_interval")
        self.lateral_offset = float(config.get("lateral_offset", 2.0))
        self.current_lane_max_dist = float(config.get("current_lane_max_dist", 2.25))

        self.controller = None
        self.trajdata_map = None
        self.init_state = None
        self.state = None

        self._path_xy = None
        self._path_cumlen = None
        self._expert_speed = None
        self._expert_angular_velocity = None
        self._expert_heading = None
        self._carla_route_xy = None
        self._carla_route_cursor = None

    def reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, **kwargs):
        if self.navigating_type == "lane_following":
            assert isinstance(trajdata_map, VectorMap), "trajdata_map must be provided for lane_following navigation type."

        if seed is not None:
            self.seed(int(seed))

        self.controller = controller
        self.trajdata_map = trajdata_map
        self.init_state = init_state
        self.state = state
        self._clear_expert_reference()
        self._carla_route_xy = None
        self._carla_route_cursor = None

        if self.navigating_type == "expert_following":
            self._build_expert_path()
        elif self.navigating_type == "lane_following":
            self._build_lane_follow_path()
        elif self.navigating_type == "snap_lane":
            self._build_snap_lane_path()
        else:
            raise ValueError(f"Unknown navigating_type: {self.navigating_type}")
        
        self.destination = self._path_xy[-1] if self._path_xy is not None else init_state["destination"]

    def observe(self):
        turn_signal, target_waypoint = self._get_turn_signal_and_target_waypoint()
        observation = {
            'navigating_type': self.navigating_type,
            'turn_signal': turn_signal,
            'waypoint': self._path_xy,
            'cummulative_length': self._path_cumlen,
            'target_waypoint': target_waypoint,
        }
        if self.carla_style_target is not None:
            observation['carla_style_target'] = self._carla_target_waypoint(self._vehicle_xy(self.controller))
        return observation

    def _clear_expert_reference(self):
        self._expert_speed = None
        self._expert_angular_velocity = None
        self._expert_heading = None
    
    def _get_turn_signal_and_target_waypoint(self):
        if  len(self._path_xy) < 2:
            return 0, self._path_xy[-1]

        ego_xy = self._vehicle_xy(self.controller)
        heading_vec = self._ego_heading_vec(self.controller)
        i0 = nearest_front_index(self._path_xy, ego_xy, heading_vec)
        if i0 >= len(self._path_xy):
            return 0, self._path_xy[-1]

        if self.forecast_type == "step":
            idx = i0 + int(self.forecast_value)
        elif self.forecast_type == "distance":
            idx = self._first_index_by_arclen(self._path_cumlen, i0, self.forecast_value)
        else:
            raise ValueError(f"Unknown forecast_type: {self.forecast_type}")
        idx = min(idx, len(self._path_xy) - 1)
        target_waypoint = self._path_xy[idx]

        left_vec = np.asarray([-heading_vec[1], heading_vec[0]], dtype=np.float32)
        lateral_shift = float((target_waypoint - ego_xy) @ left_vec)
        if lateral_shift >= self.lateral_offset:
            return 1, target_waypoint
        if lateral_shift <= -self.lateral_offset:
            return -1, target_waypoint
        return 0, target_waypoint

    @property
    def observation_space(self):
        return gym.spaces.Discrete(3)

    def destroy(self):
        self._path_xy = None
        self._path_cumlen = None
        self.controller = None
        self.trajdata_map = None
        self.init_state = None
        self.state = None
        self._carla_route_xy = None
        self._carla_route_cursor = None
        self._clear_expert_reference()

    # ---------- path builders ----------
    def _build_expert_path(self):
        timestamps = []
        points = []
        ang_vels = []
        speeds = []
        headings = []
        for ts in sorted(self.state.keys()):
            frame = self.state[ts]
            timestamps.append(ts)
            pos = frame["position"]
            x, y = float(pos[0]), float(pos[1])
            points.append([x, y])
            vel = np.array(frame.get("velocity", [0.0, 0.0]), dtype=np.float64)
            ang_vel = float(frame.get("angular_velocity", 0.0))
            ang_vels.append(ang_vel)
            speeds.append(float(np.linalg.norm(vel[:2])))
            headings.append(float(frame.get("heading_theta", 0.0)))

        if self.path_interval is not None:
            values = np.column_stack([speeds, ang_vels])
            if self.forecast_type == "distance":
                points, values, headings = self._sparsify_by_distance_interval(
                    points,
                    self.path_interval,
                    values,
                    headings,
                )
            elif self.forecast_type == "step":
                points, values, headings = self._sparsify_by_time_interval(
                    timestamps,
                    points,
                    self.path_interval,
                    values,
                    headings,
                )
            speeds = values[:, 0]
            ang_vels = values[:, 1]

        self._set_path(points)

        if self._path_xy is not None:
            self._expert_speed = np.asarray(speeds, dtype=np.float32)
            self._expert_angular_velocity = np.asarray(ang_vels, dtype=np.float32)
            self._expert_heading = np.asarray(headings, dtype=np.float32)
        else:
            self._clear_expert_reference()

    def _build_lane_follow_path(self):
        spawn_xyz = np.array(self.init_state["spawn_position"])
        spawn_yaw = float(self.init_state["spawn_yaw"])

        xyzh = np.asarray([float(spawn_xyz[0]), float(spawn_xyz[1]), float(spawn_xyz[2]), spawn_yaw], dtype=np.float32)
        lanes = self.trajdata_map.get_current_lane(
            xyzh,
            max_dist=self.current_lane_max_dist,
            max_heading_error=np.inf,
        )
        if len(lanes) == 0:
            raise RuntimeError(f"No current lane found for lane_following navigation at spawn pose {xyzh.tolist()}.")
        curr_lane = lanes[0]

        accum_length = self._seg_len(curr_lane.center.xy).sum()
        lanes = [curr_lane]
        while accum_length < lane_follow_length:
            succs = list(curr_lane.next_lanes)
            if len(succs) == 0:
                break
            next_lane = self.trajdata_map.get_road_lane(self.np_random.choice(succs))
            lanes.append(next_lane)
            accum_length += self._seg_len(next_lane.center.xy).sum()
            curr_lane = next_lane
        
        path_pts = self._concat_centerlines(lanes, spawn_xyz[:2], spawn_yaw)
        if self.path_interval is not None and self.forecast_type == "distance":
            path_pts, _, _ = self._sparsify_by_distance_interval(path_pts, self.path_interval)
        self._set_path(path_pts)
        self._clear_expert_reference()

    def _build_snap_lane_path(self):
        timestamps = []
        expert = []
        headings = []
        for ts in sorted(self.state.keys()):
            frame = self.state[ts]
            timestamps.append(ts)
            pos = frame["position"]
            expert.append([float(pos[0]), float(pos[1])])
            headings.append(float(frame["heading_theta"]))
        if self.path_interval is None:
            anchors, anchor_headings = expert, headings
        elif self.forecast_type == "distance":
            anchors, _, anchor_headings = self._sparsify_by_distance_interval(
                expert,
                self.path_interval,
                headings=headings,
            )
        else:
            anchors, _, anchor_headings = self._sparsify_by_time_interval(
                timestamps,
                expert,
                self.path_interval,
                headings=headings,
            )
        snapped = []
        for point, heading in zip(anchors, anchor_headings):
            snapped_point = self._snap_point_to_lane_center(point, heading)
            if self.forecast_type == "step" and len(snapped) > 0 and np.array_equal(snapped_point, snapped[-1]):
                continue
            snapped.append(snapped_point)
        if self.carla_style_target is not None:
            self._carla_route_xy = self._build_carla_route(snapped)
            self._carla_route_cursor = 0
        self._set_path(snapped, smooth=False)
        self._clear_expert_reference()

    # ---------- small utils ----------
    @staticmethod
    def _vehicle_xy(vehicle):
        pos = vehicle.position
        return np.array([float(pos[0]), float(pos[1])], dtype=np.float32)

    @staticmethod
    def _xy2(p):
        return float(p[0]), float(p[1])

    def _set_path(self, pts, smooth=True):
        
        pts = np.asarray(pts, dtype=np.float32)
        n = len(pts)
        if smooth and n >= 5:
            # choose an odd window <= n, default up to 9
            wl = min(9, n if (n % 2 == 1) else n - 1)
            if wl < 5 and n >= 5:
                wl = 5
            from scipy.signal import savgol_filter
            px = savgol_filter(pts[:, 0], window_length=int(wl), polyorder=3, mode='interp')
            py = savgol_filter(pts[:, 1], window_length=int(wl), polyorder=3, mode='interp')
            pts = np.column_stack([px, py])

        path = pts
        if len(path) == 0:
            self._path_xy = None
            self._path_cumlen = None
            return
        seg = self._seg_len(path)
        self._path_xy = path
        self._path_cumlen = np.concatenate([[0.0], np.cumsum(seg)])
        if (
            self._expert_speed is not None and
            len(self._expert_speed) != len(self._path_xy)
        ):
            self._clear_expert_reference()

    def _build_carla_route(self, sparse_points):
        points = np.asarray(sparse_points, dtype=np.float32)
        keep = np.concatenate([[True], np.linalg.norm(points[1:] - points[:-1], axis=1) > 1e-6])
        points = points[keep]

        hop_resolution = self.carla_style_target["hop_resolution"]
        # Turn type only marks downsampling boundaries; model command comes from target lateral offset.
        segment_vectors = points[1:] - points[:-1]
        segment_headings = np.arctan2(segment_vectors[:, 1], segment_vectors[:, 0])
        heading_changes = np.arctan2(
            np.sin(segment_headings[1:] - segment_headings[:-1]),
            np.cos(segment_headings[1:] - segment_headings[:-1]),
        )
        angle_threshold = np.deg2rad(self.carla_style_target["road_option_angle_threshold"])
        segment_turn_types = np.zeros(len(segment_vectors), dtype=np.int8)
        segment_turn_types[1:][heading_changes > angle_threshold] = 1
        segment_turn_types[1:][heading_changes < -angle_threshold] = -1

        dense_points = [points[0]]
        dense_turn_types = [segment_turn_types[0]]
        for segment_index, (start, end) in enumerate(zip(points[:-1], points[1:])):
            delta = end - start
            length = np.linalg.norm(delta)
            direction = delta / length
            for offset in np.arange(hop_resolution, length, hop_resolution):
                dense_points.append(start + direction * offset)
                dense_turn_types.append(segment_turn_types[segment_index])
            dense_points.append(end)
            next_segment = min(segment_index + 1, len(segment_turn_types) - 1)
            dense_turn_types.append(segment_turn_types[next_segment])

        dense_points = np.asarray(dense_points, dtype=np.float32)
        sample_factor = self.carla_style_target["sample_factor"]
        sampled_indices = []
        previous_turn_type = None
        distance = 0.0
        for index, turn_type in enumerate(dense_turn_types):
            if previous_turn_type is None:
                sampled_indices.append(index)
                distance = 0.0
            elif turn_type != previous_turn_type:
                sampled_indices.append(index)
                distance = 0.0
            elif distance > sample_factor:
                sampled_indices.append(index)
                distance = 0.0
            elif index == len(dense_points) - 1:
                sampled_indices.append(index)
                distance = 0.0
            else:
                distance += np.linalg.norm(dense_points[index] - dense_points[index - 1])
            previous_turn_type = turn_type

        return dense_points[sampled_indices]

    def _carla_target_waypoint(self, ego_xy):
        cursor = self._carla_route_cursor
        route = self._carla_route_xy
        if len(route) == 1:
            return route[0]

        to_pop = 0
        farthest_in_range = -np.inf
        cumulative_distance = 0.0
        for index in range(cursor + 1, len(route)):
            if cumulative_distance > self.carla_style_target["max_distance"]:
                break
            cumulative_distance += np.linalg.norm(route[index] - route[index - 1])
            distance = np.linalg.norm(route[index] - ego_xy)
            if distance <= self.carla_style_target["min_distance"] and distance > farthest_in_range:
                farthest_in_range = distance
                to_pop = index - cursor

        max_to_pop = len(route) - cursor - 2
        self._carla_route_cursor += min(to_pop, max_to_pop)
        target_index = self._carla_route_cursor + 1
        return route[target_index]

    @staticmethod
    def _sample_axis(total, interval):
        samples = np.arange(0.0, total, interval)
        if len(samples) == 0 or not np.isclose(samples[-1], total):
            samples = np.concatenate([samples, [total]])
        return samples

    @staticmethod
    def _interpolate_path(points, source_axis, sample_axis, values=None, headings=None):
        sampled_points = np.stack(
            [np.interp(sample_axis, source_axis, points[:, 0]), np.interp(sample_axis, source_axis, points[:, 1])],
            axis=1,
        )
        sampled_values = None
        if values is not None:
            sampled_values = np.stack(
                [np.interp(sample_axis, source_axis, values[:, i]) for i in range(values.shape[1])],
                axis=1,
            )
        sampled_headings = None
        if headings is not None:
            unwrapped = np.unwrap(headings)
            sampled_headings = np.interp(sample_axis, source_axis, unwrapped)
        return sampled_points, sampled_values, sampled_headings

    def _sparsify_by_distance_interval(self, points, interval, values=None, headings=None):
        points = np.asarray(points)
        seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
        keep = np.concatenate([[True], seg > 1e-6])
        points = points[keep]
        if values is not None:
            values = np.asarray(values)[keep]
        if headings is not None:
            headings = np.asarray(headings)[keep]
        cumlen = np.concatenate([[0.0], np.cumsum(np.linalg.norm(points[1:] - points[:-1], axis=1))])
        return self._interpolate_path(points, cumlen, self._sample_axis(cumlen[-1], interval), values, headings)

    def _sparsify_by_time_interval(self, timestamps, points, interval, values=None, headings=None):
        timestamps = np.asarray(timestamps)
        points = np.asarray(points)
        if values is not None:
            values = np.asarray(values)
        if headings is not None:
            headings = np.asarray(headings)
        physical_time = (timestamps - timestamps[0]) * 1e-6
        return self._interpolate_path(
            points,
            physical_time,
            self._sample_axis(physical_time[-1], interval),
            values,
            headings,
        )

    def _snap_point_to_lane_center(self, point, heading):
        lane = self._lane_for_point(point, heading)
        if lane is None:
            return np.asarray(point)
        query = np.asarray([[point[0], point[1], 0.0, heading]])
        return lane.center.project_onto(query)[0, :2]

    def _lane_for_point(self, point, heading):
        assert isinstance(self.trajdata_map, VectorMap), "trajdata_map must be provided for snap_lane navigation type."
        query = np.asarray([point[0], point[1], 0.0, heading])
        lanes = self.trajdata_map.get_current_lane(
            query,
            max_dist=self.current_lane_max_dist,
            max_heading_error=np.inf,
        )
        if len(lanes) == 0:
            return None
        return lanes[0]
    
    def _seg_len(self, points):
        seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
        return seg


    @staticmethod
    def _seg_len(points):
        seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
        return seg

    @staticmethod
    def _first_index_by_arclen(cumlen, i0, ahead_len):
        target = cumlen[i0] + max(0.0, ahead_len)
        idx = np.searchsorted(cumlen, target, side="right")
        return int(idx)

    @staticmethod
    def _ego_heading_vec(vehicle):
        h = vehicle.heading  # (cos, sin)
        return np.array([h[0], h[1]])

    def get_reference_state(self, idx):
        if (
            self._path_xy is None or
            idx is None or
            self._expert_speed is None or
            self._expert_angular_velocity is None or
            len(self._expert_speed) == 0
        ):
            return None
        clamped_idx = int(np.clip(idx, 0, len(self._expert_speed) - 1))
        heading = None
        if self._expert_heading is not None and len(self._expert_heading) > clamped_idx:
            heading = float(self._expert_heading[clamped_idx])
        position = None
        if len(self._path_xy) > clamped_idx:
            position = self._path_xy[clamped_idx].tolist()
        return dict(
            speed=float(self._expert_speed[clamped_idx]),
            angular_velocity=float(self._expert_angular_velocity[clamped_idx]),
            heading_theta=heading,
            position=position
        )

    @staticmethod
    def _signed_angle(v1, v2):
        v1n = v1 / np.linalg.norm(v1)
        v2n = v2 / np.linalg.norm(v2)
        dot = np.clip(float(np.dot(v1n, v2n)), -1.0, 1.0)
        ang = math.acos(dot)
        cross_z = v1n[0] * v2n[1] - v1n[1] * v2n[0]
        return ang if cross_z > 0 else -ang

    def _concat_centerlines(self, lane_seq, start_xy, start_heading):
        pts = []
        for idx, lane in enumerate(lane_seq):
            cl = np.asarray(lane.center.xy, dtype=np.float32)
            if idx == 0:
                heading_vec = np.array([math.cos(start_heading), math.sin(start_heading)], dtype=np.float32)
                start_idx = nearest_front_index(cl, np.asarray(start_xy), heading_vec)
                cl = cl[start_idx:]
            if len(pts) > 0 and len(cl) > 0:
                if np.allclose(pts[-1], cl[0]):
                    pts.extend(cl[1:])
                else:
                    pts.extend(cl)
            else:
                pts.extend(cl)
        return pts
