"""
OnSite Scenario Environment for StreetWorld.

This environment extends ScenarioEnv to support OnSite integration,
providing helper methods for state synchronization with OnSite server.
"""
import os
import logging
import torch
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.manager.agent_manager import AgentState
import time
logger = logging.getLogger(__name__)


class OnSiteScenarioEnv(ScenarioEnv):
    """
    OnSite-integrated ScenarioEnv.

    Key features:
    - In OnSite mode, actor lifecycle is controlled by Notify.
    - Middleware is managed externally, not held by env.
    """

    def __init__(self, model, config=None):
        scene_config_directory = config["scene_config_directory"]
        os.makedirs(scene_config_directory, exist_ok=True)
        logger.info(f"Created scene config directory at {scene_config_directory}")
        logger.debug(
            "OnSiteScenarioEnv scene config directory ready: scene_config_directory=%s, gui=%s, model=%s",
            scene_config_directory,
            config["gui"],
            type(model).__name__,
        )
        super().__init__(model, config)
        logger.debug(
            "OnSiteScenarioEnv base initialization complete: num_scenarios=%d, scenes=%s",
            self.data_manager.num_scenarios,
            self.data_manager.idx2scene,
        )

        # Cache for last received PubRole (for preserving fields)
        self.last_received_pub_role = None

    def close(self):
        try:
            super().close()
        finally:
            self.model.close()

    def _update_scene(self):
        """
        In OnSite mode, actor state is controlled by Notify, so skip actor.update_state().
        """
        if self.step_manager.eposide_step == 0:
            self.agent_managers["actor"].set_state(AgentState.ALIVE)
        self._surrounding_pre_collection = {}
        
        new_object_poses = {}
        for name, mgr in self.agent_managers.items():
            if name != "actor":
                mgr.update_state()

            if mgr.state == AgentState.ALIVE:
                base_state = mgr.get_base_state()
                self._surrounding_pre_collection[name] = base_state
                if name != "actor" and not mgr.is_static:
                    new_object_poses[name] = torch.from_numpy(base_state["transform"])

        self.model.update_scene(self.step_manager.current_timestamp, new_object_poses)
    def update_agent_from_pub_role_single(self, agent_name, role):
        """
        Update a single agent from PubRole SingleRole message.

        Args:
            agent_name: Name of the agent
            role: SingleRole proto message
        """
        if agent_name not in self.agent_managers:
            logger.warning(f"Agent {agent_name} not found in agent_managers")
            return

        agent_mgr = self.agent_managers[agent_name]
        if agent_mgr.state != AgentState.ALIVE:
            logger.debug(f"Agent {agent_name} not alive, skipping update")
            return

        # Convert quaternion and position to transform matrix
        from streetworld.misc.onsite_middleware.onsite_switch import OnSiteSwitch
        middleware = OnSiteSwitch.__new__(OnSiteSwitch)  # Create instance without __init__

        transform = middleware._quaternion_to_matrix(
            role.box.bottom_center,
            role.box.rotation
        )

        # Create state_info for policy
        state_info = {
            'transform': transform,
            'velocity': [
                role.linear_speed.x,
                role.linear_speed.y,
                role.linear_speed.z
            ],
            'angular_velocity': role.angular_speed.z,
            'valid': True
        }

        # Update policy state
        agent_mgr.policy.set_state_info(state_info)

    def update_agents_from_pub_role(self, pub_role):
        """
        Update all agents from PubRole message.

        Args:
            pub_role: PubRole proto message
        """
        # Cache the received PubRole
        self.last_received_pub_role = pub_role

        # Update each agent
        for role in pub_role.s_roles:
            if role.id in self.agent_managers and role.id != 'actor':
                self.update_agent_from_pub_role_single(role.id, role)
