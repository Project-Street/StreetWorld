import copy
import numpy as np
import torch
from streetworld.manager.base_manager import BaseManager
from streetworld.utils.scenario_utils import parse_object_state
from streetworld.component.vehicle.vehicle_type import random_vehicle_type
from streetworld.utils.trajectory import Trajectory
import json

from streetworld.configs.default_config import BASE_DEFAULT_CONFIG

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
        scene_ids = self.base_config["scene_ids"]
        if not isinstance(scene_ids, list):
            raise TypeError(f"scene_ids must be a list, got {type(scene_ids).__name__}")
        self.scene_ids = scene_ids

        self.start_scenario_index = self.base_config.get("start_scenario_index", 0)
        self.random_scenario = self.base_config.get("random_scenario", True)
        self.current_scene_index = self.start_scenario_index - 1

        # for multi-worker
        # self._scenarios = {}
        self.num_scenarios = len(self.scene_ids)


        # sort scenario for curriculum training
        self.scenario_difficulty = None
        # self.sort_scenarios()

        # stat
        # self.coverage = [0 for _ in range(self.num_scenarios)]

    def _post_process_config(self, config):
        pass

    def _load_scene(self, scene_id):
        (
            timestamp_range,
            camera_params,
            ego_poses,
            participants,
            scene_mesh_path,
            scene_mesh_transform,
        ) = self.loader(scene_id)
        ego_poses, camera_params = self._calibrate_ego_z(ego_poses, camera_params)
        metadata = self.restructure_metadata(
            scene_id=scene_id,
            timestamp_range=timestamp_range,
            camera_params=camera_params,
            ego_poses=ego_poses,
            participants=participants,
        )
        metadata["scene_mesh_path"] = scene_mesh_path
        metadata["scene_mesh_transform"] = scene_mesh_transform
        return metadata

    def _ego_vehicle_height(self):
        actor_config = self.base_config["actor_config"]
        vehicle_size = actor_config["controller_config"]["size"]
        if vehicle_size is not None:
            return float(vehicle_size[2])
        return float(actor_config["controller"].DEFAULT_HEIGHT)

    def _calibrate_ego_z(self, ego_poses, camera_params):
        ego_z_height = float(self.base_config.get("ego_z_height", 0))
        ego_origin_delta = np.eye(4, dtype=np.float32)
        ego_origin_delta[2, 3] = self._ego_vehicle_height() / 2 - ego_z_height

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
        self.current_scene_index = self.start_scenario_index - 1  # Reset to before the first scenario
        self.remain_queue = [idx for _ in range(repeat_per_scene) for idx in range(self.num_scenarios)]  # Create a queue of scenario indices based on repeat_per_scene
        self.random_scenario = not order
        self.eval_mode = True

    def restructure_metadata(self, scene_id, timestamp_range, camera_params, ego_poses, participants):
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
            'scene_id': scene_id,
            'camera_params':camera_params,
            'ego_poses': ego_poses,
            'participants': participants,
            'init_state': init_state,
            "agent_state": agent_state,
            'timestamp_range': timestamp_range
        }

    def reset(self, scene_id=None):
        """
        Reset scenario data manager.

        Args:
            scene_id: ID of the scene to load.
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
                self.current_scene_index = self.remain_queue.pop(0)
            else:
                raise LookupError("No more scenarios to evaluate.")
            
        elif scene_id is not None:
            self.current_scene_index = self.scene_ids.index(scene_id)
        elif self.random_scenario:
            self.current_scene_index = self.np_random.randint(0, self.num_scenarios)
        else:
            self.current_scene_index = (self.current_scene_index + 1) % self.num_scenarios

        self.current_config = self.base_config.copy()

        config_dict=self.current_config["actor_config"]
        config_dict["controller"] = config_dict.get("controller", random_vehicle_type(self.np_random)) 

        scene_id = self.scene_ids[self.current_scene_index]
        self.current_metadata = self._load_scene(scene_id)
        current_metadata = self.current_metadata
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
        return self.current_metadata

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

        def _score(scene_index):
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
