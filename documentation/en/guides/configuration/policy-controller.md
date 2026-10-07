<a id="section-4-5"></a>

# 4.5 Policy and Controller configuration

[简体中文](../../../zh/guides/configuration/policy-controller.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.4 Observer configuration](observation.md) · [Next: 5. API reference](../../reference/index.md)

The AD policy passes an action to step(). Policy converts it to control or motion commands, and Controller executes them. The base configuration uses EnvInputPolicy for ego steering and throttle/brake input; surrounding objects use ReplayPolicy to follow recorded trajectories.

## EnvInputILQRPolicy: track a planned trajectory

Use EnvInputILQRPolicy to compute steering and throttle/brake from a model's future `(x, y)` trajectory. `actor_config.policy` selects the class, and `actor_config.policy_config` supplies its parameters. Input points are in ego coordinates; see the [action format](../environment-interface.md#action-format).

Start with the repository's default trajectory configuration:

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg = ScenarioEnv.default_config()
cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

This configuration selects EnvInputILQRPolicy and supplies its required parameters. Before connecting a model, check these two intervals:

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.trajectory_dt` | float, seconds | `0.5` in this trajectory configuration | Sampling interval between predicted points; the first point represents one interval after the current time |
| `actor_config.policy_config.control_dt` | float, seconds | `0.5` in this trajectory configuration | iLQR control update period; must be an integer multiple of the physics step. The current implementation also requires it to equal the environment step duration |

An environment step advances `physics_world_step_size × decision_repeat / 1_000_000` seconds. With the default `0.02 s` physics step and `decision_repeat=25`, this configuration advances `0.5 s`, matching control_dt=0.5.

`trajectory_dt` is determined by the model output and can differ from the control period. If the model predicts points `0.5 s` apart but `step()` should advance `0.1 s`, keep `trajectory_dt=0.5` and change the environment timing and control period together:

```python
cfg.merge_from({
    "decision_repeat": 5,
    "actor_config.policy_config.control_dt": 0.1,
})
```

`DEFAULT_POLICY_CONFIG_0_1S` uses these timing settings. See [Policy reference](../../reference/policy.md#api-6-4) for the complete EnvInputILQRPolicy configuration and API.

## Controller: apply vehicle control

Controller is the moving object in the scene, such as a vehicle, pedestrian, or cyclist. `actor_config.controller` selects the ego object class, and `actor_config.controller_config` sets dimensions, powertrain, and collision checking. Scene metadata supplies surrounding participant types and dimensions.

The default ego Controller is DefaultVehicle. This example disables reverse drive and limits horizontal acceleration to `3 m/s²`:

```python
cfg.merge_from({
    "actor_config.controller_config.enable_reverse": False,
    "actor_config.controller_config.max_acceleration": 3.0,
})
```

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.controller` | Class object | `DefaultVehicle` | Ego simulation object class; the vehicle type determines chassis, mass, tire, and related parameters |
| `actor_config.controller_config.size` | [length, width, height] or None, meters | `None` | Ego dimensions; `None` uses the vehicle class defaults |
| `actor_config.controller_config.enable_reverse` | bool | `True` | Allows negative throttle to drive backward; with `False`, negative inputs apply braking |
| `actor_config.controller_config.spawn_velocity` | bool | `True` | Initializes the vehicle with recorded linear and angular velocities |
| `actor_config.controller_config.max_acceleration` | float, m/s² | `15.0` for the ego vehicle | Limits horizontal velocity changes; omitted for surrounding participants by default |
| `actor_config.controller_config.max_steering` | Number, degrees | Sampled by the vehicle class | Maximum wheel angle for a steering input of `1` or `-1` |
| `actor_config.controller_config.check_crash_world` | bool | `False` | Checks collisions with background geometry and terrain; the Agent's `check_crash` must also be enabled |

Policy.max_acceleration constrains trajectory optimization; the Controller's field of the same name constrains velocity changes during motion. Configure them separately. See [Object / Controller reference](../../reference/object.md) for all object settings and vehicle parameters.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.4 Observer configuration](observation.md) · [Next: 5. API reference](../../reference/index.md)
