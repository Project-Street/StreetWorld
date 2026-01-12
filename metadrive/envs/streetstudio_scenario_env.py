"""
StreetStudio Scenario Environment for MetaDrive.

This environment extends ScenarioEnv to directly load data from StreetStudio's
transforms.json format without requiring a separate SimulatorInterface.
"""

from metadrive.envs.scenario_env import ScenarioEnv
from metadrive.manager.scenario_data_manager import ScenarioDataManager
from metadrive.manager.scenario_map_manager import ScenarioMapManager
from metadrive.manager.streetstudio_data_manager import StreetStudioDataManager
from metadrive.manager.agent_manager import AgentManager
from metadrive.engine.core.physics_world import PhysicsWorld
from metadrive.engine.step_counter import StepCounter
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
        self._register_manager("map_manager", ScenarioMapManager(config['map_config'], None))

        # Create step manager
        self._register_manager(
            "step_manager",
            StepCounter(config['physics_world_step_size'] * config["decision_repeat"])
        )

        # Physics world
        self.physics_world = PhysicsWorld(disable_collision=config["disable_collision"])

        # Collision callback
        self.physics_world.dynamic_world.setContactAddedCallback(
            PythonCallbackObject(collision_callback)
        )

        # Initialize agent manager
        self.agent_managers = {}
        self.agent_managers['actor'] = self._init_agent_manager()
