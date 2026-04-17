"""
StreetStudio Data Manager for loading StreetStudio format (transforms.json).

This module extends ScenarioDataManager to directly parse transforms.json
files produced by StreetStudio's ConvertToStreetStudio class.
"""

import json
from pathlib import Path
import numpy as np

from streetworld.manager.scenario_data_manager import ScenarioDataManager
from streetworld.utils.streetstudio_utils import sec_to_us, us_to_sec, parse_instances_data, SceneTransform


class StreetStudioDataManager(ScenarioDataManager):
    """Data manager for loading StreetStudio format (transforms.json)"""

    def __init__(self, config, loader=None):
        """
        Initialize StreetStudioDataManager.

        Args:
            config: Configuration dict containing 'transforms_json_path'
            loader: Not used, kept for compatibility with parent class
        """
        self.transforms_json_path = config.get("transforms_json_path")

        if not self.transforms_json_path:
            raise ValueError("transforms_json_path must be provided in config")

        # Use the internal loading function as the loader
        super().__init__(config, self._load_from_transforms_json)

    def _load_from_transforms_json(self, cfg_path):
        """
        Load metadata directly from transforms.json.

        Args:
            cfg_path: Path to config file (not used, kept for compatibility)

        Returns:
            Tuple of (scene_name, cfg, timestamp_range, camera_params,
                     ego_poses, tracking_data, mesh_path)
        """
        transforms_path = Path(self.transforms_json_path)

        # Read transforms.json
        with open(transforms_path, "r") as f:
            data = json.load(f)

        # Extract scene name (use filename if not provided)
        scene_name = data.get("scene_name", transforms_path.parent.name)

        # Convert ego_poses: {sec: pose_4x4} -> {us: pose_4x4}
        ego_poses = {sec_to_us(float(ts)): np.array(pose) for ts, pose in data["sim_data"]["egos_data"].items()}

        # Get timestamp range from ego_poses
        timestamps = sorted(ego_poses.keys())
        original_start, original_end = timestamps[0], timestamps[-1]

        # Apply time range filtering if specified in config
        time_start_sec = self.base_config.get("time_start_sec")
        time_end_sec = self.base_config.get("time_end_sec")

        if time_start_sec is not None or time_end_sec is not None:
            # Convert to microseconds
            requested_start = sec_to_us(time_start_sec) if time_start_sec is not None else original_start
            requested_end = sec_to_us(time_end_sec) if time_end_sec is not None else original_end

            # Clip to available range and warn if needed
            clipped = False
            if requested_start < original_start:
                requested_start = original_start
                clipped = True
            if requested_end > original_end:
                requested_end = original_end
                clipped = True

            if clipped:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Time range clipped to available data: "
                    f"[{us_to_sec(original_start):.2f}s, {us_to_sec(original_end):.2f}s]"
                )

            timestamp_range = [requested_start, requested_end]
        else:
            # Use full range
            timestamp_range = [original_start, original_end]

        # Filter ego_poses to only include timestamps in range
        start_ts, end_ts = timestamp_range
        ego_poses = {
            ts: pose for ts, pose in ego_poses.items()
            if start_ts <= ts < end_ts
        }

        # Camera parameters - normalize format for GaussianObservation
        # Convert list format to torch.Tensor for ego2camera and K
        camera_params = {}
        for cam_name, cam_data in data["sim_data"]["cameras_data"].items():
            normalized_cam = {
                "H": cam_data["H"],
                "W": cam_data["W"],
            }

            # Convert K from list to numpy array (will be converted to torch.Tensor by GaussianObservation)
            if "K" in cam_data:
                K = cam_data["K"]
                if isinstance(K, list):
                    normalized_cam["K"] = np.array(K, dtype=np.float32)
                else:
                    normalized_cam["K"] = K

            # Convert ego2camera from list to numpy array (will be converted to torch.Tensor by GaussianObservation)
            if "ego2camera" in cam_data:
                ego2cam = cam_data["ego2camera"]
                if isinstance(ego2cam, list):
                    normalized_cam["ego2camera"] = np.array(ego2cam, dtype=np.float32)
                else:
                    normalized_cam["ego2camera"] = ego2cam

            camera_params[cam_name] = normalized_cam

        # Convert instances_data -> tracking_data
        tracking_data = parse_instances_data(data["instances_data"])

        # Create config object
        cfg = {"scene_name": scene_name, "transforms_json_path": str(transforms_path)}

        # Background mesh (optional)
        mesh_path = data.get("ply_file_path")
        if mesh_path:
            mesh_path = str(transforms_path.parent / mesh_path)
        else:
            mesh_path = None

        # Extract dataset_transforms for coordinate conversion
        dataset_transforms = data.get("dataset_transforms")

        return (
            scene_name,
            cfg,
            timestamp_range,
            camera_params,
            ego_poses,
            tracking_data,
            mesh_path,
            dataset_transforms,
        )

    @property
    def num_scenarios(self):
        """Always 1 for StreetStudioDataManager (single file)"""
        return 1

    def read_metadata(self, loader):
        """Override to use the internal loader"""
        self.metadata, self.idx2scene = {}, []

        scene_name, cfg, timestamp_range, camera_params, ego_poses, tracking_data, mesh_path, dataset_transforms = (
            loader(
                None  # cfg_path not needed
            )
        )

        # Store dataset_transforms for rendering coordinate conversion
        self._dataset_transforms = dataset_transforms

        # Filter tracking data (participants) by time range
        # This is done after coordinate transform but before metadata restructuring
        time_start_sec = self.base_config.get("time_start_sec")
        time_end_sec = self.base_config.get("time_end_sec")

        if time_start_sec is not None or time_end_sec is not None:
            # Get filtered timestamp range from ego_poses
            timestamps = sorted(ego_poses.keys())
            if len(timestamps) > 0:
                start_ts = timestamps[0]
                end_ts = timestamps[-1]

                # Filter each participant's poses
                for uid, participant in tracking_data.items():
                    participant["poses"] = {
                        ts: pose for ts, pose in participant["poses"].items()
                        if start_ts <= ts < end_ts
                    }

        # Apply inverse transform to poses: normalized -> real (for simulation)
        if dataset_transforms:
            transform = SceneTransform(**dataset_transforms)

            # Transform ego poses
            for ts in ego_poses.keys():
                ego_poses[ts] = transform.apply_extrinsic(ego_poses[ts], reverse=True)

            # Transform participant poses
            for uid, participant in tracking_data.items():
                for ts in participant["poses"].keys():
                    participant["poses"][ts] = transform.apply_extrinsic(participant["poses"][ts], reverse=True)

                participant["size"] = [x / transform.scaling for x in participant["size"]]

            # Transform camera poses
            for cam_name in camera_params:
                cam2ego = np.linalg.inv(camera_params[cam_name]["ego2camera"])
                cam2ego[:3, 3] /= transform.scaling
                camera_params[cam_name]["ego2camera"] = np.linalg.inv(cam2ego)

        # Restructure metadata using parent class method
        self.metadata[scene_name] = self.restructure_metadata(
            config=cfg,
            timestamp_range=timestamp_range,
            camera_params=camera_params,
            ego_poses=ego_poses,
            participants=tracking_data,
        )
        self.metadata[scene_name]["scene_mesh_path"] = mesh_path
        self.idx2scene.append(scene_name)

    @property
    def dataset_transforms(self):
        """Get dataset transforms for rendering coordinate conversion."""
        return getattr(self, "_dataset_transforms", None)
