import copy
import os
import numpy as np
import torch
from metadrive.manager.base_manager import BaseManager
from metadrive.scenario.scenario_description import ScenarioDescription as SD, MetaDriveType
from metadrive.scenario.utils import read_scenario_data, read_dataset_summary
from metadrive.scenario.parse_object_state import parse_full_trajectory, parse_object_state
from metadrive.component.vehicle.vehicle_type import random_vehicle_type, vehicle_type
from metadrive.utils.trajectory import Trajectory
import json

from metadrive.default_config import BASE_DEFAULT_CONFIG

class ScenarioDataManager(BaseManager):
    DEFAULT_DATA_BUFFER_SIZE = 100
    PRIORITY = -10


    def __init__(self, config, loader):

        super(ScenarioDataManager, self).__init__()
        self.base_config = config

        # self.store_data = engine.global_config["store_data"]
        # Allow subclasses to set directory differently
        self.directory = self.base_config.get("scene_config_directory")

        # for multi-worker
        # self._scenarios = {}

        # Read summary file first:
        self.read_metadata(loader)
        self.base_config["num_scenarios"] = self.num_scenarios

        # sort scenario for curriculum training
        self.scenario_difficulty = None
        # self.sort_scenarios()


        # stat
        # self.coverage = [0 for _ in range(self.num_scenarios)]
    def _post_process_config(self, config):
        pass

    def read_metadata(self, loader):
        self.metadata, self.idx2scene = {}, []
        self.num_scenarios = 0
        for config_file in os.listdir(self.directory):
            self.num_scenarios += 1
            cfg_path = os.path.join(self.directory, config_file)

            scene_name, cfg, timestamp_range, camera_params, ego_poses, participants, scene_mesh_path = loader(cfg_path)
            # scene_name : str
            # cfg : object
            # timestamp : list|tuple [2]
            # camera params : 
            #     "camera_name" :
            #         "K" : list[3][3]
            #         "H" : int
            #         "W" : int
            #         "ego2camera" : list[4][4]
            # ego poses : 
            #     1 : list[4][4]
            #     ...
            #     n : list[4][4]            
            # participants :
            #     "unique_name" : 
            #         "size" : list[3]
            #         "type" : str (vehicle/pedestrian/bicycle)
            #         "poses" :
            #             1 : list[4][4]
            #             ...
            #             n : list[4][4]
            # scene_mesh_path : str

            self.metadata[scene_name] = self.restructure_metadata(
                config=cfg,
                timestamp_range=timestamp_range,
                camera_params=camera_params,
                ego_poses=ego_poses,
                participants=participants,
            )
            self.metadata[scene_name]['scene_mesh_path'] = scene_mesh_path

            self.idx2scene.append(scene_name)

    def restructure_metadata(self, config, timestamp_range, camera_params, ego_poses, participants):
        init_state, agent_state = {}, {}
        ego_ts = sorted(int(ts) for ts in ego_poses.keys())
        timestamp_range[0] = min(ego_ts, key=lambda ts: abs(ts - timestamp_range[0]))
        timestamp_range[1] = min(ego_ts, key=lambda ts: abs(ts - timestamp_range[1]))
        scene_timestamp_list = list(range(timestamp_range[0], timestamp_range[1], int(self.base_config['physics_world_step_size'])))
        for name, tracking in (participants | {'actor': ego_poses}).items():
            if name == 'actor':
                timestamp_list = scene_timestamp_list
                traj = Trajectory(ego_poses)
            else:
                org_ts_list = sorted(int(ts) for ts in tracking['poses'].keys())
                if not org_ts_list:
                    continue
                def round_to_scene_ts(value):
                    return min(scene_timestamp_list, key=lambda ts: abs(ts - value))
                rounded_start = round_to_scene_ts(org_ts_list[0])
                rounded_end = round_to_scene_ts(org_ts_list[-1])

                timestamp_list = [ts for ts in scene_timestamp_list if rounded_start <= ts <= rounded_end]
                traj = Trajectory(tracking['poses'])
            if len(timestamp_list) < 2:
                continue
            traj_mat = {int(k): traj.get_transform(k) for k in timestamp_list}

            first_ts, last_ts = timestamp_list[0], timestamp_list[-1]
            parsed_data = {}
            for idx in range(len(timestamp_list)):
                parsed_data[timestamp_list[idx]] = parse_object_state(
                    traj_mat, 
                    idx, 
                    include_z_position=True,
                    zero_velocity=(name != 'actor')
                )
            
            first_state, last_state = parsed_data[first_ts], parsed_data[last_ts]
            init_state[name] = dict(
                spawn_position=list(first_state["position"]),
                spawn_yaw=first_state["heading_theta"],
                spawn_velocity=first_state["velocity"],
                spawn_angular_velocity=first_state["angular_velocity"],
                destination=last_state["position"],
                destination_yaw=last_state["heading_theta"]
            )
            agent_state[name] = parsed_data

        for cam_name, cam_param in camera_params.items():
            cam_param['ego2camera'] = torch.tensor(cam_param['ego2camera'])
            cam_param['K'] = torch.tensor(cam_param['K'])

        return {
            'scene_config': config,
            'camera_params':camera_params,
            'ego_poses': ego_poses,
            'participants': participants,
            'init_state': init_state,
            "agent_state": agent_state,
            'timestamp_range': timestamp_range
        }

    @staticmethod
    def _normalize_vector(vec, fallback):
        arr = np.asarray(vec, dtype=float)
        norm = np.linalg.norm(arr)
        if norm > 1e-6:
            return arr / norm
        return np.asarray(fallback, dtype=float)

    @classmethod
    def _extract_ground_samples(cls, ego_poses):
        pose_items = sorted(ego_poses.items(), key=lambda item: int(item[0]))
        if not pose_items:
            return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=float)

        positions = []
        up_vectors = []
        for _, pose in pose_items:
            pose_mat = np.asarray(pose, dtype=float)
            if pose_mat.ndim != 2 or pose_mat.shape[0] < 3 or pose_mat.shape[1] < 4:
                continue
            positions.append(pose_mat[:3, 3])
            up_vectors.append(cls._normalize_vector(pose_mat[:3, 2], [0.0, 0.0, 1.0]))

        if not positions:
            return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=float)

        positions = np.asarray(positions, dtype=float)
        up_vectors = np.asarray(up_vectors, dtype=float)

        filtered_positions = [positions[0]]
        filtered_up = [up_vectors[0]]
        for idx in range(1, len(positions)):
            if np.linalg.norm(positions[idx] - filtered_positions[-1]) > 1e-3:
                filtered_positions.append(positions[idx])
                filtered_up.append(up_vectors[idx])

        return np.asarray(filtered_positions, dtype=float), np.asarray(filtered_up, dtype=float)

    @staticmethod
    def _interpolate_path(cumulative_distances, points, s):
        s_clamped = float(np.clip(s, cumulative_distances[0], cumulative_distances[-1]))
        idx = int(np.searchsorted(cumulative_distances, s_clamped, side="left"))
        if idx <= 0:
            return points[0]
        if idx >= len(cumulative_distances):
            return points[-1]
        left_s = cumulative_distances[idx - 1]
        right_s = cumulative_distances[idx]
        if right_s - left_s < 1e-6:
            return points[idx]
        ratio = (s_clamped - left_s) / (right_s - left_s)
        return (1.0 - ratio) * points[idx - 1] + ratio * points[idx]

    @staticmethod
    def _default_tangent_for_normal(normal):
        ref = np.array([0.0, 0.0, 1.0], dtype=float)
        if abs(float(np.dot(ref, normal))) > 0.95:
            ref = np.array([1.0, 0.0, 0.0], dtype=float)
        tangent = np.cross(ref, normal)
        tangent_norm = np.linalg.norm(tangent)
        if tangent_norm > 1e-6:
            return tangent / tangent_norm
        return np.array([1.0, 0.0, 0.0], dtype=float)

    @classmethod
    def _fit_normal_from_positions(
        cls,
        positions,
        reference_up,
        min_spread_ratio=0.02,
        max_up_deviation_deg=20.0,
    ):
        ref_up = cls._normalize_vector(reference_up, [0.0, 0.0, 1.0])
        if len(positions) < 3:
            return ref_up

        centered = positions - np.mean(positions, axis=0)
        _, singular_values, vh = np.linalg.svd(centered, full_matrices=False)
        if singular_values[0] < 1e-6:
            return ref_up

        spread_ratio = singular_values[1] / singular_values[0]
        if spread_ratio < float(min_spread_ratio):
            return ref_up

        candidate = cls._normalize_vector(vh[-1], ref_up)
        if np.dot(candidate, ref_up) < 0:
            candidate = -candidate

        deviation_cos = float(np.clip(np.dot(candidate, ref_up), -1.0, 1.0))
        deviation_deg = float(np.degrees(np.arccos(deviation_cos)))
        if deviation_deg > float(max_up_deviation_deg):
            return ref_up
        return candidate

    @classmethod
    def _fit_ground_plane(cls, ego_poses):
        positions, up_vectors = cls._extract_ground_samples(ego_poses)
        if len(positions) == 0:
            return np.array([0.0, 0.0, 1.0], dtype=float), np.array([0.0, 0.0, 0.0], dtype=float)

        avg_up = cls._normalize_vector(np.mean(up_vectors, axis=0), [0.0, 0.0, 1.0])

        centroid = np.mean(positions, axis=0)
        normal = cls._fit_normal_from_positions(
            positions,
            avg_up,
            min_spread_ratio=0.02,
            max_up_deviation_deg=20.0,
        )

        return normal, centroid

    @classmethod
    def _fit_ground_plane_chunks(
        cls,
        ego_poses,
        offset,
        chunk_length=5.0,
        chunk_width=40.0,
        chunk_overlap=0.5,
        fit_radius=None,
    ):
        chunk_length = max(float(chunk_length), 1e-3)
        chunk_width = max(float(chunk_width), 1e-3)
        chunk_overlap = max(float(chunk_overlap), 0.0)
        fit_radius = max(float(fit_radius if fit_radius is not None else chunk_length * 1.5), chunk_length)

        positions, up_vectors = cls._extract_ground_samples(ego_poses)
        if len(positions) < 2:
            return []

        segment_lengths = np.linalg.norm(np.diff(positions, axis=0), axis=1)
        cumulative_distances = np.concatenate(([0.0], np.cumsum(segment_lengths)))
        total_distance = float(cumulative_distances[-1])
        if total_distance < 1e-3:
            return []

        global_normal, _ = cls._fit_ground_plane(ego_poses)
        global_up = cls._normalize_vector(np.mean(up_vectors, axis=0), global_normal)

        centers = np.arange(0.0, total_distance + 1e-6, chunk_length)
        if total_distance - centers[-1] > 0.5 * chunk_length:
            centers = np.concatenate([centers, np.array([total_distance], dtype=float)])

        tangent_delta = max(chunk_length * 0.5, 0.25)
        chunks = []

        for s_center in centers:
            center = cls._interpolate_path(cumulative_distances, positions, s_center)

            s_start = max(0.0, s_center - fit_radius)
            s_end = min(total_distance, s_center + fit_radius)
            local_mask = (cumulative_distances >= s_start) & (cumulative_distances <= s_end)

            local_positions = positions[local_mask]
            local_ups = up_vectors[local_mask]

            local_up = global_up
            if len(local_ups) > 0:
                local_up = cls._normalize_vector(np.mean(local_ups, axis=0), global_up)

            normal = cls._fit_normal_from_positions(
                local_positions,
                local_up,
                min_spread_ratio=0.02,
                max_up_deviation_deg=25.0,
            )

            forward = cls._interpolate_path(cumulative_distances, positions, min(total_distance, s_center + tangent_delta))
            backward = cls._interpolate_path(cumulative_distances, positions, max(0.0, s_center - tangent_delta))
            tangent = forward - backward
            tangent = tangent - np.dot(tangent, normal) * normal
            tangent = cls._normalize_vector(tangent, cls._default_tangent_for_normal(normal))

            chunk_constant = float(np.dot(normal, center) - offset)
            chunks.append({
                "center": center.tolist(),
                "normal": normal.tolist(),
                "constant": chunk_constant,
                "tangent": tangent.tolist(),
                "length": float(chunk_length + 2.0 * chunk_overlap),
                "width": chunk_width,
            })

        return chunks

    @classmethod
    def _adjust_init_state_for_ground_plane(cls, init_state, normal, constant, offset):
        updated_init_state = copy.deepcopy(init_state)
        actor_state = updated_init_state.get("actor")
        if actor_state is None:
            return updated_init_state

        spawn_position = np.asarray(actor_state.get("spawn_position", [0.0, 0.0, 0.0]), dtype=float)
        normal_vec = cls._normalize_vector(normal, [0.0, 0.0, 1.0])
        target_dot = float(constant + offset)

        if abs(float(normal_vec[2])) > 1e-4:
            new_z = (target_dot - normal_vec[0] * spawn_position[0] - normal_vec[1] * spawn_position[1]) / normal_vec[2]
            spawn_position[2] = float(new_z)
        else:
            current_dot = float(np.dot(normal_vec, spawn_position))
            spawn_position = spawn_position + (target_dot - current_dot) * normal_vec

        actor_state["spawn_position"] = spawn_position.tolist()
        updated_init_state["actor"] = actor_state
        return updated_init_state

    def reset(self, scene_id=None):
        """
        Reset scenario data manager.

        Args:
            scene_id: Scene index (int) to load specific scene.
                     If None, randomly select a scene (default behavior).

        Raises:
            ValueError: If scene_id is out of valid range.

        Returns:
            dict: Updated init_state with actor spawn_position aligned to the computed ground plane offset.
        """
        # if not self.store_data:
        #     assert len(self._scenarios) <= 1, "It seems you access multiple scenarios in one episode"
        #     self._scenarios = {}

        # Support explicit scene selection for OnSite integration
        if scene_id is not None:
            if not (0 <= scene_id < self.num_scenarios):
                raise ValueError(f"scene_id {scene_id} out of range [0, {self.num_scenarios})")
            self.current_scenario_id = scene_id
        else:
            self.current_scenario_id = self.np_random.randint(0, self.num_scenarios)
        self.current_config = self.base_config.copy()

        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 

        current_metadata = self.get_current_scenario_data()
        ego_poses = current_metadata['ego_poses']

        up_dir, plane_anchor = self._fit_ground_plane(ego_poses)
        offset = config_dict["controller"].DEFAULT_HEIGHT / 2 - 0.1
        ground_constant = float(np.dot(up_dir, plane_anchor) - offset)

        map_config = self.base_config.get("map_config", {})
        plane_mode = str(map_config.get("ground_plane_mode", self.base_config.get("ground_plane_mode", "single"))).lower()
        chunk_length = map_config.get("ground_plane_chunk_length", self.base_config.get("ground_plane_chunk_length", 5.0))
        chunk_width = map_config.get("ground_plane_chunk_width", self.base_config.get("ground_plane_chunk_width", 40.0))
        chunk_overlap = map_config.get("ground_plane_chunk_overlap", self.base_config.get("ground_plane_chunk_overlap", 0.5))
        chunk_fit_radius = map_config.get(
            "ground_plane_chunk_fit_radius",
            self.base_config.get("ground_plane_chunk_fit_radius", None),
        )

        plane_params = {
            'type': 'single',
            'normal': up_dir.tolist(),
            'constant': ground_constant
        }

        if plane_mode in {"chunked", "chunks", "piecewise"}:
            chunks = self._fit_ground_plane_chunks(
                ego_poses,
                offset=offset,
                chunk_length=chunk_length,
                chunk_width=chunk_width,
                chunk_overlap=chunk_overlap,
                fit_radius=chunk_fit_radius,
            )
            if len(chunks) > 0:
                plane_params['type'] = 'chunked'
                plane_params['chunks'] = chunks

        current_metadata['ground_plane'] = plane_params

        return self._adjust_init_state_for_ground_plane(
            current_metadata['init_state'],
            up_dir,
            ground_constant,
            offset,
        )

    def get_current_scenario_data(self):
        return self.get_scenario_data(self.current_scenario_id)

    def get_scenario_data(self, i, should_copy=False):
        assert 0 <= i < self.num_scenarios, \
            "scenario index exceeds range, scenario index: {}, worker_index: {}".format(i, self.worker_index)
        scenario_name = self.idx2scene[i]
        return self.metadata[scenario_name]

    @property
    def current_scenario_length(self):
        timestamp_range = self.get_current_scenario_data()['timestamp_range']
        return timestamp_range[1] - timestamp_range[0]

    def sort_scenarios(self):
        """
        TODO(LQY): consider exposing this API to config
        Sort scenarios to support curriculum training. You are encouraged to customize your own sort method
        :return: sorted scenario list
        """
        if self.engine.max_level == 0:
            raise ValueError("Curriculum Level should be greater than 1")
        elif self.engine.max_level == 1:
            return

        def _score(scenario_id):
            file_path = os.path.join(self.directory, self.mapping[scenario_id], scenario_id)
            scenario = read_scenario_data(file_path, centralize=True)
            obj_weight = 0

            # calculate curvature
            ego_car_id = scenario[SD.METADATA][SD.SDC_ID]
            state_dict = scenario["tracks"][ego_car_id]["state"]
            valid_track = state_dict["position"][np.where(state_dict["valid"].astype(int))][..., :2]

            dir = valid_track[1:] - valid_track[:-1]
            dir = np.arctan2(dir[..., 1], dir[..., 0])
            curvature = sum(abs(dir[1:] - dir[:-1]) / np.pi) + 1

            sdc_moving_dist = SD.sdc_moving_dist(scenario)
            num_moving_objs = SD.num_moving_object(scenario, object_type=MetaDriveType.VEHICLE)
            return sdc_moving_dist * curvature + num_moving_objs * obj_weight, scenario

        start = self.start_scenario_index
        end = self.start_scenario_index + self.num_scenarios
        id_score_scenarios = [(s_id, *_score(s_id)) for s_id in self.summary_lookup[start:end]]
        id_score_scenarios = sorted(id_score_scenarios, key=lambda scenario: scenario[-2])
        self.summary_lookup[start:end] = [id_score_scenario[0] for id_score_scenario in id_score_scenarios]
        self.scenario_difficulty = {
            id_score_scenario[0]: id_score_scenario[1]
            for id_score_scenario in id_score_scenarios
        }
        self._scenarios = {i + start: id_score_scenario[-1] for i, id_score_scenario in enumerate(id_score_scenarios)}

    @property
    def current_scenario_difficulty(self):
        return self.scenario_difficulty[self.summary_lookup[self.engine.global_random_seed]
                                        ] if self.scenario_difficulty is not None else 0

    # @property
    # def data_coverage(self):
    #     return sum(self.coverage) / len(self.coverage) * self.engine.global_config["num_workers"]

    def destroy(self):
        """
        Clear memory
        """
        super(ScenarioDataManager, self).destroy()
        self._scenarios = {}
        # Config.clear_nested_dict(self.summary_dict)
        self.summary_lookup.clear()
        self.mapping.clear()
        self.summary_dict, self.summary_lookup, self.mapping = None, None, None


