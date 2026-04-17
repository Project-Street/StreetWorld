"""
StreetStudio Map Manager for handling StreetStudio scenarios.

This module extends ScenarioMapManager to work without a separate map loader,
as StreetStudio loads all data (including map) from transforms.json.
"""

from streetworld.manager.scenario_map_manager import ScenarioMapManager
from streetworld.component.terrain.ground import GroundPlane
from streetworld.component.terrain.mesh_terrain import MeshTerrain


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
        We always use an infinite ground plane for StreetStudio scenarios.
        """
        self.config = config
        self.current_sdc_route = None
        self.sdc_dest_point = None

        # Skip vec_map loading (not used in StreetStudio)
        vec_map = None

        # Always use infinite ground plane (ignore scene_mesh_path)
        plane_params = kwargs['ground_plane']
        normal = plane_params.get('normal')
        constant = plane_params.get('constant')
        self.spawn_object(
            GroundPlane,
            physics_world=physics_world,
            direction=normal,
            constant=constant,
            random_seed=self.random_seed
        )

        return vec_map
