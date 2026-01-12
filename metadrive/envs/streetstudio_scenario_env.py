"""
StreetStudio Scenario Environment for MetaDrive.

This environment extends ScenarioEnv to directly load data from StreetStudio's
transforms.json format without requiring a separate SimulatorInterface.
"""

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.manager.streetstudio_data_manager import StreetStudioDataManager
from metadrive.manager.streetstudio_map_manager import StreetStudioMapManager
from metadrive.manager.agent_manager import AgentManager
from metadrive.engine.core.physics_world import PhysicsWorld
from metadrive.engine.step_counter import StepCounter
from metadrive.component.vehicle.vehicle_type import get_vehicle_type
from metadrive.component.traffic_participants.pedestrian import Pedestrian
from metadrive.component.traffic_participants.cyclist import Cyclist
from metadrive.obs.observation_base import DummyObservation
from metadrive.policy.replay_policy import ReplayPolicy
from panda3d.core import PythonCallbackObject
from metadrive.engine.core.collision_callback import collision_callback


class StreetStudioScenarioEnv(ScenarioEnv):
    """
    StreetStudio-integrated ScenarioEnv.

    This environment directly loads data from transforms.json format
    without requiring a separate SimulatorInterface or config files.

    Config requirements:
        - transforms_json_path: path to transforms.json file

    Example:
        >>> config = {
        ...     "transforms_json_path": "/path/to/transforms.json",
        ... }
        >>> env = StreetStudioScenarioEnv(config)
        >>> obs, info = env.reset()
    """

    def __init__(self, config=None):
        """
        Initialize StreetStudioScenarioEnv.

        Note: model parameter is not used (data loaded from transforms.json).
        We pass None as model to parent class.
        """
        # Pass None as model since we load data directly from transforms.json
        super().__init__(None, config)

    def setup(self, config):
        """
        Override setup to use StreetStudioDataManager.

        This replaces the default ScenarioDataManager with StreetStudioDataManager,
        which reads data directly from transforms.json files.
        """
        # Create StreetStudioDataManager (loads from transforms.json)
        self._register_manager("data_manager", StreetStudioDataManager(config))

        # Create map manager (no model.load_model needed)
        self._register_manager("map_manager", StreetStudioMapManager(config["map_config"]))

        # Create step manager
        self._register_manager(
            "step_manager", StepCounter(config["physics_world_step_size"] * config["decision_repeat"])
        )

        # Physics world
        self.physics_world = PhysicsWorld(disable_collision=config["disable_collision"])

        # Collision callback
        self.physics_world.dynamic_world.setContactAddedCallback(PythonCallbackObject(collision_callback))

        # Initialize agent manager
        self.agent_managers = {}
        self.agent_managers["actor"] = self._init_agent_manager()

    def close(self):
        """Close the environment and clean up resources."""
        if hasattr(self, "engine") and self.engine is not None:
            self.engine.close()

    def _update_scene(self):
        """
        Override to skip model.update_scene() since we use gRPC rendering.

        In StreetStudio mode, rendering is handled via gRPC calls from
        GaussianObservation, not via a local model.
        """
        # Still update agent states for physics simulation
        for name, mgr in self.agent_managers.items():
            mgr.update_state()
        # Skip self.model.update_scene() - rendering is handled via gRPC

    def _reset_agents(self, scenario_data, scene_map):
        """
        Reset agents with gRPC rendering function.

        Overrides parent class method to provide gRPC-based remote rendering
        instead of using self.model.render.
        """
        camera_params = scenario_data['camera_params']

        for name, init_state in scenario_data['init_state'].items():
            if name != 'actor':
                tracking = scenario_data['participants'][name]
                cfg = self.config['participant_config'].copy()
                cfg['controller_config']['size'] = tracking['size']
                if tracking['type'] == 'vehicle':
                    cfg['controller'] = get_vehicle_type(tracking['size'][1], False)
                elif tracking['type'] == 'pedestrian':
                    cfg['controller'] = Pedestrian
                elif tracking['type'] == 'cyclist':
                    cfg['controller'] = Cyclist

                self.agent_managers[name] = AgentManager(cfg, self.step_manager)
            else:
                cfg = self.config['actor_config']
                tracking = scenario_data['ego_poses']

            input_data = {
                'config': cfg,
                'physics_world': self.physics_world,
                'camera_params': camera_params,
                'init_state': init_state,
                'state': scenario_data['agent_state'][name],
                'timestamp_range': scenario_data['timestamp_range'],
                'trajdata_map': scene_map,
                'collector': self._collect_all_object
            }

            # Create gRPC render_fn for StreetStudio (self.model is None)
            if self.model is None:
                from metadrive.utils.streetstudio_utils import GRPCRenderClient

                render_server_url = self.config.get('render_server_url', 'localhost:50051')
                dataset_transforms = self.data_manager.dataset_transforms

                if dataset_transforms is None:
                    raise ValueError("dataset_transforms not found in metadata. "
                                     "Please ensure transforms.json contains 'dataset_transforms' field.")

                render_client = GRPCRenderClient(
                    server_url=render_server_url,
                    dataset_transforms=dataset_transforms
                )

                def render_fn(K, H, W, extrinsics, timestamp_us=0):
                    return render_client.render(K, H, W, extrinsics, timestamp_us)

                input_data['render_fn'] = render_fn
            else:
                # Fallback to parent class behavior
                input_data['render_fn'] = self.model.render

            if cfg['controller'] in [Pedestrian, Cyclist]:
                cfg['observer'] = DummyObservation
                cfg['policy'] = ReplayPolicy

            self.agent_managers[name].reset(**input_data)
