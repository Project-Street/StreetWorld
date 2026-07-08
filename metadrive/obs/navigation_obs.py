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
        self.forecast_value = float(config.get("forecast_value", 20.0))
        self.lateral_offset = float(config.get("lateral_offset", 2.0))
        self.snap_lane_interval = float(config.get("snap_lane_interval", 2.0))
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
        return {
            'navigating_type': self.navigating_type,
            'turn_signal': self._get_turn_signal(), 
            'waypoint': self._path_xy,
            'cummulative_length': self._path_cumlen
        }

    def _clear_expert_reference(self):
        self._expert_speed = None
        self._expert_angular_velocity = None
        self._expert_heading = None
    
    def _get_turn_signal(self):
        if self._path_xy is None or len(self._path_xy) < 2:
            return 0

        ego_xy = self._vehicle_xy(self.controller)
        heading_vec = self._ego_heading_vec(self.controller)
        i0 = nearest_front_index(self._path_xy, ego_xy, heading_vec)
        if i0 >= len(self._path_xy):
            return 0

        if self.forecast_type == "step":
            idx = i0 + int(self.forecast_value)
        elif self.forecast_type == "distance":
            idx = self._first_index_by_arclen(self._path_cumlen, i0, self.forecast_value)
        else:
            raise ValueError(f"Unknown forecast_type: {self.forecast_type}")
        idx = min(idx, len(self._path_xy) - 1)

        left_vec = np.asarray([-heading_vec[1], heading_vec[0]], dtype=np.float32)
        lateral_shift = float((self._path_xy[idx] - ego_xy) @ left_vec)
        if lateral_shift >= self.lateral_offset:
            return 1
        if lateral_shift <= -self.lateral_offset:
            return -1
        return 0

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
        self._clear_expert_reference()

    # ---------- path builders ----------
    def _build_expert_path(self):
        points = []
        ang_vels = []
        speeds = []
        headings = []
        for ts in sorted(self.state.keys()):
            frame = self.state[ts]
            pos = frame["position"]
            x, y = float(pos[0]), float(pos[1])
            points.append([x, y])
            vel = np.array(frame.get("velocity", [0.0, 0.0]), dtype=np.float64)
            ang_vel = float(frame.get("angular_velocity", 0.0))
            ang_vels.append(ang_vel)
            speeds.append(float(np.linalg.norm(vel[:2])))
            headings.append(float(frame.get("heading_theta", 0.0)))

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
        
        path_pts = self._concat_centerlines(lanes, spawn_xyz, spawn_yaw)
        self._set_path(path_pts)
        self._clear_expert_reference()

    def _build_snap_lane_path(self):
        expert = []
        headings = []
        for ts in sorted(self.state.keys()):
            frame = self.state[ts]
            pos = frame["position"]
            expert.append([float(pos[0]), float(pos[1])])
            headings.append(float(frame["heading_theta"]))
        expert = np.asarray(expert, dtype=np.float32)
        headings = np.asarray(headings, dtype=np.float32)
        if self.forecast_type == "step":
            anchors, anchor_headings = expert, headings
        else:
            anchors, anchor_headings = self._sparsify_expert_by_distance(expert, headings, self.snap_lane_interval)
        snapped = []
        for point, heading in zip(anchors, anchor_headings):
            snapped_point = self._snap_point_to_lane_center(point, heading)
            if self.forecast_type == "step" and len(snapped) > 0 and np.array_equal(snapped_point, snapped[-1]):
                continue
            snapped.append(snapped_point)
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
        if len(path) < 3:
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

    def _sparsify_by_distance(self, points, interval):
        interval = float(interval)
        if interval <= 0.0:
            raise ValueError(f"snap_lane_interval must be positive, got {interval}")
        points = np.asarray(points, dtype=np.float32)
        seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
        keep = np.concatenate([[True], seg > 1e-6])
        points = points[keep]
        if len(points) < 2:
            return points

        cumlen = np.concatenate([[0.0], np.cumsum(np.linalg.norm(points[1:] - points[:-1], axis=1))])
        total = float(cumlen[-1])
        samples = np.arange(0.0, total, interval, dtype=np.float32)
        if len(samples) == 0 or not np.isclose(float(samples[-1]), total):
            samples = np.concatenate([samples, np.asarray([total], dtype=np.float32)])
        x = np.interp(samples, cumlen, points[:, 0])
        y = np.interp(samples, cumlen, points[:, 1])
        return np.stack([x, y], axis=1).astype(np.float32)

    def _sparsify_expert_by_distance(self, points, headings, interval):
        interval = float(interval)
        if interval <= 0.0:
            raise ValueError(f"snap_lane_interval must be positive, got {interval}")
        points = np.asarray(points, dtype=np.float32)
        headings = np.asarray(headings, dtype=np.float32)
        if len(points) != len(headings):
            raise ValueError(f"points/headings length mismatch: {len(points)} vs {len(headings)}")

        seg = np.linalg.norm(points[1:] - points[:-1], axis=1)
        keep = np.concatenate([[True], seg > 1e-6])
        points = points[keep]
        headings = headings[keep]
        if len(points) < 2:
            return points, headings

        cumlen = np.concatenate([[0.0], np.cumsum(np.linalg.norm(points[1:] - points[:-1], axis=1))])
        total = float(cumlen[-1])
        samples = np.arange(0.0, total, interval, dtype=np.float32)
        if len(samples) == 0 or not np.isclose(float(samples[-1]), total):
            samples = np.concatenate([samples, np.asarray([total], dtype=np.float32)])
        x = np.interp(samples, cumlen, points[:, 0])
        y = np.interp(samples, cumlen, points[:, 1])
        unwrapped_heading = np.unwrap(headings.astype(np.float64))
        sampled_heading = np.interp(samples, cumlen, unwrapped_heading)
        sampled_heading = np.arctan2(np.sin(sampled_heading), np.cos(sampled_heading))
        return np.stack([x, y], axis=1).astype(np.float32), sampled_heading.astype(np.float32)

    def _snap_point_to_lane_center(self, point, heading):
        lane = self._lane_for_point(point, heading)
        if lane is None:
            return np.asarray(point, dtype=np.float32)
        query = np.asarray([[float(point[0]), float(point[1]), 0.0, float(heading)]], dtype=np.float32)
        return lane.center.project_onto(query)[0, :2].astype(np.float32)

    def _lane_for_point(self, point, heading):
        assert isinstance(self.trajdata_map, VectorMap), "trajdata_map must be provided for snap_lane navigation type."
        query = np.asarray([float(point[0]), float(point[1]), 0.0, float(heading)], dtype=np.float32)
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
        return np.array([float(h[0]), float(h[1])], dtype=np.float32)

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
        for idx, lane_id in enumerate(lane_seq):
            cl = np.asarray(self.trajdata_map.lane_centerline(lane_id), dtype=np.float32)
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
