<a id="section-2-5"></a>

# 2.5 step: execute an action

[简体中文](../../../zh/guides/architecture/step.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.4 reset: start a scene](reset.md) · [Next: 2.6 Synchronous and asynchronous execution](execution-mode.md)

`step(action)` submits a driving action and simulates the next interval of vehicle motion. The environment updates the ego vehicle and participants, produces a new observation, computes reward, and checks whether the episode has ended. The policy then uses the result to compute its next action.

An environment step can contain several physics steps. `physics_world_step_size` specifies each physics step's simulation time in microseconds; the default `20_000` is 0.02 s. A smaller value updates physical state more frequently but requires more physics steps for the same simulated duration.

`decision_repeat` sets the number of physics steps per environment step. The environment generates an observation after these steps, so this value also determines the simulated interval between observations:

```text
Simulated duration per environment step (seconds)
  = physics_world_step_size × decision_repeat / 1_000_000
```

With a `0.02 s` physics step and `decision_repeat=5`, each environment step advances 0.1 s. Keeping the physics step fixed and changing `decision_repeat` to `25` advances `0.5 s` per step and produces observations at `0.5 s` intervals of simulation time.

For iLQR trajectory tracking, adjust the policy's control period accordingly. See the [timing example](../configuration/policy-controller.md#section-4-5).

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.4 reset: start a scene](reset.md) · [Next: 2.6 Synchronous and asynchronous execution](execution-mode.md)
