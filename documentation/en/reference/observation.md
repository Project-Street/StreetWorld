# 5.3 Observation

[简体中文](../../zh/reference/observation.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.2 Manager](manager.md) · [Next: 5.4 Policy](policy.md)

See [API reference contents](index.md) for configuration paths and example variables.

On this page

- [5.3.1 BaseObservation](#api-5-1)
- [5.3.2 DummyObservation](#api-5-2)
- [5.3.3 DefaultObservation](#api-5-3)
- [5.3.4 AssemblyObservation](#api-5-4)
- [5.3.5 GaussianObservation](#api-5-5)
- [5.3.6 StateObservation](#api-5-6)
- [5.3.7 NavigationObservation](#api-5-7)
- [5.3.8 SurroundingObservation](#api-5-8)
- [5.3.9 CollisionBodyObservation](#api-5-9)

<a id="api-5-1"></a>

## 5.3.1 BaseObservation

### Purpose and construction

BaseObservation defines how simulation data becomes Agent input. Cameras, motion state, and navigation need different collection methods; a shared interface lets AgentManager call them consistently and supports new observation types.

Subclasses implement `observe()` and `observation_space` and receive scene inputs through reset(). AgentManager first passes Controller and other context to `reset()`, then calls observe(). Base construction stores a configuration copy.

Source: [streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py).

### Configuration

Subclasses define config fields; reset receives scene/object context. BaseObservation prescribes no application settings.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config)` | `config`: component configuration dictionary | None | Deep-copies configuration on initial construction. | — |
| Instance method<br>`observe(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | Defined by subclasses | Observation collection interface. | The base implementation raises NotImplementedError. |
| Instance method<br>`reset(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | None | Scene-context hook; the base implementation does nothing. | — |
| Instance method<br>`destroy(self)` | — | None | Resource cleanup hook; the base implementation does nothing. | — |
| Property getter<br>`observation_space(self)` | — | Defined by subclasses | Observation space interface. | The base implementation raises NotImplementedError. |

### Example

```python
import gymnasium as gym
from streetworld.obs.observation_base import BaseObservation

class SpeedObservation(BaseObservation):
    def reset(self, controller, **kwargs):
        self.controller = controller

    def observe(self):
        return float(self.controller.speed)

    @property
    def observation_space(self):
        return gym.spaces.Box(0.0, float("inf"), shape=())
```

<a id="api-5-2"></a>

## 5.3.2 DummyObservation

### Purpose and construction

DummyObservation is an empty Observer for replay objects. Replay gets motion from recordings but still needs the AgentManager Observer interface; returning an empty dictionary satisfies that call flow for participants needing no observations.

BaseEnv assigns it to pedestrians and cyclists with ReplayPolicy. It can also be constructed directly; construction logs a warning, and `observe()` returns an empty dictionary.

Source: [streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py).

### Configuration

No additional configuration.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config=None)` | `config`: component configuration dictionary | None | Initializes the empty Observer and logs a DummyObservation warning. | — |
| Instance method<br>`observe(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Returns {} on every call. | — |
| Property getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | Declares a one-dimensional Box in [0, 1]. | observe returns an empty dictionary, which differs from the declared space. |

### Example

```python
from streetworld.obs.observation_base import DummyObservation

observer = DummyObservation({})
print(observer.observe())
```

<a id="api-5-3"></a>

## 5.3.3 DefaultObservation

### Purpose and construction

DefaultObservation is the empty Observer used by surrounding vehicles by default. ReplayPolicy updates them from recorded tracks, so an empty observation maintains the AgentManager flow without collecting inputs.

Selected through participant `observer` configuration and normally created on the first AgentManager `reset()`, it returns an empty dictionary. Unlike [DummyObservation](#api-5-2), construction does not log a warning.

Source: [streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py).

### Configuration

No additional configuration.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config=None)` | `config`: component configuration dictionary | None | Initializes the empty Observer, using an empty dictionary when config is None. | — |
| Instance method<br>`observe(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Returns {} on every call. | — |
| Property getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | Declares a one-dimensional Box in [0, 1]. | observe returns an empty dictionary, which differs from the declared space. |

### Example

```python
from streetworld.obs.observation_base import DefaultObservation

observer = DefaultObservation({})
print(observer.observe())
```

<a id="api-5-4"></a>

## 5.3.4 AssemblyObservation

### Purpose and construction

AssemblyObservation combines Observers into one dictionary. AD policies often need cameras, vehicle state, and navigation together; users can add, remove, or replace a child while retaining the other observation sources.

Construction creates children from observer_class. `observe()` places their outputs under names such as `gaussian`, `states`, and navigation. `reset()` passes the same scene arguments to every child; custom Observers can accept unused inputs with **kwargs.

Source: [streetworld/obs/assembly_obs.py](../../../streetworld/obs/assembly_obs.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer` | Observation class | `AssemblyObservation` | Selects combined observations |
| `actor_config.observer_config.<observation_name>.observer_class` | Observation class | Required | Creates the child Observer; <observation_name> is also its output dictionary key |
| `actor_config.observer_config.<observation_name>.<field>` | Defined by the child Observer | See each subclass | After removing observer_class, passes remaining settings to child construction |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config: Dict[str, Any])` | `config`: component configuration dictionary | None | Creates children and stores their names/classes. | Missing observer_class raises ValueError; the misspelling obsever_class is not accepted. |
| Instance method<br>`reset(self, **kwargs)` | `**kwargs`: keyword arguments | None | Passes all kwargs unchanged to every child Observer.reset. | Does not filter arguments by signature; unsupported arguments raise TypeError in children. |
| Instance method<br>`observe(self)` | — | dict[str, observation] | Calls each observe and returns results by configured name. | — |
| Instance method<br>`destroy(self)` | — | None | Destroys children and clears the container. | — |
| Property getter<br>`observation_space(self)` | — | gym.spaces.Dict | Combines spaces by name, wrapping plain space dictionaries in gym.spaces.Dict. | Does not validate child spaces against actual outputs. |

### Example

```python
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.observation_base import DefaultObservation

observer = AssemblyObservation({"empty": {"observer_class": DefaultObservation}})
observer.reset()
assert observer.observe() == {"empty": {}}
observer.destroy()
```

<a id="api-5-5"></a>

## 5.3.5 GaussianObservation

### Purpose and construction

GaussianObservation produces camera inputs for visual AD policies. After ego motion changes the pose, it updates camera extrinsics and renders the current view, closing the loop between visual input and vehicle motion.

AgentManager passes Controller, a render callback, and camera parameters on reset(). `observe()` calls SimulatorInterface.render() and returns images/calibration. Cameras come from scene metadata unless `cameras` is configured.

Source: [streetworld/obs/gaussian_obs.py](../../../streetworld/obs/gaussian_obs.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.gaussian.clip_rgb` | bool | False (environment default; required by class construction) | Selects image buffer dtype and space bounds; True uses float32 without dividing RGB values by 255 |
| `actor_config.observer_config.gaussian.cameras` | dict | `{}` | Empty uses metadata cameras; nonempty replaces them with this camera set |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.H` | int, px | Required | Image height |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.W` | int, px | Required | Image width |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.focal` | float, px | Required | Focal length; K uses equal fx/fy and a centered principal point |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.offset` | Three-element sequence, meters | Required | Camera center in vehicle coordinates |
| `actor_config.observer_config.gaussian.cameras.<camera_name>.hpr` | Three-element sequence, degrees | Required | Heading/pitch/roll; extrinsics use ZYX rotation |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config)` | `config`: component configuration dictionary | None | Stores clip_rgb and configured cameras. | Missing clip_rgb raises KeyError. |
| Instance method<br>`reset(self, controller, render_fn, camera_params, **kwargs)` | `controller`: current Agent Controller; `render_fn`: SimulatorInterface.render or a callback with the same signature; `camera_params`: scene camera metadata; `**kwargs`: keyword arguments | None | Builds camera intrinsics/extrinsics, batch render arguments, and per-camera image buffers. | Missing K/H/W/ego2camera in metadata or required custom camera fields raises ValueError. |
| Instance method<br>`an_observation_shape(self, h, w)` | `h`: image height in pixels; `w`: image width in pixels | (1, h, w, 3) | Returns the RGB shape including a single-frame dimension. | — |
| Instance method<br>`observe(self)` | — | {'camera_info': dict, 'image': dict} | Computes world-to-camera transforms from the current ego transform, calls backend render, and updates images/calibration. | Call reset first. Images reuse internal buffers; copy them if retaining historical frames. |
| Instance method<br>`destroy(self)` | — | None | Releases image buffer references. | Environment.close owns renderer cleanup. |
| Property getter<br>`observation_space(self)` | — | dict[str, Box] | Declares one image space per camera; clip_rgb=False gives uint8 [0, 255]. | Includes images only, without camera_info. clip_rgb=True declares [0, 1] but does not normalize images. |

image contains {camera_name: ndarray(1,H,W,3)}; camera_info contains {camera_name: {K, H, W, ego2camera, extra?}}. K is a 3×3 intrinsic matrix; ego2camera is a 4×4 extrinsic transform. Metadata extra is passed to the backend, such as NuRec logical_id. Custom cameras generate only K, H, W, and ego2camera.

For gRPC images, set server clip_rgb=False to transmit uint8 RGB bytes. ST Renderer batch cameras must share H/W; see the [renderer contract](../guides/interfaces.md#render).

### Example

```python
# cfg is the full environment configuration; modify it before constructing the environment.
cfg.merge_from({"actor_config.observer_config.gaussian.cameras": {
    "FRONT": {"H": 480, "W": 960, "focal": 760.0,
              "offset": [1.3, 0.0, 2.3], "hpr": [0.0, 0.0, 0.0]},
}})
cfg.merge_from({"image_layout": [["FRONT"]]})
```

<a id="api-5-6"></a>

## 5.3.6 StateObservation

### Purpose and construction

StateObservation provides an Agent's motion state. AD policies, rewards, and metrics need position, velocity, steering, and related state; this component exposes physical object state as observation fields.

`reset()` stores Controller and collector. `observe()` finds the current Controller in collected object `states` and reads pose, velocity, acceleration, steering, and lane information. The default AssemblyObservation returns it under states.

Source: [streetworld/obs/state_obs.py](../../../streetworld/obs/state_obs.py).

### Configuration

Pass Controller and collector on reset; no additional configuration.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config=None)` | `config`: component configuration dictionary | None | Initializes Controller/collector references and space constants. | — |
| Instance method<br>`reset(self, controller, collector, seed=None, **kwargs)` | `controller`: current Agent Controller; `collector`: no-argument callback returning base states by object ID; `seed`: random `seed`, with None using caller/environment random state; `**kwargs`: keyword arguments | None | Stores Controller and the object collection callback. | seed is unused. |
| Instance method<br>`observe(self)` | — | dict | Collects ego state; fields, units, and shapes are listed below. | collector must include the current Controller, which must expose vehicle steering/acceleration methods; missing inputs cause errors. |
| Instance method<br>`destroy(self)` | — | None | Clears Controller/collector references. | — |
| Property getter<br>`observation_space(self)` | — | gym.spaces.Dict | Declares position(2), velocity(2), and a heading_theta scalar. | Actual output uses ego_pos, linear_velocity, and other fields that differ from this declaration. |

| Field | Type, unit, and meaning |
| --- | --- |
| ego_pos | float32 (3,), ego world position in meters |
| ego_rot | float32 (3,), XYZ Euler angles converted from rotation, radians |
| heading_theta | float, horizontal heading in radians |
| ego_steer | float, normalized steering × maximum wheel angle, radians |
| linear_velocity | float32 (3,), world linear velocity in m/s |
| ego_velo | float, horizontal speed in m/s |
| linear_acceleration | float32 (3,), first two values from Controller.get_longitudinal_acceleration and a zero third component |
| accelerate | float32 (3,), world acceleration from total Bullet force / mass, m/s² |
| angular_velocity | float32 (3,), only Z contains yaw rate, rad/s |
| angular_acceleration | float32 (3,), only Z contains yaw acceleration, rad/s² |
| current_lane | Local RoadLane or None; the object becomes a string through gRPC |

get_longitudinal_acceleration multiplies horizontal acceleration and heading elementwise, returning a two-element vector rather than a scalar dot product.

### Example

```python
# observation is returned by env.reset or env.step.
states = observation["states"]
print(states["ego_pos"], states["ego_velo"])
print(states["heading_theta"], states["ego_steer"])
```

<a id="api-5-7"></a>

## 5.3.7 NavigationObservation

### Purpose and construction

NavigationObservation provides the route and lookahead target. Cameras and motion state alone do not specify the driving task's route; this component supplies paths, target points, and turn commands to AD policies and a reference for path rewards/progress.

`reset()` builds a path from recorded tracks, map lanes, or tracks projected onto lane centers. `observe()` updates the target/command from current vehicle position. AgentManager supplies Controller, recorded states, and map; Randomizable manages path-generation choices.

Source: [streetworld/obs/navigation_obs.py](../../../streetworld/obs/navigation_obs.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.navigation.navigating_type` | str | snap_lane (environment); expert_following (class) | expert_following, lane_following, or snap_lane |
| `actor_config.observer_config.navigation.forecast_type` | str | `distance` | distance looks ahead in meters; step looks ahead by path-point index |
| `actor_config.observer_config.navigation.forecast_value` | Number, meters or points | `20.0` | Lookahead amount; the default trajectory preset changes this to step/6 |
| `actor_config.observer_config.navigation.path_interval` | float or None, meters or seconds | `None` | distance resamples by arc length; step resamples recorded paths by time. lane_following only supports distance resampling |
| `actor_config.observer_config.navigation.lateral_offset` | float, m | `2.0` | Target lateral offset relative to current heading used for left/right commands |
| `actor_config.observer_config.navigation.current_lane_max_dist` | float, m | `2.25` | Map lookup radius for spawn lanes and path-point projection |
| `actor_config.observer_config.navigation.snap_lane_interval` | float | 2.0 (environment default) | Unused; path_interval controls sampling |
| `actor_config.observer_config.navigation.carla_style_target` | dict or None | `None` | Adds a Carla-style target for snap_lane routes; supply all listed subfields when configuring it |
| `actor_config.observer_config.navigation.carla_style_target.hop_resolution` | float, m | Required; 1.0 in the TransFuser preset | Spacing for route densification |
| `actor_config.observer_config.navigation.carla_style_target.sample_factor` | float, m | Required; 50.0 in the TransFuser preset | Cumulative distance threshold for segmented route downsampling |
| `actor_config.observer_config.navigation.carla_style_target.min_distance` | float, m | Required; 7.5 in the TransFuser preset | Distance threshold for consuming nearby route points |
| `actor_config.observer_config.navigation.carla_style_target.max_distance` | float, m | Required; 50.0 in the TransFuser preset | Maximum distance for checking route points ahead |
| `actor_config.observer_config.navigation.carla_style_target.road_option_angle_threshold` | float, degrees | Required; 35.0 in the TransFuser preset | Marks segment boundaries using adjacent-line turn angles |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config)` | `config`: component configuration dictionary | None | Stores navigation/target settings and initializes path/random state. | — |
| Instance method<br>`reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, **kwargs)` | `trajdata_map`: current trajdata.VectorMap, or None; `init_state`: spawn/destination dictionary; `state`: recorded states keyed by microsecond timestamp; `controller`: current Agent Controller; `seed`: random `seed`, with None using caller/environment `state`; `**kwargs`: keyword arguments | None | Creates the path using navigating_type and stores destination/map location. | lane_following/snap_lane need VectorMap. Missing spawn lane raises RuntimeError in lane_following; unknown types raise ValueError. |
| Instance method<br>`observe(self)` | — | dict | Returns target/turn command, the full path, and location. | Call reset first. Unknown forecast_type raises ValueError; only snap_lane produces carla_style_target. |
| Instance method<br>`destroy(self)` | — | None | Releases paths, reference tracks, Controller, map, and scene references. | — |
| Instance method<br>`get_reference_state(self, idx)` | `idx`: navigation path index | dict or None | Gets expert speed, angular velocity, heading, and position at a clipped valid index. | Only expert_following builds the expert reference; other modes return None. |
| Property getter<br>`observation_space(self)` | — | Discrete(3) | Declares a turn-command space. | observe returns a full dictionary with turn values -1/0/1, which are not mapped to this declaration. |

| Field | Type, coordinates, and meaning |
| --- | --- |
| navigating_type | Current navigation mode string |
| turn_signal | -1 right, 0 straight, 1 left, determined by target lateral offset in vehicle coordinates |
| waypoint | World-coordinate (N, 2) path in meters |
| cummulative_length | N cumulative path distances in meters; spelling follows the source |
| target_waypoint | World-coordinate (2,) target in meters |
| location | Map location string, or None without a map |
| carla_style_target | Optional world-coordinate (2,) target in meters |

lane_following extends roughly 200 m along successor lanes and chooses branches randomly. snap_lane retains recorded points when no lane is found. expert_following and lane_following may apply Savitzky–Golay smoothing; snap_lane uses projected points.

### Example

```python
# cfg is the full environment configuration; expert_following does not require a map.
cfg.merge_from({
    "actor_config.observer_config.navigation.navigating_type": "expert_following",
    "actor_config.observer_config.navigation.forecast_type": "step",
    "actor_config.observer_config.navigation.forecast_value": 6,
    "actor_config.observer_config.navigation.path_interval": 0.5,
})
```

<a id="api-5-8"></a>

## 5.3.8 SurroundingObservation

### Purpose and construction

SurroundingObservation collects participant state for Policies and metrics. Following policies need object positions, velocities, and dimensions, while metrics use them to estimate collision risk.

`reset()` stores the current Controller and collector. Collection excludes ego, converts coordinates, and filters distance as configured. Default AssemblyObservation returns the result under surrounding.

Source: [streetworld/obs/surrounding_obs.py](../../../streetworld/obs/surrounding_obs.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.surrounding.coordinate_mode` | str | agent (environment default; required by class construction) | agent returns vehicle coordinates; world returns world coordinates. Any string other than agent uses the world branch |
| `actor_config.observer_config.surrounding.ignore_dist` | float or None, meters | `None` | Retains objects within this 3D position distance; filtering uses CUDA tensors |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config)` | `config`: component configuration dictionary | None | Reads coordinate mode and optional distance threshold. | Missing coordinate_mode raises KeyError. |
| Instance method<br>`reset(self, collector, controller, **kwargs)` | `collector`: no-argument callback returning base states by object ID; `controller`: current Agent Controller; `**kwargs`: keyword arguments | None | Stores the object collection callback and current Controller. | — |
| Instance method<br>`observe(self)` | — | dict[str, dict] | Returns surrounding state by object ID. agent mode rotates velocity/acceleration and computes relative pose/heading. | Distance filtering with surrounding objects requires CUDA. Velocities are rotated only; ego velocity is not subtracted. |
| Instance method<br>`destroy(self)` | — | None | Releases Controller/collector references. | — |
| Property getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | Provides a placeholder for variable object counts. | Actual output is keyed by object ID and cannot be validated against this Box. |

Each object includes transform(4,4), position(3,), velocity(3,), acceleration(3,), heading_theta, angular_velocity, angular_acceleration, current_lane, covered_lanes, size(length/width/height), and type. Position is in meters; see [observation units](../guides/interfaces.md#observation-data) for the rest. Lane fields retain map object references and do not transform with coordinate mode.

IDMPolicy and TrajectoryIDMPolicy read surrounding positions/velocities in world coordinates; set coordinate_mode="world" for them. Default ego metrics compute TTC in vehicle coordinates, so retain agent mode there.

### Example

```python
# observation is from an environment that has been reset.
for object_id, state in observation["surrounding"].items():
    print(object_id, state["position"], state["velocity"], state["type"])
```

<a id="api-5-9"></a>

## 5.3.9 CollisionBodyObservation

### Purpose and construction

CollisionBodyObservation renders physical collision geometry as camera images to inspect collision box dimensions, poses, and terrain contact. It displays the geometry used by simulation so contact results can be compared with object locations in camera views.

Add it through Observer configuration. `reset()` receives Controller, the object collection callback, and ground. It renders boxes/terrain through Panda3D on a dedicated thread; `destroy()` shuts down the thread and releases resources.

Source: [streetworld/obs/collision_body_obs.py](../../../streetworld/obs/collision_body_obs.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.observer_config.collision_body.observer_class` | Observation class | Explicitly add CollisionBodyObservation | Adds this child to AssemblyObservation |
| `actor_config.observer_config.collision_body.cameras` | Nonempty dict | Required | Maps camera names to camera settings |
| `actor_config.observer_config.collision_body.cameras.<camera_name>.H` | Positive integer, pixels | Required | Image height; bool is not accepted as an integer |
| `actor_config.observer_config.collision_body.cameras.<camera_name>.W` | Positive integer, pixels | Required | Image width; bool is not accepted as an integer |
| `actor_config.observer_config.collision_body.cameras.<camera_name>.focal` | Positive finite number, pixels | Required | Pinhole focal length |
| `actor_config.observer_config.collision_body.cameras.<camera_name>.offset` | Three finite values, meters | Required | Camera position in vehicle coordinates; renders ego itself when outside the ego bounding box |
| `actor_config.observer_config.collision_body.cameras.<camera_name>.hpr` | Three finite values, degrees | Required | Same ZYX orientation convention as GaussianObservation |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config: Mapping[str, Any])` | `config`: component configuration dictionary | None | Validates/stores cameras without starting the render thread yet. | Missing cameras/fields or invalid values raises ValueError. Non-mapping camera entries or non-integer H/W raises TypeError. |
| Instance method<br>`reset(self, controller: Any, collector: Any, ground: Any, **kwargs) -> None` | `controller`: current Agent Controller; `collector`: no-argument callback returning base states by ID; `ground`: current GroundPlane or MeshTerrain; `**kwargs`: keyword arguments | None | Stores Controller/collector, creates the render thread, updates the ground snapshot, and decides whether each camera draws ego. | ground must be GroundPlane or MeshTerrain. |
| Instance method<br>`observe(self) -> Dict[str, np.ndarray]` | — | dict[str, ndarray(H,W,3)] | Renders RGB uint8 images from current physical poses, using different colors for vehicles, pedestrians, and cyclists. | Calls before reset or a collector missing ego raise RuntimeError; unknown object types raise ValueError. |
| Instance method<br>`destroy(self) -> None` | — | None | Stops the render thread and clears references. | — |
| Property getter<br>`observation_space(self) -> gym.spaces.Dict` | — | gym.spaces.Dict | Each camera is Box(0,255,(H,W,3),uint8). | — |

Collision images omit GaussianObservation's frame dimension. WebUI image_layout combines only gaussian.image and does not show collision_body. gRPC does not transmit it; read observation["collision_body"] locally.

### Example

```python
from streetworld.obs.collision_body_obs import CollisionBodyObservation

# Add a child Observer to the full cfg before constructing the environment.
cfg.merge_from({"actor_config.observer_config.collision_body": {
    "observer_class": CollisionBodyObservation,
    "cameras": {"CHASE": {"H": 480, "W": 640, "focal": 420.0,
                           "offset": [-8.0, 0.0, 4.0], "hpr": [0.0, 15.0, 0.0]}},
}})
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.2 Manager](manager.md) · [Next: 5.4 Policy](policy.md)
