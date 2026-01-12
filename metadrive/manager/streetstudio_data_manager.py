"""
StreetStudio Data Manager for loading StreetStudio format (transforms.json).

This module extends ScenarioDataManager to directly parse transforms.json
files produced by StreetStudio's ConvertToStreetStudio class.
"""

import json
from pathlib import Path

from metadrive.manager.scenario_data_manager import ScenarioDataManager
from metadrive.utils.streetstudio_utils import sec_to_us, parse_instances_data


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
        with open(transforms_path, 'r') as f:
            data = json.load(f)

        # Extract scene name (use filename if not provided)
        scene_name = data.get("scene_name", transforms_path.parent.name)

        # Convert ego_poses: {sec: pose_4x4} -> {us: pose_4x4}
        ego_poses = {
            sec_to_us(float(ts)): pose
            for ts, pose in data["sim_data"]["egos_data"].items()
        }

        # Get timestamp range
        timestamps = sorted(ego_poses.keys())
        timestamp_range = [timestamps[0], timestamps[-1]]

        # Camera parameters - direct mapping
        camera_params = data["sim_data"]["cameras_data"]

        # Convert instances_data -> tracking_data
        tracking_data = parse_instances_data(data["instances_data"])

        # Create config object
        cfg = {
            "scene_name": scene_name,
            "transforms_json_path": str(transforms_path)
        }

        # Background mesh (optional)
        mesh_path = data.get("ply_file_path")
        if mesh_path:
            mesh_path = str(transforms_path.parent / mesh_path)
        else:
            mesh_path = None

        return (
            scene_name,
            cfg,
            timestamp_range,
            camera_params,
            ego_poses,
            tracking_data,
            mesh_path
        )

    @property
    def num_scenarios(self):
        """Always 1 for StreetStudioDataManager (single file)"""
        return 1

    def read_metadata(self, loader):
        """Override to use the internal loader"""
        self.metadata, self.idx2scene = {}, []
        self.num_scenarios = 1

        scene_name, cfg, timestamp_range, camera_params, ego_poses, tracking_data, mesh_path = loader(
            None  # cfg_path not needed
        )

        # Restructure metadata using parent class method
        self.metadata[scene_name] = self.restructure_metadata(
            config=cfg,
            timestamp_range=timestamp_range,
            camera_params=camera_params,
            ego_poses=ego_poses,
            participants=tracking_data,
        )
        self.metadata[scene_name]['scene_mesh_path'] = mesh_path
        self.idx2scene.append(scene_name)
