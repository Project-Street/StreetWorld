<a id="chapter-4"></a>

# 4. Configuration system

[简体中文](../../zh/guides/configuration.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 3. Interface contracts](interfaces.md) · [Next chapter: 5. Component reference](../reference/index.md)

- [4.1 Using Config](#section-4-1)
- [4.2 Configuration hierarchy and precedence](#section-4-2)
- [4.3 Environment and Agent parameters](#section-4-3)
- [4.4 Observer configuration](#section-4-4)
- [4.5 Policy and Controller configuration](#section-4-5)

<a id="section-4-1"></a>

## 4.1 Using Config

Testing AD policies involves selecting scenes, changing simulation timing, and sometimes replacing the ego Policy or camera settings. StreetWorld stores these settings in [Config](../../../streetworld/config.py), which is passed when constructing Environment. The environment forwards the ego, participant, and observation settings to their components.

Config is a Python container for nested configuration dictionaries, with deep copying and merging. `Config()` stores the supplied values; it does not add environment defaults.

### Create a configuration and pass it to an environment

For example, select nuScenes scene `0007` and disable ego reverse drive:

```python
from streetworld.config import Config

cfg = Config({
    "scene_ids": ["0007"],
    "actor_config": {
        "controller_config": {"enable_reverse": False},
    },
})
```

Pass `cfg` as the environment's `config` argument, for example ScenarioEnv(`simulator`, `config`=`cfg`). Here `simulator` is a SimulatorInterface instance from [Chapter 3](interfaces.md#section-3-2). See [3.1](interfaces.md#section-3-1) for a complete environment call example.

### Access, modify, and copy values

Config supports dictionary and attribute access. This example changes the scene list and enables reverse drive again:

```python
cfg["scene_ids"] = ["0007", "0008"]
cfg.actor_config.controller_config.enable_reverse = True
```

Use `copy()` to make an independent deep copy for another experiment. `to_dict()` converts the outermost container to a regular dictionary:

```python
independent = cfg.copy()
values = cfg.to_dict()
```

`to_dict()` does not copy nested values, which may still be ConfigDict instances. Missing fields raise KeyError with dictionary access and AttributeError with attribute access.

### Merge configurations with merge_from()

Launch scripts often modify a few fields in an existing configuration, such as changing control parameters while retaining scenes and cameras. `merge_from()` writes the new settings into the existing Config: supplied values replace matching fields, and other fields remain.

Nested dictionaries merge recursively. Dotted keys can also address nested fields directly. Both examples below disable ego reverse drive while retaining `scene_ids`:

```python
cfg.merge_from({"actor_config": {"controller_config": {"enable_reverse": False}}})
cfg.merge_from({"actor_config.controller_config.enable_reverse": False})
```

Lists and numeric values are replaced directly. For example, `image_layout` controls the interactive environment's camera layout; this change displays only the front camera:

```python
cfg.merge_from({"image_layout": [["FRONT"]]})
```

`replace_keys` selects fields to replace as a whole. For example, `replace_keys=["actor_config"]` replaces the entire ego configuration, removing omitted fields, so supply a complete ego configuration. This argument applies only at the current level and is not passed into recursive merges.

`allow_list_keys=True` permits numeric strings as list indices. An index equal to the list length appends; an out-of-range index raises KeyError. Assignment to an existing index is not implemented. Assign to the list directly or replace the whole list to change an existing entry.

### Load from a file

Save ordinary numeric values, strings, and lists in JSON or YAML:

```python
cfg = Config.fromfile("simulation.yaml")
```

Set class objects such as Observation, Policy, and Controller in Python scripts; see the [configuration hierarchy example](#section-4-2). `Config.fromfile()` currently raises `NameError` when checking a `.py` file's syntax. See the [Config reference](../reference/config.md) for all methods and implementation limitations.

<a id="section-4-2"></a>

## 4.2 Configuration hierarchy and precedence

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

### Defaults and runtime configuration

Base parameters come from [BASE_DEFAULT_CONFIG](../../../streetworld/configs/default_config.py). ScenarioEnv adds [SCENARIO_ENV_CONFIG](../../../streetworld/configs/default_scenario_config.py), and interactive environments add [INTERACTIVE_ENV_CONFIG](../../../streetworld/envs/interactive_env.py). Construction merges caller-supplied settings last, so they override matching defaults.

The example retains the default AssemblyObservation while changing `decision_repeat` from `5` to 25. `default_config()` returns class defaults. Read `env.config` for the active configuration; after loading a scene, it returns the scene configuration copy held by ScenarioDataManager.

### Merge order in the launch scripts

For nuScenes and Waymo, the Environment Server merges [DEFAULT_POLICY_CONFIG_0_5S](../../../streetworld/configs/default_policy_config.py), the model configuration selected by `--ad-policy-config`, and command-line settings in that order. Later values override matching earlier ones; for example, `--web-port` overrides the configuration's web port.

The NuRec branch builds an environment configuration from command-line arguments, then merges [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py) to set its cameras and navigation mode. It does not apply `--ad-policy-config` and defaults to raw control input. See the [NuRec example](interfaces.md#nurec).

<a id="section-4-3"></a>

## 4.3 Environment and Agent parameters

Environment parameters control the whole scene; Agent parameters control individual objects. This table uses base environment defaults, which launch scripts and model configurations may override.

### Environment

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | Required | Scene IDs to run; the format depends on the dataset. See [Scene asset directories](interfaces.md#scene-files) |
| `random_scenario` | bool | `True` | Select a random scene outside evaluation mode when no scene is specified; `False` cycles through the list in order |
| `physics_world_step_size` | Number, microseconds | `20_000` | Simulation time advanced by each physics step, equivalent to `0.02 s` |
| `decision_repeat` | int, physics steps | `5` | Physics steps per environment step; the default advances `0.1 s` |
| `max_step` | int or None, environment steps | `None` | Episode step limit; `None` disables this environment-level limit, while the ego Agent's `max_step` still applies |
| `async_mode` | bool | `False` | Whether simulation continues while waiting for driving input; see [Synchronous and asynchronous execution](architecture.md#section-2-6) |

### Agent

The ego vehicle uses `actor_config`, and surrounding objects use participant_config. AgentManager reads both. The following table uses ego paths:

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.max_step` | int or None, environment steps | `10_000` | Ego Agent step limit; reaching it ends the episode |
| `actor_config.check_crash` | bool | `True` | Whether to check collisions for this object; ego collisions produce the corresponding termination reason |
| `actor_config.warmup_step` | int or None, environment steps | `None` | When set, ExpertILQRPolicy follows the recorded trajectory for the first specified number of steps, then the configured Policy takes over |

See [Environment](../reference/environment.md) and [AgentManager](../reference/manager.md#api-4-3) for all fields, and [AgentState](interfaces.md#agent-states) for termination states.

<a id="section-4-4"></a>

## 4.4 Observer configuration

An AD policy typically needs both camera images and ego motion/navigation data. Each Observation produces a specific part of that data. `actor_config.observer` selects the ego observation class; `actor_config.observer_config` supplies its parameters.

The default ego Observer, [AssemblyObservation](../reference/observation.md#api-5-4), combines multiple Observations. It constructs each child from configuration, calls them when collecting observations, and returns a dictionary keyed by their configured names. A single `reset()` or `step()` returns images, navigation, ego state, and surrounding objects, while each child retains its own settings.

### Default observations

The complete default ego observation configuration in [BASE_DEFAULT_CONFIG](../../../streetworld/configs/default_config.py) is:

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.gaussian_obs import GaussianObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "actor_config": {
        "observer": AssemblyObservation,
        "observer_config": {
            "gaussian": {
                "observer_class": GaussianObservation,
                "clip_rgb": False,
            },
            "navigation": {
                "observer_class": NavigationObservation,
                "navigating_type": "snap_lane",
                "forecast_type": "distance",
                "forecast_value": 20.0,
                "lateral_offset": 2.0,
                "snap_lane_interval": 2.0,
                "current_lane_max_dist": 2.25,
            },
            "states": {
                "observer_class": StateObservation,
            },
            "surrounding": {
                "observer_class": SurroundingObservation,
                "coordinate_mode": "agent",
                "ignore_dist": None,
            },
        },
    },
})
```

`gaussian`, `navigation`, `states`, and `surrounding` name the children and the four keys in the returned dictionary. Each entry's `observer_class` selects its class; the other fields are passed to that class. For example, `clip_rgb` goes only to GaussianObservation, and `coordinate_mode` goes only to SurroundingObservation.

After constructing the environment with this configuration, read them from `reset()`:

```python
observation, info = env.reset()
images = observation["gaussian"]["image"]
speed = observation["states"]["ego_velo"]
target = observation["navigation"]["target_waypoint"]
objects = observation["surrounding"]
```

`images` is a dictionary keyed by camera name, with local `images` shaped (1, H, W, 3). `speed` is ego `speed` in `m/s`; `target` is a 2D navigation `target` in world coordinates, in meters. `objects` is keyed by participant ID, with poses and velocities transformed into ego coordinates by default.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer` | Class object | `AssemblyObservation` | Creates and combines child Observations |
| `actor_config.observer_config.<observation_name>.observer_class` | Class object | The class for each Observation | Selects the child's observation class; required for every child |
| `actor_config.observer_config.gaussian.clip_rgb` | bool | `False` | `False` produces `uint8` RGB values in 0–255; `True` uses `float32` without dividing by 255 in the current implementation. Use `False` for gRPC image transfer |
| `actor_config.observer_config.gaussian.cameras` | dict | `{}` | An empty or omitted dictionary uses all recorded cameras; a nonempty dictionary specifies every camera to use in this run |
| `actor_config.observer_config.navigation.navigating_type` | str | `snap_lane` | Projects the recorded path onto map lanes; `expert_following` follows the recorded path, and `lane_following` follows map lanes |
| `actor_config.observer_config.navigation.forecast_type` | str | `distance` | Navigation target lookup: `distance` looks ahead by `distance`; `step` looks ahead by path-point index |
| `actor_config.observer_config.navigation.forecast_value` | Number, meters or points | `20.0` | Looks approximately 20 m ahead by default; in `step` mode, this is the number of path points ahead |
| `actor_config.observer_config.navigation.path_interval` | float or None, meters or seconds | `None` | Path resampling interval: meters in `distance` mode; seconds for a recorded path in `step` mode |
| `actor_config.observer_config.navigation.lateral_offset` | float, meters | `2.0` | Produces a left/right turn command when the target's lateral offset in ego coordinates exceeds this value |
| `actor_config.observer_config.navigation.current_lane_max_dist` | float, meters | `2.25` | Map lookup radius for the spawn lane and path-point projection |
| `actor_config.observer_config.navigation.snap_lane_interval` | float | `2.0` | Not read by the current implementation; path sampling uses `path_interval` |
| `actor_config.observer_config.surrounding.coordinate_mode` | str | `agent` | `agent` outputs poses, linear velocities, and linear accelerations in ego coordinates; `world` outputs `world` coordinates |
| `actor_config.observer_config.surrounding.ignore_dist` | float or None, meters | `None` | Includes only objects within this distance of the ego vehicle; no distance filter by default |

### Observations in the default trajectory configuration

[DEFAULT_POLICY_CONFIG_0_5S](../../../streetworld/configs/default_policy_config.py) configures model trajectory input. Merging it with environment defaults retains the four observations above:

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

This configuration sets `navigation.forecast_type`=`step`, `forecast_value`=`6`, and path_interval=0.5. It resamples the recorded path at 0.5 s intervals and queries the sixth point ahead. Cameras are not overridden, so GaussianObservation retains the scene calibration. `project_trajectory_on_camera="FRONT"` overlays trajectories on the web page's front view without changing camera parameters.

### Configure GaussianObservation cameras

To change resolution, focal length, or camera mounting, set gaussian.cameras. For example, [TRANSFUSER_CONFIG](../../../streetworld/configs/transfuser_config.py) defines three front cameras:

```python
cfg.merge_from({
    "actor_config.observer_config.gaussian.cameras": {
        "FRONT_LEFT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (60.0, 0.0, 0.0),
        },
        "FRONT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (0.0, 0.0, 0.0),
        },
        "FRONT_RIGHT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (-60.0, 0.0, 0.0),
        },
    },
    "image_layout": [["FRONT_LEFT", "FRONT", "FRONT_RIGHT"]],
})
```

All three `cameras` are at `(1.3, 0.0, 2.3) m` in vehicle coordinates and produce `480 × 960` images. They face front-left, front, and front-right. A nonempty `cameras` configuration makes GaussianObservation render only the listed `cameras`, so this example returns three front views.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.H` | int, pixels | Required for custom cameras | Image height |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.W` | int, pixels | Required for custom cameras | Image width |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.focal` | float, pixels | Required for custom cameras | Horizontal and vertical focal length; the principal point is at the image center |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.hpr` | Three-element sequence, degrees | Required for custom cameras | Heading, pitch, and roll; zero faces forward, and positive heading turns left |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.offset` | Three-element sequence, meters | Required for custom cameras | Camera position in vehicle coordinates: X forward, Y left, Z up |

`image_layout` controls how images are arranged on the web page; it does not change the observation's cameras. Layout names must match actual cameras. Cameras in the same ST Renderer batch share H and W. NuRec fisheye cameras require extra calibration, which is retained by using scene parameters. See the [camera interface](interfaces.md#render).

See the [Observation reference](../reference/observation.md) for complete outputs and APIs.

<a id="section-4-5"></a>

## 4.5 Policy and Controller configuration

The AD policy passes an action to step(). Policy converts it to control or motion commands, and Controller executes them. The base configuration uses EnvInputPolicy for ego steering and throttle/brake input; surrounding objects use ReplayPolicy to follow recorded trajectories.

### EnvInputILQRPolicy: track a planned trajectory

Use EnvInputILQRPolicy to compute steering and throttle/brake from a model's future `(x, y)` trajectory. `actor_config.policy` selects the class, and `actor_config.policy_config` supplies its parameters. Input points are in ego coordinates; see the [action format](interfaces.md#action-format).

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

`DEFAULT_POLICY_CONFIG_0_1S` uses these timing settings. See [Policy reference](../reference/policy.md#api-6-4) for the complete EnvInputILQRPolicy configuration and API.

### Controller: apply vehicle control

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

Policy.max_acceleration constrains trajectory optimization; the Controller's field of the same name constrains velocity changes during motion. Configure them separately. See [Object / Controller reference](../reference/object.md) for all object settings and vehicle parameters.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 3. Interface contracts](interfaces.md) · [Next chapter: 5. Component reference](../reference/index.md)
