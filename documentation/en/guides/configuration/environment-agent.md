<a id="section-4-3"></a>

# 4.3 Environment and Agent parameters

[简体中文](../../../zh/guides/configuration/environment-agent.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.2 Configuration hierarchy and precedence](hierarchy.md) · [Next: 4.4 Observer configuration](observation.md)

Environment parameters control the whole scene; Agent parameters control individual objects. This table uses base environment defaults, which launch scripts and model configurations may override.

## Environment

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | Required | Scene IDs to run; the format depends on the dataset. See [Scene asset directories](../rendering-backends.md#scene-files) |
| `random_scenario` | bool | `True` | Select a random scene outside evaluation mode when no scene is specified; `False` cycles through the list in order |
| `physics_world_step_size` | Number, microseconds | `20_000` | Simulation time advanced by each physics step, equivalent to `0.02 s` |
| `decision_repeat` | int, physics steps | `5` | Physics steps per environment step; the default advances `0.1 s` |
| `max_step` | int or None, environment steps | `None` | Episode step limit; `None` disables this environment-level limit, while the ego Agent's `max_step` still applies |
| `async_mode` | bool | `False` | Whether simulation continues while waiting for driving input; see [Synchronous and asynchronous execution](../architecture.md#section-2-6) |

## Agent

The ego vehicle uses `actor_config`, and surrounding objects use participant_config. AgentManager reads both. The following table uses ego paths:

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.max_step` | int or None, environment steps | `10_000` | Ego Agent step limit; reaching it ends the episode |
| `actor_config.check_crash` | bool | `True` | Whether to check collisions for this object; ego collisions produce the corresponding termination reason |
| `actor_config.warmup_step` | int or None, environment steps | `None` | When set, ExpertILQRPolicy follows the recorded trajectory for the first specified number of steps, then the configured Policy takes over |

See [Environment](../../reference/environment.md) and [AgentManager](../../reference/manager.md#api-4-3) for all fields, and [AgentState](../environment-interface.md#agent-states) for termination states.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4.2 Configuration hierarchy and precedence](hierarchy.md) · [Next: 4.4 Observer configuration](observation.md)
