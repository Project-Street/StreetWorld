# StreetWorld API Class and Function Index

[简体中文](API_CLASS_FUNCTIONS.md)

This index lists the classes covered in the documentation and members defined or overridden by each class. Unmodified inherited members and internal methods with double underscores are omitted; constructors are included when defined locally.

Each class has a class-details table and a member table. Members are ordered by constructors, methods, protected methods, and properties. Member tables use the columns Category, Signature, and Notes; module functions use the same format.

Signatures preserve `self`, `cls`, defaults, and type annotations from the source. Property getters and setters are listed separately. Protected methods retain a single underscore; internal private methods use double underscores and are omitted.

The index covers 44 classes, 241 locally defined member signatures, and 6 module functions.

## Class index

- [1. Environments: local environments](#api-group-1)
    - [1.1 BaseEnv](#api-1-1)
    - [1.2 ScenarioEnv](#api-1-2)
    - [1.3 InteractiveScenarioEnv](#api-1-3)
- [2. gRPC: remote environment interface](#api-group-2)
    - [2.1 GrpcClientEnv](#api-2-1)
    - [2.2 EnvServicer](#api-2-2)
- [3. Config System](#api-group-3)
    - [3.1 Config](#api-3-1)
- [4. Managers](#api-group-4)
    - [4.1 BaseManager](#api-4-1)
    - [4.2 ScenarioDataManager](#api-4-2)
    - [4.3 AgentManager](#api-4-3)
- [5. Observations](#api-group-5)
    - [5.1 BaseObservation](#api-5-1)
    - [5.2 DummyObservation](#api-5-2)
    - [5.3 DefaultObservation](#api-5-3)
    - [5.4 AssemblyObservation](#api-5-4)
    - [5.5 GaussianObservation](#api-5-5)
    - [5.6 StateObservation](#api-5-6)
    - [5.7 NavigationObservation](#api-5-7)
    - [5.8 SurroundingObservation](#api-5-8)
    - [5.9 CollisionBodyObservation](#api-5-9)
- [6. Policies](#api-group-6)
    - [6.1 BasePolicy](#api-6-1)
    - [6.2 EnvInputPolicy](#api-6-2)
    - [6.3 EnvInputPIDPolicy](#api-6-3)
    - [6.4 EnvInputILQRPolicy](#api-6-4)
    - [6.5 ExpertILQRPolicy](#api-6-5)
    - [6.6 ReplayPolicy](#api-6-6)
    - [6.7 IDMPolicy](#api-6-7)
    - [6.8 TrajectoryIDMPolicy](#api-6-8)
- [7. Objects](#api-group-7)
    - [7.1 BaseObject](#api-7-1)
    - [7.2 BaseVehicle](#api-7-2)
    - [7.3 DefaultVehicle](#api-7-3)
    - [7.4 XLVehicle](#api-7-4)
    - [7.5 LVehicle](#api-7-5)
    - [7.6 MVehicle](#api-7-6)
    - [7.7 SVehicle](#api-7-7)
    - [7.8 BaseTrafficParticipant](#api-7-8)
    - [7.9 Pedestrian](#api-7-9)
    - [7.10 Cyclist](#api-7-10)
    - [7.11 GroundPlane](#api-7-11)
    - [7.12 MeshTerrain](#api-7-12)
- [8. Runtime utilities](#api-group-8)
    - [8.1 StepCounter](#api-8-1)
    - [8.2 PhysicsWorld](#api-8-2)
- [9. Base Classes](#api-group-9)
    - [9.1 Configurable](#api-9-1)
    - [9.2 Nameable](#api-9-2)
    - [9.3 Randomizable](#api-9-3)
    - [9.4 BaseRunnable](#api-9-4)

<a id="api-group-1"></a>

## 1. Environments: local environments

<a id="api-1-1"></a>

### 1.1 BaseEnv

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/envs/base_env.py · L46](../streetworld/envs/base_env.py#L46) |
| Base classes | `gym.Env` |
| Notes | `capture()` and `export_scenarios()` depend on an engine that is not connected to the current environment. `stop()` changes a flag without pausing simulation. See [BaseEnv API](en/reference/environment.md#api-1-1) for details. |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, model, config: Config=None)` | — |
| Class method | `default_config(cls) -> Config` | — |
| Instance method | `eval(self, order=True, repeat_per_scene=1)` | — |
| Instance method | `reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | — |
| Instance method | `step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | — |
| Instance method | `close(self)` | — |
| Instance method | `capture(self, file_name=None)` | Screenshot interface; unavailable because engine is not initialized. |
| Instance method | `export_scenarios(self, policies: Union[dict, Callable], scenario_index: Union[list, int], max_episode_length=None, verbose=False, suppress_warning=False, render_topdown=False, return_done_info=True, to_dict=True)` | Recording export interface; unavailable because the recording components are not connected. |
| Instance method | `stop(self)` | Toggles in_stop; pause control is not connected. |
| Protected method | `_init_async_state(self)` | Initializes asynchronous execution state. |
| Protected method | `_setup(self, config)` | — |
| Protected method | `_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | Environment reset implementation called by reset(). |
| Protected method | `_step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | Environment advancement implementation called by step(). |
| Protected method | `_reward_function(self, object_id: str) -> Tuple[float, Dict]` | The base implementation raises NotImplementedError. |
| Protected method | `_cost_function(self, object_id: str) -> Tuple[float, Dict]` | The base implementation raises NotImplementedError. |
| Protected method | `_done_function(self)` | — |
| Protected method | `_close(self)` | Resource cleanup implementation called by close(). |
| Property getter | `config(self)` | Read-only property. |
| Property getter | `scene_id(self) -> str` | Read-only property; str. |
| Property getter | `actor_manager(self)` | Read-only property. |
| Property getter | `actor_controller(self)` | Read-only property. |
| Property getter | `observations(self)` | Read-only property. |
| Property getter | `observation_space(self) -> gym.Space` | Read-only property; gym.Space. |
| Property getter | `action_space(self) -> gym.Space` | Read-only property; gym.Space. |

<a id="api-1-2"></a>

### 1.2 ScenarioEnv

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/envs/scenario_env.py · L15](../streetworld/envs/scenario_env.py#L15) |
| Base classes | [BaseEnv](#api-1-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, model, config=None)` | — |
| Class method | `default_config(cls)` | Overrides [BaseEnv](#api-1-1).`default_config()`. |
| Instance method | `get_average_metric(self)` | — |
| Protected method | `_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | Overrides [BaseEnv](#api-1-1).`_reset()`. |
| Protected method | `_step(self, actions)` | Overrides [BaseEnv](#api-1-1).`_step()`. |
| Protected method | `_reward_function(self)` | Overrides [BaseEnv](#api-1-1).`_reward_function()`. |

<a id="api-1-3"></a>

### 1.3 InteractiveScenarioEnv

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/envs/interactive_env.py · L46](../streetworld/envs/interactive_env.py#L46) |
| Base classes | [ScenarioEnv](#api-1-2) |
| Notes | The class returned by make_interactive_env(`ScenarioEnv`). The factory defines `InteractiveEnv` internally, then names the returned class InteractiveScenarioEnv. Its public execution methods are inherited from ScenarioEnv. |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, simulator_interface, config=None)` | — |
| Class method | `default_config(cls)` | Overrides [ScenarioEnv](#api-1-2).`default_config()`. |
| Protected method | `_reset(self, *args, **kwargs)` | Overrides [ScenarioEnv](#api-1-2).`_reset()`. |
| Protected method | `_step(self, action)` | Overrides [ScenarioEnv](#api-1-2).`_step()`. |
| Protected method | `_close(self)` | Overrides [BaseEnv](#api-1-1).`_close()`. |

### 1.4 Module functions

| Category | Signature | Notes |
| --- | --- | --- |
| Module function | `make_interactive_env(env_class)` | [streetworld/envs/interactive_env.py · L45](../streetworld/envs/interactive_env.py#L45). |

<a id="api-group-2"></a>

## 2. gRPC: remote environment interface

<a id="api-2-1"></a>

### 2.1 GrpcClientEnv

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/envs/grpc_client_env.py · L16](../streetworld/envs/grpc_client_env.py#L16) |
| Base classes | `gym.Env` |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, host: str='127.0.0.1', port: int=50052, timeout_sec: float=10.0, auto_wait_ready: bool=True)` | — |
| Instance method | `reset(self, *, seed: Optional[int]=None, options: Optional[Dict[str, Any]]=None) -> Tuple[Any, Dict[str, Any]]` | — |
| Instance method | `step(self, action: Optional[np.ndarray]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]` | — |
| Instance method | `close(self) -> None` | Closes the client channel; the server environment keeps running. |

<a id="api-2-2"></a>

### 2.2 EnvServicer

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/envs/env_servicer.py · L42](../streetworld/envs/env_servicer.py#L42) |
| Base classes | `service_pb2_grpc.EnvServiceServicer` |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, env)` | — |
| Instance method | `Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse` | — |
| Instance method | `Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse` | — |

### 2.3 Module functions

| Category | Signature | Notes |
| --- | --- | --- |
| Module function | `serve(env, *, host: str, port: int) -> None` | [streetworld/envs/env_servicer.py · L15](../streetworld/envs/env_servicer.py#L15). |

<a id="api-group-3"></a>

## 3. Config System

<a id="api-3-1"></a>

### 3.1 Config

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/config.py · L26](../streetworld/config.py#L26) |
| Base classes | — |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, cfg_dict: Union[Dict, None]=None, **kwargs)` | — |
| Instance method | `keys(self)` | — |
| Instance method | `values(self)` | — |
| Instance method | `items(self)` | — |
| Instance method | `get(self, key, default=None)` | — |
| Instance method | `copy(self)` | — |
| Instance method | `merge_from(self, options: Dict, allow_list_keys: bool=True, replace_keys: list=None)` | — |
| Instance method | `to_dict(self)` | — |
| Class method | `fromfile(cls, filename: str)` | — |
| Property getter | `filename(self)` | Read/write property. |
| Property setter | `filename(self, value)` | Read/write property. |

<a id="api-group-4"></a>

## 4. Managers

<a id="api-4-1"></a>

### 4.1 BaseManager

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/manager/base_manager.py · L9](../streetworld/manager/base_manager.py#L9) |
| Base classes | [Randomizable](#api-9-3) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self)` | — |
| Instance method | `before_step(self, *args, **kwargs) -> dict` | — |
| Instance method | `step(self, *args, **kwargs)` | — |
| Instance method | `after_step(self, *args, **kwargs) -> dict` | — |
| Instance method | `before_reset(self)` | — |
| Instance method | `reset(self)` | — |
| Instance method | `after_reset(self)` | — |
| Instance method | `destroy(self)` | Overrides [Randomizable](#api-9-3).`destroy()`. |
| Instance method | `clear_object(self, object_id)` | — |
| Instance method | `clear_all_objects(self)` | — |
| Instance method | `get_metadata(self)` | — |
| Protected method | `_spawn_object(self, object_class, **kwargs)` | — |

<a id="api-4-2"></a>

### 4.2 ScenarioDataManager

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/manager/scenario_data_manager.py · L12](../streetworld/manager/scenario_data_manager.py#L12) |
| Base classes | [BaseManager](#api-4-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config, meta_loader, model_loader)` | — |
| Instance method | `eval(self, order=True, repeat_per_scene=1)` | — |
| Instance method | `reset(self, scene_id=None)` | Overrides [BaseManager](#api-4-1).`reset()`. |
| Instance method | `get_current_scenario_data(self)` | — |
| Instance method | `sort_scenarios(self)` | — |
| Instance method | `destroy(self)` | Overrides [BaseManager](#api-4-1).`destroy()`. |
| Property getter | `current_scenario_difficulty(self)` | Read-only property. |

<a id="api-4-3"></a>

### 4.3 AgentManager

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/manager/agent_manager.py · L28](../streetworld/manager/agent_manager.py#L28) |
| Base classes | [BaseManager](#api-4-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config, step_manager)` | — |
| Instance method | `reset(self, config=None, **kwargs)` | Overrides [BaseManager](#api-4-1).`reset()`. |
| Instance method | `step(self, action)` | Overrides [BaseManager](#api-4-1).`step()`. |
| Instance method | `initialize_state(self)` | — |
| Instance method | `update_state(self)` | — |
| Instance method | `set_state(self, new_state)` | — |
| Instance method | `observe(self)` | — |
| Instance method | `get_base_state(self, transform=None)` | — |
| Instance method | `get_observation_spaces(self)` | — |
| Instance method | `get_action_spaces(self)` | — |
| Instance method | `get_state(self)` | — |
| Instance method | `destroy(self)` | Overrides [BaseManager](#api-4-1).`destroy()`. |
| Property getter | `is_static(self)` | Read-only property. |
| Property getter | `active_policy(self)` | Read-only property. |
| Property getter | `is_warmup_step(self)` | Read-only property. |

<a id="api-group-5"></a>

## 5. Observations

<a id="api-5-1"></a>

### 5.1 BaseObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/observation_base.py · L11](../streetworld/obs/observation_base.py#L11) |
| Base classes | `ABC` |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config)` | — |
| Instance method | `observe(self, *args, **kwargs)` | The base implementation raises NotImplementedError. |
| Instance method | `reset(self, *args, **kwargs)` | — |
| Instance method | `destroy(self)` | — |
| Property getter | `observation_space(self)` | Read-only property; the base getter raises `NotImplementedError`. |

<a id="api-5-2"></a>

### 5.2 DummyObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/observation_base.py · L43](../streetworld/obs/observation_base.py#L43) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config=None)` | — |
| Instance method | `observe(self, *args, **kwargs)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-3"></a>

### 5.3 DefaultObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/observation_base.py · L59](../streetworld/obs/observation_base.py#L59) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config=None)` | — |
| Instance method | `observe(self, *args, **kwargs)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-4"></a>

### 5.4 AssemblyObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/assembly_obs.py · L10](../streetworld/obs/assembly_obs.py#L10) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config: Dict[str, Any])` | — |
| Instance method | `reset(self, **kwargs)` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `observe(self)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self)` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-5"></a>

### 5.5 GaussianObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/gaussian_obs.py · L9](../streetworld/obs/gaussian_obs.py#L9) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config)` | — |
| Instance method | `reset(self, controller, render_fn, camera_params, **kwargs)` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `an_observation_shape(self, h, w)` | — |
| Instance method | `observe(self)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self)` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-6"></a>

### 5.6 StateObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/state_obs.py · L8](../streetworld/obs/state_obs.py#L8) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config=None)` | — |
| Instance method | `reset(self, controller, collector, seed=None, **kwargs)` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `observe(self)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self)` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-7"></a>

### 5.7 NavigationObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/navigation_obs.py · L13](../streetworld/obs/navigation_obs.py#L13) |
| Base classes | [BaseObservation](#api-5-1), [Randomizable](#api-9-3) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config)` | — |
| Instance method | `reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, **kwargs)` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `observe(self)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self)` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Instance method | `get_reference_state(self, idx)` | — |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-8"></a>

### 5.8 SurroundingObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/surrounding_obs.py · L8](../streetworld/obs/surrounding_obs.py#L8) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config)` | — |
| Instance method | `reset(self, collector, controller, **kwargs)` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `observe(self)` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self)` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Property getter | `observation_space(self)` | Read-only property; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-5-9"></a>

### 5.9 CollisionBodyObservation

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/obs/collision_body_obs.py · L606](../streetworld/obs/collision_body_obs.py#L606) |
| Base classes | [BaseObservation](#api-5-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config: Mapping[str, Any])` | — |
| Instance method | `reset(self, controller: Any, collector: Any, ground: Any, **kwargs) -> None` | Overrides [BaseObservation](#api-5-1).`reset()`. |
| Instance method | `observe(self) -> Dict[str, np.ndarray]` | Overrides [BaseObservation](#api-5-1).`observe()`. |
| Instance method | `destroy(self) -> None` | Overrides [BaseObservation](#api-5-1).`destroy()`. |
| Property getter | `observation_space(self) -> gym.spaces.Dict` | Read-only property; gym.spaces.Dict; overrides [BaseObservation](#api-5-1).`observation_space`. |

<a id="api-group-6"></a>

## 6. Policies

<a id="api-6-1"></a>

### 6.1 BasePolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/base_policy.py · L10](../streetworld/policy/base_policy.py#L10) |
| Base classes | [Randomizable](#api-9-3), [Configurable](#api-9-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | — |
| Instance method | `act(self, *args, **kwargs)` | — |
| Instance method | `get_action_info(self)` | — |
| Instance method | `destroy(self)` | Overrides [Randomizable](#api-9-3).`destroy()`. |
| Class method | `get_input_space(cls)` | — |
| Instance method | `get_state(self)` | — |
| Property getter | `is_arrive(self)` | Read-only property. |
| Property getter | `is_spawned(self)` | Read-only property. |
| Property getter | `name(self)` | Read-only property. |

<a id="api-6-2"></a>

### 6.2 EnvInputPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/env_input_policy.py · L10](../streetworld/policy/env_input_policy.py#L10) |
| Base classes | [BasePolicy](#api-6-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [BasePolicy](#api-6-1).`reset()`. |
| Instance method | `act(self, action, *args, **kwargs)` | Overrides [BasePolicy](#api-6-1).`act()`. |
| Instance method | `get_input_space(self)` | Overrides [BasePolicy](#api-6-1).`get_input_space()`. |

<a id="api-6-3"></a>

### 6.3 EnvInputPIDPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/env_input_pid_policy.py · L19](../streetworld/policy/env_input_pid_policy.py#L19) |
| Base classes | [EnvInputPolicy](#api-6-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [EnvInputPolicy](#api-6-2).`reset()`. |
| Instance method | `act(self, action, *args, **kwargs)` | Overrides [EnvInputPolicy](#api-6-2).`act()`. |

<a id="api-6-4"></a>

### 6.4 EnvInputILQRPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/env_input_ilqr_policy.py · L19](../streetworld/policy/env_input_ilqr_policy.py#L19) |
| Base classes | [EnvInputPolicy](#api-6-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [EnvInputPolicy](#api-6-2).`reset()`. |
| Instance method | `act(self, action, *args, **kwargs)` | Overrides [EnvInputPolicy](#api-6-2).`act()`. |
| Protected method | `_xy_transform(self)` | Extracts a 2D homogeneous transform from the Controller transform. `ExpertILQRPolicy` uses this interface to transform the expert trajectory. |

<a id="api-6-5"></a>

### 6.5 ExpertILQRPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/expert_ilqr_policy.py · L6](../streetworld/policy/expert_ilqr_policy.py#L6) |
| Base classes | [EnvInputILQRPolicy](#api-6-4) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [EnvInputILQRPolicy](#api-6-4).`reset()`. |
| Instance method | `act(self, action=None, *args, **kwargs)` | Overrides [EnvInputILQRPolicy](#api-6-4).`act()`. |
| Property getter | `is_arrive(self)` | Read-only property; overrides [BasePolicy](#api-6-1).`is_arrive`. |

<a id="api-6-6"></a>

### 6.6 ReplayPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/replay_policy.py · L9](../streetworld/policy/replay_policy.py#L9) |
| Base classes | [BasePolicy](#api-6-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [BasePolicy](#api-6-1).`reset()`. |
| Instance method | `act(self, *args, **kwargs)` | Overrides [BasePolicy](#api-6-1).`act()`. |
| Property getter | `is_arrive(self)` | Read-only property; overrides [BasePolicy](#api-6-1).`is_arrive`. |

<a id="api-6-7"></a>

### 6.7 IDMPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/idm_policy.py · L131](../streetworld/policy/idm_policy.py#L131) |
| Base classes | [BasePolicy](#api-6-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, trajdata_map=None, **kwargs)` | Overrides [BasePolicy](#api-6-1).`reset()`. |
| Instance method | `act(self, observation, *args, **kwargs)` | Overrides [BasePolicy](#api-6-1).`act()`. |

<a id="api-6-8"></a>

### 6.8 TrajectoryIDMPolicy

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/policy/trajectory_idm_policy.py · L14](../streetworld/policy/trajectory_idm_policy.py#L14) |
| Base classes | [BasePolicy](#api-6-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_manager, config=None)` | — |
| Instance method | `reset(self, controller, seed, state, init_state, **kwargs)` | Overrides [BasePolicy](#api-6-1).`reset()`. |
| Instance method | `act(self, observation, *args, **kwargs)` | Overrides [BasePolicy](#api-6-1).`act()`. |

### 6.9 Module functions

| Category | Signature | Notes |
| --- | --- | --- |
| Module function | `smooth_1d(arr, kernel_size=5)` | [streetworld/policy/env_input_pid_policy.py · L7](../streetworld/policy/env_input_pid_policy.py#L7). |
| Module function | `smooth_1d(arr, kernel_size=5)` | [streetworld/policy/env_input_ilqr_policy.py · L7](../streetworld/policy/env_input_ilqr_policy.py#L7). |

<a id="api-group-7"></a>

## 7. Objects

<a id="api-7-1"></a>

### 7.1 BaseObject

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/base_object.py · L15](../streetworld/objects/base_object.py#L15) |
| Base classes | [BaseRunnable](#api-9-4), `MetaDriveType`, `ABC` |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, physics_world, size=None, name=None, random_seed=None, config=None, escape_random_seed_assertion=False)` | — |
| Instance method | `destroy(self)` | Overrides [BaseRunnable](#api-9-4).`destroy()`. |
| Instance method | `set_position(self, position)` | — |
| Instance method | `set_heading_theta(self, heading_theta, to_deg=True) -> None` | — |
| Instance method | `set_transform(self, m)` | — |
| Instance method | `set_velocity(self, velocity)` | — |
| Instance method | `set_angular_velocity(self, angular_velocity, in_rad=True)` | — |
| Instance method | `rename(self, new_name)` | Overrides [Nameable](#api-9-2).`rename()`. |
| Instance method | `attachDyWld(self, obj=None)` | — |
| Instance method | `detachDyWld(self, obj=None)` | — |
| Instance method | `set_kinematic(self, is_kinematic)` | — |
| Property getter | `position(self)` | Read-only property. |
| Property getter | `heading_theta(self)` | Read-only property. |
| Property getter | `transform(self)` | Read-only property. |
| Property getter | `velocity(self)` | Read-only property. |
| Property getter | `angular_velocity(self)` | Read-only property. |
| Property getter | `angular_acceleration(self)` | Read-only property. |
| Property getter | `acceleration(self)` | Read-only property. |
| Property getter | `speed(self)` | Read-only property. |
| Property getter | `speed_km_h(self)` | Read-only property. |
| Property getter | `heading(self)` | Read-only property. |

<a id="api-7-2"></a>

### 7.2 BaseVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/base_vehicle.py · L32](../streetworld/objects/vehicle/base_vehicle.py#L32) |
| Base classes | [BaseObject](#api-7-1), `BaseVehicleState` |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config: Union[dict, Config], physics_world, size=None, name: str=None, random_seed=None, position=None, heading_theta=None, _calling_reset=True, **kwargs)` | — |
| Instance method | `attachDyWld(self)` | Overrides [BaseObject](#api-7-1).`attachDyWld()`. |
| Instance method | `detachDyWld(self)` | Overrides [BaseObject](#api-7-1).`detachDyWld()`. |
| Instance method | `reset(self, name=None, random_seed=None, position: np.ndarray=None, heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, *args, **kwargs)` | Overrides [BaseRunnable](#api-9-4).`reset()`. |
| Instance method | `move(self, action=None)` | — |
| Instance method | `check_crash_world(self)` | — |
| Instance method | `destroy(self)` | Overrides [BaseObject](#api-7-1).`destroy()`. |
| Instance method | `set_position(self, position)` | Overrides [BaseObject](#api-7-1).`set_position()`. |
| Instance method | `get_steering_wheel_angle(self)` | — |
| Instance method | `get_longitudinal_acceleration(self)` | — |
| Property getter | `current_action(self)` | Read-only property. |
| Property getter | `max_speed_km_h(self)` | Read-only property. |

<a id="api-7-3"></a>

### 7.3 DefaultVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/vehicle_type.py · L15](../streetworld/objects/vehicle/vehicle_type.py#L15) |
| Base classes | [BaseVehicle](#api-7-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-4"></a>

### 7.4 XLVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/vehicle_type.py · L28](../streetworld/objects/vehicle/vehicle_type.py#L28) |
| Base classes | [BaseVehicle](#api-7-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-5"></a>

### 7.5 LVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/vehicle_type.py · L41](../streetworld/objects/vehicle/vehicle_type.py#L41) |
| Base classes | [BaseVehicle](#api-7-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-6"></a>

### 7.6 MVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/vehicle_type.py · L54](../streetworld/objects/vehicle/vehicle_type.py#L54) |
| Base classes | [BaseVehicle](#api-7-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-7"></a>

### 7.7 SVehicle

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/vehicle/vehicle_type.py · L66](../streetworld/objects/vehicle/vehicle_type.py#L66) |
| Base classes | [BaseVehicle](#api-7-2) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-8"></a>

### 7.8 BaseTrafficParticipant

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/traffic_participants/base_traffic_participant.py · L10](../streetworld/objects/traffic_participants/base_traffic_participant.py#L10) |
| Base classes | [BaseObject](#api-7-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config, physics_world, size, position: Sequence[float], heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, random_seed=None, name=None, **kwargs)` | — |
| Instance method | `reset(self, position: Sequence[float], heading_theta: float=0.0, random_seed=None, name=None, *args, **kwargs)` | Overrides [BaseRunnable](#api-9-4).`reset()`. |
| Instance method | `move(self, state_info)` | — |
| Instance method | `destroy(self)` | Overrides [BaseObject](#api-7-1).`destroy()`. |

<a id="api-7-9"></a>

### 7.9 Pedestrian

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/traffic_participants/pedestrian.py · L5](../streetworld/objects/traffic_participants/pedestrian.py#L5) |
| Base classes | [BaseTrafficParticipant](#api-7-8) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-10"></a>

### 7.10 Cyclist

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/traffic_participants/cyclist.py · L5](../streetworld/objects/traffic_participants/cyclist.py#L5) |
| Base classes | [BaseTrafficParticipant](#api-7-8) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| — | — | This class defines or overrides no members to list. |

<a id="api-7-11"></a>

### 7.11 GroundPlane

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/terrain/ground.py · L11](../streetworld/objects/terrain/ground.py#L11) |
| Base classes | [BaseObject](#api-7-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, physics_world, direction: Sequence[float], constant: float=0.0, random_seed=None, name=None, config=None, **kwargs)` | — |
| Instance method | `reset(self, random_seed=None, name=None, *args, **kwargs)` | Overrides [BaseRunnable](#api-9-4).`reset()`. |
| Instance method | `destroy(self)` | Overrides [BaseObject](#api-7-1).`destroy()`. |

<a id="api-7-12"></a>

### 7.12 MeshTerrain

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/objects/terrain/mesh_terrain.py · L14](../streetworld/objects/terrain/mesh_terrain.py#L14) |
| Base classes | [BaseObject](#api-7-1) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, physics_world, model_path: str, transform=None, position=(0, 0, 0), scale=1.0, friction=0.8, restitution=0.0, random_seed=None, name='GroundMesh', config=None, **kwargs)` | — |
| Instance method | `reset(self, random_seed=None, name=None, *args, **kwargs)` | Overrides [BaseRunnable](#api-9-4).`reset()`. |
| Instance method | `destroy(self)` | Overrides [BaseObject](#api-7-1).`destroy()`. |

### 7.13 Module functions

| Category | Signature | Notes |
| --- | --- | --- |
| Module function | `get_vehicle_type(length)` | [streetworld/objects/vehicle/vehicle_type.py · L5](../streetworld/objects/vehicle/vehicle_type.py#L5). |
| Module function | `random_vehicle_type(np_random, p=None)` | [streetworld/objects/vehicle/vehicle_type.py · L81](../streetworld/objects/vehicle/vehicle_type.py#L81). |

<a id="api-group-8"></a>

## 8. Runtime utilities

<a id="api-8-1"></a>

### 8.1 StepCounter

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/misc/step_counter.py · L1](../streetworld/misc/step_counter.py#L1) |
| Base classes | — |
| Notes | The spelling `eposide_step` follows the source. |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, step_size, physical_repeat=0)` | — |
| Instance method | `reset(self, timestamp_range, **kwargs)` | — |
| Instance method | `step(self)` | — |
| Property getter | `relative_timestamp(self)` | Read-only property. |
| Property getter | `current_timestamp(self)` | Read-only property. |
| Property getter | `key_step(self)` | Read-only property. |
| Property getter | `eposide_step(self)` | Read-only property. |

<a id="api-8-2"></a>

### 8.2 PhysicsWorld

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/engine/physics_world.py · L7](../streetworld/engine/physics_world.py#L7) |
| Base classes | — |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, physics_world_step_size=0.01, substep: int=1)` | — |
| Instance method | `destroy(self)` | — |
| Instance method | `step(self)` | — |
| Property getter | `step_size_sec(self)` | Read-only property. |

<a id="api-group-9"></a>

## 9. Base Classes

<a id="api-9-1"></a>

### 9.1 Configurable

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/base_class/configurable.py · L6](../streetworld/base_class/configurable.py#L6) |
| Base classes | — |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, config: Union[Dict, Config]=None)` | — |
| Instance method | `get_config(self, copy=True) -> Config` | — |
| Instance method | `update_config(self, config: dict)` | — |
| Instance method | `destroy(self)` | — |
| Property getter | `config(self)` | Read-only property. |

<a id="api-9-2"></a>

### 9.2 Nameable

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/base_class/nameable.py · L6](../streetworld/base_class/nameable.py#L6) |
| Base classes | — |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, name=None)` | — |
| Instance method | `rename(self, new_name)` | — |
| Instance method | `destroy(self)` | — |
| Property getter | `class_name(self)` | Read-only property. |

<a id="api-9-3"></a>

### 9.3 Randomizable

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/base_class/randomizable.py · L4](../streetworld/base_class/randomizable.py#L4) |
| Base classes | — |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, random_seed)` | — |
| Instance method | `seed(self, random_seed)` | — |
| Instance method | `generate_seed(self)` | — |
| Instance method | `destroy(self)` | — |

<a id="api-9-4"></a>

### 9.4 BaseRunnable

**Class details**

| Item | Details |
| --- | --- |
| Source | [streetworld/base_class/base_runnable.py · L9](../streetworld/base_class/base_runnable.py#L9) |
| Base classes | [Configurable](#api-9-1), [Nameable](#api-9-2), [Randomizable](#api-9-3) |
| Notes | — |

**Members defined in this class**

| Category | Signature | Notes |
| --- | --- | --- |
| Constructor | `__init__(self, name=None, random_seed=None, config=None)` | — |
| Instance method | `get_state(self) -> Dict` | The base implementation raises NotImplementedError. |
| Instance method | `set_state(self, state: Dict)` | The base implementation raises NotImplementedError. |
| Instance method | `before_step(self, *args, **kwargs)` | — |
| Instance method | `set_action(self, *args, **kwargs)` | The base implementation raises NotImplementedError. |
| Instance method | `step(self, *args, **kwargs)` | — |
| Instance method | `after_step(self, *args, **kwargs)` | — |
| Instance method | `reset(self, random_seed=None, *args, **kwargs)` | — |
| Instance method | `sample_parameters(self)` | — |
| Instance method | `destroy(self)` | Overrides [Configurable](#api-9-1).`destroy()`. |
