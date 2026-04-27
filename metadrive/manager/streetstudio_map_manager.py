"""
StreetStudio Map Manager for handling StreetStudio scenarios.

This module extends ScenarioMapManager to work without a separate map loader,
as StreetStudio loads all data (including map) from transforms.json.
"""

from metadrive.manager.scenario_map_manager import ScenarioMapManager


class StreetStudioMapManager(ScenarioMapManager):
    """
    Map manager for StreetStudio scenarios.

    Unlike ScenarioMapManager, this doesn't require a separate loader function
    since all map data is already loaded by StreetStudioDataManager.
    """

    def __init__(self, config):
        """
        Initialize StreetStudioMapManager.

        Args:
            config: Configuration dict
        """
        # Pass None as loader since we don't need it
        super().__init__(config, loader=None)

    def reset(self, config, scene_config, physics_world, scene_mesh_path, **kwargs):
        """
        Reset map manager for StreetStudio scenario.

        Since StreetStudio doesn't use vector maps (only mesh terrain),
        we override this to skip the loader call.

        Note: scene_mesh_path (ply_file_path) contains point cloud data and is not used.
        Ground representation is chosen from plane_params.
        """
        self.config = config
        self.current_sdc_route = None
        self.sdc_dest_point = None

        # Skip vec_map loading (not used in StreetStudio)
        vec_map = None

        # scene_mesh_path is ignored for StreetStudio. Terrain type is chosen from plane_params.
        plane_params = kwargs.get('ground_plane', {})
        self._spawn_ground_from_plane_params(physics_world=physics_world, plane_params=plane_params)

        return vec_map
