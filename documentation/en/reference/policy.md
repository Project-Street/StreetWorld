# 5.4 Policy

[简体中文](../../zh/reference/policy.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.3 Observation](observation.md) · [Next: 5.5 Object / Controller](object.md)

See [configuration and example conventions](environment.md#reference-conventions).

On this page

- [5.4.1 BasePolicy](#api-6-1)
- [5.4.2 EnvInputPolicy](#api-6-2)
- [5.4.3 EnvInputPIDPolicy](#api-6-3)
- [5.4.4 EnvInputILQRPolicy](#api-6-4)
- [5.4.5 ExpertILQRPolicy](#api-6-5)
- [5.4.6 ReplayPolicy](#api-6-6)
- [5.4.7 IDMPolicy](#api-6-7)
- [5.4.8 TrajectoryIDMPolicy](#api-6-8)
- [5.4.9 Policy module functions](#section-5-4-9)

<a id="api-6-1"></a>

## 5.4.1 BasePolicy

### Purpose and construction

BasePolicy connects a control strategy to Agent execution. External controls, trajectory tracking, replay, and rule-based policies all submit control inputs or recorded states through `act()`, giving AgentManager one interface for different Policies.

AgentManager constructs it with StepCounter/config and passes Controller, recorded state, and seed on reset(). BasePolicy stores these inputs and exposes spawn, arrival, and action diagnostics. Manager calls `act()` every physics step; concrete Policies decide whether to update only on key_step.

Source: [streetworld/policy/base_policy.py](../../../streetworld/policy/base_policy.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.out_of_road_threshold` | float, m | `5.0` | Stored by Policy and also read by AgentManager for road checks |
| `actor_config.policy_config.arrive_speed_threshold` | float, m/s | `10.0` | Allowed difference between current speed and recorded destination speed for arrival |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None)` | `step_manager`: StepCounter instance; `config`: component configuration dictionary | None | Stores StepCounter, initializes configuration/random state, and creates action_info. | A configuration dictionary is required; config=None raises AttributeError at config.get. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Stores Controller, trajectory, and destination; seeds randomness and determines spawn time, destination speed, and whether the trajectory is static. | Requires at least one valid state, otherwise ValueError. init_state must include destination and destination_yaw. |
| Instance method<br>`act(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | None in the base class | Subclasses compute Controller actions; the base act does nothing. | The base returns None; operational Policies must override act. |
| Instance method<br>`get_action_info(self)` | — | dict | Deep-copies current action_info. | — |
| Instance method<br>`destroy(self)` | — | None | Clears configuration and the random generator. | — |
| Class method<br>`get_input_space(cls)` | — | Box(-1,1,(2,),float32) | Declares normalized steering and throttle/brake input by default. | Trajectory subclasses do not override this declaration. |
| Instance method<br>`get_state(self)` | — | dict | Returns the deep copy from get_action_info(). | — |
| Property getter<br>`is_arrive(self)` | — | bool | True for a nonstatic object that passes the destination's longitudinal plane, is within 20 m laterally, and has speed error within arrive_speed_threshold. | — |
| Property getter<br>`is_spawned(self)` | — | bool | True when current time reaches the first recorded trajectory frame. | — |
| Property getter<br>`name(self)` | — | str | Returns the Policy class name. | — |

A recorded mean speed below 0.01 m/s sets static=True. AgentManager does not call act on static objects, and the base is_arrive returns False for them.

reset state uses {timestamp: {position, velocity, heading_theta, angular_velocity, transform, valid, ...}}. init_state must provide at least spawn position, spawn heading, and destination.

### Example

```python
from streetworld.policy.base_policy import BasePolicy

class StopPolicy(BasePolicy):
    def act(self, *args, **kwargs):
        self.action_info["action"] = (0.0, 0.0)
        return 0.0, 0.0

cfg.merge_from({"actor_config.policy": StopPolicy})
```

<a id="api-6-2"></a>

## 5.4.2 EnvInputPolicy

### Purpose and construction

EnvInputPolicy receives external vehicle control. When an AD policy or browser already supplies steering and throttle/brake, it passes `env.step(action)` input to Controller for direct-control training or interactive driving.

Select it through the Agent `policy` setting; AgentManager constructs it. It accepts a new action on `key_step` and reuses `last_action` for other physics steps. Discrete actions map to continuous controls as configured.

Source: [streetworld/policy/env_input_policy.py](../../../streetworld/policy/env_input_policy.py).

### Configuration

Also uses common BasePolicy settings.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.discrete_action` | bool | False (environment default; required by class construction) | False accepts two control values; True accepts a combined discrete index |
| `actor_config.policy_config.discrete_steering_dim` | int | 5 (environment default; required by class construction) | Steering levels mapped evenly to [-1, 1]; must exceed 1 |
| `actor_config.policy_config.discrete_throttle_dim` | int | 5 (environment default; required by class construction) | Throttle/brake levels mapped evenly to [-1, 1]; must exceed 1 |
| `actor_config.policy_config.action_check` | bool | False (environment default) | EnvInputPolicy.act asserts get_input_space.contains before conversion |
| `actor_config.policy_config.controller` | str | keyboard (ego environment default) | Policy does not read this field or listen for keys; the interactive environment submits browser actions |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`: StepCounter; `config`: component configuration; `enable_expert`: stored flag, not read by EnvInputPolicy to switch control | None | Reads discrete settings, builds level intervals, and initializes zero action. | Missing required fields raises KeyError; one level causes division by zero. enable_expert is only stored; AgentManager manages warmup switching. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Runs BasePolicy.reset and clears last_action. | — |
| Instance method<br>`act(self, action, *args, **kwargs)` | `action`: external input in the current Policy's format; `*args`: positional arguments; `**kwargs`: keyword arguments | Two-element control input | Reads action on key_step, takes the first row of a 2D NumPy action, and converts discrete indices to continuous control. | Failed action_check raises AssertionError. None is not converted into valid vehicle control. |
| Instance method<br>`get_input_space(self)` | — | Box or Discrete | Continuous mode uses Box(-1,1,(2,),float32); discrete mode uses Discrete with steering-level count × throttle-level count actions. | — |

For discrete action k, steering level is `k % discrete_steering_dim` and throttle level is `k // discrete_steering_dim`, each linearly mapped to [-1, 1]. Positive steering turns left; Controller.enable_reverse determines whether negative throttle_brake brakes or reverses.

### Example

```python
from streetworld.policy.env_input_policy import EnvInputPolicy

cfg.merge_from({"actor_config.policy": EnvInputPolicy,
                "actor_config.policy_config.discrete_action": False})
# After constructing and resetting the environment with this cfg:
# observation, reward, terminated, truncated, info = env.step([0.1, 0.3])
```

<a id="api-6-3"></a>

## 5.4.3 EnvInputPIDPolicy

### Purpose and construction

EnvInputPIDPolicy tracks external planned trajectories with PID. It converts AD policy future waypoints to steering and throttle/brake commands, allowing trajectory planners to be tested through env.step(trajectory).

It extends [EnvInputPolicy](#api-6-2) and accepts future vehicle-coordinate points. On `key_step` it resamples a new trajectory at control_dt. Later control updates transform the cached path to current vehicle coordinates, remove consumed points, and compute PID control.

Source: [streetworld/policy/env_input_pid_policy.py](../../../streetworld/policy/env_input_pid_policy.py).

### Configuration

Construction still needs EnvInputPolicy's discrete settings, but act uses trajectory control without discrete conversion or action_check. No default environment preset is provided; tune the example PID gains for the vehicle.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.smooth` | bool | Required; False in the default trajectory preset | Applies five-point weighted smoothing separately to X/Y after prepending the origin |
| `actor_config.policy_config.trajectory_dt` | float, s | Required; 0.5 in the default trajectory preset | Predicted point interval; the first point is one trajectory_dt ahead |
| `actor_config.policy_config.control_dt` | float, s | Required; 0.5 in the default trajectory preset | Resampling/control update interval; must be a multiple of the physics interval and should match the environment decision period |
| `actor_config.policy_config.turn_controller` | Three-element sequence | Required | Steering PID Kp, Ki, and Kd |
| `actor_config.policy_config.speed_controller` | Three-element sequence | Required | Speed PID Kp, Ki, and Kd |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`: StepCounter; `config`: component configuration; `enable_expert`: stored flag, not read by EnvInputPolicy to switch control | None | Initializes EnvInputPolicy, trajectory settings, and two PIDControllers. | Missing fields raises KeyError; control_dt not divisible by the physics interval raises ValueError. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Resets base trajectory data, cached transforms, control timing, and PID state. | — |
| Instance method<br>`act(self, action, *args, **kwargs)` | `action`: external input in the current Policy's format; `*args`: positional arguments; `**kwargs`: keyword arguments | (steering, throttle_brake) | Steers toward the midpoint of the first two resampled points and derives target speed from their distance. Returns -1 braking input when overspeeding. | None returns (0,0). Needs at least two resampled points; stationary/zero-target-speed cases can divide by zero. |

### Example

```python
from streetworld.policy.env_input_pid_policy import EnvInputPIDPolicy

cfg.merge_from({"actor_config.policy": EnvInputPIDPolicy,
    "actor_config.policy_config": {
        "smooth": False, "trajectory_dt": 0.5, "control_dt": 0.1,
        "turn_controller": [1.25, 0.75, 0.3],
        "speed_controller": [5.0, 0.5, 1.0],
    },
})
# Default physics step: 0.02 s * decision_repeat 5 = control_dt 0.1 s.
```

<a id="api-6-4"></a>

## 5.4.4 EnvInputILQRPolicy

### Purpose and construction

EnvInputILQRPolicy tracks external trajectories with iLQR. It solves a control sequence from current vehicle state and a motion model, converting AD policy waypoints to vehicle commands under wheelbase, steering, and acceleration constraints.

Select it through the Agent `policy` setting. It extends [EnvInputPolicy](#api-6-2) trajectory processing. The solver uses wheelbase/max steering and a five-dimensional state comprising planar position, heading, speed, and wheel angle. Its first control is normalized to Controller steering and throttle/brake input.

Source: [streetworld/policy/env_input_ilqr_policy.py](../../../streetworld/policy/env_input_ilqr_policy.py).

### Configuration

Construction still requires EnvInputPolicy's discrete settings, but act skips discrete conversion and action_check.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.smooth` | bool | Required; False in the default trajectory preset | Applies five-point weighted smoothing separately to X/Y after prepending the origin |
| `actor_config.policy_config.trajectory_dt` | float, s | Required; 0.5 in the default trajectory preset | Predicted point interval; the first point is one trajectory_dt ahead |
| `actor_config.policy_config.control_dt` | float, s | Required; 0.5 in the default trajectory preset | Resampling/control update interval; must be a multiple of the physics interval and should match the environment decision period |
| `actor_config.policy_config.max_acceleration` | float, m/s² | Required; 3.0 in the default trajectory preset | iLQR acceleration bound and acceleration-to-normalized-throttle/brake scale |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`: StepCounter; `config`: component configuration; `enable_expert`: stored flag, not read by EnvInputPolicy to switch control | None | Stores trajectory control settings and iLQR warm-start parameters. | Missing fields raises KeyError; control_dt not divisible by the physics interval raises ValueError. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Reads wheelbase/steering limits, creates solver parameters, and clears trajectory caches. | Controller needs FRONT_WHEELBASE, REAR_WHEELBASE, and max_steering; the latter is read with .item(). |
| Instance method<br>`act(self, action, *args, **kwargs)` | `action`: external input in the current Policy's format; `*args`: positional arguments; `**kwargs`: keyword arguments | (steering, throttle_brake) | Resamples the trajectory and solves iLQR; reuses last_action between control updates. | None returns (0,0). Nonempty input must be a reshapeable NumPy array with enough future points. |
| Protected method<br>`_xy_transform(self)` | — | ndarray(3,3) | Extracts an X/Y homogeneous transform from Controller.transform for trajectory caching and expert subclasses. | — |

The solver allows 100 iterations, convergence tolerance 1e-6, and 0.1 s maximum solve time. State/input costs and warm-start parameters are fixed in the class and not exposed by Environment Config.

control_dt must equal physics_world_step_size × decision_repeat × 1e-6. Construction only checks divisibility by the physics interval; source comments note problems with other decision-period combinations.

### Example

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
# After constructing and resetting the environment with this cfg, submit an N-by-2 float32 trajectory:
# trajectory = np.array([[2.0, 0.0], [4.0, 0.0], [6.0, 0.2]], dtype=np.float32)
# observation, reward, terminated, truncated, info = env.step(trajectory)
```

<a id="api-6-5"></a>

## 5.4.5 ExpertILQRPolicy

### Purpose and construction

ExpertILQRPolicy tracks recorded expert trajectories through vehicle control. It can check continuous scene/control execution and provide warmup driving before an AD policy takes over.

It selects future recorded points, transforms them to vehicle coordinates, and tracks them with [EnvInputILQRPolicy](#api-6-4). Configure it as the ego Policy directly, or set `warmup_step` so AgentManager creates an expert Policy for warmup.

Source: [streetworld/policy/expert_ilqr_policy.py](../../../streetworld/policy/expert_ilqr_policy.py).

### Configuration

Common settings inherit from EnvInputPolicy and BasePolicy. Using warmup_step also requires expert settings such as trajectory_dt and control_dt.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.policy_config.trajectory_steps` | Positive integer, points | `10` | Maximum future recorded points selected per update |
| `actor_config.policy_config.trajectory_dt` | float, s | Required | Recorded path resampling interval; at least one microsecond |
| `actor_config.policy_config.control_dt` | float, s | Required | Same control-period requirements as iLQR |
| `actor_config.policy_config.smooth` | bool | Forced False | Overrides the caller's value during construction |
| `actor_config.policy_config.max_acceleration` | float, m/s² | Forced 3.2 | Overrides the caller's value during construction |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`: StepCounter; `config`: component configuration; `enable_expert`: stored flag, not read by EnvInputPolicy to switch control | None | Overrides smooth/max_acceleration, initializes iLQR, and reads trajectory_steps. | config=None raises TypeError at dict(config); trajectory_steps<1 raises ValueError. Parent-required settings still apply. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Initializes iLQR, resamples valid expert timestamps, and retains the final timestamp. | No valid recorded points or trajectory_dt below one microsecond raises ValueError. |
| Instance method<br>`act(self, action=None, *args, **kwargs)` | `action`: external input in the current Policy's format; `*args`: positional arguments; `**kwargs`: keyword arguments | (steering, throttle_brake) | Ignores external action and selects future recorded points; duplicates a lone future point to provide two tracking points. | With no future or forward points, marks arrival and returns the previous control. |
| Property getter<br>`is_arrive(self)` | — | bool | True once arrival is marked or current time reaches the recorded end. | — |

### Example

```python
from streetworld.policy.expert_ilqr_policy import ExpertILQRPolicy

cfg.merge_from({"actor_config.policy": ExpertILQRPolicy,
    "actor_config.policy_config": {"trajectory_dt": 0.1,
                                   "control_dt": 0.1, "trajectory_steps": 30}})
# After constructing and resetting with this cfg, env.step(None) lets the expert generate its path.
```

<a id="api-6-6"></a>

## 5.4.6 ReplayPolicy

### Purpose and construction

ReplayPolicy reproduces recorded motion. During closed-loop ego evaluation, it keeps background participants on their original timelines; it is their default Policy.

`reset()` makes Controller kinematic; `act()` returns recorded state at the current simulation timestamp. Controller restores pose and velocity. AgentManager supplies resampled tracks and StepCounter.

Source: [streetworld/policy/replay_policy.py](../../../streetworld/policy/replay_policy.py).

### Configuration

Uses BasePolicy settings with no extra fields. participant_config discrete-action fields do not affect ReplayPolicy.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Runs base reset, enables kinematic mode, and stores the final recorded timestamp. | — |
| Instance method<br>`act(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict or None | Returns the frame at the current microsecond timestamp; valid=False returns None. | The timestamp must exist or KeyError is raised. Vehicle move cannot handle a None frame. |
| Property getter<br>`is_arrive(self)` | — | bool | True when the recorded trajectory's final timestamp is reached. | — |

### Example

```python
from streetworld.policy.replay_policy import ReplayPolicy

cfg.merge_from({"participant_config.policy": ReplayPolicy})
# ScenarioDataManager resamples the replay object's state onto the physics time axis.
```

<a id="api-6-7"></a>

## 5.4.7 IDMPolicy

### Purpose and construction

IDMPolicy uses a lane map and the Intelligent Driver Model to drive rule-based traffic. It adjusts acceleration from leading-vehicle gap and relative speed while following map routes; configuration controls lane changing.

`reset()` builds a route from trajdata VectorMap lane topology, requiring spawn/destination matches. At runtime it reads `states` and world-coordinate `surrounding` observations and computes longitudinal control and steering for the vehicle Controller.

Source: [streetworld/policy/idm_policy.py](../../../streetworld/policy/idm_policy.py).

### Configuration

The table uses participant paths. For ego, replace the prefix with actor_config; see [BasePolicy](#api-6-1) for common fields.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `participant_config.policy_config.disable_idm_deceleration` | bool | `False` | Disables IDM deceleration output |
| `participant_config.policy_config.enable_lane_change` | bool | `True` | Enables overtaking through adjacent lanes |
| `participant_config.policy_config.normal_speed` | float, km/h | `30.0` | Normal cruising target speed |
| `participant_config.policy_config.creep_speed` | float, km/h | `5.0` | Slow-driving target speed |
| `participant_config.policy_config.max_long_dist` | float, m | `30.0` | Maximum longitudinal range for front/rear vehicle searches |
| `participant_config.policy_config.safe_lane_change_distance` | float, m | `15.0` | Front/rear safety distance during lane changes |
| `participant_config.policy_config.current_lane_max_dist` | float, m | `2.25` | Distance threshold for spawn/destination lane matching during route initialization |
| `participant_config.policy_config.lane_change_speed_increase` | float, km/h | `10.0` | Required speed gain for a lane change |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None)` | `step_manager`: StepCounter instance; `config`: component configuration dictionary | None | Stores IDM settings and initializes heading/lateral PID and route state. | — |
| Instance method<br>`reset(self, controller, seed, state, init_state, trajdata_map=None, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `trajdata_map`: current trajdata.VectorMap or None; `**kwargs`: keyword arguments | None | Validates vehicle/map, locates lanes, builds a route to the recorded destination, and resets PID/lane-change timing. | A non-vehicle or missing map raises ValueError. Lane/route initialization failure raises IDMRouteInitializationError. |
| Instance method<br>`act(self, observation, *args, **kwargs)` | `observation`: latest Observer output, with required fields described for this Policy; `*args`: positional arguments; `**kwargs`: keyword arguments | [steering, throttle_brake] | On key_step, reads world-coordinate states/surrounding, selects a target lane along the route, and computes control. | Missing observations raises ValueError/KeyError. Runtime lane topology errors can raise IDMLaneRuntimeError. With current_lane=None, returns zero control and records idm_out_of_road. |

act reads ego_pos, heading_theta, linear_velocity, current_lane, and other states, plus world positions/velocities, size, and lanes from surrounding. StateObservation requires a vehicle Controller; pedestrians and cyclists use replay.

AgentManager catches IDMRouteInitializationError and selects ReplayPolicy for valid recorded paths shorter than 5 m, otherwise TrajectoryIDMPolicy. Direct IDMPolicy.reset calls still raise the exception.

### Example

```python
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation
from streetworld.policy.idm_policy import IDMPolicy

cfg.merge_from({"participant_config": {
    "policy": IDMPolicy, "observer": AssemblyObservation,
    "observer_config": {
        "states": {"observer_class": StateObservation},
        "surrounding": {"observer_class": SurroundingObservation,
                        "coordinate_mode": "world", "ignore_dist": None},
    },
    "policy_config": {"enable_lane_change": True},
}})
```

<a id="api-6-8"></a>

## 5.4.8 TrajectoryIDMPolicy

### Purpose and construction

TrajectoryIDMPolicy follows recorded routes with IDM responses. It retains the recording's path while adjusting acceleration to surrounding traffic, for vehicles that need a fixed route and reactive following.

`reset()` builds a world-coordinate path from valid recorded states. Runtime IDM control uses world-coordinate `surrounding` observations. This class does not generate map routes or change lanes.

Source: [streetworld/policy/trajectory_idm_policy.py](../../../streetworld/policy/trajectory_idm_policy.py).

### Configuration

For ego configuration, use actor_config; common fields are in [BasePolicy](#api-6-1).

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `participant_config.policy_config.front_distance` | float, m | `5.0` | Desired minimum gap to leading vehicles; non-vehicles use a fixed 2 m |
| `participant_config.policy_config.react_time` | float, s | `1.0` | Desired following time gap |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_manager, config=None)` | `step_manager`: StepCounter instance; `config`: component configuration dictionary | None | Stores following settings and samples a speed limit from 25–50 km/h. | Speed sampling uses a separate gym Box, not the BasePolicy.np_random seed. |
| Instance method<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `state`: recorded states keyed by microsecond timestamp; `init_state`: spawn/destination dictionary; `**kwargs`: keyword arguments | None | Validates the vehicle, extracts valid path points, and computes arc length and curvature radius. | A non-vehicle, fewer than three valid points, or zero-length path raises ValueError. |
| Instance method<br>`act(self, observation, *args, **kwargs)` | `observation`: latest Observer output, with required fields described for this Policy; `*args`: positional arguments; `**kwargs`: keyword arguments | (steering, throttle_brake) | On key_step, computes acceleration from curvature/front gap and steers toward a forward path point. | Missing surrounding raises KeyError; no forward path point raises RuntimeError. Participant positions/velocities must use world coordinates. |

Target speed is the minimum of the random speed limit and curvature limit. Acceleration normalization uses Controller MASS, max_engine_force, max_brake_force, and TIRE_RADIUS; steering normalization uses max_steering.

### Example

```python
from streetworld.policy.trajectory_idm_policy import TrajectoryIDMPolicy

# Keep the states/surrounding(world) observation configuration from the IDMPolicy example.
cfg.merge_from({"participant_config.policy": TrajectoryIDMPolicy,
                "participant_config.policy_config.front_distance": 5.0,
                "participant_config.policy_config.react_time": 1.0})
```

<a id="section-5-4-9"></a>

## 5.4.9 Policy module functions

[env_input_pid_policy.py](../../../streetworld/policy/env_input_pid_policy.py) and [env_input_ilqr_policy.py](../../../streetworld/policy/env_input_ilqr_policy.py) each define smooth_1d with the same signature and implementation. The table applies to both.

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Module function<br>`smooth_1d(arr, kernel_size=5)` | arr: 1D numeric sequence; kernel_size: kernel length, default 5 | float32 ndarray | Pads by repeating boundary values, then smooths by convolution. kernel_size=5 uses [1,4,6,4,1]; other sizes use uniform weights. | Requires a nonempty 1D sequence and a positive integer kernel size. Even kernels produce one extra output value. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.3 Observation](observation.md) · [Next: 5.5 Object / Controller](object.md)
