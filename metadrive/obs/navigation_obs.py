import math
import json
import os
import numpy as np
import gymnasium as gym
from trajdata import VectorMap
from metadrive.obs.observation_base import BaseObservation
from metadrive.base_class.randomizable import Randomizable
from metadrive.utils.navigation_utils import nearest_front_index

lane_follow_length = 200.0

INTENT_UNKNOWN = 0
INTENT_GO_STRAIGHT = 1
INTENT_GO_LEFT = 2
INTENT_GO_RIGHT = 3

class NavigationObservation(BaseObservation, Randomizable):
    trajdata_map: VectorMap

    def __init__(self, config):
        BaseObservation.__init__(self, config)
        Randomizable.__init__(self, None)
        self.navigating_type = config.get("navigating_type", "expert_following")  # lane_following, destination_following, expert_following
        self.early_signal_distance = float(config.get("early_signal_distance", 10.0))  # meters
        # New radius-based threshold using triangle inradius (meters). Smaller -> sharper turn.
        # You may tune this based on map scale; ~20m is a moderate default.
        self.turn_inradius_threshold = float(config.get("turn_radius_threshold", 15.0))
        self.command_horizon_steps = int(config.get("command_horizon_steps", 6))
        self.command_lateral_threshold = float(config.get("command_lateral_threshold", 2.0))
        self.controller = None
        self.trajdata_map = None
        self.init_state = None
        self.state = None

        self._path_xy = None
        self._path_cumlen = None
        self._expert_speed = None
        self._expert_angular_velocity = None
        self._expert_heading = None
        self._scene_name = None
        self._intent_lookup = None
        self._expert_intent_signal = None
        self.intent_data_dir = str(
            config.get(
                "intent_data_dir",
                os.path.join("/data/users/jrguo", "WOD-E2E-train-intents")
            )
        )

    def reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, scene_name=None, **kwargs):
        if self.navigating_type in ["lane_following", "destination_following"]:
            assert isinstance(trajdata_map, VectorMap), "trajdata_map must be provided for lane_following or destination_following navigation type."

        if seed is not None:
            self.seed(int(seed))

        self.controller = controller
        self.trajdata_map = trajdata_map
        self.init_state = init_state
        self.state = state
        self._scene_name = self._normalize_scene_name(scene_name)
        self._intent_lookup = self._load_intent_lookup(self._scene_name)
        self._clear_expert_reference()

        if self.navigating_type == "expert_following":
            self._build_expert_path()
        elif self.navigating_type == "lane_following":
            self._build_lane_follow_path()
        elif self.navigating_type == "destination_following":
            self._build_destination_path()
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
        self._expert_intent_signal = None
    
    def _get_turn_signal(self):
        # signal_from_intent = self._get_turn_signal_from_intent()
        # if signal_from_intent is not None:
        #     print(f"Using intent-based turn signal: {signal_from_intent}")
        #     return signal_from_intent
        return self._get_turn_signal_deprecated()

    def _get_turn_signal_from_intent(self):
        if self._path_xy is None or len(self._path_xy) < 5:
            return None
        if self._expert_intent_signal is None or len(self._expert_intent_signal) == 0:
            return None

        ego_xy = self._vehicle_xy(self.controller)
        heading_vec = self._ego_heading_vec(self.controller)
        i0 = nearest_front_index(self._path_xy, ego_xy, heading_vec)
        if i0 >= len(self._path_xy):
            return None
        if i0 >= len(self._expert_intent_signal):
            i0 = len(self._expert_intent_signal) - 1
            if i0 < 0:
                return None
        return int(self._expert_intent_signal[i0])

    def _get_turn_signal_deprecated(self):
        if self._path_xy is None or len(self._path_xy) < 2:
            return 0

        ego_xy = self._vehicle_xy(self.controller)
        rel = self._path_xy - ego_xy[None, :]
        i0 = int(np.argmin(np.sum(rel * rel, axis=1)))

        j = min(i0 + max(1, self.command_horizon_steps), len(self._path_xy) - 1)
        if j <= i0:
            return 0

        if i0 + 1 < len(self._path_xy):
            tangent = self._path_xy[i0 + 1] - self._path_xy[i0]
        elif i0 - 1 >= 0:
            tangent = self._path_xy[i0] - self._path_xy[i0 - 1]
        else:
            return 0
        tangent_norm = np.linalg.norm(tangent)
        if tangent_norm < 1e-6:
            return 0
        tangent = tangent / tangent_norm

        anchor_xy = self._path_xy[i0]
        target_xy = self._path_xy[j]
        right_vec = np.array([tangent[1], -tangent[0]], dtype=np.float32)
        lateral = float(np.dot(target_xy - anchor_xy, right_vec))

        if lateral >= self.command_lateral_threshold:
            return -1
        if lateral <= -self.command_lateral_threshold:
            return 1

        return 0

    @staticmethod
    def _intent_id_to_turn_signal(intent_id):
        intent_id = int(intent_id)
        if intent_id == INTENT_GO_LEFT:
            return 1
        if intent_id == INTENT_GO_RIGHT:
            return -1
        if intent_id in (INTENT_UNKNOWN, INTENT_GO_STRAIGHT):
            return 0
        return 0

    @staticmethod
    def _normalize_scene_name(scene_name):
        if scene_name is None:
            return None
        return str(scene_name)

    def _load_intent_lookup(self, scene_name):
        if not scene_name:
            return None
        intent_file = os.path.join(self.intent_data_dir, f"{scene_name}.json")
        if not os.path.isfile(intent_file):
            return None
        try:
            with open(intent_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return None

        frames = payload.get("frames", [])
        lookup = {}
        for frame in frames:
            frame_id = str(frame.get("frame_id", "")).zfill(3)
            intent = frame.get("intent", {}) or {}
            intent_id = int(intent.get("id", INTENT_UNKNOWN))
            lookup[frame_id] = intent_id
        return lookup

    def _build_expert_intent_signal(self):
        if self._path_xy is None:
            self._expert_intent_signal = None
            return
        n = len(self._path_xy)
        if n == 0:
            self._expert_intent_signal = np.zeros((0,), dtype=np.int8)
            return
        if not self._intent_lookup:
            self._expert_intent_signal = None
            return

        signals = []
        for ts in sorted(self.state.keys()):
            frame_id = int(ts) // 100000
            frame_key = f"{frame_id:03d}"
            intent_id = self._intent_lookup.get(frame_key, INTENT_UNKNOWN)
            signals.append(self._intent_id_to_turn_signal(intent_id))

        if len(signals) != n:
            if len(signals) == 0:
                self._expert_intent_signal = None
                return
            x_old = np.linspace(0.0, 1.0, num=len(signals), dtype=np.float32)
            x_new = np.linspace(0.0, 1.0, num=n, dtype=np.float32)
            interp = np.interp(x_new, x_old, np.asarray(signals, dtype=np.float32))
            signals = np.where(interp > 0.5, 1, np.where(interp < -0.5, -1, 0)).astype(np.int8)
            self._expert_intent_signal = signals
            return

        self._expert_intent_signal = np.asarray(signals, dtype=np.int8)

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
            self._build_expert_intent_signal()
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

    def _build_destination_path(self):
        spawn_xyz = np.array(self.init_state["spawn_position"])
        spawn_yaw = self.init_state["spawn_yaw"]
        dest_xyz = np.array(self.init_state["destination"])
        dest_yaw = self.init_state["destination_yaw"]

        start_lanes = self.trajdata_map.get_current_lane(self._vec4(spawn_xyz,spawn_yaw))
        goal_lanes = self.trajdata_map.get_current_lane(self._vec4(dest_xyz,dest_yaw))
        if len(start_lanes) == 0 or len(goal_lanes) == 0:
            Warning("No lane found for destination_following navigation, switch to expert_following.")
            return self._build_expert_path()
        start_lane = start_lanes[0]
        goal_lane = goal_lanes[0]

        if start_lane == goal_lane:
            lane_seq = [start_lane]
        else:
            lane_seq = self._bfs_lane_seq(start_lane, goal_lane)
            if len(lane_seq) == 0:
                lane_seq = [start_lane]
        path_pts = self._concat_centerlines(lane_seq, spawn_xyz, spawn_yaw)
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

    def _bfs_lane_seq(self, start_lane, goal_lane):
        if start_lane == goal_lane:
            return [start_lane]
        from collections import deque
        q = deque([start_lane])
        parent = {start_lane: None}
        visited = {start_lane}
        while len(q) > 0:
            u = q.popleft()
            for v in self.trajdata_map.successors(u):
                if v in visited:
                    continue
                parent[v] = u
                if v == goal_lane:
                    seq = [v]
                    while parent[seq[-1]] is not None:
                        seq.append(parent[seq[-1]])
                    seq.reverse()
                    return seq
                visited.add(v)
                q.append(v)
        return []
