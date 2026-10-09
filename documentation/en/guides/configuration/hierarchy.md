<a id="section-4-2"></a>

# 4.2 Configuration hierarchy and precedence

[简体中文](../../../zh/guides/configuration/hierarchy.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.1 Using Config](config.md) · [Next: 4.3 Environment and Agent parameters](environment-agent.md)

This configuration uses iLQR to track a trajectory, advances `0.5 s` per environment step, and disables reverse drive. Start from ScenarioEnv defaults, then apply the experiment settings:

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.policy.env_input_ilqr_policy import EnvInputILQRPolicy

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "scene_ids": ["0007"],
    "decision_repeat": 25,
    "actor_config": {
        "policy": EnvInputILQRPolicy,
        "policy_config": {
            "smooth": False,
            "max_acceleration": 3.0,
            "trajectory_dt": 0.5,
            "control_dt": 0.5,
        },
        "controller_config": {"enable_reverse": False},
    },
})
```

The top-level `scene_ids` and `decision_repeat` select the scene and the number of physics steps per environment step. `actor_config` configures the ego AgentManager: `policy` selects the Policy class, `policy_config` supplies its arguments, and `controller_config` supplies vehicle parameters. `observer` and `observer_config` similarly select and configure observations; this example keeps their defaults.

Surrounding participants use `participant_config` with the same hierarchy. The ego can use EnvInputILQRPolicy to track model trajectories while surrounding vehicles retain ReplayPolicy. Select Policy, Observer, and Controller independently for each object.

## Defaults and runtime configuration

Base parameters come from [BASE_DEFAULT_CONFIG](../../../../streetworld/configs/default_config.py). ScenarioEnv adds [SCENARIO_ENV_CONFIG](../../../../streetworld/configs/default_scenario_config.py), and interactive environments add [INTERACTIVE_ENV_CONFIG](../../../../streetworld/envs/interactive_env.py). Construction merges caller-supplied settings last, so they override matching defaults.

The example retains the default AssemblyObservation while changing `decision_repeat` from `5` to 25. `default_config()` returns class defaults. Read `env.config` for the active configuration; after loading a scene, it returns the scene configuration copy held by ScenarioDataManager.

## Merge order in the launch scripts

For nuScenes and Waymo, the Environment Server merges [DEFAULT_POLICY_CONFIG_0_5S](../../../../streetworld/configs/default_policy_config.py), the model configuration selected by `--ad-policy-config`, and command-line settings in that order. Later values override matching earlier ones; for example, `--web-port` overrides the configuration's web port.

The NuRec branch builds an environment configuration from command-line arguments, then merges [NUREC_CONFIG](../../../../streetworld/configs/nurec_config.py) to set its cameras and navigation mode. It does not apply `--ad-policy-config` and defaults to raw control input. See the [NuRec example](../rendering-backends.md#nurec).

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.1 Using Config](config.md) · [Next: 4.3 Environment and Agent parameters](environment-agent.md)
