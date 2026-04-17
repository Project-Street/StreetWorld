import copy
import os
import numpy as np
import torch
from streetworld.manager.base_manager import BaseManager
from streetworld.utils.scenario_utils import parse_object_state
from streetworld.component.vehicle.vehicle_type import random_vehicle_type
from streetworld.utils.trajectory import Trajectory
import json

from streetworld.default_config import BASE_DEFAULT_CONFIG

class ScenarioDataManager(BaseManager):
    DEFAULT_DATA_BUFFER_SIZE = 100
    PRIORITY = -10

    @staticmethod
    def _build_ground_plane(ego_poses, ego_height, start_ts):
        normals = np.stack([np.asarray(pose)[:3, 2] for pose in ego_poses.values()], axis=0)
        average_normal = normals.sum(axis=0)
        average_normal_norm = np.linalg.norm(average_normal)
        if average_normal_norm == 0:
            raise ValueError("Average ego normal has zero length.")
        average_normal = average_normal / average_normal_norm

        start_pose = np.asarray(ego_poses[start_ts])
        start_bottom_center = start_pose[:3, 3] - start_pose[:3, 2] * (ego_height / 2)

        return {
            'normal': average_normal.tolist(),
            'constant': float(np.dot(average_normal, start_bottom_center))
        }

    def __init__(self, config, loader):

        super(ScenarioDataManager, self).__init__()
        self.base_config = config
        self.loader = loader

        # self.store_data = engine.global_config["store_data"]
        # Allow subclasses to set directory differently
        self.directory = self.base_config.get("scene_config_directory")

        self.start_scenario_index = self.base_config.get("start_scenario_index", 0)
        self.random_scenario = self.base_config.get("random_scenario", True)
        self.current_scenario_id = self.start_scenario_index - 1

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

    def _load_single_scene(self, cfg_path):
        scene_name, cfg, timestamp_range, camera_params, ego_poses, participants, scene_mesh_path = self.loader(cfg_path)
        metadata = self.restructure_metadata(
            config=cfg,
            timestamp_range=timestamp_range,
            camera_params=camera_params,
            ego_poses=ego_poses,
            participants=participants,
        )
        metadata["scene_mesh_path"] = scene_mesh_path
        return scene_name, metadata

    def read_metadata(self, loader):
        self.metadata, self.idx2scene = {}, []
        self.num_scenarios = 0
        for config_file in sorted(os.listdir(self.directory)):
            cfg_path = os.path.join(self.directory, config_file)
            scene_name, metadata = self._load_single_scene(cfg_path)
            self.metadata[scene_name] = metadata
            self.idx2scene.append(scene_name)
            self.num_scenarios += 1

    def hotload_scenario(self, cfg_path):
        scene_name, metadata = self._load_single_scene(cfg_path)
        if scene_name not in self.metadata:
            self.idx2scene.append(scene_name)
            self.num_scenarios += 1
            self.base_config["num_scenarios"] = self.num_scenarios
        self.metadata[scene_name] = metadata
        return scene_name

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
                    include_z_position=True
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

    def reset(self, scene_name=None):
        """
        Reset scenario data manager.

        Args:
            scene_name: Name of the scene to load.
                     If None, randomly select a scene (default behavior).

        Raises:
            ValueError: If scene_id is out of valid range.
        """
        # if not self.store_data:
        #     assert len(self._scenarios) <= 1, "It seems you access multiple scenarios in one episode"
        #     self._scenarios = {}

        # Support explicit scene selection for OnSite integration
        if scene_name is not None:
            self.current_scenario_id = self.idx2scene.index(scene_name)
        elif self.random_scenario:
            self.current_scenario_id = self.np_random.randint(0, self.num_scenarios)
        else:
            self.current_scenario_id = (self.current_scenario_id + 1) % self.num_scenarios

        self.current_config = self.base_config.copy()

        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 

        current_metadata = self.get_current_scenario_data()
        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 
        current_metadata = self.get_current_scenario_data()
        ego_poses = current_metadata['ego_poses']
        start_ts = current_metadata['timestamp_range'][0]
        current_metadata['ground_plane'] = self._build_ground_plane(
            ego_poses,
            ego_height=config_dict["controller"].DEFAULT_HEIGHT,
            start_ts=start_ts
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
