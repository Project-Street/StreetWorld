# 5.1 Environment

[简体中文](../../zh/reference/environment.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5. API reference](index.md) · [Next: 5.2 Manager](manager.md)

See [API reference contents](index.md) for configuration paths and example variables.

On this page

- [5.1.1 BaseEnv](#api-1-1)
- [5.1.2 ScenarioEnv](#api-1-2)
- [5.1.3 InteractiveScenarioEnv](#api-1-3)
- [5.1.4 GrpcClientEnv](#api-2-1)
- [5.1.5 EnvServicer](#api-2-2)
- [5.1.6 Environment module functions](#section-5-1-6)

<a id="api-1-1"></a>

## 5.1.1 BaseEnv

### Purpose and construction

BaseEnv is StreetWorld's simulation environment base class, exposing Gym-style `reset()`, `step()`, and close(). It orders scene loading, policy execution, physics updates, and observation collection so an AD policy can interact with closed-loop simulation through one interface.

Pass a SimulatorInterface and configuration to construct the Managers and PhysicsWorld. The first `reset()` loads a scene and creates objects. Subclasses must implement rewards, and scene finalization also uses reward_calculator. Use [ScenarioEnv](#api-1-2) for training and evaluation.

Source: [streetworld/envs/base_env.py](../../../streetworld/envs/base_env.py).

### Configuration

[ScenarioDataManager](manager.md#api-4-2) reads scene_ids, random_scenario, start_scenario_index, and ego_z_height. BaseEnv's top-level settings are listed below.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `physics_world_step_size` | Number, µs | `20_000` | Physics interval, also used to resample trajectories; converted to integer microseconds |
| `decision_repeat` | int, physics steps | `5` | Physics steps per synchronous step; the asynchronous period is this count times the physics interval |
| `async_mode` | bool | `False` | Advances at regular intervals on a background thread; cannot be switched dynamically by changing configuration after construction |
| `max_step` | int or None, environment steps | `None` | Environment step limit; ScenarioEnv changes this to 200 |
| `actor_config` | dict | See [AgentManager](manager.md#api-4-3) | Ego Observer, Policy, Controller, and state-check settings |
| `participant_config` | dict | See [AgentManager](manager.md#api-4-3) | Surrounding vehicle settings; types, dimensions, and recorded states come from the scene |
| `random_agent_model` | bool | `False` | Not used when creating the ego vehicle |
| `agent_configs` | dict | `{'default_agent': {'use_special_color': True, 'spawn_lane_index': None}}` | Replaced as a whole during construction merging; its fields are not used to create the ego vehicle |
| `horizon` | int or None | `None` | Not used for step truncation |
| `truncate_as_terminate` | bool | `False` | Not used for termination; OUT_OF_STEP can set both terminated and truncated |
| `disable_collision` | bool | `False` | Not used to construct BulletWorld; AgentManager.check_crash controls collision checking |
| `curriculum_level` | int | `1` | Curriculum sorting is not connected to the environment |
| `num_workers` | int | `1` | Scene sampling is not partitioned by worker |
| `pstats` | bool | `False` | Does not start Panda3D performance statistics |
| `debug` | bool | `False` | Not used to configure logging or windows during initialization |
| `debug_panda3d` | bool | `False` | Unused |
| `debug_physics_world` | bool | `False` | Unused; CollisionBodyObservation provides collision geometry images |
| `debug_static_world` | bool | `False` | Unused |
| `log_level` | Integer logging level | `logging.INFO` | BaseEnv's log-level assignment is commented out |
| `show_coordinates` | bool | `False` | Unused |
| `record_episode` | bool | `False` | Stored on reset; recording Manager registration and advancement are not connected |
| `replay_episode` | Recorded data or None | `None` | Stores the replay flag on reset; does not select ReplayPolicy |
| `only_reset_when_replay` | bool | `False` | Stored on reset; the corresponding replay flow is not connected |
| `force_reuse_object_name` | bool | `False` | Not used during object creation |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, model, config: Config=None)` | `model`: backend instance implementing the SimulatorInterface contract; `config`: component configuration dictionary | None | Merges default and caller configurations and creates runtime components. | model must implement [SimulatorInterface](../guides/simulator-interface.md#section-3-2). Missing scene_ids raises KeyError during ScenarioDataManager construction. |
| Class method<br>`default_config(cls) -> Config` | — | Config | Returns a new configuration from BASE_DEFAULT_CONFIG. | Does not include the required scene_ids. |
| Instance method<br>`eval(self, order=True, repeat_per_scene=1)` | `order`: ordering flag; `repeat_per_scene`: number of passes through the scene list | None | Asks ScenarioDataManager to build an evaluation queue; subsequent reset calls use the queue and ignore scene_id. | order=False only changes the random-mode flag; it does not shuffle the queue. |
| Instance method<br>`reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`: random `seed`, with None using caller/environment random state; `scene_id`: ID in scene_ids, selected by Manager when None | (observation, info) | Loads and resets the scene; asynchronous mode submits a reset request and waits for completion. | Raises RuntimeError after closure or when another reset is pending; an exhausted evaluation queue raises LookupError. |
| Instance method<br>`step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | `actions`: external input in the current Policy's format | (observation, reward, terminated, truncated, info) | Calls _step in synchronous mode. Asynchronous mode updates the action, waits for any current step/reset to finish, then reads the cache. | Call reset first. Asynchronous worker errors are re-raised in the caller. |
| Instance method<br>`close(self)` | — | None | Closes Agents, ground, physics, and rendering. Asynchronous mode waits for cleanup on the owning thread. | Repeated close returns immediately after closure; worker cleanup errors propagate to the caller. |
| Instance method<br>`capture(self, file_name=None)` | `file_name`: output image path, generated when None | None | Captures the engine window and writes the image. | engine is not created by the current environment, so this raises AttributeError. Use the interactive environment for browser views and video output. |
| Instance method<br>`export_scenarios(self, policies: Union[dict, Callable], scenario_index: Union[list, int], max_episode_length=None, verbose=False, suppress_warning=False, render_topdown=False, return_done_info=True, to_dict=True)` | `policies`: action callback or callbacks keyed by Agent ID; `scenario_index`: one or more scene indices; `max_episode_length`: per-scene step limit; `verbose`: log export progress; `suppress_warning`: suppress long-episode warnings; `render_topdown`: draw top-down views; `return_done_info`: include termination information; `to_dict`: convert to dictionaries | Intended return: scene dictionary, or (scene dictionary, termination information dictionary) | Records episodes and exports scenes. | Not connected: is_multi_agent, engine, and the record conversion function are missing, and reset results are not unpacked using the current contract. This interface cannot be used directly. |
| Instance method<br>`stop(self)` | — | None | Toggles in_stop. | The advancement loop does not read this flag; simulation continues. |
| Protected method<br>`_init_async_state(self)` | — | None | Initializes the condition variable, action cache, reset requests, and worker exception records. Subclasses may override it. | — |
| Protected method<br>`_setup(self, config)` | `config`: component configuration dictionary | None | Creates scene management, timing, BulletWorld, and the ego AgentManager; registers collision callbacks. | — |
| Protected method<br>`_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`: random `seed`, with None using caller/environment random state; `scene_id`: ID in scene_ids, selected by Manager when None | (observation, info) | Cleans up the previous scene, loads the map/ground/Agents, resets timing and renderer state, and collects the first observation. | Direct use of the base class reaches unimplemented reward methods. |
| Protected method<br>`_step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | `actions`: external input in the current Policy's format | Five-element step result | Runs Policy and physics updates per physics step, updates Agent states, then updates renderer state and collects observations. | Passes the same external input to all AgentManagers, each interpreted by its Policy. |
| Protected method<br>`_reward_function(self, object_id: str) -> Tuple[float, Dict]` | `object_id`: object ID | Subclasses should return (float, dict) | Computes rewards; implemented by subclasses. | The base implementation raises NotImplementedError. Environment calls it without object_id, so subclass overrides must have no required argument beyond self. |
| Protected method<br>`_cost_function(self, object_id: str) -> Tuple[float, Dict]` | `object_id`: object ID | Subclasses should return (float, dict) | Computes costs; implemented by subclasses. | The base implementation raises NotImplementedError; step does not call it. |
| Protected method<br>`_done_function(self)` | — | (bool, dict) | Checks ego state and environment max_step, records the termination reason in info.reason, and adds accumulated reward diagnostics at episode end. | Requires reward_calculator.episode_info(); crash_*_done settings do not affect this check. |
| Protected method<br>`_close(self)` | — | None | Destroys Agents, ground, and PhysicsWorld, then calls backend close. Interactive subclasses also close their UI. | — |
| Property getter<br>`config(self)` | — | Config | Returns current_config when a scene configuration exists, otherwise base_config. | Returns a mutable object. |
| Property getter<br>`scene_id(self) -> str` | — | str | Returns the scene ID at the current index. | The index is not selected before reset; do not use this to query a loaded scene yet. |
| Property getter<br>`actor_manager(self)` | — | AgentManager | Returns the ego Manager. | — |
| Property getter<br>`actor_controller(self)` | — | BaseObject subclass instance | Returns the current ego Controller. | Available after the first reset. |
| Property getter<br>`observations(self)` | — | The BaseEnv instance | Returns self. | Does not return the observation cache; use observations from reset/step. |
| Property getter<br>`observation_space(self) -> gym.Space` | — | gym.Space, requires is_multi_agent | Queries ego observation spaces and wraps them according to the single/multi-Agent branch. | is_multi_agent is undefined, so access raises AttributeError. Child Observer space declarations may also differ from actual outputs. |
| Property getter<br>`action_space(self) -> gym.Space` | — | gym.Space, requires is_multi_agent | Queries ego Policy spaces and wraps them according to the single/multi-Agent branch. | is_multi_agent is undefined, so access raises AttributeError. |

### Example

```python
# env is an existing ScenarioEnv or interactive environment.
observation, info = env.reset(scene_id="0007")
print(info["scene_name"], info["current_timestamp"])
observation, reward, terminated, truncated, info = env.step([0.0, 0.0])
env.close()
```

<a id="api-1-2"></a>

## 5.1.2 ScenarioEnv

### Purpose and construction

ScenarioEnv runs AD policy training and evaluation in recorded scenes. It adds rewards and driving metrics to BaseEnv, summarizing an episode's driving behavior into scene results for training algorithms and benchmarks.

Construction creates RewardCalculator and MetricCalculator. `reset()` clears scene statistics, `step()` updates metrics, and episode end finalizes them. Rewards require [NavigationObservation](observation.md#api-5-7), with `states`, `navigation`, and `surrounding` present in observations.

Source: [streetworld/envs/scenario_env.py](../../../streetworld/envs/scenario_env.py).

### Configuration

Runtime parameters inherit from BaseEnv. SCENARIO_ENV_CONFIG adds or overrides the following fields.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `start_scenario_index` | int | `0` | Initial scene index; see [ScenarioDataManager](manager.md#api-4-2) |
| `position_deviation_threshold` | float, m | `2.0` | Starts a penalty when lateral distance to the navigation path exceeds this threshold |
| `position_penalty_gain` | float | `0.2` | Linear penalty coefficient for excess lateral error |
| `position_penalty_max` | float | `0.25` | Maximum absolute position penalty per step |
| `heading_deviation_threshold` | float, rad | `0.1` | Reference-heading error threshold; skipped when no expert heading is available |
| `heading_penalty_weight` | float | `0.5` | Penalty coefficient for excess heading error |
| `heading_penalty_max` | float | `0.5` | A positive value caps the absolute heading penalty per step |
| `progress_reward_weight` | float | `2.0` | Reward coefficient for forward progress along the navigation path |
| `reverse_penalty_weight` | float | `1.0` | Penalty coefficient for backward progress along the path |
| `progress_deviation_weight` | float | `0.1` | Multiplies forward reward by exp(-coefficient × path deviation) |
| `ttc_safe_horizon` | float, s | `4.0` | TTC below this value incurs a risk penalty; above it can receive a safety bonus |
| `ttc_warn_horizon` | float, s | `2.0` | TTC below this value uses the high-risk penalty region |
| `ttc_mid_penalty_weight` | float | `0.5` | Maximum penalty scale between warning and safe thresholds |
| `ttc_high_penalty_weight` | float | `0.8` | Maximum penalty scale below the warning threshold |
| `ttc_safe_bonus_weight` | float | `0.2` | Positive reward scale above the safe threshold |
| `ttc_safe_bonus_min_speed` | float, m/s | `0.5` | Combined with the progress threshold to detect stagnation, which cancels positive TTC reward |
| `ttc_safe_bonus_min_progress` | float, m/environment step | `0.05` | Combined with the speed threshold to detect stagnation |
| `living_cost` | float | `0.05` | Added directly to total reward; the default is positive despite the field's name |
| `collision_penalty_weight` | float | `50.0` | Subtracted for collision, crash_world, or out_of_road |
| `success_bonus` | float | `75.0` | Added when the ego state is SUCCESS |
| `max_step` | int, environment steps | `200` | Overrides BaseEnv's environment step limit |
| `num_scenarios` | int | `3` | Scene count is len(scene_ids); this field is unused |
| `sequential_seed` | bool | `False` | Not used to update the global seed |
| `worker_index` | int | `0` | Scene selection is not partitioned by worker |
| `num_workers` | int | `1` | Scene selection is not partitioned by worker |
| `curriculum_level` | int | `1` | Curriculum sorting is not connected |
| `episodes_to_evaluate_curriculum` | int or None | `None` | Unused |
| `target_success_rate` | float | `0.8` | Unused |
| `store_map` | bool | `True` | The backend loads maps directly; this field does not control caching |
| `store_data` | bool | `True` | Manager does not use this caching switch |
| `need_lane_localization` | bool | `True` | Does not control lane queries |
| `no_map` | bool | `False` | Does not make the backend skip map loading |
| `map_region_size` | Number | `1024` | Not used for map cropping |
| `cull_lanes_outside_map` | bool | `True` | Not used during map loading |
| `no_traffic` | bool | `False` | Does not filter surrounding objects during Agent creation |
| `no_static_vehicles` | bool | `False` | Does not filter static vehicles during Agent creation |
| `no_light` | bool | `False` | No traffic-light Manager is connected to Environment |
| `reactive_traffic` | bool | `False` | Select IDM through participant_config.policy; this field is inactive |
| `filter_overlapping_car` | bool | `True` | Not used during object creation |
| `default_vehicle_in_traffic` | bool | `False` | Not used during object creation |
| `skip_missing_light` | bool | `True` | No traffic-light Manager is connected to Environment |
| `static_traffic_object` | bool | `True` | Not used during object creation |
| `show_sidewalk` | bool | `False` | Not used during rendering |
| `even_sample_vehicle_class` | Any value or None | `None` | Deprecated and unused |
| `crash_vehicle_cost` | float | `1.0` | Cost code is commented out and omitted from step results |
| `crash_object_cost` | float | `1.0` | Cost code is commented out and omitted from step results |
| `out_of_road_cost` | float | `1.0` | Cost code is commented out and omitted from step results |
| `crash_human_cost` | float | `1.0` | Cost code is commented out and omitted from step results |
| `out_of_route_done` | bool | `False` | Not used in termination checks |
| `crash_vehicle_done` | bool | `False` | Not used in termination checks; CRASH_VEHICLE terminates directly |
| `crash_object_done` | bool | `False` | Not used in termination checks; CRASH_OBJECT terminates directly |
| `crash_human_done` | bool | `False` | Not used in termination checks; CRASH_HUMAN terminates directly |
| `relax_out_of_road_done` | bool | `True` | Not used in termination checks; OUT_OF_ROAD terminates directly |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, model, config=None)` | `model`: backend instance implementing the SimulatorInterface contract; `config`: component configuration dictionary | None | Creates BaseEnv runtime components and the reward/metric calculators. | — |
| Class method<br>`default_config(cls)` | — | Config | Merges SCENARIO_ENV_CONFIG into BaseEnv defaults. | — |
| Instance method<br>`get_average_metric(self)` | — | dict[str, float] | Averages each metric over completed scenes, ignoring NaNs per metric. | No completed scenes leads to IndexError from accessing an empty list. |
| Protected method<br>`_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`: random `seed`, with None using caller/environment random state; `scene_id`: ID in scene_ids, selected by Manager when None | (observation, info) | Resets rewards, then the environment; resets metrics using ego warmup_step and records the starting frame. | — |
| Protected method<br>`_step(self, actions)` | `actions`: external input in the current Policy's format | Five-element step result | Advances the environment, updates metrics, and finalizes them on terminated or truncated. | — |
| Protected method<br>`_reward_function(self)` | — | (float, dict) | Calls RewardCalculator.compute, returning reward, components, TTC, path deviations, and other diagnostics. | Missing navigation Observer or a valid path raises TypeError/ValueError. |

Total reward sums living_cost, forward/reverse progress, TTC, position/heading deviation, collision, and success terms. TTC divides center-to-center distance by relative approach speed; it does not model contact between vehicle rectangles. With no approaching object, TTC is None and its reward term is omitted.

Model-controlled samples begin after expert warmup. The handover frame establishes the origin and is not counted as a sample. Metrics are calculated as follows.

| Metric | Current calculation |
| --- | --- |
| NC | 1 if no crash_vehicle/human/object/world reason occurred, otherwise 0; out_of_road is not counted as an NC collision |
| DAC | Fraction of model-controlled steps where current_lane is not None |
| TTC | Fraction of steps with minimum TTC either None or at least 5 s |
| COM | Fraction of steps with horizontal acceleration at most 2 m/s² and absolute yaw rate at most 0.5 rad/s |
| RC | Post-handover route progress / route length remaining at handover, clipped to [0, 1] |
| RE | Post-handover route progress / elapsed simulation time, in m/s |

COM checks angular velocity although the calculator field is named yaw_acc_threshold. MetricCalculator defines these thresholds; Environment Config does not expose them. Without model-controlled samples, DAC/TTC/COM/RE are NaN and RC is 0. RC is NaN when remaining route length is nonpositive.

### Example

```python
from st_renderer import SimulatorInterface
from streetworld.envs.scenario_env import ScenarioEnv

env = ScenarioEnv(SimulatorInterface(dataset="nuscenes"), {"scene_ids": ["0007"]})
try:
    obs, info = env.reset()
    while True:
        obs, reward, terminated, truncated, info = env.step([0.0, 0.0])
        if terminated or truncated:
            print(env.get_average_metric())
            break
finally:
    env.close()
```

<a id="api-1-3"></a>

## 5.1.3 InteractiveScenarioEnv

### Purpose and construction

InteractiveScenarioEnv adds tools for observing, controlling, and debugging scene runs. TUI, WebUI, video recording, and trajectory projection show vehicle state and AD policy plans; WebUI also supports browser driving.

`make_interactive_env(ScenarioEnv)` returns the class InteractiveScenarioEnv. Construct it with a SimulatorInterface and configuration, as with ScenarioEnv. UI and recording features follow configuration and update or release resources during reset, step, and close.

Source: [streetworld/envs/interactive_env.py](../../../streetworld/envs/interactive_env.py).

### Configuration

The wrapped environment supplies basic runtime settings. The interactive class adds these fields.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `web_host` | str | `127.0.0.1` | WebUI bind host |
| `web_port` | int | `8080` | WebUI port; separate from gRPC |
| `video_output_dir` | str or None | `videos` | Video output directory; None disables recording |
| `video_hud` | bool | True (default when read) | Overlays vehicle state on video |
| `image_layout` | list[list[str]] | `[['FRONT_LEFT', 'FRONT', 'FRONT_RIGHT'], ['BACK_LEFT', 'BACK', 'BACK_RIGHT']]` | Camera mosaic order; names must exist in gaussian.image |
| `project_trajectory_on_camera` | str or None | `None` | Camera used for trajectory projection; actions that are not 2D trajectories are not drawn |
| `history_size` | int | `200` | Length of WebUI metric histories |
| `jpeg_quality` | int | `85` | Initial WebUI JPEG quality |
| `max_image_edge` | int, px | `1200` | Maximum WebUI image edge length |
| `eval_mode` | bool | `True` | Enters scene evaluation mode during construction |
| `eval_order` | bool | `True` | Ordering argument passed to eval |
| `eval_repeat_per_scene` | int | `1` | Repeat count passed to eval |
| `tui` | bool | `True` | Creates and starts the terminal UI |
| `webui` | bool | `True` | Creates and starts the browser UI |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, simulator_interface, config=None)` | `simulator_interface`: backend implementing SimulatorInterface; `config`: component configuration dictionary | None | Creates the base environment and configured UI/video components, then starts TUI, WebUI, and the evaluation queue. | Enabled output features require gaussian and states observations during step. |
| Class method<br>`default_config(cls)` | — | Config | Merges INTERACTIVE_ENV_CONFIG into the wrapped class defaults. | — |
| Protected method<br>`_reset(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | (observation, info) | Refreshes UI, writes the previous scene's video, resets the environment, and registers the new scene. | An exhausted queue updates TUI state and re-raises LookupError. |
| Protected method<br>`_step(self, action)` | `action`: external input in the current Policy's format | Five-element step result | Consumes WebUI takeover input, advances simulation, builds camera mosaics, and updates UI/video. Writes metrics and video at episode end. | Camera names in image_layout must exist. |
| Protected method<br>`_close(self)` | — | None | Closes TUI, finishes pending video, closes WebUI, then calls base cleanup. | — |

### Example

```python
from st_renderer import SimulatorInterface
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.envs.interactive_env import make_interactive_env

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
env = InteractiveScenarioEnv(SimulatorInterface(dataset="nuscenes"), {
    "scene_ids": ["0007"], "web_port": 18080,
    "tui": False, "video_output_dir": None,
})
try:
    obs, info = env.reset()
    obs, reward, terminated, truncated, info = env.step([0.0, 0.0])
finally:
    env.close()
```

<a id="api-2-1"></a>

## 5.1.4 GrpcClientEnv

### Purpose and construction

GrpcClientEnv is a Gym client for remote AD policy interaction. When policy and simulation require different Python dependencies, run separate processes while keeping `reset()`/`step(action)` calls and exchanging observations/actions through gRPC.

Construction connects to a running Environment Server. `Reset`/`Step` requests restore returned images and Struct observations into Python data; server Environment performs scene loading, physics, and rendering.

Source: [streetworld/envs/grpc_client_env.py](../../../streetworld/envs/grpc_client_env.py).

### Configuration

Set host, port, timeout_sec, and auto_wait_ready through constructor arguments; no Config is needed. See [Environment: local and remote calls](../guides/environment-interface.md#section-3-1) for transport formats.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, host: str='127.0.0.1', port: int=50052, timeout_sec: float=10.0, auto_wait_ready: bool=True)` | `host`: gRPC `host`; `port`: gRPC `port`; `timeout_sec`: RPC timeout in seconds; `auto_wait_ready`: wait for READY during construction | None | Creates an unauthenticated channel and stub, optionally waiting for READY. | Readiness timeout raises grpc.FutureTimeoutError. Space declarations are placeholders. |
| Instance method<br>`reset(self, *, seed: Optional[int]=None, options: Optional[Dict[str, Any]]=None) -> Tuple[Any, Dict[str, Any]]` | `seed`: random `seed`, with None using caller/environment random state; `options`: Gym reset extension parameters | (observation, info) | Sends an empty Reset request with twice timeout_sec as the RPC timeout. | seed/options are discarded. A response with status=True raises RuntimeError; transport failures raise grpc.RpcError. |
| Instance method<br>`step(self, action: Optional[np.ndarray]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]` | `action`: external input in the current Policy's format | (observation, float, bool, bool, info) | Flattens and sends the action; None sends an empty array. The RPC timeout is timeout_sec. | The server reshapes to (-1, 2). Failed responses raise RuntimeError; transport failures raise grpc.RpcError. |
| Instance method<br>`close(self) -> None` | — | None | Unsubscribes connectivity notifications, closes the gRPC channel, and clears the channel reference. | Closes only the client connection; the server Environment keeps running. |

### Example

```python
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv(host="127.0.0.1", port=50052, timeout_sec=360.0)
try:
    obs, info = env.reset()
    print(obs["gaussian"]["image"]["FRONT"].shape)
finally:
    env.close()
```

<a id="api-2-2"></a>

## 5.1.5 EnvServicer

### Purpose and construction

EnvServicer handles Environment Server requests, exposing a local Environment to [GrpcClientEnv](#api-2-1). It decodes actions, calls `reset()`/`step()`, and encodes observations, rewards, and termination flags so remote AD policies use the same simulation flow.

`serve(env, ...)` creates and registers the instance. A lock serializes requests to avoid concurrent environment changes. Direct `Reset`/`Step` calls require generated Protobuf requests and a gRPC context.

Source: [streetworld/envs/env_servicer.py](../../../streetworld/envs/env_servicer.py).

### Configuration

serve() host/port set the bind address. Scenes and Policy use the local environment configuration; EnvServicer has no separate Config.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, env)` | `env`: local Environment instance | None | Stores env and creates a mutex. | — |
| Instance method<br>`Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse` | `request`: generated Protobuf `request`; `context`: gRPC ServicerContext | ResetResponse | Calls env.reset under the lock, serializing the first observation and info. | Queue exhaustion becomes status=True with a message; other errors propagate to gRPC. |
| Instance method<br>`Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse` | `request`: generated Protobuf `request`; `context`: gRPC ServicerContext | StepResponse | Reshapes nonempty actions to (-1, 2) under the lock, calls env.step, and serializes results. | An odd element count raises ValueError. Environment and serialization errors propagate directly. |

### Example

```python
# env is an existing local environment; serve blocks until the server exits.
from streetworld.envs.env_servicer import serve

serve(env, host="127.0.0.1", port=50052)
```

<a id="section-5-1-6"></a>

## 5.1.6 Environment module functions

make_interactive_env is defined in interactive_env.py; serve is defined in env_servicer.py.
| Module function<br>`make_interactive_env(env_class)` | env_class: Environment class to wrap | Environment class | Returns a class with UI and recording features, named Interactive followed by the original class name. Bind the returned class, then construct it. | The wrapped environment must provide rewards and the interfaces required by interactive evaluation. |
| Module function<br>`serve(env, *, host: str, port: int) -> None` | env: local environment; host: bind host; port: bind port | None | Creates a single-worker gRPC server and blocks. On exit, stops RPC and closes env on its owning thread. | Bind failure raises RuntimeError. Reads env.config["tui"], so add tui=False for a plain ScenarioEnv. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5. API reference](index.md) · [Next: 5.2 Manager](manager.md)