class ScenarioOnlineDataManager(BaseManager):
    """
    Compared to ScenarioDataManager, this manager allow user to pass in Scenario Description online.
    It will not read data from disk, but receive data from user.
    """
    PRIORITY = -10
    _scenario = None

    @property
    def current_scenario_summary(self):
        return self.current_scenario[SD.METADATA]

    def set_scenario(self, scenario_description):
        SD.sanity_check(scenario_description)
        scenario_description = SD.centralize_to_ego_car_initial_position(scenario_description)
        self._scenario = scenario_description

    def get_scenario(self, seed=None, should_copy=False):
        assert self._scenario is not None, "Please set scenario first via env.set_scenario(scenario_description)!"
        if should_copy:
            return copy.deepcopy(self._scenario)
        return self._scenario

    def get_metadata(self):
        raise ValueError()
        state = super(ScenarioDataManager, self).get_metadata()
        raw_data = self.current_scenario
        state["raw_data"] = raw_data
        return state

    @property
    def current_scenario_length(self):
        return self.current_scenario[SD.LENGTH]

    @property
    def current_scenario(self):
        return self._scenario

    @property
    def current_scenario_difficulty(self):
        return 0

    @property
    def current_scenario_id(self):
        return self.current_scenario_summary["scenario_id"]

    @property
    def data_coverage(self):
        return None

    def destroy(self):
        """
        Clear memory
        """
        super(ScenarioOnlineDataManager, self).destroy()
        self._scenario = None
