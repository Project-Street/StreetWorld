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
        self.navigating_type = config.get("navigating_type", "expert_following")  # lane_following, expert_following
        self.early_signal_distance = float(config.get("early_signal_distance", 10.0))  # meters
        # New radius-based threshold using triangle inradius (meters). Smaller -> sharper turn.
        # You may tune this based on map scale; ~20m is a moderate default.
        self.turn_inradius_threshold = float(config.get("turn_radius_threshold", 10.0))

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
        else:
            raise ValueError(f"Unknown navigating_type: {self.navigating_type}")
        
        self.destination = self._path_xy[-1] if self._path_xy is not None else init_state["destination"]

    def observe(self):
        return {
            'turn_signal': self._get_turn_signal(), 
            'waypoint': self._path_xy,
            'cummulative_length': self._path_cumlen
        }

    def _clear_expert_reference(self):
        self._expert_speed = None
        self._expert_angular_velocity = None
        self._expert_heading = None
    
    def _get_turn_signal(self):
        if self._path_xy is None or len(self._path_xy) < 5:
            return 0

        ego_xy = self._vehicle_xy(self.controller)
        heading_vec = self._ego_heading_vec(self.controller)
        i0 = nearest_front_index(self._path_xy, ego_xy, heading_vec)
        if i0 >= len(self._path_xy):
            return 0

        j = self._first_index_by_arclen(self._path_cumlen, i0, self.early_signal_distance)
        if j == len(self._path_cumlen) or j == 0:
            return 0

        # Vectorized scan within [i0+1, j-1] using numpy
        N = len(self._path_xy)
        k_start = max(i0 + 1, 1)
        k_end = min(j - 1, N - 2)
        if k_start > k_end:
            return 0

        idx = np.arange(k_start, k_end + 1, dtype=np.int32)
        p = self._path_xy
        p0 = p[idx - 1]
        p1 = p[idx]
        p2 = p[idx + 1]

        v01 = p1 - p0
        v12 = p2 - p1
        v02 = p2 - p0

        len01 = np.linalg.norm(v01, axis=1)
        len12 = np.linalg.norm(v12, axis=1)
        len02 = np.linalg.norm(v02, axis=1)
        cross = v01[:, 0] * v12[:, 1] - v01[:, 1] * v12[:, 0]
        area2 = np.abs(cross)

        eps = 1e-10
        valid = (len01 >= eps) & (len12 >= eps) & (len02 >= eps)
        R = np.full_like(len01, np.inf, dtype=np.float32)
        R[valid] = (len01[valid] * len12[valid] * len02[valid]) / (2 * area2[valid] + eps)
        meets = valid & (R <= float(self.turn_inradius_threshold))

        c = np.sign(cross * meets.astype(np.float32))
        n = len(c)
        if n < 5:
            return 0

        for k in range(0, n - 4): 
            sum = np.sum(c[k:k + 5])
            if sum == 5:
                return 1
            elif sum == -5: # 
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

        lanes = self.trajdata_map.get_current_lane(self._vec4(spawn_xyz,spawn_yaw))
        if len(lanes) == 0:
            Warning("No lane found for lane_following navigation, switch to expert_following.")
            return self._build_expert_path()
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

    # ---------- small utils ----------
    @staticmethod
    def _vehicle_xy(vehicle):
        pos = vehicle.position
        return np.array([float(pos[0]), float(pos[1])], dtype=np.float32)

    @staticmethod
    def _xy2(p):
        return float(p[0]), float(p[1])

    def _set_path(self, pts):
        
        pts = np.asarray(pts, dtype=np.float32)
        n = len(pts)
        if n >= 5:
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
