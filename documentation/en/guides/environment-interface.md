<a id="chapter-3"></a>

<a id="section-3-1"></a>

# 3.1 Environment: local and remote calls

[简体中文](../../zh/guides/environment-interface.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 2. Architecture](architecture.md) · [Next: 3.2 3D assets and SimulatorInterface](simulator-interface.md)

Environment runs driving episodes: it loads a scene, accepts actions, simulates vehicle motion, and returns observations, reward, and termination flags. A local AD policy calls it directly; a model in a separate process calls the server environment through GrpcClientEnv.

## Local calls

Construct an environment with a SimulatorInterface for scene loading/rendering and an environment configuration. This nuScenes scene `0007` example keeps the vehicle straight with 20% throttle:

```python
from st_renderer import SimulatorInterface
from streetworld.config import Config
from streetworld.envs.scenario_env import ScenarioEnv

env = ScenarioEnv(
    SimulatorInterface("nuscenes"),
    Config({"scene_ids": ["0007"]}),
)
try:
    observation, info = env.reset()
    while True:
        action = [0.0, 0.2]
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
finally:
    env.close()
```

`reset()` starts an episode and returns the initial observation and scene information. `step(action)` returns the five values below; `close()` releases environment resources.

| Return value | Type and meaning |
| --- | --- |
| `observation` | Ego observation; by default, a dictionary containing `gaussian`, `navigation`, `states`, and `surrounding` |
| `reward` | Numeric reward for this step; see [Reward calculation](#reward-calculation) |
| `terminated` | Boolean indicating that the episode ended, for example due to arrival, collision, leaving the road, or the step limit |
| `truncated` | Boolean indicating that the episode ended at a configured step limit |
| `info` | Dictionary with scene name, timestamps, termination reason, reward components, and related information |

<a id="action-format"></a>

## action: trajectories and control inputs

The ego Policy determines `step(action)`'s input format. EnvInputILQRPolicy and EnvInputPIDPolicy accept future waypoints from an AD policy and convert them to control inputs. EnvInputPolicy accepts steering and throttle/brake directly.

### Trajectory input

Trajectory Policies such as EnvInputILQRPolicy and EnvInputPIDPolicy accept an `(N, 2)` array. `N` is the number of future points, and each row contains `[x, y]` in meters:

| Component | Meaning |
| --- | --- |
| `x` | Distance along the ego vehicle's forward axis; positive is forward |
| `y` | Lateral distance from the ego vehicle; positive is left |

The coordinates use the ego position at action submission as their origin and rotate with its heading. For example, `[10.0, 2.0]` is a target 10 m ahead and 2 m left. `trajectory_dt` sets the future time of each point: with `0.5 s`, the first point is `0.5 s` ahead and the second is 1 s ahead.

```python
import numpy as np

action = np.array([[2.0, 0.0], [4.0, 0.0], [6.0, 0.5]], dtype=np.float32)
```

Policy computes steering and throttle to track this trajectory. Configure point spacing, the control period, and environment step duration separately; see the [timing example](configuration/policy-controller.md#section-4-5).

### Control input

EnvInputPolicy uses continuous control by default, accepting `[steering, throttle_brake]` with both values in `[-1, 1]`:

| Component | Meaning |
| --- | --- |
| `steering` | Steering input: `1` is maximum left, `-1` maximum right, and `0` centered. The vehicle's `max_steering` determines the wheel angle |
| `throttle_brake` | Throttle/brake input: positive drives forward, `1` is maximum throttle, and `0` is no throttle. Negative values drive backward when reverse is enabled and apply braking otherwise |

For example, `[0.0, 0.2]` centers steering and applies 20% throttle; `[0.5, 0.0]` steers left at half the maximum angle with no throttle. `actor_config.controller_config.enable_reverse=True` by default, so negative throttle slows a forward-moving vehicle and then reverses it. Input magnitude specifies control effort; actual acceleration also depends on vehicle parameters and motion state.

<a id="observation-data"></a>

## observation: data available to the AD policy

The ego AssemblyObservation combines the default observations. Changing the Observer or its configuration changes the returned fields.

| Field | Contents and format |
| --- | --- |
| `gaussian` | Camera images and parameters; local gaussian['image'][camera_name] has shape `(1, H, W, 3)`, using `uint8` RGB values in 0–255 by default. The first dimension is one frame, H/W are image height/width, and the last dimension contains RGB channels |
| `navigation` | Navigation data including the current road, route, and ego position relative to the route |
| `states` | Ego speed and motion state |
| `surrounding` | Poses, dimensions, and motion state of surrounding vehicles, pedestrians, and other objects |

Positions use meters, velocity `m/s`, acceleration `m/s²`, angular velocity `rad/s`, and angular acceleration rad/s². Heading angles such as `heading_theta` use radians. Vehicle coordinates are X forward, Y left, Z up. SurroundingObservation can return participant data in ego or world coordinates; see the [Observation reference](../reference/observation.md). See [SimulatorInterface](simulator-interface.md#load-metadata) for camera parameters and pose matrices.

<a id="scenario-info"></a>

## info: scene and runtime information

Both `reset()` and `step()` return `info`, which records scene progress, termination reasons, and reward components.

| Field | Meaning and unit |
| --- | --- |
| `scene_name` | Current scene ID |
| `current_timestamp` | Current scene timestamp in microseconds |
| `relative_timestamp` | Simulation time since the episode began, in microseconds; divide by `1_000_000` for seconds |
| `episode_length` | Completed environment steps in this episode; 0 after reset |
| `reason` | Current ego state; at episode end, this is the termination reason. Values are listed below |
| `episode_reward` | Accumulated episode reward, returned by step |
| `steering`, `throttle_brake` | Current ego steering and throttle/brake inputs, returned by step |
| `step_reward`, `reward_components` | Current reward and component values from the default calculator; `reward_components['total']` is their sum |

<a id="agent-states"></a>

## AgentState and termination reasons

AgentState describes a simulation object's current state. Environment checks the ego state, writes it to `info['reason']`, and determines whether the episode has ended. Values are strings:

| AgentState | `reason` value | Meaning |
| --- | --- | --- |
| `NOT_SPAWN` | `not_spawn` | The object's spawn time has not arrived |
| `ALIVE` | `alive` | The object has spawned and is active |
| `IDLE` | `idle` | The object was placed in an idle state by an external call |
| `SUCCESS` | `arrive_dest` | Policy considers the destination reached; the test depends on the Policy |
| `OUT_OF_ROAD` | `out_of_road` | Road check failed: no nearby lane with a map, or too far from the expert trajectory without a map |
| `OUT_OF_STEP` | `out_of_step` | The environment or ego Agent step limit was reached |
| `CRASH_VEHICLE` | `crash_vehicle` | Collision with a vehicle |
| `CRASH_HUMAN` | `crash_human` | Collision with a pedestrian |
| `CRASH_OBJECT` | `crash_object` | Collision with another traffic object |
| `CRASH_WORLD` | `crash_world` | Collision with scene background geometry or terrain |

Arrival, leaving the road, step limits, and collisions set terminated=True. A step limit also sets `truncated=True`, so both flags can be true. Use `if terminated or truncated` to detect episode end.

`max_step` sets the environment limit; `actor_config.max_step` sets the ego Agent limit. `check_crash` enables ego collision checking, and `check_crash_world` additionally controls background collision checking. Fields such as `crash_vehicle_done` do not participate in this termination logic, so they cannot keep a scene running after collision.

<a id="reward-calculation"></a>

## Calculate and customize rewards
For reinforcement learning, adapt the reward to the training objective by changing the reward calculator or overriding the reward function.
ScenarioEnv uses [RewardCalculator](../../../streetworld/misc/reward_calculator.py). It calls `reset()` at the start of each episode and `compute(env)` to obtain (reward, `reward_info`). Environment merges `reward_info` into `info` and accumulates the per-step reward.

The default reward contains these terms:

| Reward term | Calculation |
| --- | --- |
| `progress`, `reverse` | Reward for forward route progress and a penalty for reversing; route deviation reduces forward reward |
| `position`, `heading` | Penalties when lateral or heading errors exceed their thresholds |
| `ttc` | Estimated time to collision from relative positions and velocities; penalizes risk and grants a safety bonus when conditions permit |
| `collision` | Penalty for collision or leaving the road; default `-50` |
| `success_bonus` | Reward for reaching the destination; default `75` |
| `living_cost` | Constant added on each calculation; current default `0.05` |

Set weights or thresholds such as `progress_reward_weight` and `collision_penalty_weight` in Config; see [ScenarioEnv configuration](../reference/environment.md#api-1-2). To add a reward term, override `_reward_function()` in a ScenarioEnv subclass. This example retains the default reward and penalizes large steering inputs:

```python
from streetworld.envs.scenario_env import ScenarioEnv

class SteeringPenaltyEnv(ScenarioEnv):
    def _reward_function(self):
        reward, info = super()._reward_function()
        penalty = -0.1 * abs(self.actor_controller.steering)
        total = float(reward + penalty)
        info["reward_components"]["steering_penalty"] = penalty
        info["reward_components"]["total"] = total
        info["step_reward"] = total
        return total, info
```

Construct `SteeringPenaltyEnv` in place of `ScenarioEnv`, using the same calls. The method must return a numeric reward and an information dictionary. The new penalty is included in episode_reward.

Alternatively, copy or subclass RewardCalculator, change `compute(env)`, and assign your calculator to `self.reward_calculator` in a custom environment constructor. It must also implement `reset()` to clear episode records and `episode_info()` to return accumulated diagnostics at termination. Config does not currently select a reward calculator class.

<a id="interactive-env"></a>

## InteractiveEnv: images, state, and video

ScenarioEnv returns observations and results. To view images/state or record videos during simulation, create an interactive environment with `make_interactive_env()`:

```python
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.scenario_env import ScenarioEnv

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
```

The returned class retains `reset()`, `step()`, and `close()` and manages these UI components:

| Class | Function | Switches and main settings |
| --- | --- | --- |
| WebUI | Displays camera mosaics, speed, and control inputs in a browser; accepts W/A/S/D input | `webui` is enabled by default; `web_host` and `web_port` set the address |
| TUI | Displays the scene queue, runtime state, speed, termination reason, and evaluation metrics in the terminal | `tui` is enabled by default |
| VideoExporter | Saves per-scene MP4 videos, optionally showing speed/angular-velocity history and control inputs beside the images | `video_output_dir` defaults to `videos`; `None` disables recording. `video_hud` controls additional state displays |

After each step, the interactive environment reads camera images from `observation`, arranges them with `image_layout`, and passes images and vehicle state to these components. At scene end, the terminal shows the termination reason and metrics, and the video is written to disk. `close()` shuts down the interfaces and saves unfinished recordings.
The web service starts during environment construction. After reset, it waits for the first `step()` to display camera images. Manual driving requires continuous key handling; see the [browser driving example](../getting-started/web-controller.md#section-1-2). See the [API reference](../reference/environment.md#api-1-3) for all interactive environment settings.

## Remote calls
AD policies and the simulator often have conflicting dependencies. Run each in its own Python environment and exchange simulation observations and inference results between processes.
Start the Environment Server as described in [Chapter 1](../getting-started/environment-server.md#section-1-3), then connect with GrpcClientEnv. The client still uses `reset()`, `step()`, and `close()`; scene loading, vehicle simulation, and rewards run on the server.

```python
import numpy as np
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv("127.0.0.1", 50052, timeout_sec=360.0)
try:
    observation, info = env.reset()
    trajectory = np.array([[0.5 * i, 0.0] for i in range(1, 7)], dtype=np.float32)
    observation, reward, terminated, truncated, info = env.step(trajectory)
finally:
    env.close()
```

This example submits six future position points to the server's default `trajectory` Policy. Replace `trajectory` with your model's prediction from `observation`, then repeat the calls in a loop.

The server configuration selects remote scenes. Client `reset()` currently does not send `seed` or `options` and has no `scene_id` argument. For continuous control, send `[steering, throttle_brake]`; the server restores a one-row, two-column array, and EnvInputPolicy takes that row. Discrete action IDs are not supported by this transport; a nonempty action must contain an even number of elements. Sending `None` also gives the server None.

| Details | Changes in remote calls |
| --- | --- |
| Camera images | Client images have shape `(H, W, 3)`, removing the local frame dimension. Read them as `uint8` RGB; the server must use `clip_rgb=False` |
| Map objects | Objects such as `current_lane` become strings in transmission and cannot be used as local map objects |
| `collision_body` | This observation is not currently transmitted |
| Connections and resources | Client `close()` closes its connection; the server owns shutdown of its simulation and process |

A gRPC message can be at most 200 MiB in either direction. The client restores numeric observation arrays as NumPy arrays; `info` remains a dictionary. See [Environment reference](../reference/environment.md#api-2-1) for the complete client and server APIs.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 2. Architecture](architecture.md) · [Next: 3.2 3D assets and SimulatorInterface](simulator-interface.md)
