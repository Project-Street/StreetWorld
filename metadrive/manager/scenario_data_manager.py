import copy
import os
import numpy as np
import torch
from metadrive.manager.base_manager import BaseManager
from metadrive.utils.scenario_utils import parse_object_state
from metadrive.component.vehicle.vehicle_type import random_vehicle_type
from metadrive.utils.trajectory import Trajectory
import json

from metadrive.default_config import BASE_DEFAULT_CONFIG

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
        self.eval_mode = False

        # self.store_data = engine.global_config["store_data"]
        self.scene_config_list = self._build_scene_config_list()

        self.start_scenario_index = self.base_config.get("start_scenario_index", 0)
        self.random_scenario = self.base_config.get("random_scenario", True)
        self.hotload = bool(self.base_config.get("hotload", False))
        self.current_scenario_id = self.start_scenario_index - 1

        # for multi-worker
        # self._scenarios = {}

        if self.hotload:
            self.metadata = {}
            self.idx2scene = [None] * len(self.scene_config_list)
            self.num_scenarios = len(self.scene_config_list)
        else:
            self.read_metadata(loader)
        self.base_config["num_scenarios"] = self.num_scenarios

        # sort scenario for curriculum training
        self.scenario_difficulty = None
        # self.sort_scenarios()


        # stat
        # self.coverage = [0 for _ in range(self.num_scenarios)]
    def _post_process_config(self, config):
        pass

    def _build_scene_config_list(self):
        scene_config_input = self.base_config.get("scene_config_list")
        if scene_config_input is None:
            scene_config_input = self.base_config.get("scene_config_directory")

        if isinstance(scene_config_input, list):
            return scene_config_input

        return [
            os.path.join(scene_config_input, config_file)
            for config_file in sorted(os.listdir(scene_config_input))
        ]

    def _load_single_scene(self, cfg_path):
        scene_name, cfg, timestamp_range, camera_params, ego_poses, participants, scene_mesh_path = self.loader(cfg_path)
        ego_poses, camera_params = self._calibrate_ego_center(cfg, ego_poses, camera_params)
        metadata = self.restructure_metadata(
            config=cfg,
            timestamp_range=timestamp_range,
            camera_params=camera_params,
            ego_poses=ego_poses,
            participants=participants,
        )
        metadata["scene_mesh_path"] = scene_mesh_path
        return scene_name, metadata

    def _ego_vehicle_height(self):
        actor_config = self.base_config["actor_config"]
        vehicle_size = actor_config["controller_config"]["size"]
        if vehicle_size is not None:
            return float(vehicle_size[2])
        return float(actor_config["controller"].DEFAULT_HEIGHT)

    def _calibrate_ego_center(self, config, ego_poses, camera_params):
        ego_center_height = float(config.get("ego_center_height", 0))
        ego_origin_delta = np.eye(4, dtype=np.float32)
        ego_origin_delta[2, 3] = self._ego_vehicle_height() / 2 - ego_center_height

        calibrated_ego_poses = {
            int(timestamp): (np.asarray(pose, dtype=np.float32) @ ego_origin_delta).astype(np.float32)
            for timestamp, pose in ego_poses.items()
        }

        calibrated_camera_params = {}
        for cam_name, cam_param in camera_params.items():
            calibrated_cam_param = dict(cam_param)
            calibrated_cam_param["ego2camera"] = (
                np.asarray(cam_param["ego2camera"], dtype=np.float32) @ ego_origin_delta
            ).astype(np.float32)
            calibrated_camera_params[cam_name] = calibrated_cam_param

        return calibrated_ego_poses, calibrated_camera_params

    def eval(self, order=True, repeat_per_scene=1):
        """
        Set the manager to evaluation mode. This will reset the scenario index to start and optionally shuffle the scenarios.

        Args:
            order: If True, scenarios will be evaluated in order. If False, scenarios will be shuffled.
            repeat_per_scene: Number of times to repeat each scenario before moving to the next one.
        """
        self.current_scenario_id = self.start_scenario_index - 1  # Reset to before the first scenario
        self.remain_queue = [idx for _ in range(repeat_per_scene) for idx in range(self.num_scenarios)]  # Create a queue of scenario indices based on repeat_per_scene
        self.random_scenario = not order
        self.eval_mode = True

    def read_metadata(self, loader):
        self.metadata, self.idx2scene = {}, []
        self.num_scenarios = 0
        for cfg_path in self.scene_config_list:
            scene_name, metadata = self._load_single_scene(cfg_path)
            self.metadata[scene_name] = metadata
            self.idx2scene.append(scene_name)
            self.num_scenarios += 1

    def hotload_scenario(self, scenario_id):
        cfg_path = self.scene_config_list[scenario_id]
        scene_name, metadata = self._load_single_scene(cfg_path)
        old_scene_name = self.idx2scene[scenario_id]
        if old_scene_name is not None and old_scene_name != scene_name:
            self.metadata.pop(old_scene_name)
        self.idx2scene[scenario_id] = scene_name
        self.metadata[scene_name] = metadata
        return scene_name

    def hotload_scene_name(self, scene_name):
        if scene_name in self.idx2scene:
            return self.idx2scene.index(scene_name)

        for scenario_id in range(self.num_scenarios):
            if self.idx2scene[scenario_id] is not None:
                continue
            loaded_scene_name = self.hotload_scenario(scenario_id)
            if loaded_scene_name == scene_name:
                return scenario_id

        raise ValueError(f"Scene not found: {scene_name}")

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
        if self.eval_mode :
            if self.remain_queue:
                self.current_scenario_id = self.remain_queue.pop(0)
            else:
                raise LookupError("No more scenarios to evaluate.")
            
        elif scene_name is not None:
            if self.hotload:
                self.current_scenario_id = self.hotload_scene_name(scene_name)
            else:
                self.current_scenario_id = self.idx2scene.index(scene_name)
        elif self.random_scenario:
            self.current_scenario_id = self.np_random.randint(0, self.num_scenarios)
        else:
            self.current_scenario_id = (self.current_scenario_id + 1) % self.num_scenarios

        if self.hotload and self.idx2scene[self.current_scenario_id] is None:
            self.hotload_scenario(self.current_scenario_id)

        self.current_config = self.base_config.copy()

        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 

        current_metadata = self.get_current_scenario_data()
        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 
        current_metadata = self.get_current_scenario_data()
        ego_poses = current_metadata['ego_poses']
        # average_ego_height =  np.mean([pose[2][3] for pose in ego_poses.values()])
        start_ts = current_metadata['timestamp_range'][0]
        start_ego_height = ego_poses[start_ts][2][3]
        ground_height = start_ego_height - config_dict["controller"].DEFAULT_HEIGHT / 2 + 0.1
        current_metadata['ground_plane'] = {
            'normal': [0, 0, 1],
            'constant': ground_height
        }
        # current_metadata['ground_plane'] = self._build_ground_plane(
        #     ego_poses,
        #     ego_height=config_dict["controller"].DEFAULT_HEIGHT,
        #     start_ts=start_ts
        # )
    def get_current_scenario_data(self):
        return self.get_scenario_data(self.current_scenario_id)

    def get_scenario_data(self, i, should_copy=False):
        assert 0 <= i < self.num_scenarios, \
            "scenario index exceeds range, scenario index: {}, worker_index: {}".format(i, self.worker_index)
        if self.hotload and self.idx2scene[i] is None:
            self.hotload_scenario(i)
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
            file_path = self.scene_config_list[scenario_id]
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
