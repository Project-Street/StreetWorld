import gymnasium as gym
import numpy as np

from streetworld.objects.vehicle.base_vehicle import BaseVehicle
from streetworld.obs.observation_base import BaseObservation
import torch
from scipy.spatial.transform import Rotation as R

class GaussianObservation(BaseObservation):
    """
    Use only image info as input
    """
    REQUIRED_CAMERA_PARAM_KEYS = ("K", "H", "W", "ego2camera")

    def __init__(self, config):
        super().__init__(config)
        self.clip_rgb = config['clip_rgb']
        self.camera_configs = config.get('cameras', {})

    def reset(self, controller, render_fn, camera_params, **kwargs):
        """
        Clear frame
        :param env: StreetWorld
        :param vehicle: BaseVehicle
        :param step_mgr: StepManager for timestamp tracking
        :return: None
        """
        
        self.controller = controller
        self.render_fn = render_fn
        self.__build_camera_params(camera_params)

        dtype = np.float32 if self.clip_rgb else np.uint8
        self.state = {
            name: np.zeros(self.an_observation_shape(height, width), dtype=dtype)
            for name, height, width in zip(self.camera_names, self.params['H'], self.params['W'])
        }

    def __build_camera_params(self, _camera_params):
        if not self.camera_configs:
            for cam_name, params in _camera_params.items():
                missing = [key for key in self.REQUIRED_CAMERA_PARAM_KEYS if key not in params]
                if missing:
                    raise ValueError(f"Camera {cam_name} missing required params: {missing}")
        else:
            parsed_camera_params = {}
            R_ego2cam_base = np.array([
                [0, -1, 0],
                [0, 0, -1],
                [1, 0, 0]
            ], dtype=np.float32)

            for cam_name, cam_cfg in self.camera_configs.items():
                H = int(cam_cfg["H"])
                W = int(cam_cfg["W"])
                focal = float(cam_cfg["focal"])
                K = torch.tensor([
                    [focal, 0, W / 2.0],
                    [0, focal, H / 2.0],
                    [0, 0, 1]
                ], dtype=torch.float32)

                hpr = np.asarray(cam_cfg["hpr"], dtype=np.float32)
                hpr_rad = np.deg2rad(hpr)
                R_camera2ego = R.from_euler('ZYX', hpr_rad, degrees=False).as_matrix()
                R_final = np.asarray(R_ego2cam_base @ np.linalg.inv(R_camera2ego), dtype=np.float32)

                offset = np.asarray(cam_cfg["offset"], dtype=np.float32)
                translation = -np.asarray(R_final @ offset, dtype=np.float32)

                ego2camera = np.eye(4, dtype=np.float32)
                ego2camera[:3, :3] = R_final
                ego2camera[:3, 3] = translation

                parsed_camera_params[cam_name] = {
                    "K": K,
                    "H": H,
                    "W": W,
                    "ego2camera": torch.from_numpy(ego2camera)
                }
            _camera_params = parsed_camera_params

        self.camera_names = tuple(_camera_params)
        camera_params = tuple(_camera_params.values())
        self.params = {
            'K': torch.stack([torch.as_tensor(params['K'], dtype=torch.float32) for params in camera_params]),
            'H': [params['H'] for params in camera_params],
            'W': [params['W'] for params in camera_params],
        }
        self.ego_to_cameras = torch.stack([
            torch.as_tensor(params['ego2camera'], dtype=torch.float32) for params in camera_params
        ])
        extras = [params.get('extra') for params in camera_params]
        if any(extra is not None for extra in extras):
            self.params['extra'] = extras


    @property
    def observation_space(self):
        # sensor_cls = self.config["sensors"][self.image_source][0]
        # assert sensor_cls == "MainCamera" or issubclass(sensor_cls, BaseCamera), "Sensor should be BaseCamera"
        
        space = {}
        for name, height, width in zip(self.camera_names, self.params['H'], self.params['W']):
            shape = self.an_observation_shape(height, width)
            if self.clip_rgb:
                space[name] = gym.spaces.Box(-0.0, 1.0, shape=shape, dtype=np.float32)
            else:
                space[name] = gym.spaces.Box(0, 255, shape=shape, dtype=np.uint8)
        return space

    def an_observation_shape(self, h, w):
        return (1, h, w, 3)
 
    def observe(self):
        """
        Get the image Observation. By setting new_parent_node and the reset parameters, it can capture a new image from
        a different position and pose
        """
        ego_pose = torch.tensor(self.controller.transform).inverse()
        images = self.render_fn(**self.params, extrinsics=self.ego_to_cameras @ ego_pose)

        camera_info = {}
        for index, (cam_name, ret) in enumerate(zip(self.camera_names, images)):
            self.state[cam_name][0] = ret
            camera_info[cam_name] = {
                'ego2camera': self.ego_to_cameras[index].cpu().numpy().astype(np.float32),
                'K': self.params['K'][index].cpu().numpy().astype(np.float32),
                'H': self.params['H'][index],
                'W': self.params['W'][index]
            }
            if 'extra' in self.params and self.params['extra'][index] is not None:
                camera_info[cam_name]['extra'] = self.params['extra'][index]

        return {
            'camera_info': camera_info,
            'image': self.state
        }


    def destroy(self):
        """
        Clear memory
        """
        super(GaussianObservation, self).destroy()
        self.state = None
