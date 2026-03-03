import logging

from metadrive.policy.base_policy import BasePolicy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReplayPolicy(BasePolicy):
    """
       Replay policy from Real data. For adding new policy, overwrite get_trajectory_info()
       This policy is designed for Waymo Policy by default
       """
    def reset(self, controller, seed, state, init_state, **kwargs):
        super().reset(controller, seed, state, init_state, **kwargs)
        self.controller.set_kinematic(True)

        timestamp_list = sorted(self.trajectory.keys())
        self.terminate_timestamp = timestamp_list[-1]
        
    def act(self, *args, **kwargs):
        info_timestamp = self.step_manager.current_timestamp if self.step_manager.current_timestamp <= self.terminate_timestamp else self.terminate_timestamp
        info = self.trajectory[info_timestamp]

        if not bool(info["valid"]):
            return None  # Return None action so the base vehicle will not overwrite the steering & throttle

        return info
    
    @property
    def is_arrive(self):
        return self.step_manager.current_timestamp > self.terminate_timestamp
