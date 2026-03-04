import numpy as np
import gymnasium as gym

from trajdata import VectorMap

from metadrive.obs.observation_base import BaseObservation


class GlobalRLSLObserver(BaseObservation):
    def __init__(self, config=None):
        super().__init__(config or {})
        self.map = None
        self.controller = None
        self.collector = None

    def reset(self, map=None, trajdata_map=None, controller=None, collector=None, **kwargs):
        if map is None:
            map = trajdata_map
        if map is None:
            raise ValueError("GlobalRLSLObserver requires map, but got None.")
        if not isinstance(map, VectorMap):
            raise TypeError("GlobalRLSLObserver requires trajdata.VectorMap.")

        env_name = str(map.env_name).lower()
        map_name = str(map.map_name).lower()
        if "xodr" not in env_name and "xodr" not in map_name:
            raise ValueError(f"GlobalRLSLObserver only supports xodr map, got map_id={map.map_id}.")

        self.map = map
        self.controller = controller
        self.collector = collector

    @property
    def observation_space(self):
        return gym.spaces.Box(-np.inf, np.inf, shape=(1,), dtype=np.float32)

    def observe(self):
        objs = self.collector()
        out = {}

        # Ego RLSL must come from controller directly.
        ego_type = str(self.controller.metadrive_type).lower()
        if "vehicle" in ego_type:
            ego_xyz = np.asarray(self.controller.position, dtype=np.float64)
            ego_heading = float(self.controller.heading_theta)
            ego_lane = self._pick_lane(ego_xyz, ego_heading)
            if ego_lane is None:
                out["actor"] = dict(road_id=None, lane_id=None, s=None, l=None, z=float(ego_xyz[2]))
            else:
                ego_s, ego_l = self._compute_sl(ego_lane.center.points[:, :3], ego_xyz)
                ego_road_id, ego_lane_id = self._decode_road_lane_id(str(ego_lane.id))
                out["actor"] = dict(
                    road_id=ego_road_id,
                    lane_id=ego_lane_id,
                    s=float(ego_s),
                    l=float(ego_l),
                    z=float(ego_xyz[2]),
                )
        else:
            out["actor"] = None

        for name, state in objs.items():
            if state["controller"] is self.controller:
                continue
            if not self._is_vehicle(state):
                out[name] = None
                continue

            xyz = np.asarray(state["position"], dtype=np.float64)
            heading = float(state["heading_theta"])
            lane = self._pick_lane(xyz, heading)
            if lane is None:
                out[name] = None
                continue

            s_val, l_val = self._compute_sl(lane.center.points[:, :3], xyz)
            road_id, lane_id = self._decode_road_lane_id(str(lane.id))
            out[name] = dict(
                road_id=road_id,
                lane_id=lane_id,
                s=float(s_val),
                l=float(l_val),
                z=float(xyz[2]),
            )
        return out

    def _pick_lane(self, xyz, heading):
        xyzh = np.array([xyz[0], xyz[1], xyz[2], heading], dtype=np.float64)
        candidates = self.map.get_current_lane(xyzh)
        if len(candidates) > 0:
            return candidates[0]
        return None

    @staticmethod
    def _compute_sl(center_xyz, xyz):
        p0 = center_xyz[:-1, :2]
        p1 = center_xyz[1:, :2]
        seg = p1 - p0
        seg_len = np.linalg.norm(seg, axis=1)
        seg_len2 = np.maximum(seg_len * seg_len, 1e-9)

        xy = xyz[:2]
        rel = xy[None, :] - p0
        t = np.sum(rel * seg, axis=1) / seg_len2
        t = np.clip(t, 0.0, 1.0)
        proj = p0 + seg * t[:, None]

        d = xy[None, :] - proj
        d2 = np.sum(d * d, axis=1)
        idx = int(np.argmin(d2))

        cum = np.concatenate(([0.0], np.cumsum(seg_len)))
        s = cum[idx] + t[idx] * seg_len[idx]

        seg_xy = seg[idx]
        delta_xy = xy - proj[idx]
        cross_z = seg_xy[0] * delta_xy[1] - seg_xy[1] * delta_xy[0]
        l = np.sign(cross_z) * np.linalg.norm(delta_xy)
        return s, l

    def _decode_road_lane_id(self, lane_id_raw):
        reverse_map = self.map.xodr_lane_id_reverse_map
        if lane_id_raw not in reverse_map:
            raise KeyError(f"lane id '{lane_id_raw}' not found in xodr_lane_id_reverse_map.")
        raw = reverse_map[lane_id_raw]
        if "_" not in raw:
            raise ValueError(f"Invalid original lane key '{raw}', expected 'roadId_laneId'.")
        road_id, lane_id = raw.split("_", 1)
        return road_id, lane_id

    @staticmethod
    def _is_vehicle(state):
        type_name = str(state["type"]).lower()
        return "vehicle" in type_name

    def destroy(self):
        self.map = None
        self.controller = None
        self.collector = None
        super().destroy()
