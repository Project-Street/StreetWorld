<a id="section-2-6"></a>

# 2.6 Synchronous and asynchronous execution

[简体中文](../../../zh/guides/architecture/execution-mode.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.5 step: execute an action](step.md) · [Next: 3. Interface contracts](../interfaces.md)

`async_mode` controls whether simulation continues while the AD policy computes its next action. The default is False.

In synchronous mode, the environment waits for `step(action)`, advances one environment step, and returns the result. If each step simulates `0.1 s` and inference takes `0.3 s` of wall time, simulation time stays fixed during inference. The next `step()` still advances only 0.1 s. This supports stepwise evaluation where inference time does not affect simulated vehicle motion.

With `async_mode=True`, simulation runs continuously after `reset()` completes. While the policy computes a new action, the environment keeps advancing with the most recently submitted action. This mode supports continuous interaction such as browser driving and evaluation of how inference latency affects driving.

In the same example, if physics and rendering finish within `0.1 s`, the environment updates about once every `0.1 s` of wall time. Simulation advances about `0.3 s` while the model spends `0.3 s` on inference.

In asynchronous mode, `step(action)` updates the action and returns the most recently completed step. The observation may not reflect the action just submitted, and repeated calls can return the same frame. After a scene ends, the environment waits for reset().

If physics and rendering take longer than the configured interval, asynchronous simulation falls behind wall time. Each step still advances the duration defined by physics_world_step_size and decision_repeat.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.5 step: execute an action](step.md) · [Next: 3. Interface contracts](../interfaces.md)
