from streetworld.utils.logger import get_logger
from streetworld.policy.base_policy import BasePolicy
import gymnasium as gym
import numpy as np

logger = get_logger()

JOYSTICK_DEADZONE = 0.025

class EnvInputPolicy(BasePolicy):
    """
    Control the current track vehicle
    """

    DEBUG_MARK_COLOR = (252, 244, 3, 255)

    def __init__(self, step_manager, config=None, enable_expert=True):
        super(EnvInputPolicy, self).__init__(step_manager, config)
        self.discrete_action = self.config["discrete_action"]
        self.discrete_steering_dim = self.config["discrete_steering_dim"]
        self.discrete_throttle_dim = self.config["discrete_throttle_dim"]
        self.steering_unit = 2.0 / (self.discrete_steering_dim - 1)
        self.throttle_unit = 2.0 / (self.discrete_throttle_dim - 1)

        self.enable_expert = enable_expert
        self.last_action = (0.0, 0.0)

    def reset(self, controller, seed, state, init_state, **kwargs):
        super().reset(controller, seed, state, init_state, **kwargs)
        self.last_action = (0.0, 0.0)

    def act(self, action, *args, **kwargs):
        if not self.step_manager.key_step:
            return self.last_action
        if isinstance(action, np.ndarray) and action.ndim == 2:
            action = action[0]
        if self.config["action_check"]:
            assert self.get_input_space().contains(action), "Input {} is not compatible with action space {}!".format(action, self.get_input_space())
        if self.discrete_action:
            action=self._convert_to_continuous_action(action)
        self.last_action = action
        self.action_info["action"] = action
        return action

    def _convert_to_continuous_action(self, action):
        steering = float(action % self.discrete_steering_dim) * self.steering_unit - 1.0
        throttle = float(action // self.discrete_steering_dim) * self.throttle_unit - 1.0
        return steering, throttle

    def get_input_space(self):
        """
        The Input space is a class attribute
        """
        if not self.discrete_action:
            _input_space = gym.spaces.Box(-1.0, 1.0, shape=(2, ), dtype=np.float32)
        else:
            _input_space = gym.spaces.Discrete(self.discrete_steering_dim * self.discrete_throttle_dim)
        return _input_space
