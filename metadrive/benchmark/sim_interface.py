# Simulator Interface for Gaussian Splatting Integration
import yaml
import numpy as np
import logging
import torch
import os
import json

from render_essentials import render_frame, load_from_ply

LOGGER = logging.getLogger(__name__)

Xfront2Y = np.array([
    [ 0., -1.,  0., 0.],
    [ 1.,  0.,  0., 0.],
    [ 0. , 0.,  1., 0.],
    [ 0., 0.,  0., 1.]
])

class SharpVideoSimulatorInterface:
    def __init__(self, zNear=0.0001, zFar=1000):
        """
        __init__
        
        :param zNear: (float): Near clipping plane distance
        :param zFar: (float): Far clipping plane distance
        """
        self.zNear = zNear
        self.zFar = zFar
        self.current_timestamp = 0

        # Rendering related data
        self.end_timestamp = None
        self.fg_gaussians_path = None # fg_gaussians_path/frame_XXXXXX.ply
        self.bg_gaussians_path = None # ply path to background model
        self.fg_gaussians = None
        self.bg_gaussians = None
        self.bg_gaussians_back = None

    def load_metadata(self, cfg_path) -> tuple:
        """
        load_metadata 

        :param cfg_path: config path of a single scene config file. Use this to identify which scene to load.
        :return: tuple of (scene_name, cfg, timestamp_range, camera_params, ego_poses, tracking_data, bk_ground_model_path)
        :rtype: tuple
        """
        LOGGER.info("Loading scene configuration from %s", cfg_path)

        with open(cfg_path, 'r') as f:
            cfg_text = yaml.safe_load(f)
        
        scene_name = cfg_text['scene_name']
        timestamp_range = [cfg_text['start_time'], cfg_text['end_time']]
        self.end_timestamp = cfg_text['end_time']

        camera_rig_config = cfg_text['camera_rig_config']
        camera_params = self._load_camera_rig(camera_rig_config)
        cfg_text['camera_params'] = camera_params

        c2w_path = cfg_text['c2w_path']
        ego_poses = self._load_ego_pose(c2w_path)
        cfg_text['ego_poses'] = ego_poses
        
        with open(cfg_text['tracking_data_path'], 'r') as f:
            tracking_data = json.load(f)
        
        # Scale timestamps to microseconds
        for obj_id in tracking_data:
            new_poses = {}
            for ts_str, pose in tracking_data[obj_id]['poses'].items():
                ts_us = int(int(ts_str) * 100000) # 1/10 seconds to microseconds

                # The loaded size: (x, y, z) <-> (w, l, h).
                # Convert from x front to y front
                #   The loaded pose assumes x front, which is consistent with Bullet.
                #   StreetGaussian expects y front, since StreetGaussian handles y front to x front internally for Bullet simulation.
                #   The pose passed to Bullent is finally: pose = pose @ Xfornt2Y @ Yfront2X = pose
                new_poses[ts_us] = np.array(pose) @ Xfront2Y
            
            tracking_data[obj_id]['poses'] = new_poses

            # StreetGaussian expects (l,w,h) as size order.
            tracking_data[obj_id]['size'] = [tracking_data[obj_id]['size'][i] * 0.7 for i in [1, 0, 2]] # (w,l,h) -> (l,w,h)
            # print([s * 0.1 for s in tracking_data[obj_id]['size']])
        # tracking_data = {}

        bk_ground_model_path = None

        return scene_name, cfg_text, timestamp_range, camera_params, ego_poses, tracking_data, bk_ground_model_path
    
    def load_model(self, cfg):
        """
        load_model
            - Initialize rendering pipeline
            - Identify the scene from cfg
            - Load the pre-trained Gaussian model weights for this specific scene
            - prepare GPU/CUDA resources
        :param cfg: Configuration object for a specific scene.
        """
        LOGGER.info("Loading simulation model with given configuration")
        # Load foreground and background Gaussian models
        self.fg_gaussians_path = cfg['fg_gaussians_path']
        self.bg_gaussians_path = cfg['bg_gaussians_path']

        # Round to nearest timestamp at interval of 100_000 microseconds
        rounded_timestamp = min(self.current_timestamp - (self.current_timestamp % 100000), self.end_timestamp) if self.current_timestamp % 100000 < 50000 else min(self.current_timestamp + (100000 - self.current_timestamp % 100000), self.end_timestamp)
        rounded_timestamp = int(rounded_timestamp // 100000)
        
        LOGGER.info("   -> Loading foreground Gaussians from %s at timestamp %d", self.fg_gaussians_path, rounded_timestamp)
        fg_gaussians_file = f"{self.fg_gaussians_path}/frame_{rounded_timestamp:06d}.ply"
        self.fg_gaussians = load_from_ply(fg_gaussians_file).to(device='cuda')
        
        LOGGER.info("   -> Loading background Gaussians from %s", self.bg_gaussians_path)
        if os.path.isdir(self.bg_gaussians_path):
            self.bg_gaussians = load_from_ply(os.path.join(self.bg_gaussians_path, 'background_front.ply')).to(device='cuda')
            self.bg_gaussians_back = load_from_ply(os.path.join(self.bg_gaussians_path, 'background_back.ply')).to(device='cuda')
        else:
            self.bg_gaussians = load_from_ply(self.bg_gaussians_path).to(device='cuda')

        return None
    
    def update_scene(self, timestamp, object_poses):
        """
        update_scene
            - Update dynamic object poses in the scene
            - Prepare scene for rendering at the given timestamp

        :param timestamp: (int): Current timestamp
        :param object_poses: (dict): Current poses of dynamic objects
        """
        # MARK: Time stamp here seems 1 indexed.
        new_timestamp = timestamp - 100000 if timestamp - 100000 >= 0 else 0
        if new_timestamp == self.current_timestamp:
            return
        self.current_timestamp = new_timestamp

        # Round to nearest timestamp at interval of 100_000 microseconds
        print("Current timestamp: ", self.current_timestamp)
        rounded_timestamp = min(self.current_timestamp - (self.current_timestamp % 100000), self.end_timestamp) if self.current_timestamp % 100000 < 50000 else min(self.current_timestamp + (100000 - self.current_timestamp % 100000), self.end_timestamp)
        rounded_timestamp = int(rounded_timestamp // 100000)
        
        fg_gaussians_file = f"{self.fg_gaussians_path}/frame_{rounded_timestamp:06d}.ply"
        # LOGGER.info("   -> Updating foreground Gaussians to timestamp %d, from %s", rounded_timestamp, fg_gaussians_file)
        self.fg_gaussians = load_from_ply(fg_gaussians_file).to(device='cuda')
    
    def render(self, K, H, W, extrinsics, timestamp_us=None, meta=None) -> np.ndarray:
        """
        render
            - Render the scene from the given camera parameters
            - Return rendered images and depth maps

        :param K: (torch.Tensor or list): 3x3 camera intrinsic matrix
        :param H: (int): Image height in pixels
        :param W: (int): Image width in pixels
        :param extrinsics: (torch.Tensor or list): 4x4 "camera-to-world" transformation matrix
        :return: Rendered RGB image of shape (H, W, 3) with values in range [0, 255] (uint8) or [0.0, 1.0] (float32)
        :rtype: np.ndarray
        """

        if timestamp_us is not None and timestamp_us != self.current_timestamp:
            self.update_scene(timestamp_us, object_poses={})
            # LOGGER.info("Rendering at specified timestamp %d", timestamp_us)
        # Prepare intrinsics, extrinsics, width, height
        if isinstance(K, list):
            intrinsics_4x4 = torch.eye(4).float()
            intrinsics_4x4[0:3, 0:3] = torch.tensor(K).float()
        else:
            intrinsics_4x4 = torch.eye(4).float()
            intrinsics_4x4[0:3, 0:3] = K.float()
        
        if isinstance(extrinsics, list):
            extrinsics_4x4 = torch.tensor(extrinsics).float()
        else:
            extrinsics_4x4 = extrinsics.float()
        
        # StreetGaussian uses z up, while gaussians are in -y up.
        axes_transformation = np.array([
            [0, 0, 1, 0],
            [-1, 0, 0, 0],
            [0, -1, 0, 0],
            [0, 0, 0, 1]
        ])

        extrinsics_4x4 = torch.tensor(np.linalg.inv(axes_transformation)).float() @ extrinsics_4x4

        if self.bg_gaussians_back is not None and meta is not None and meta.get("render_gaussian", "front") == "back":
            # Back cameras
            rendering_result = render_frame(
                fg_gaussians=self.fg_gaussians,
                bg_gaussians=self.bg_gaussians_back,
                intrinsics=intrinsics_4x4.to(device='cuda'),
                extrinsics=torch.inverse(extrinsics_4x4).to(device='cuda'),
                width=W,
                height=H,
            )
        else:
            rendering_result = render_frame(
                fg_gaussians=self.fg_gaussians,
                bg_gaussians=self.bg_gaussians,
                intrinsics=intrinsics_4x4.to(device='cuda'),
                extrinsics=torch.inverse(extrinsics_4x4).to(device='cuda'),
                width=W,
                height=H,
            )

        return rendering_result['rgb']

    def _load_camera_rig(self, camera_rig_config):
        """Load camera intrinsics and extrinsics from the rig file."""
        camera_rig_path = camera_rig_config['camera_rig_path']
        camera_rig_type = camera_rig_config.get('camera_rig_type', None)
        front = camera_rig_config.get('front_camera', None)
        Hs = camera_rig_config.get('Hs', None)
        Ws = camera_rig_config.get('Ws', None)

        LOGGER.info("Loading camera parameters from %s", camera_rig_path)
        cameras_data = np.load(camera_rig_path)
        
        if "intrinsics" not in cameras_data or "extrinsics" not in cameras_data:
            raise ValueError("cameras.npz must contain 'intrinsics' and 'extrinsics' arrays")
        
        intrinsics_array = cameras_data["intrinsics"]
        c2e_array = cameras_data["extrinsics"]
        
        # Apply coordinate transformations (same as predict_multicam_combined.py)
        if camera_rig_type == "waymo-e2e":
            axes_transformation = np.array([
                [0, -1, 0, 0],
                [0, 0, -1, 0],
                [1, 0, 0, 0],
                [0, 0, 0, 1]
            ])
            
            c2e_array = np.linalg.inv(
                np.array([[0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) @ 
                np.array([[0, 0, 1, 0], [0, 1, 0, 0], [-1, 0, 0, 0], [0, 0, 0, 1]])
            ) @ c2e_array @ np.linalg.inv(axes_transformation)
        
        self.num_cameras = len(intrinsics_array)

        LOGGER.info("   -> Found %d cameras in rig", self.num_cameras)
    
        camera_param_dict = {} # camera_name -> ("K_3x3", "H", "W", "ego2camera")

        for cam_idx in range(self.num_cameras):
            intrinsics = intrinsics_array[cam_idx]
            c2e = c2e_array[cam_idx]
            K_3x3 = np.array([[intrinsics[0, 0], 0, intrinsics[0, 2]],
                              [0, intrinsics[1, 1], intrinsics[1, 2]],
                              [0, 0, 1]])
            H = Hs[cam_idx]
            W = Ws[cam_idx]

            ego2camera = np.linalg.inv(c2e)
            assert K_3x3.shape == (3, 3) and ego2camera.shape == (4, 4)
            camera_param_dict[f"camera_{cam_idx}"] = {
                "K": K_3x3,
                "H": H,
                "W": W,
                "ego2camera": ego2camera.astype(np.float32),
                "meta":
                    {
                        "render_gaussian": "front" if cam_idx in front else "back",
                        "camera_rig_type": camera_rig_type
                    }
            }
        return camera_param_dict
    
    def _load_ego_pose(self, c2w_path):
        """Load ego poses from a given path."""
        LOGGER.info("Loading ego poses from %s", c2w_path)
        c2w_data = np.load(c2w_path, allow_pickle=True).item()
        
        num_frames = len(c2w_data)
        timestamp_interval = 100_000 # 100_000 microseconds interval

        LOGGER.info("   -> Found %d frames in c2w data", num_frames)
        LOGGER.info("   -> Assume %d microseconds interval between frames", timestamp_interval)

        # StreetGaussian uses z up, while gaussians are in -y up.
        axes_transformation = np.array([
            [0, 0, 1, 0],
            [-1, 0, 0, 0],
            [0, -1, 0, 0],
            [0, 0, 0, 1]
        ])

        ego_poses = {} # timestamp -> 4x4 pose matrix
        for frame_idx in range(num_frames):
            timestamp = frame_idx * timestamp_interval
            # print(c2w_data[f'{frame_idx:06d}'].shape)
            c2w = c2w_data[f'{frame_idx:06d}']
            c2w = axes_transformation @ c2w['e2w']
            ego_poses[timestamp] = c2w.astype(np.float32)
        return ego_poses