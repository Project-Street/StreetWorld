<a id="section-2-1"></a>

# 2.1 Environment roles and types

[简体中文](../../../zh/guides/architecture/environment.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2. Architecture](../architecture.md) · [Next: 2.2 SimulatorInterface: scene loading and rendering](simulator.md)

StreetWorld follows the OpenAI Gymnasium environment interface. Environment inherits `gym.Env` and connects the AD policy to simulation. The policy starts a scene, submits actions, and receives observations, rewards, and termination flags after the vehicle moves. The environment handles scene loading, vehicle motion, and observation generation.

The environment classes add different capabilities to this interface:

- [BaseEnv](../../reference/environment.md#api-1-1) provides scene loading, physics simulation, and the `reset()`/`step()` execution flow for task-specific extensions.
- [ScenarioEnv](../../reference/environment.md#api-1-2) adds the driving task, rewards, and driving performance metrics to BaseEnv.
- [InteractiveScenarioEnv](../../reference/environment.md#api-1-3) adds browser views, terminal state displays, and video recording to ScenarioEnv. The Chapter 1 examples use it to show vehicle motion and policy behavior.
- [GrpcClientEnv](../../reference/environment.md#api-2-1) is the remote environment wrapper used by the AD policy process. It exposes Gymnasium-style calls, sends `reset()` and `step()` as gRPC requests to the Environment Server, and returns the server's observations, rewards, and termination flags.

Environment reads scenes and camera images through SimulatorInterface. Each simulated object is managed by an AgentManager.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 2. Architecture](../architecture.md) · [Next: 2.2 SimulatorInterface: scene loading and rendering](simulator.md)
