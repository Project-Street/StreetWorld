"""
This environment can load all scenarios exported from other environments via env.export_scenarios()
"""

from typing import Union

from streetworld.manager.agent_manager import AgentState
from streetworld.configs.default_scenario_config import SCENARIO_ENV_CONFIG
from streetworld.envs.base_env import BaseEnv
from streetworld.manager.agent_manager import AgentManager
from streetworld.misc.metric_calculator import MetricCalculator
from streetworld.misc.reward_calculator import RewardCalculator


class ScenarioEnv(BaseEnv):
    @classmethod
    def default_config(cls):
        config = super(ScenarioEnv, cls).default_config()
        config.update(SCENARIO_ENV_CONFIG)
        return config

    def __init__(self, model, config=None):
        super(ScenarioEnv, self).__init__(model, config)
        self.metric_calculator = MetricCalculator()
        self.reward_calculator = RewardCalculator()

    def _reset(self, seed: Union[None, int] = None, scene_id: Union[None, str] = None):
        self.reward_calculator.reset()
        obs, info = super()._reset(seed=seed, scene_id=scene_id)
        self.metric_calculator.reset(warmup_step=self.agent_managers["actor"].warmup_step)
        self.metric_calculator.update(obs, info)
        return obs, info

    def _step(self, actions):
        obs, reward, terminated, truncated, info = super()._step(actions)
        self.metric_calculator.update(obs, info)
        if terminated or truncated:
            self.metric_calculator.finalize()
        return obs, reward, terminated, truncated, info

    def get_average_metric(self):
        return self.metric_calculator.get_average_metric()

    def _reward_function(self):
        return self.reward_calculator.compute(self)


    # def _cost_function(self):
    #     actor_mgr = self.agent_managers['actor']
    #     state = actor_mgr.state

    #     step_info = dict(num_crash_object=0, num_crash_human=0, num_crash_vehicle=0, num_on_line=0)
    #     cost = 0

    #     if state == AgentState.OUT_OF_ROAD:
    #         cost += self.config["out_of_road_cost"]
    #     if state == AgentState.CRASH_VEHICLE:
    #         cost += self.config["crash_vehicle_cost"]
    #         step_info["crash_vehicle_cost"] = self.config["crash_vehicle_cost"]
    #         step_info["num_crash_vehicle"] = 1
    #     if state == AgentState.CRASH_HUMAN:
    #         cost += self.config["crash_human_cost"]
    #         step_info["num_crash_human"] = 1
    #     if state == AgentState.CRASH_OBJECT:
    #         step_info["num_crash_object"] = 1

    #     step_info["cost"] = cost
    #     return cost, step_info
