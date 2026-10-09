# 5.2 Manager

[简体中文](../../zh/reference/manager.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.1 Environment](environment.md) · [Next: 5.3 Observation](observation.md)

See [configuration and example conventions](environment.md#reference-conventions).

On this page

- [5.2.1 BaseManager](#api-4-1)
- [5.2.2 ScenarioDataManager](#api-4-2)
- [5.2.3 AgentManager](#api-4-3)

<a id="api-4-1"></a>

## 5.2.1 BaseManager

### Purpose and construction

BaseManager provides object registration, creation, and destruction for Managers. Subclasses can use it to manage multiple physical objects during a scene and release them together when scenes change.

It uses [Randomizable](randomizable.md#api-9-3), stores objects by ID in `spawned_objects`, and calls their `destroy()` during cleanup. Environment calls each concrete Manager's `reset()`, `step()`, and `update_state()` directly; it does not automatically run every before/after hook.

Source: [streetworld/manager/base_manager.py](../../../streetworld/manager/base_manager.py).

### Configuration

Pass object constructor arguments through _spawn_object kwargs. BaseManager has no Config argument; subclasses store their own configuration.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self)` | — | None | Creates random state and an empty spawned_objects registry. | — |
| Instance method<br>`before_step(self, *args, **kwargs) -> dict` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Pre-step hook; the base implementation returns an empty dictionary. | — |
| Instance method<br>`step(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | None | Advancement hook; the base implementation does nothing. | — |
| Instance method<br>`after_step(self, *args, **kwargs) -> dict` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Post-step hook; the base implementation returns an empty dictionary. | — |
| Instance method<br>`before_reset(self)` | — | None | Destroys all objects created by this Manager. | — |
| Instance method<br>`reset(self)` | — | None | Scene-reset hook; the base implementation does nothing. | — |
| Instance method<br>`after_reset(self)` | — | None | Post-reset hook; the base implementation does nothing. | — |
| Instance method<br>`destroy(self)` | — | None | Clears the random generator and all managed objects. | — |
| Instance method<br>`clear_object(self, object_id)` | `object_id`: object ID | The destroyed Object instance | Removes the object from spawned_objects and calls destroy. | Unknown IDs raise KeyError. |
| Instance method<br>`clear_all_objects(self)` | — | None | Destroys all entries and clears spawned_objects. | — |
| Instance method<br>`get_metadata(self)` | — | dict | Reads metadata before the first step; the base implementation returns an empty dictionary. | The checked episode_step property is not defined in BaseManager, so direct calls raise AttributeError. |
| Protected method<br>`_spawn_object(self, object_class, **kwargs)` | `object_class`: Object class to construct; `**kwargs`: keyword arguments | Object instance | Constructs object_class with kwargs and stores it under object.id. | Constructor errors propagate. Duplicate IDs overwrite registry entries without a check. |

### Example

```python
from streetworld.manager.base_manager import BaseManager

class ObjectManager(BaseManager):
    def create(self, object_class, **kwargs):
        return self._spawn_object(object_class, **kwargs)

manager = ObjectManager()
manager.seed(7)
print(manager.spawned_objects)
manager.destroy()
```

<a id="api-4-2"></a>

## 5.2.2 ScenarioDataManager

### Purpose and construction

ScenarioDataManager prepares recorded scenes for simulation. It resamples ego and participant trajectories onto the physics timeline so initialization, replay, and physics use consistent timestamps despite different recording intervals.

BaseEnv constructs it with configuration and metadata/model loading callbacks. `reset()` selects a scene, loads data and rendering models, prepares object initial states and camera parameters, and adjusts the ego origin and camera extrinsics for Controller height.

Source: [streetworld/manager/scenario_data_manager.py](../../../streetworld/manager/scenario_data_manager.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | Required | Available scene IDs; scene count is the list length and cannot be replaced by num_scenarios |
| `start_scenario_index` | int | `0` | Initial index for sequential sampling; the evaluation queue still begins at 0 |
| `random_scenario` | bool | `True` | Random selection outside evaluation when no scene_id is given; False cycles sequentially |
| `physics_world_step_size` | Number, µs | 20_000 (environment default) | Interval for alignment and interpolation of recorded tracks |
| `ego_z_height` | float, m | `0.0` | Height of the recorded ego origin; corrected by half the Controller height minus this value |
| `actor_config.controller` | Object class | DefaultVehicle (environment default) | Determines ego height and object type; supplied by complete environment configuration |
| `actor_config.controller_config.size` | Three-element sequence or None, meters | `None` | Uses the third element as ego height when supplied, otherwise the class DEFAULT_HEIGHT |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config, meta_loader, model_loader)` | `config`: component configuration dictionary; `meta_loader`: SimulatorInterface.load_metadata callback; `model_loader`: SimulatorInterface.load_model callback | None | Stores configuration/loaders and initializes the scene list and index. | Non-list scene_ids raises TypeError; an empty list cannot select a scene later. |
| Instance method<br>`eval(self, order=True, repeat_per_scene=1)` | `order`: ordering flag; `repeat_per_scene`: number of passes through the scene list | None | Rebuilds the index queue and enters evaluation mode. | order=False changes random_scenario without shuffling. repeat=2 repeats the whole list as A,B,A,B. |
| Instance method<br>`reset(self, scene_id=None)` | `scene_id`: ID in scene_ids, selected by Manager when None | VectorMap or None | Selects a scene, copies active configuration, loads/reformats metadata, prepares plane data, and calls model_loader. | The evaluation queue takes precedence over scene_id and raises LookupError when exhausted. Outside evaluation, an unknown ID raises ValueError. |
| Instance method<br>`get_current_scenario_data(self)` | — | dict | Returns current_metadata for ground, Agent, and camera creation. | Available after the first reset; returns the original object. |
| Instance method<br>`sort_scenarios(self)` | — | None, incomplete implementation | Curriculum difficulty sorting interface. | Incomplete: references uninitialized engine/summary_lookup and undefined scenario/SD. |
| Instance method<br>`destroy(self)` | — | None | Performs base object cleanup, then clears scene cache fields. | summary_lookup/mapping are not initialized by construction; calling this raises AttributeError. |
| Property getter<br>`current_scenario_difficulty(self)` | — | Number | Returns 0 when no difficulty table exists. | With a difficulty table, still depends on legacy summary_lookup/engine fields; sorting is not connected. |

The following metadata is available after loading.

| Field | Format and purpose |
| --- | --- |
| timestamp_range | Start/end microsecond timestamps aligned to ego recordings |
| scene_id | Current scene ID |
| camera_params | Camera K, H, W, ego2camera, and optional extra |
| ego_poses | Recorded ego poses after height correction |
| participants | Original participant poses, size, and type |
| init_state | Keyed by Agent name; contains spawn_position, spawn_yaw, spawn_velocity, spawn_angular_velocity, destination, and destination_yaw |
| agent_state | Keyed by Agent name and timestamp; each frame contains transform, position, velocity, angular_velocity, heading_theta, valid, and vehicle_class |
| ground_plane | Plane normal/constant; Environment uses mesh terrain when available |
| scene_mesh_path, scene_mesh_transform | Optional ground mesh path and coordinate transform |

Manager generates sample timestamps excluding the end time. An object with fewer than two recorded samples gets no trajectory. Ego recordings determine the scene time range.

### Example

```python
# The environment is already reset and manages this Manager's loading sequence.
manager = env.data_manager
metadata = manager.get_current_scenario_data()
print(metadata["timestamp_range"])
print(metadata["init_state"]["actor"])
print(metadata["agent_state"]["actor"].keys())
```

<a id="api-4-3"></a>

## 5.2.3 AgentManager

### Purpose and construction

AgentManager connects one Agent's Observer, Policy, and Controller. It also checks spawning, collisions, and destination arrival, allowing Environment to advance ego and surrounding participants through the same flow.

BaseEnv creates AgentManagers from ego/participant settings. `reset()` creates the Controller and passes scene data to Observer and Policy. The ego Manager persists across scenes; participant Managers are recreated. Observer and Policy are created only on the first reset, so later class-setting changes do not recreate them.

Source: [streetworld/manager/agent_manager.py](../../../streetworld/manager/agent_manager.py).

### Configuration

The config constructor argument takes actor_config or participant_config contents. The table uses complete environment paths for editing these settings.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.check_crash` | bool | `True` | Checks collisions for nonstatic vehicles in ALIVE state |
| `actor_config.max_step` | int or None, environment steps | `10_000` | This Agent's step limit, distinct from top-level max_step |
| `actor_config.observer` | Observation class | `AssemblyObservation` | Created on the first reset |
| `actor_config.observer_config` | dict | `gaussian/navigation/states/surrounding` | Passed to Observer; fields are described under each Observation |
| `actor_config.policy` | Policy class | `EnvInputPolicy` | Created on first reset; output goes to Controller.move |
| `actor_config.policy_config` | dict | See each Policy | Passed to Policy; also supplies Manager.out_of_road_threshold |
| `actor_config.controller` | Object class | `DefaultVehicle` | Creates a Controller of this class on every reset |
| `actor_config.controller_config` | dict | See [BaseVehicle](object.md#api-7-2) | Physics and spawn settings |
| `actor_config.warmup_step` | int or None, environment steps | `None` | When not None, creates ExpertILQRPolicy and uses it while eposide_step is below this value |
| `actor_config.policy_config.out_of_road_threshold` | float, m | `5.0` | Nearby-lane lookup radius with a map; without a map, compares distance to recorded trajectory samples |
| `participant_config.check_crash` | bool | `True` | Collision checking for surrounding vehicles |
| `participant_config.max_step` | int or None, environment steps | `10_000` | Surrounding Agent step limit |
| `participant_config.observer` | Observation class | `DefaultObservation` | Surrounding vehicles do not collect observations by default |
| `participant_config.observer_config` | dict | `{}` | Passed to the participant Observer |
| `participant_config.policy` | Policy class | `ReplayPolicy` | Surrounding vehicles replay recordings by default |
| `participant_config.policy_config` | dict | Same discrete-action fields as ego | ReplayPolicy does not read discrete-action fields |
| `participant_config.policy_config.discrete_action` | bool | `False` | EnvInputPolicy input mode; default ReplayPolicy does not read it |
| `participant_config.policy_config.discrete_steering_dim` | int | `5` | EnvInputPolicy steering levels; default ReplayPolicy does not read it |
| `participant_config.policy_config.discrete_throttle_dim` | int | `5` | EnvInputPolicy throttle/brake levels; default ReplayPolicy does not read it |
| `participant_config.policy_config.action_check` | bool | `False` | EnvInputPolicy input checking; default ReplayPolicy does not read it |
| `participant_config.controller` | Object class | Supplied from metadata type/dimensions | Vehicles use a Vehicle class; pedestrians/cyclists use their dedicated classes |
| `participant_config.controller_config` | dict | `size=None, enable_reverse=True, spawn_velocity=True, check_crash_world=False` | Scene dimensions override size. Environment assigns DummyObservation/ReplayPolicy to pedestrians and cyclists |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config, step_manager)` | `config`: component configuration dictionary; `step_manager`: StepCounter instance | None | Stores configuration and timing, initializing uncreated component references to None. | Requires max_step and check_crash; required component settings are read on first reset. |
| Instance method<br>`reset(self, config=None, **kwargs)` | `config`: optional updated settings; `kwargs`: runtime context including state, init_state, physics_world, render_fn, camera_params, collector, trajdata_map, and ground | None | Creates Controller, initializes Policy/Observer, and prepares spawn time, trajectories, and map. | kwargs must include scene state/init_state and component reset inputs. IDM route initialization failure selects ReplayPolicy or TrajectoryIDMPolicy based on recorded path length. |
| Instance method<br>`step(self, action)` | `action`: external input in the current Policy's format | None | For nonstatic ALIVE Agents, calls active_policy to compute the action, then Controller.move. | — |
| Instance method<br>`initialize_state(self)` | — | None | Attaches Controller and enters ALIVE on the key_step reaching Policy spawn time. | — |
| Instance method<br>`update_state(self)` | — | None | Checks spawning, collision, Agent steps, road range, and destination in order; updates state and clears terminated objects. | — |
| Instance method<br>`set_state(self, new_state)` | `new_state`: AgentState value | None | Sets state externally; NOT_SPAWN→ALIVE attaches the body, and listed terminal states clear objects. | OUT_OF_STEP is absent from this method's cleanup list; normal advancement handles it in update_state. |
| Instance method<br>`observe(self)` | — | {'observation': observation_or_None} | Collects and caches Observer output when ALIVE; other states return the last cache. | — |
| Instance method<br>`get_base_state(self, transform=None)` | `transform`: 4×4 homogeneous `transform` | dict | Returns world pose/motion, dimensions, type, and map lane; static Agents have zero motion values. | Non-ALIVE Agents raise ValueError. Controller.transform overwrites the transform argument, so it cannot specify a sampling pose. |
| Instance method<br>`get_observation_spaces(self)` | — | Observer space declaration | Returns observer.observation_space directly. | Use after Observer creation and any required reset. |
| Instance method<br>`get_action_spaces(self)` | — | gym.Space | Returns active_policy.get_input_space. | During warmup, the expert Policy supplies the space. Trajectory Policies inherit a two-control input declaration. |
| Instance method<br>`get_state(self)` | — | dict, incomplete implementation | Agent state export is incomplete. | BaseManager has no get_state and _agent_object is undefined; calls raise AttributeError. |
| Instance method<br>`destroy(self)` | — | None | After initialization, clears objects and all three components; otherwise returns immediately. | — |
| Property getter<br>`is_static(self)` | — | bool | Returns whether the current Policy considers the recorded track static. | — |
| Property getter<br>`active_policy(self)` | — | BasePolicy subclass instance | Returns the expert during warmup and the configured Policy afterward. | — |
| Property getter<br>`is_warmup_step(self)` | — | bool | True when an expert Policy exists and eposide_step < warmup_step. | — |

AgentState includes NOT_SPAWN, ALIVE, SUCCESS, OUT_OF_ROAD, OUT_OF_STEP, CRASH_VEHICLE, CRASH_HUMAN, CRASH_OBJECT, CRASH_WORLD, and IDLE. When conditions coincide, update_state's check order determines reason. At termination it destroys physical objects while retaining Manager state and the last observation for the environment response.

With a map, checks lanes near the center of the vehicle's bottom face. Without one, checks minimum horizontal distance to recorded path points. get_base_state uses a fixed 2.25 m current-lane lookup radius, independent of NavigationObservation.current_lane_max_dist.

### Example

```python
# The environment is already reset; it advances the ego vehicle, so do not call manager.step separately.
manager = env.actor_manager
print(manager.state, manager.active_policy.name)
print(manager.get_base_state()["velocity"])
print(manager.is_warmup_step)
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.1 Environment](environment.md) · [Next: 5.3 Observation](observation.md)
