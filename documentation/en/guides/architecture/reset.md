<a id="section-2-4"></a>

# 2.4 reset: start a scene

[简体中文](../../../zh/guides/architecture/reset.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.3 AgentManager components](agent-manager.md) · [Next: 2.5 step: execute an action](step.md)

`reset()` starts a new driving episode. It loads the selected scene, initializes the ego vehicle and surrounding participants, clears the previous episode's accumulated records, and returns the first observation and scene information.

Call `reset()` before the first action so the AD policy can plan from the initial observation. Call it again after a scene ends to start another episode.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2.3 AgentManager components](agent-manager.md) · [Next: 2.5 step: execute an action](step.md)
