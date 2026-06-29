# TODO: how to lane shifting?
# TODO: how to use map?
# TODO: parameter space
# TODO: pid steering

import math
import numpy as np
import gymnasium as gym

from metadrive.policy.base_policy import BasePolicy
from metadrive.type import MetaDriveType
from metadrive.utils.navigation_utils import nearest_front_index

class TrajectoryIDMPolicy(BasePolicy):
    ACC_FACTOR = 2.0
    DEACC_FACTOR = 3.0
    DELTA = 4.0
    lookahead_path_length = 50
    LANE_WIDTH = 3.5

    def __init__(self, step_manager, config=None):
        super().__init__(step_manager, config)
        self.front_distance = float(self.config["front_distance"]) if "front_distance" in self.config else 5.0
        self.react_time = float(self.config["react_time"]) if "react_time" in self.config else 1.0

        # Sample speeds (km/h)
        self.max_speed = float(gym.spaces.Box(low=np.array([25.0]), high=np.array([50.0]), dtype=np.float32).sample()[0])
        self.path = None
        self.cumlen = None
        self.curve_radius = None

    def reset(self, controller, seed, state, init_state, **kwargs):
        if controller.metadrive_type != MetaDriveType.VEHICLE:
            raise ValueError("IDMPolicy can only be used for vehicle agents.")
        super().reset(controller, seed, state, init_state, **kwargs)
        self.path, self.cumlen = self._build_path_from_trajectory()
        self.curve_radius = self._curve_radius(self.path)

    def act(self, observation, *args, **kwargs):
        if observation is None or "surrounding" not in observation:
            raise KeyError("IDMPolicy requires observation['surrounding'].")
        surround = observation["surrounding"]
        pts = self.path
        cumlen = self.cumlen
        v = self.controller.speed_km_h
        v_m_s = self.controller.speed

        # Ego pose and heading
        ego_xy = np.array([self.controller.position[0], self.controller.position[1]], dtype=np.float32)
        h = self.controller.heading
        heading_vec = np.array([float(h[0]), float(h[1])], dtype=np.float32)

        # nearest forward index for ego; if none, return zeros
        rel_all = pts - ego_xy[None, :]
        if not np.any((rel_all @ heading_vec) >= 0.0):
            raise RuntimeError("IDMPolicy found no forward waypoint on the trajectory path.")
        front_idx = int(nearest_front_index(pts, ego_xy, heading_vec))
        v0 = self._target_speed(front_idx)

        # Free road acceleration
        a_free = self.ACC_FACTOR * (1.0 - (v / max(v0, 1e-3)) ** self.DELTA)

        left_vec = np.array([-heading_vec[1], heading_vec[0]], dtype=np.float32)

        # Select closest lead object in ego heading frame.
        lead = None
        lead_longitudinal = None
        for obj in surround.values():
            rel = np.asarray(obj["position"], dtype=np.float32)[:2] - ego_xy
            longitudinal = float(np.dot(rel, heading_vec))
            lateral = float(np.dot(rel, left_vec))
            if longitudinal <= 0 or abs(lateral) > self.LANE_WIDTH * 0.5:
                continue
            if lead is None or longitudinal < lead_longitudinal:
                lead = obj
                lead_longitudinal = longitudinal

        a_int = 0.0
        if lead is not None:
            pos_world = np.asarray(lead["position"], dtype=np.float32)[:2]
            obj_closest_idx = np.argmin(np.sum((pts - pos_world[None, :]) ** 2, axis=1))
            delta_dist = float(cumlen[obj_closest_idx] - cumlen[front_idx])
            ego_len = self.controller.LENGTH
            obj_len = lead["size"][0]
            lead_type = lead["type"]
            s0 = self.front_distance if lead_type == MetaDriveType.VEHICLE else 2.0

            # Gap s computed from path arclen minus half lengths
            s = max(1e-3, delta_dist - 0.5 * ego_len - 0.5 * obj_len)

            # Tangent at object's nearest point on path
            
            k0 = max(0, obj_closest_idx - 1)
            k1 = min(len(pts) - 1, obj_closest_idx + 1)
            t_vec = pts[k1] - pts[k0]
            path_dir = t_vec / (np.linalg.norm(t_vec) + 1e-9)

            # Tangential velocities (km/h)
            v_obj = np.asarray(lead["velocity"], dtype=np.float32)[:2]
            v_obj_t = np.dot(v_obj, path_dir) * 3.6
            dv = max(0.0, v - v_obj_t)
            dv_m_s = dv / 3.6

            s_star = s0 + v_m_s * self.react_time + v_m_s * dv_m_s / (2.0 * math.sqrt(self.ACC_FACTOR * self.DEACC_FACTOR))
            a_int = self.ACC_FACTOR * (s_star / s) ** 2

        a_cmd = a_free - a_int
        if a_cmd >= 0.0:
            throttle_brake = a_cmd / self._controller_max_acceleration()
        else:
            throttle_brake = a_cmd / self._controller_max_deceleration()
        throttle_brake = float(np.clip(throttle_brake, -1.0, 1.0))

        # Steering from lookahead path
        steering = 0.0
        if len(pts) >= 3:
            target = pts[front_idx]
            to_target = target - ego_xy
            n = np.linalg.norm(to_target)
            if n > 1e-6:
                to_target /= n
                cross_z = heading_vec[0] * to_target[1] - heading_vec[1] * to_target[0]
                dot_h = np.clip(float(np.dot(heading_vec, to_target)), -1.0, 1.0)
                ang = math.atan2(cross_z, dot_h)
                ang_limit = math.radians(float(self.controller.max_steering))
                steering = float(np.clip(ang / ang_limit, -1.0, 1.0))

        return steering, throttle_brake

    def _build_path_from_trajectory(self):
        points = []
        for ts in sorted(self.trajectory.keys()):
            frame = self.trajectory[ts]
            if not frame["valid"]:
                continue
            pos = frame["position"]
            points.append([float(pos[0]), float(pos[1])])
        path = np.asarray(points, dtype=np.float32)
        if len(path) < 3:
            raise ValueError(f"IDMPolicy requires at least 3 valid trajectory points, got {len(path)}.")
        seg_len = np.linalg.norm(path[1:] - path[:-1], axis=1)
        if not np.any(seg_len > 1e-6):
            raise ValueError("IDMPolicy got zero-length trajectory path.")
        cumlen = np.concatenate([[0.0], np.cumsum(seg_len)]).astype(np.float32)
        return path, cumlen

    def _target_speed(self, front_idx):
        radius = float(self.curve_radius[front_idx])
        curve_speed = math.sqrt(self._controller_max_acceleration() * radius) * 3.6
        return float(min(self.max_speed, curve_speed))

    def _controller_max_acceleration(self):
        return 4.0 * float(self.controller.max_engine_force) / float(self.controller.MASS)

    def _controller_max_deceleration(self):
        return 4.0 * float(self.controller.max_brake_force) / (
            float(self.controller.MASS) * float(self.controller.TIRE_RADIUS)
        )

    @staticmethod
    def _curve_radius(path):
        radius = np.full(len(path), np.inf, dtype=np.float32)
        for i in range(1, len(path) - 1):
            a = float(np.linalg.norm(path[i] - path[i - 1]))
            b = float(np.linalg.norm(path[i + 1] - path[i]))
            c = float(np.linalg.norm(path[i + 1] - path[i - 1]))
            v1 = path[i] - path[i - 1]
            v2 = path[i + 1] - path[i]
            cross = float(v1[0] * v2[1] - v1[1] * v2[0])
            if abs(cross) > 1e-6:
                radius[i] = a * b * c / (2.0 * abs(cross))
        return radius
