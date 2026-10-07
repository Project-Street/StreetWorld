# StreetWorld API 类与函数清单

[English](API_CLASS_FUNCTIONS_EN.md)

本文列出文档中计划呈现的类及其本类定义或覆写的成员。纯继承且未覆写的函数、属性和构造函数不列出；双下划线的内部私有方法不列出，构造函数保留。

每个类固定使用“类信息”和“本类成员”两张表。成员按构造函数、方法、受保护方法、属性的顺序排列，统一使用“类别、签名、说明”三列。模块级函数使用相同的成员表格式。

签名取自当前源码，保留 `self`、`cls`、默认值和类型注解；属性 getter/setter 分别列出。受保护方法使用单下划线，内部私有方法使用双下划线并从清单中排除。

共 44 个呈现类、241 条本类成员签名，另列 6 个模块级函数。

## 清单索引

- [1. Environments：本地环境](#api-group-1)
    - [1.1 BaseEnv](#api-1-1)
    - [1.2 ScenarioEnv](#api-1-2)
    - [1.3 InteractiveScenarioEnv](#api-1-3)
- [2. gRPC：远程环境接口](#api-group-2)
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
- [8. 运行辅助组件](#api-group-8)
    - [8.1 StepCounter](#api-8-1)
    - [8.2 PhysicsWorld](#api-8-2)
- [9. Base Classes](#api-group-9)
    - [9.1 Configurable](#api-9-1)
    - [9.2 Nameable](#api-9-2)
    - [9.3 Randomizable](#api-9-3)
    - [9.4 BaseRunnable](#api-9-4)

<a id="api-group-1"></a>

## 1. Environments：本地环境

<a id="api-1-1"></a>

### 1.1 BaseEnv

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/envs/base_env.py · L46](../streetworld/envs/base_env.py#L46) |
| 基类 | `gym.Env` |
| 说明 | `capture()` 和 `export_scenarios()` 依赖尚未接入的 engine；`stop()` 只修改标志，不会暂停仿真。具体限制见 [BaseEnv API](zh/reference/environment.md#api-1-1)。 |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, model, config: Config=None)` | — |
| 类方法 | `default_config(cls) -> Config` | — |
| 实例方法 | `eval(self, order=True, repeat_per_scene=1)` | — |
| 实例方法 | `reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | — |
| 实例方法 | `step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | — |
| 实例方法 | `close(self)` | — |
| 实例方法 | `capture(self, file_name=None)` | 截图接口；当前缺少 engine，不能直接使用。 |
| 实例方法 | `export_scenarios(self, policies: Union[dict, Callable], scenario_index: Union[list, int], max_episode_length=None, verbose=False, suppress_warning=False, render_topdown=False, return_done_info=True, to_dict=True)` | 记录导出接口；依赖未接入的记录组件，不能直接使用。 |
| 实例方法 | `stop(self)` | 切换 in_stop 标志；未接入暂停控制。 |
| 受保护方法 | `_init_async_state(self)` | 初始化异步执行状态。 |
| 受保护方法 | `_setup(self, config)` | — |
| 受保护方法 | `_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `reset()` 调用的环境重置实现。 |
| 受保护方法 | `_step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | `step()` 调用的环境推进实现。 |
| 受保护方法 | `_reward_function(self, object_id: str) -> Tuple[float, Dict]` | 基类实现抛出 `NotImplementedError`。 |
| 受保护方法 | `_cost_function(self, object_id: str) -> Tuple[float, Dict]` | 基类实现抛出 `NotImplementedError`。 |
| 受保护方法 | `_done_function(self)` | — |
| 受保护方法 | `_close(self)` | `close()` 调用的资源释放实现。 |
| 属性 getter | `config(self)` | 只读属性。 |
| 属性 getter | `scene_id(self) -> str` | 只读属性；str。 |
| 属性 getter | `actor_manager(self)` | 只读属性。 |
| 属性 getter | `actor_controller(self)` | 只读属性。 |
| 属性 getter | `observations(self)` | 只读属性。 |
| 属性 getter | `observation_space(self) -> gym.Space` | 只读属性；gym.Space。 |
| 属性 getter | `action_space(self) -> gym.Space` | 只读属性；gym.Space。 |

<a id="api-1-2"></a>

### 1.2 ScenarioEnv

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/envs/scenario_env.py · L15](../streetworld/envs/scenario_env.py#L15) |
| 基类 | [BaseEnv](#api-1-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, model, config=None)` | — |
| 类方法 | `default_config(cls)` | 覆写 [BaseEnv](#api-1-1) 的 `default_config()`。 |
| 实例方法 | `get_average_metric(self)` | — |
| 受保护方法 | `_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | 覆写 [BaseEnv](#api-1-1) 的 `_reset()`。 |
| 受保护方法 | `_step(self, actions)` | 覆写 [BaseEnv](#api-1-1) 的 `_step()`。 |
| 受保护方法 | `_reward_function(self)` | 覆写 [BaseEnv](#api-1-1) 的 `_reward_function()`。 |

<a id="api-1-3"></a>

### 1.3 InteractiveScenarioEnv

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/envs/interactive_env.py · L46](../streetworld/envs/interactive_env.py#L46) |
| 基类 | [ScenarioEnv](#api-1-2) |
| 说明 | 对应 `make_interactive_env(ScenarioEnv)` 的返回类。工厂内部定义的类名为 `InteractiveEnv`，返回时按传入类改名为 `InteractiveScenarioEnv`；其公开运行接口继承自 `ScenarioEnv`。 |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, simulator_interface, config=None)` | — |
| 类方法 | `default_config(cls)` | 覆写 [ScenarioEnv](#api-1-2) 的 `default_config()`。 |
| 受保护方法 | `_reset(self, *args, **kwargs)` | 覆写 [ScenarioEnv](#api-1-2) 的 `_reset()`。 |
| 受保护方法 | `_step(self, action)` | 覆写 [ScenarioEnv](#api-1-2) 的 `_step()`。 |
| 受保护方法 | `_close(self)` | 覆写 [BaseEnv](#api-1-1) 的 `_close()`。 |

### 1.4 模块级函数

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 模块函数 | `make_interactive_env(env_class)` | [streetworld/envs/interactive_env.py · L45](../streetworld/envs/interactive_env.py#L45)。 |

<a id="api-group-2"></a>

## 2. gRPC：远程环境接口

<a id="api-2-1"></a>

### 2.1 GrpcClientEnv

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/envs/grpc_client_env.py · L16](../streetworld/envs/grpc_client_env.py#L16) |
| 基类 | `gym.Env` |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, host: str='127.0.0.1', port: int=50052, timeout_sec: float=10.0, auto_wait_ready: bool=True)` | — |
| 实例方法 | `reset(self, *, seed: Optional[int]=None, options: Optional[Dict[str, Any]]=None) -> Tuple[Any, Dict[str, Any]]` | — |
| 实例方法 | `step(self, action: Optional[np.ndarray]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]` | — |
| 实例方法 | `close(self) -> None` | 关闭客户端通道，服务端环境继续运行。 |

<a id="api-2-2"></a>

### 2.2 EnvServicer

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/envs/env_servicer.py · L42](../streetworld/envs/env_servicer.py#L42) |
| 基类 | `service_pb2_grpc.EnvServiceServicer` |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, env)` | — |
| 实例方法 | `Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse` | — |
| 实例方法 | `Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse` | — |

### 2.3 模块级函数

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 模块函数 | `serve(env, *, host: str, port: int) -> None` | [streetworld/envs/env_servicer.py · L15](../streetworld/envs/env_servicer.py#L15)。 |

<a id="api-group-3"></a>

## 3. Config System

<a id="api-3-1"></a>

### 3.1 Config

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/config.py · L26](../streetworld/config.py#L26) |
| 基类 | — |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, cfg_dict: Union[Dict, None]=None, **kwargs)` | — |
| 实例方法 | `keys(self)` | — |
| 实例方法 | `values(self)` | — |
| 实例方法 | `items(self)` | — |
| 实例方法 | `get(self, key, default=None)` | — |
| 实例方法 | `copy(self)` | — |
| 实例方法 | `merge_from(self, options: Dict, allow_list_keys: bool=True, replace_keys: list=None)` | — |
| 实例方法 | `to_dict(self)` | — |
| 类方法 | `fromfile(cls, filename: str)` | — |
| 属性 getter | `filename(self)` | 读写属性。 |
| 属性 setter | `filename(self, value)` | 读写属性。 |

<a id="api-group-4"></a>

## 4. Managers

<a id="api-4-1"></a>

### 4.1 BaseManager

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/manager/base_manager.py · L9](../streetworld/manager/base_manager.py#L9) |
| 基类 | [Randomizable](#api-9-3) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self)` | — |
| 实例方法 | `before_step(self, *args, **kwargs) -> dict` | — |
| 实例方法 | `step(self, *args, **kwargs)` | — |
| 实例方法 | `after_step(self, *args, **kwargs) -> dict` | — |
| 实例方法 | `before_reset(self)` | — |
| 实例方法 | `reset(self)` | — |
| 实例方法 | `after_reset(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [Randomizable](#api-9-3) 的 `destroy()`。 |
| 实例方法 | `clear_object(self, object_id)` | — |
| 实例方法 | `clear_all_objects(self)` | — |
| 实例方法 | `get_metadata(self)` | — |
| 受保护方法 | `_spawn_object(self, object_class, **kwargs)` | — |

<a id="api-4-2"></a>

### 4.2 ScenarioDataManager

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/manager/scenario_data_manager.py · L12](../streetworld/manager/scenario_data_manager.py#L12) |
| 基类 | [BaseManager](#api-4-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config, meta_loader, model_loader)` | — |
| 实例方法 | `eval(self, order=True, repeat_per_scene=1)` | — |
| 实例方法 | `reset(self, scene_id=None)` | 覆写 [BaseManager](#api-4-1) 的 `reset()`。 |
| 实例方法 | `get_current_scenario_data(self)` | — |
| 实例方法 | `sort_scenarios(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [BaseManager](#api-4-1) 的 `destroy()`。 |
| 属性 getter | `current_scenario_difficulty(self)` | 只读属性。 |

<a id="api-4-3"></a>

### 4.3 AgentManager

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/manager/agent_manager.py · L28](../streetworld/manager/agent_manager.py#L28) |
| 基类 | [BaseManager](#api-4-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config, step_manager)` | — |
| 实例方法 | `reset(self, config=None, **kwargs)` | 覆写 [BaseManager](#api-4-1) 的 `reset()`。 |
| 实例方法 | `step(self, action)` | 覆写 [BaseManager](#api-4-1) 的 `step()`。 |
| 实例方法 | `initialize_state(self)` | — |
| 实例方法 | `update_state(self)` | — |
| 实例方法 | `set_state(self, new_state)` | — |
| 实例方法 | `observe(self)` | — |
| 实例方法 | `get_base_state(self, transform=None)` | — |
| 实例方法 | `get_observation_spaces(self)` | — |
| 实例方法 | `get_action_spaces(self)` | — |
| 实例方法 | `get_state(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [BaseManager](#api-4-1) 的 `destroy()`。 |
| 属性 getter | `is_static(self)` | 只读属性。 |
| 属性 getter | `active_policy(self)` | 只读属性。 |
| 属性 getter | `is_warmup_step(self)` | 只读属性。 |

<a id="api-group-5"></a>

## 5. Observations

<a id="api-5-1"></a>

### 5.1 BaseObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/observation_base.py · L11](../streetworld/obs/observation_base.py#L11) |
| 基类 | `ABC` |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config)` | — |
| 实例方法 | `observe(self, *args, **kwargs)` | 基类实现抛出 `NotImplementedError`。 |
| 实例方法 | `reset(self, *args, **kwargs)` | — |
| 实例方法 | `destroy(self)` | — |
| 属性 getter | `observation_space(self)` | 只读属性；基类 getter 抛出 `NotImplementedError`。 |

<a id="api-5-2"></a>

### 5.2 DummyObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/observation_base.py · L43](../streetworld/obs/observation_base.py#L43) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config=None)` | — |
| 实例方法 | `observe(self, *args, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-3"></a>

### 5.3 DefaultObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/observation_base.py · L59](../streetworld/obs/observation_base.py#L59) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config=None)` | — |
| 实例方法 | `observe(self, *args, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-4"></a>

### 5.4 AssemblyObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/assembly_obs.py · L10](../streetworld/obs/assembly_obs.py#L10) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config: Dict[str, Any])` | — |
| 实例方法 | `reset(self, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `observe(self)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-5"></a>

### 5.5 GaussianObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/gaussian_obs.py · L9](../streetworld/obs/gaussian_obs.py#L9) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config)` | — |
| 实例方法 | `reset(self, controller, render_fn, camera_params, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `an_observation_shape(self, h, w)` | — |
| 实例方法 | `observe(self)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-6"></a>

### 5.6 StateObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/state_obs.py · L8](../streetworld/obs/state_obs.py#L8) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config=None)` | — |
| 实例方法 | `reset(self, controller, collector, seed=None, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `observe(self)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-7"></a>

### 5.7 NavigationObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/navigation_obs.py · L13](../streetworld/obs/navigation_obs.py#L13) |
| 基类 | [BaseObservation](#api-5-1)、[Randomizable](#api-9-3) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config)` | — |
| 实例方法 | `reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `observe(self)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 实例方法 | `get_reference_state(self, idx)` | — |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-8"></a>

### 5.8 SurroundingObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/surrounding_obs.py · L8](../streetworld/obs/surrounding_obs.py#L8) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config)` | — |
| 实例方法 | `reset(self, collector, controller, **kwargs)` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `observe(self)` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 属性 getter | `observation_space(self)` | 只读属性；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-5-9"></a>

### 5.9 CollisionBodyObservation

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/obs/collision_body_obs.py · L606](../streetworld/obs/collision_body_obs.py#L606) |
| 基类 | [BaseObservation](#api-5-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config: Mapping[str, Any])` | — |
| 实例方法 | `reset(self, controller: Any, collector: Any, ground: Any, **kwargs) -> None` | 覆写 [BaseObservation](#api-5-1) 的 `reset()`。 |
| 实例方法 | `observe(self) -> Dict[str, np.ndarray]` | 覆写 [BaseObservation](#api-5-1) 的 `observe()`。 |
| 实例方法 | `destroy(self) -> None` | 覆写 [BaseObservation](#api-5-1) 的 `destroy()`。 |
| 属性 getter | `observation_space(self) -> gym.spaces.Dict` | 只读属性；gym.spaces.Dict；覆写 [BaseObservation](#api-5-1) 的 `observation_space`。 |

<a id="api-group-6"></a>

## 6. Policies

<a id="api-6-1"></a>

### 6.1 BasePolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/base_policy.py · L10](../streetworld/policy/base_policy.py#L10) |
| 基类 | [Randomizable](#api-9-3)、[Configurable](#api-9-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | — |
| 实例方法 | `act(self, *args, **kwargs)` | — |
| 实例方法 | `get_action_info(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [Randomizable](#api-9-3) 的 `destroy()`。 |
| 类方法 | `get_input_space(cls)` | — |
| 实例方法 | `get_state(self)` | — |
| 属性 getter | `is_arrive(self)` | 只读属性。 |
| 属性 getter | `is_spawned(self)` | 只读属性。 |
| 属性 getter | `name(self)` | 只读属性。 |

<a id="api-6-2"></a>

### 6.2 EnvInputPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/env_input_policy.py · L10](../streetworld/policy/env_input_policy.py#L10) |
| 基类 | [BasePolicy](#api-6-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `reset()`。 |
| 实例方法 | `act(self, action, *args, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `act()`。 |
| 实例方法 | `get_input_space(self)` | 覆写 [BasePolicy](#api-6-1) 的 `get_input_space()`。 |

<a id="api-6-3"></a>

### 6.3 EnvInputPIDPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/env_input_pid_policy.py · L19](../streetworld/policy/env_input_pid_policy.py#L19) |
| 基类 | [EnvInputPolicy](#api-6-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [EnvInputPolicy](#api-6-2) 的 `reset()`。 |
| 实例方法 | `act(self, action, *args, **kwargs)` | 覆写 [EnvInputPolicy](#api-6-2) 的 `act()`。 |

<a id="api-6-4"></a>

### 6.4 EnvInputILQRPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/env_input_ilqr_policy.py · L19](../streetworld/policy/env_input_ilqr_policy.py#L19) |
| 基类 | [EnvInputPolicy](#api-6-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [EnvInputPolicy](#api-6-2) 的 `reset()`。 |
| 实例方法 | `act(self, action, *args, **kwargs)` | 覆写 [EnvInputPolicy](#api-6-2) 的 `act()`。 |
| 受保护方法 | `_xy_transform(self)` | 从控制器的变换矩阵提取二维齐次变换；`ExpertILQRPolicy` 通过此接口转换专家轨迹。 |

<a id="api-6-5"></a>

### 6.5 ExpertILQRPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/expert_ilqr_policy.py · L6](../streetworld/policy/expert_ilqr_policy.py#L6) |
| 基类 | [EnvInputILQRPolicy](#api-6-4) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None, enable_expert=True)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [EnvInputILQRPolicy](#api-6-4) 的 `reset()`。 |
| 实例方法 | `act(self, action=None, *args, **kwargs)` | 覆写 [EnvInputILQRPolicy](#api-6-4) 的 `act()`。 |
| 属性 getter | `is_arrive(self)` | 只读属性；覆写 [BasePolicy](#api-6-1) 的 `is_arrive`。 |

<a id="api-6-6"></a>

### 6.6 ReplayPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/replay_policy.py · L9](../streetworld/policy/replay_policy.py#L9) |
| 基类 | [BasePolicy](#api-6-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `reset()`。 |
| 实例方法 | `act(self, *args, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `act()`。 |
| 属性 getter | `is_arrive(self)` | 只读属性；覆写 [BasePolicy](#api-6-1) 的 `is_arrive`。 |

<a id="api-6-7"></a>

### 6.7 IDMPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/idm_policy.py · L131](../streetworld/policy/idm_policy.py#L131) |
| 基类 | [BasePolicy](#api-6-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, trajdata_map=None, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `reset()`。 |
| 实例方法 | `act(self, observation, *args, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `act()`。 |

<a id="api-6-8"></a>

### 6.8 TrajectoryIDMPolicy

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/policy/trajectory_idm_policy.py · L14](../streetworld/policy/trajectory_idm_policy.py#L14) |
| 基类 | [BasePolicy](#api-6-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_manager, config=None)` | — |
| 实例方法 | `reset(self, controller, seed, state, init_state, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `reset()`。 |
| 实例方法 | `act(self, observation, *args, **kwargs)` | 覆写 [BasePolicy](#api-6-1) 的 `act()`。 |

### 6.9 模块级函数

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 模块函数 | `smooth_1d(arr, kernel_size=5)` | [streetworld/policy/env_input_pid_policy.py · L7](../streetworld/policy/env_input_pid_policy.py#L7)。 |
| 模块函数 | `smooth_1d(arr, kernel_size=5)` | [streetworld/policy/env_input_ilqr_policy.py · L7](../streetworld/policy/env_input_ilqr_policy.py#L7)。 |

<a id="api-group-7"></a>

## 7. Objects

<a id="api-7-1"></a>

### 7.1 BaseObject

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/base_object.py · L15](../streetworld/objects/base_object.py#L15) |
| 基类 | [BaseRunnable](#api-9-4)、`MetaDriveType`、`ABC` |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, physics_world, size=None, name=None, random_seed=None, config=None, escape_random_seed_assertion=False)` | — |
| 实例方法 | `destroy(self)` | 覆写 [BaseRunnable](#api-9-4) 的 `destroy()`。 |
| 实例方法 | `set_position(self, position)` | — |
| 实例方法 | `set_heading_theta(self, heading_theta, to_deg=True) -> None` | — |
| 实例方法 | `set_transform(self, m)` | — |
| 实例方法 | `set_velocity(self, velocity)` | — |
| 实例方法 | `set_angular_velocity(self, angular_velocity, in_rad=True)` | — |
| 实例方法 | `rename(self, new_name)` | 覆写 [Nameable](#api-9-2) 的 `rename()`。 |
| 实例方法 | `attachDyWld(self, obj=None)` | — |
| 实例方法 | `detachDyWld(self, obj=None)` | — |
| 实例方法 | `set_kinematic(self, is_kinematic)` | — |
| 属性 getter | `position(self)` | 只读属性。 |
| 属性 getter | `heading_theta(self)` | 只读属性。 |
| 属性 getter | `transform(self)` | 只读属性。 |
| 属性 getter | `velocity(self)` | 只读属性。 |
| 属性 getter | `angular_velocity(self)` | 只读属性。 |
| 属性 getter | `angular_acceleration(self)` | 只读属性。 |
| 属性 getter | `acceleration(self)` | 只读属性。 |
| 属性 getter | `speed(self)` | 只读属性。 |
| 属性 getter | `speed_km_h(self)` | 只读属性。 |
| 属性 getter | `heading(self)` | 只读属性。 |

<a id="api-7-2"></a>

### 7.2 BaseVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/base_vehicle.py · L32](../streetworld/objects/vehicle/base_vehicle.py#L32) |
| 基类 | [BaseObject](#api-7-1)、`BaseVehicleState` |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config: Union[dict, Config], physics_world, size=None, name: str=None, random_seed=None, position=None, heading_theta=None, _calling_reset=True, **kwargs)` | — |
| 实例方法 | `attachDyWld(self)` | 覆写 [BaseObject](#api-7-1) 的 `attachDyWld()`。 |
| 实例方法 | `detachDyWld(self)` | 覆写 [BaseObject](#api-7-1) 的 `detachDyWld()`。 |
| 实例方法 | `reset(self, name=None, random_seed=None, position: np.ndarray=None, heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, *args, **kwargs)` | 覆写 [BaseRunnable](#api-9-4) 的 `reset()`。 |
| 实例方法 | `move(self, action=None)` | — |
| 实例方法 | `check_crash_world(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [BaseObject](#api-7-1) 的 `destroy()`。 |
| 实例方法 | `set_position(self, position)` | 覆写 [BaseObject](#api-7-1) 的 `set_position()`。 |
| 实例方法 | `get_steering_wheel_angle(self)` | — |
| 实例方法 | `get_longitudinal_acceleration(self)` | — |
| 属性 getter | `current_action(self)` | 只读属性。 |
| 属性 getter | `max_speed_km_h(self)` | 只读属性。 |

<a id="api-7-3"></a>

### 7.3 DefaultVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/vehicle_type.py · L15](../streetworld/objects/vehicle/vehicle_type.py#L15) |
| 基类 | [BaseVehicle](#api-7-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-4"></a>

### 7.4 XLVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/vehicle_type.py · L28](../streetworld/objects/vehicle/vehicle_type.py#L28) |
| 基类 | [BaseVehicle](#api-7-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-5"></a>

### 7.5 LVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/vehicle_type.py · L41](../streetworld/objects/vehicle/vehicle_type.py#L41) |
| 基类 | [BaseVehicle](#api-7-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-6"></a>

### 7.6 MVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/vehicle_type.py · L54](../streetworld/objects/vehicle/vehicle_type.py#L54) |
| 基类 | [BaseVehicle](#api-7-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-7"></a>

### 7.7 SVehicle

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/vehicle/vehicle_type.py · L66](../streetworld/objects/vehicle/vehicle_type.py#L66) |
| 基类 | [BaseVehicle](#api-7-2) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-8"></a>

### 7.8 BaseTrafficParticipant

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/traffic_participants/base_traffic_participant.py · L10](../streetworld/objects/traffic_participants/base_traffic_participant.py#L10) |
| 基类 | [BaseObject](#api-7-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config, physics_world, size, position: Sequence[float], heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, random_seed=None, name=None, **kwargs)` | — |
| 实例方法 | `reset(self, position: Sequence[float], heading_theta: float=0.0, random_seed=None, name=None, *args, **kwargs)` | 覆写 [BaseRunnable](#api-9-4) 的 `reset()`。 |
| 实例方法 | `move(self, state_info)` | — |
| 实例方法 | `destroy(self)` | 覆写 [BaseObject](#api-7-1) 的 `destroy()`。 |

<a id="api-7-9"></a>

### 7.9 Pedestrian

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/traffic_participants/pedestrian.py · L5](../streetworld/objects/traffic_participants/pedestrian.py#L5) |
| 基类 | [BaseTrafficParticipant](#api-7-8) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-10"></a>

### 7.10 Cyclist

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/traffic_participants/cyclist.py · L5](../streetworld/objects/traffic_participants/cyclist.py#L5) |
| 基类 | [BaseTrafficParticipant](#api-7-8) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| — | — | 本类没有定义或覆写需列出的成员。 |

<a id="api-7-11"></a>

### 7.11 GroundPlane

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/terrain/ground.py · L11](../streetworld/objects/terrain/ground.py#L11) |
| 基类 | [BaseObject](#api-7-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, physics_world, direction: Sequence[float], constant: float=0.0, random_seed=None, name=None, config=None, **kwargs)` | — |
| 实例方法 | `reset(self, random_seed=None, name=None, *args, **kwargs)` | 覆写 [BaseRunnable](#api-9-4) 的 `reset()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObject](#api-7-1) 的 `destroy()`。 |

<a id="api-7-12"></a>

### 7.12 MeshTerrain

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/objects/terrain/mesh_terrain.py · L14](../streetworld/objects/terrain/mesh_terrain.py#L14) |
| 基类 | [BaseObject](#api-7-1) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, physics_world, model_path: str, transform=None, position=(0, 0, 0), scale=1.0, friction=0.8, restitution=0.0, random_seed=None, name='GroundMesh', config=None, **kwargs)` | — |
| 实例方法 | `reset(self, random_seed=None, name=None, *args, **kwargs)` | 覆写 [BaseRunnable](#api-9-4) 的 `reset()`。 |
| 实例方法 | `destroy(self)` | 覆写 [BaseObject](#api-7-1) 的 `destroy()`。 |

### 7.13 模块级函数

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 模块函数 | `get_vehicle_type(length)` | [streetworld/objects/vehicle/vehicle_type.py · L5](../streetworld/objects/vehicle/vehicle_type.py#L5)。 |
| 模块函数 | `random_vehicle_type(np_random, p=None)` | [streetworld/objects/vehicle/vehicle_type.py · L81](../streetworld/objects/vehicle/vehicle_type.py#L81)。 |

<a id="api-group-8"></a>

## 8. 运行辅助组件

<a id="api-8-1"></a>

### 8.1 StepCounter

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/misc/step_counter.py · L1](../streetworld/misc/step_counter.py#L1) |
| 基类 | — |
| 说明 | `eposide_step` 按当前源码拼写列出。 |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, step_size, physical_repeat=0)` | — |
| 实例方法 | `reset(self, timestamp_range, **kwargs)` | — |
| 实例方法 | `step(self)` | — |
| 属性 getter | `relative_timestamp(self)` | 只读属性。 |
| 属性 getter | `current_timestamp(self)` | 只读属性。 |
| 属性 getter | `key_step(self)` | 只读属性。 |
| 属性 getter | `eposide_step(self)` | 只读属性。 |

<a id="api-8-2"></a>

### 8.2 PhysicsWorld

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/engine/physics_world.py · L7](../streetworld/engine/physics_world.py#L7) |
| 基类 | — |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, physics_world_step_size=0.01, substep: int=1)` | — |
| 实例方法 | `destroy(self)` | — |
| 实例方法 | `step(self)` | — |
| 属性 getter | `step_size_sec(self)` | 只读属性。 |

<a id="api-group-9"></a>

## 9. Base Classes

<a id="api-9-1"></a>

### 9.1 Configurable

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/base_class/configurable.py · L6](../streetworld/base_class/configurable.py#L6) |
| 基类 | — |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, config: Union[Dict, Config]=None)` | — |
| 实例方法 | `get_config(self, copy=True) -> Config` | — |
| 实例方法 | `update_config(self, config: dict)` | — |
| 实例方法 | `destroy(self)` | — |
| 属性 getter | `config(self)` | 只读属性。 |

<a id="api-9-2"></a>

### 9.2 Nameable

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/base_class/nameable.py · L6](../streetworld/base_class/nameable.py#L6) |
| 基类 | — |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, name=None)` | — |
| 实例方法 | `rename(self, new_name)` | — |
| 实例方法 | `destroy(self)` | — |
| 属性 getter | `class_name(self)` | 只读属性。 |

<a id="api-9-3"></a>

### 9.3 Randomizable

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/base_class/randomizable.py · L4](../streetworld/base_class/randomizable.py#L4) |
| 基类 | — |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, random_seed)` | — |
| 实例方法 | `seed(self, random_seed)` | — |
| 实例方法 | `generate_seed(self)` | — |
| 实例方法 | `destroy(self)` | — |

<a id="api-9-4"></a>

### 9.4 BaseRunnable

**类信息**

| 项目 | 内容 |
| --- | --- |
| 源码 | [streetworld/base_class/base_runnable.py · L9](../streetworld/base_class/base_runnable.py#L9) |
| 基类 | [Configurable](#api-9-1)、[Nameable](#api-9-2)、[Randomizable](#api-9-3) |
| 说明 | — |

**本类成员**

| 类别 | 签名 | 说明 |
| --- | --- | --- |
| 构造函数 | `__init__(self, name=None, random_seed=None, config=None)` | — |
| 实例方法 | `get_state(self) -> Dict` | 基类实现抛出 `NotImplementedError`。 |
| 实例方法 | `set_state(self, state: Dict)` | 基类实现抛出 `NotImplementedError`。 |
| 实例方法 | `before_step(self, *args, **kwargs)` | — |
| 实例方法 | `set_action(self, *args, **kwargs)` | 基类实现抛出 `NotImplementedError`。 |
| 实例方法 | `step(self, *args, **kwargs)` | — |
| 实例方法 | `after_step(self, *args, **kwargs)` | — |
| 实例方法 | `reset(self, random_seed=None, *args, **kwargs)` | — |
| 实例方法 | `sample_parameters(self)` | — |
| 实例方法 | `destroy(self)` | 覆写 [Configurable](#api-9-1) 的 `destroy()`。 |
