<a id="chapter-2"></a>

# 2. Architecture

[简体中文](../../zh/guides/architecture.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.4 Run Expert iLQR](../getting-started/expert-ilqr.md) · [Next: 3.1 Environment: local and remote calls](environment-interface.md)

- [2.1 Environment roles and types](#section-2-1)
- [2.2 SimulatorInterface: scene loading and rendering](#section-2-2)
- [2.3 AgentManager components](#section-2-3)
- [2.4 reset: start a scene](#section-2-4)
- [2.5 step: execute an action](#section-2-5)
- [2.6 Synchronous and asynchronous execution](#section-2-6)

<a id="section-2-1"></a>

## 2.1 Environment roles and types

StreetWorld follows the OpenAI Gymnasium environment interface. Environment inherits `gym.Env` and connects the AD policy to simulation. The policy starts a scene, submits actions, and receives observations, rewards, and termination flags after the vehicle moves. The environment handles scene loading, vehicle motion, and observation generation.

The environment classes add different capabilities to this interface:

- [BaseEnv](../reference/environment.md#api-1-1) provides scene loading, physics simulation, and the `reset()`/`step()` execution flow for task-specific extensions.
- [ScenarioEnv](../reference/environment.md#api-1-2) adds the driving task, rewards, and driving performance metrics to BaseEnv.
- [InteractiveScenarioEnv](../reference/environment.md#api-1-3) adds browser views, terminal state displays, and video recording to ScenarioEnv. The Chapter 1 examples use it to show vehicle motion and policy behavior.
- [GrpcClientEnv](../reference/environment.md#api-2-1) is the remote environment wrapper used by the AD policy process. It exposes Gymnasium-style calls, sends `reset()` and `step()` as gRPC requests to the Environment Server, and returns the server's observations, rewards, and termination flags.

Environment reads scenes and camera images through SimulatorInterface. Each simulated object is managed by an AgentManager.

<a id="section-2-2"></a>

## 2.2 SimulatorInterface: scene loading and rendering

SimulatorInterface defines the scene data supplied to Environment and how a renderer generates camera images from simulation state. Datasets can use different file formats, and renderers can run in different ways, provided their implementations return data in this format.

Pass a SimulatorInterface instance when constructing an Environment. During `reset()`, the environment reads trajectories, camera parameters, and terrain, then loads 3D assets and road maps. During simulation, it passes the current timestamp and participant poses to the backend; the ego camera Observer requests images from it.

The ST Renderer implementation reads nuScenes or Waymo assets and renders on the local GPU. The NuRec implementation reads NuRec assets and requests images from a separate rendering service. See [Chapter 3](simulator-interface.md#section-3-2) for data formats and backend configuration.

<a id="section-2-3"></a>

## 2.3 AgentManager components

Environment advances a scene through multiple AgentManagers: one for the ego vehicle and one for each surrounding participant. At each simulation step, it calls these Managers to update their objects in the same scene.

Each object can have its own observations, policy, and motion model:

- Observer produces camera images, vehicle state, and other observations.
- Policy computes control or motion commands from external actions, recorded trajectories, or traffic models. The ego vehicle can use iLQR to track a model's trajectory, while surrounding vehicles replay recordings or use IDM to respond to traffic.
- Controller executes those commands to move the simulated object.

Here, Controller refers to simulation objects such as `BaseVehicle`, `Pedestrian`, and Cyclist.

<a id="section-2-4"></a>

## 2.4 reset: start a scene

`reset()` starts a new driving episode. It loads the selected scene, initializes the ego vehicle and surrounding participants, clears the previous episode's accumulated records, and returns the first observation and scene information.

Call `reset()` before the first action so the AD policy can plan from the initial observation. Call it again after a scene ends to start another episode.

<a id="section-2-5"></a>

## 2.5 step: execute an action

`step(action)` submits a driving action and simulates the next interval of vehicle motion. The environment updates the ego vehicle and participants, produces a new observation, computes reward, and checks whether the episode has ended. The policy then uses the result to compute its next action.

An environment step can contain several physics steps. `physics_world_step_size` specifies each physics step's simulation time in microseconds; the default `20_000` is 0.02 s. A smaller value updates physical state more frequently but requires more physics steps for the same simulated duration.

`decision_repeat` sets the number of physics steps per environment step. The environment generates an observation after these steps, so this value also determines the simulated interval between observations:

```text
Simulated duration per environment step (seconds)
  = physics_world_step_size × decision_repeat / 1_000_000
```

With a `0.02 s` physics step and `decision_repeat=5`, each environment step advances 0.1 s. Keeping the physics step fixed and changing `decision_repeat` to `25` advances `0.5 s` per step and produces observations at `0.5 s` intervals of simulation time.

For iLQR trajectory tracking, adjust the policy's control period accordingly. See the [timing example](configuration/policy-controller.md#section-4-5).

<a id="section-2-6"></a>

## 2.6 Synchronous and asynchronous execution

`async_mode` controls whether simulation continues while the AD policy computes its next action. The default is False.

In synchronous mode, the environment waits for `step(action)`, advances one environment step, and returns the result. If each step simulates `0.1 s` and inference takes `0.3 s` of wall time, simulation time stays fixed during inference. The next `step()` still advances only 0.1 s. This supports stepwise evaluation where inference time does not affect simulated vehicle motion.

With `async_mode=True`, simulation runs continuously after `reset()` completes. While the policy computes a new action, the environment keeps advancing with the most recently submitted action. This mode supports continuous interaction such as browser driving and evaluation of how inference latency affects driving.

In the same example, if physics and rendering finish within `0.1 s`, the environment updates about once every `0.1 s` of wall time. Simulation advances about `0.3 s` while the model spends `0.3 s` on inference.

In asynchronous mode, `step(action)` updates the action and returns the most recently completed step. The observation may not reflect the action just submitted, and repeated calls can return the same frame. After a scene ends, the environment waits for reset().

If physics and rendering take longer than the configured interval, asynchronous simulation falls behind wall time. Each step still advances the duration defined by physics_world_step_size and decision_repeat.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.4 Run Expert iLQR](../getting-started/expert-ilqr.md) · [Next: 3.1 Environment: local and remote calls](environment-interface.md)
