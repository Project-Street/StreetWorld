import math
import numpy as np
from gymnasium.spaces import Space
from metadrive.utils.logger import get_logger
from metadrive.component.vehicle.base_vehicle import BaseVehicle
from metadrive.manager.base_manager import BaseManager
from metadrive.obs.navigation_obs import NavigationObservation
from metadrive.policy.idm_policy import IDMRouteInitializationError
from metadrive.policy.replay_policy import ReplayPolicy
from metadrive.policy.trajectory_idm_policy import TrajectoryIDMPolicy
logger = get_logger()


class AgentState:
    IDLE = "idle"
    NOT_SPAWN = "not_spawn"
    ALIVE = "alive"
    SUCCESS = "arrive_dest"
    OUT_OF_ROAD = "out_of_road"
    OUT_OF_STEP = "out_of_step"
    CRASH_VEHICLE = "crash_vehicle"
    CRASH_HUMAN = "crash_human"
    CRASH_OBJECT = "crash_object"
    CRASH_WORLD = "crash_world"

class AgentManager(BaseManager):
    """
    This class maintains a single vehicle agent in the environment.
    Simplified to handle only one vehicle object instead of multiple agents.

    Note:
    agent name: Single agent name (typically default_agent)
    object name: The unique name for the single vehicle object
    """
    INITIALIZED = False  # when vehicle instance is created, it will be set to True

    def __init__(self, config, step_manager):
        """
        The real init is happened in self.init(), in which super().__init__() will be called
        """
        """
        The real init is happened in self.init(), in which super().__init__() will be called
        """
        super().__init__()
        self.INITIALIZED = False
        self.max_step = config["max_step"]
        self.check_crash = config["check_crash"]


        # for getting {agent_id: BaseObject}, use agent_manager.active_agents
        self.config = config
        self.step_manager = step_manager
        self.observer = None
        self.policy = None
        self.step_action = None
        self.trajectory = None
        self.init_state = None
        self.trajdata_map = None
        self.out_of_road_threshold = float(config.get("policy_config", {}).get("out_of_road_threshold", 5))
        
    def lazy_init(self):
        self.observer = self.config['observer'](self.config['observer_config'])
        self.policy = self.config['policy'](step_manager=self.step_manager, config=self.config['policy_config'])
        self.INITIALIZED = True
        
    def reset(self, config=None, **kwargs):

        """
        Agent manager is really initialized after the BaseObject Instances are created
        """
        self.last_observation = None
        self.step_action = None
        if config is not None:
            self.config = config
        self.max_step = self.config["max_step"]
        self.check_crash = self.config["check_crash"]
        self.trajectory = kwargs["state"]
        self.init_state = kwargs["init_state"]
        self.trajdata_map = kwargs.get("trajdata_map")
        self.out_of_road_threshold = float(
            self.config.get("policy_config", {}).get("out_of_road_threshold", 5)
        )

        if not self.INITIALIZED:
            self.lazy_init()
        
        self.controller = self._create_agent(**kwargs)
        self.state = AgentState.NOT_SPAWN

        try:
            self.policy.reset(controller=self.controller, seed=self.generate_seed(), **kwargs)
        except IDMRouteInitializationError:
            positions = [
                np.asarray(self.trajectory[timestamp]["position"], dtype=np.float32)[:2]
                for timestamp in sorted(self.trajectory.keys())
                if self.trajectory[timestamp]["valid"]
            ]
            expert_distance = 0.0
            if len(positions) >= 2:
                expert_distance = float(np.linalg.norm(np.diff(np.asarray(positions), axis=0), axis=1).sum())

            self.policy.destroy()
            if expert_distance < 5.0:
                self.policy = ReplayPolicy(step_manager=self.step_manager, config=self.config["policy_config"])
            else:
                self.policy = TrajectoryIDMPolicy(step_manager=self.step_manager, config=self.config["policy_config"])
            self.policy.reset(controller=self.controller, seed=self.generate_seed(), **kwargs)

        if self._is_out_of_road():
            self.clear_all_objects()
            self.state = AgentState.OUT_OF_ROAD
            assert isinstance(self.get_action_spaces(), Space)
            return

        self.observer.reset(controller=self.controller, seed=self.generate_seed(), step_mgr=self.step_manager, **kwargs)

        if isinstance(self.observer, NavigationObservation):
            self.policy.destination = self.observer.destination

        if self.step_manager.key_step and math.isclose(self.policy.spawn_timestamp, self.step_manager.current_timestamp):
            self.controller.attachDyWld()
        
        assert isinstance(self.get_action_spaces(), Space)

    def _create_agent(self, physics_world, init_state, **kwargs):
        # Only create one agent - use the first config or default agent
        obj_name = "default_agent"

        obj = self.spawn_object(
            self.config['controller'], 
            name=obj_name,
            config=self.config['controller_config'], 
            physics_world=physics_world,
            random_seed=self.generate_seed(),
            size=self.config['controller_config']['size'],
            position=init_state['spawn_position'],
            heading_theta=init_state['spawn_yaw'],
            velocity=init_state['spawn_velocity'],
            angular_velocity=init_state['spawn_angular_velocity'],
            **kwargs
        )
        # self.init_pos = init_state['spawn_position']
        # self.dest_pos = init_state['destination']
        return obj

    def decide_action(self, action=None):
        if self.is_static:
            return

        if self.state != AgentState.ALIVE:
            return
        self.step_action = self.policy.act(action=action, observation=self.last_observation)

    def step(self):
        if self.is_static:
            return
        if self.state != AgentState.ALIVE:
            return

        self.controller.move(self.step_action)
        return

    def update_state(self):
        """
        Derive and cache the agent's discrete state.
        """
        # Not spawned yet
        if self.state == AgentState.NOT_SPAWN and self.step_manager.key_step and self.policy.is_spawned:
            self.controller.attachDyWld()
            self.state = AgentState.ALIVE
            return

        if self.state == AgentState.ALIVE:
            # crash checks from controller
            if not self.is_static and self.check_crash and isinstance(self.controller, BaseVehicle):
                self.controller.crash_check()
                
                if self.controller.crash_human:
                    self.clear_all_objects()
                    self.state = AgentState.CRASH_HUMAN
                    return
                if self.controller.crash_vehicle:
                    self.clear_all_objects()
                    self.state = AgentState.CRASH_VEHICLE
                    return
                if self.controller.crash_object:
                    self.clear_all_objects()
                    self.state = AgentState.CRASH_OBJECT
                    return
                if self.controller.crash_world:
                    self.clear_all_objects()
                    self.state = AgentState.CRASH_WORLD
                    return

            if self.max_step is not None and self.step_manager.eposide_step >= self.max_step:
                self.clear_all_objects()
                self.state = AgentState.OUT_OF_STEP
                return

            if self._is_out_of_road():
                self.clear_all_objects()
                self.state = AgentState.OUT_OF_ROAD
                return

            if self.policy.is_arrive:
                self.clear_all_objects()
                self.state = AgentState.SUCCESS
                return

    def _is_out_of_road(self):
        if self.trajdata_map is not None:
            position = np.asarray(self.controller.position, dtype=np.float32)
            lanes = self.trajdata_map.get_lanes_within(position[:3], self.out_of_road_threshold)
            if len(lanes) == 0:
                return True
            return False

        ego_position = np.asarray(self.controller.position, dtype=np.float32)[:2]
        expert_positions = np.asarray(
            [np.asarray(state["position"], dtype=np.float32)[:2] for state in self.trajectory.values()],
            dtype=np.float32,
        )
        distances = np.linalg.norm(expert_positions - ego_position[None, :], axis=1)
        return float(np.min(distances)) >= self.out_of_road_threshold

    def set_state(self, new_state):
        """
        Set agent state directly (for OnSite integration).

        This method is called by external code (OnSite integration) to control
        agent lifecycle based on Notify messages, bypassing the normal policy-based
        state transitions.

        Args:
            new_state: AgentState enum value
        """
        old_state = self.state
        self.state = new_state

        # Handle state transitions
        if new_state == AgentState.ALIVE:
            # Activate agent: attach to physics world
            if old_state == AgentState.NOT_SPAWN:
                self.controller.attachDyWld()
                logger.info(f"Agent {self.controller.name} activated (attached to physics world)")
        elif new_state in [
            AgentState.SUCCESS,
            AgentState.OUT_OF_ROAD,
            AgentState.CRASH_VEHICLE,
            AgentState.CRASH_HUMAN,
            AgentState.CRASH_OBJECT,
            AgentState.CRASH_WORLD,
            AgentState.IDLE,
        ]:
            # Terminal states: detach from physics world
            self.clear_all_objects()
            logger.info(f"Agent {self.controller.name} terminated with state {new_state}")

        logger.debug(f"Agent state changed: {old_state} -> {new_state}")

    def observe(self):
        if self.state == AgentState.ALIVE:
            self.last_observation = self.observer.observe()
        return {'observation': self.last_observation}

    def get_pose(self):
        if self.state != AgentState.ALIVE:
            raise ValueError(f"Cannot get pose for agent in state {self.state}")
        return self.controller.transform

    def get_base_state(self, transform=None):
        if self.state != AgentState.ALIVE:
            raise ValueError(f"Cannot get state for agent in state {self.state}")

        transform = self.get_pose()
        position = np.asarray(self.controller.position, dtype=np.float32)
        length = self.controller.LENGTH
        width = self.controller.WIDTH
        height = self.controller.HEIGHT
        if self.is_static:
            velocity = np.zeros(3, dtype=np.float32)
            acceleration = np.zeros(3, dtype=np.float32)
            angular_velocity = 0.0
            angular_acceleration = 0.0
        else:
            velocity = np.asarray(self.controller.velocity, dtype=np.float32)
            acceleration = np.asarray(self.controller.acceleration, dtype=np.float32)
            angular_velocity = float(self.controller.angular_velocity)
            angular_acceleration = float(self.controller.angular_acceleration)

        return {
            "controller": self.controller,
            "transform": transform,
            "position": position,
            "velocity": velocity,
            "acceleration": acceleration,
            "heading_theta": float(self.controller.heading_theta),
            "angular_velocity": angular_velocity,
            "angular_acceleration": angular_acceleration,
            "size": [length, width, height],
            "type": self.controller.metadrive_type
        }
    
    def get_observation_spaces(self):
        return self.observer.observation_space

    def get_action_spaces(self):
        return self.policy.get_input_space()

    def get_state(self):
        ret = super().get_state()
        ret["created_agents"] = self._agent_object.name
        return ret
    
    def destroy(self):
        # when new agent joins in the game, we only change this two maps.
        if self.INITIALIZED:
            super().destroy()
        self.clear_all_objects()
        self.observer.destroy()
        self.policy.destroy()

        self.controller = None
        self.observer = None
        self.policy = None

        self.INITIALIZED = False

    @property
    def is_static(self):
        return hasattr(self.policy, "static") and self.policy.static
