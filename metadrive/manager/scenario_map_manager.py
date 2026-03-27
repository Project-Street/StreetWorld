import copy
import numpy as np

from metadrive.component.terrain.chunked_ground import ChunkedGroundTerrain
from metadrive.component.terrain.ground import GroundPlane
from metadrive.component.terrain.mesh_terrain import MeshTerrain
from metadrive.constants import DEFAULT_AGENT
from metadrive.manager.base_manager import BaseManager
from metadrive.utils.logger import get_logger, set_log_level
logger = get_logger()


class ScenarioMapManager(BaseManager):
    PRIORITY = 0  # Map update has the most high priority
    DEFAULT_DATA_BUFFER_SIZE = 200

    def __init__(self, config, loader):
        super(ScenarioMapManager, self).__init__()
        self.config = config
        self.store_map = self.config.get("store_map", False)
        self.current_map = None

        # we put the route searching function here
        self.sdc_start_point = None
        self.sdc_destinations = []
        self.sdc_dest_point = None
        self.current_sdc_route = None

        self.loader = loader
        self.ground = None

    def reset(self, config, scene_config, physics_world, scene_mesh_path, **kwargs):
        self.config = config
        self.current_sdc_route = None
        self.sdc_dest_point = None

        vec_map = self.loader(scene_config)

        if not scene_mesh_path:
            plane_params = kwargs.get('ground_plane', {})
            self._spawn_ground_from_plane_params(physics_world=physics_world, plane_params=plane_params)
        else:   
            self.spawn_object(
                MeshTerrain,
                model_path=scene_mesh_path,
                physics_world=physics_world,
                random_seed=self.random_seed
            )
        
        return vec_map

    def clear_object(self, object_id):
        obj = self.spawned_objects.pop(object_id)
        obj.destroy()  

    def _spawn_ground_from_plane_params(self, physics_world, plane_params):
        plane_params = plane_params or {}
        plane_mode = str(plane_params.get("type", plane_params.get("mode", "single"))).lower()
        chunks = plane_params.get("chunks") or []
        mode_unspecified = ("type" not in plane_params) and ("mode" not in plane_params)
        use_chunked = len(chunks) > 0 and (plane_mode in {"chunked", "chunks", "piecewise"} or mode_unspecified)

        if use_chunked:
            try:
                self.spawn_object(
                    ChunkedGroundTerrain,
                    physics_world=physics_world,
                    chunks=chunks,
                    random_seed=self.random_seed,
                )
                return
            except Exception as e:
                logger.warning("Failed to spawn chunked ground terrain: %s. Falling back to single plane.", e)

        normal = np.asarray(plane_params.get('normal', [0.0, 0.0, 1.0]), dtype=float)
        normal_norm = np.linalg.norm(normal)
        if normal_norm > 1e-6:
            normal = normal / normal_norm
        else:
            normal = np.array([0.0, 0.0, 1.0], dtype=float)
        constant = float(plane_params.get('constant', 0.0))
        self.spawn_object(
            GroundPlane,
            physics_world=physics_world,
            direction=normal.tolist(),
            constant=constant,
            random_seed=self.random_seed
        )


    def destroy(self):
        self.clear_stored_maps()
        self._stored_maps = None
        self.current_map = None

        self.sdc_start_point = None
        self.sdc_destinations = []
        self.sdc_dest_point = None
        self.current_sdc_route = None

        super(ScenarioMapManager, self).destroy()
    
    def clear_stored_maps(self):
        for m in self._stored_maps.values():
            if m is not None:
                m.detach_from_world()
                m.destroy()
        self._stored_maps = {
            i: None
            for i in range(self.start_scenario_index, self.start_scenario_index + self.map_num)
        }
