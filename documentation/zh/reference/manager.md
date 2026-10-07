# 5.2 Manager

[English](../../en/reference/manager.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.1 Environment](environment.md) · [下一页：5.3 Observation](observation.md)

配置字段和示例变量见[组件参考目录](index.md)。

本页目录

- [5.2.1 BaseManager](#api-4-1)
- [5.2.2 ScenarioDataManager](#api-4-2)
- [5.2.3 AgentManager](#api-4-3)

<a id="api-4-1"></a>

## 5.2.1 BaseManager

### 职责与创建方式

BaseManager 是 Manager 的基础类，提供对象登记、创建和销毁接口。一个 Manager 可能在场景运行中创建多个物理对象，切换场景时需要统一释放；子类可以使用这套对象管理机制实现自己的场景或 Agent 管理逻辑。

它通过 [Randomizable](base-classes.md#api-9-3) 管理随机状态，在 `spawned_objects` 中按 ID 保存对象，清理时调用对象的 `destroy()`。Environment 直接调用具体 Manager 的 `reset()`、`step()` 和 `update_state()`；前后置钩子不会全部自动执行。

源码：[streetworld/manager/base_manager.py](../../../streetworld/manager/base_manager.py)。

### 配置

对象构造参数通过 _spawn_object 的 kwargs 传入。BaseManager 没有 Config 参数，子类自行保存配置。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self)` | — | None | 创建随机状态与空的 spawned_objects。 | — |
| 实例方法<br>`before_step(self, *args, **kwargs) -> dict` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 前置扩展钩子；基类返回空字典。 | — |
| 实例方法<br>`step(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | None | 推进扩展钩子；基类不执行操作。 | — |
| 实例方法<br>`after_step(self, *args, **kwargs) -> dict` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 后置扩展钩子；基类返回空字典。 | — |
| 实例方法<br>`before_reset(self)` | — | None | 销毁本 Manager 创建的所有对象。 | — |
| 实例方法<br>`reset(self)` | — | None | 场景重置扩展钩子；基类不执行操作。 | — |
| 实例方法<br>`after_reset(self)` | — | None | 重置后的扩展钩子；基类不执行操作。 | — |
| 实例方法<br>`destroy(self)` | — | None | 清理随机生成器和所有对象。 | — |
| 实例方法<br>`clear_object(self, object_id)` | `object_id`：对象 ID | 已销毁的 Object 实例 | 从 spawned_objects 移除对象并调用 destroy。 | 不存在的 ID 抛 KeyError。 |
| 实例方法<br>`clear_all_objects(self)` | — | None | 逐项销毁并清空 spawned_objects。 | — |
| 实例方法<br>`get_metadata(self)` | — | dict | 在第一步前读取元数据；基类返回空字典。 | 检查的 episode_step 属性在 BaseManager 中没有定义；直接调用抛 AttributeError。 |
| 受保护方法<br>`_spawn_object(self, object_class, **kwargs)` | `object_class`：待创建的 Object 类；`**kwargs`：关键字参数 | Object 实例 | 以 kwargs 构造 object_class，并以 object.id 保存。 | 构造异常原样传播；相同 ID 覆盖字典项，不检查重复 ID。 |

### 使用示例

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

### 职责与创建方式

ScenarioDataManager 是将记录场景整理为仿真输入的数据管理器。记录数据的采样间隔与物理步长不同，它将主车和周边参与者的轨迹重采样到物理步时间轴，使初始化、轨迹回放和物理仿真使用相同的时间戳。

BaseEnv 创建它，并传入配置、元数据加载函数和模型加载函数。每次 `reset()` 选择场景、加载数据与渲染模型，准备对象初始状态和相机参数，并按 Controller 高度校准主车原点与相机外参。

源码：[streetworld/manager/scenario_data_manager.py](../../../streetworld/manager/scenario_data_manager.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | `必填` | 可运行的场景 ID；实际数量取列表长度，不能用 num_scenarios 替代。 |
| `start_scenario_index` | int | `0` | 顺序采样从此索引开始；eval 队列当前仍从索引 0 生成。 |
| `random_scenario` | bool | `True` | 非评测模式且没有显式 scene_id 时随机选场景；False 顺序循环。 |
| `physics_world_step_size` | 数值，µs | `20_000（环境默认）` | 对齐、插值记录轨迹的时间步长。 |
| `ego_z_height` | float，m | `0.0` | 记录主车原点高度；按 Controller 半高减去此值校准。 |
| `actor_config.controller` | Object 类 | `DefaultVehicle（环境默认）` | 用于主车高度和实例类型；完整环境配置提供此字段。 |
| `actor_config.controller_config.size` | 三元素序列或 None，m | `None` | 给出时以第三项作为主车高度；否则使用类 DEFAULT_HEIGHT。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config, meta_loader, model_loader)` | `config`：组件配置字典；`meta_loader`：SimulatorInterface.load_metadata 回调；`model_loader`：SimulatorInterface.load_model 回调 | None | 保存配置与加载回调，建立场景列表和初始索引。 | scene_ids 不是 list 时抛 TypeError；空列表随后无法正常选择场景。 |
| 实例方法<br>`eval(self, order=True, repeat_per_scene=1)` | `order`：顺序模式标志；`repeat_per_scene`：场景列表的遍历次数 | None | 重建索引队列并切换到评测模式。 | order=False 只修改 random_scenario，不打乱队列；repeat=2 时按 A,B,A,B 重复整个列表。 |
| 实例方法<br>`reset(self, scene_id=None)` | `scene_id`：scene_ids 中的场景 ID；None 由 Manager 选择 | VectorMap 或 None | 选择场景，复制当前配置，加载并重整元数据，设置平面信息，再调用 model_loader。 | 评测队列优先于 scene_id；队列耗尽抛 LookupError；非评测模式未知 ID 抛 ValueError。 |
| 实例方法<br>`get_current_scenario_data(self)` | — | dict | 返回本场景的 current_metadata，供环境创建地面、Agent 和相机。 | 首次 reset 后可用；返回原对象。 |
| 实例方法<br>`sort_scenarios(self)` | — | None（实现未完成） | 课程难度排序接口。 | 尚未完成：引用了未初始化的 engine/summary_lookup 和未定义的 scenario/SD。 |
| 实例方法<br>`destroy(self)` | — | None | 先执行基类对象清理，再清理场景缓存字段。 | summary_lookup/mapping 未在构造时初始化，调用会抛出 AttributeError。 |
| 属性 getter<br>`current_scenario_difficulty(self)` | — | 数值 | 没有难度表时返回 0。 | 有难度表时仍依赖旧的 summary_lookup/engine 字段，排序流程尚未接入。 |

加载后可读取以下元数据。

| 字段 | 格式与用途 |
| --- | --- |
| timestamp_range | 与主车记录时间对齐的起止微秒时间 |
| scene_id | 当前场景 ID |
| camera_params | 相机 K、H、W、ego2camera 和可选 extra |
| ego_poses | 完成高度校准后的主车记录位姿 |
| participants | 周边对象的原始 poses、size 和 type |
| init_state | 按 Agent 名索引；含 spawn_position、spawn_yaw、spawn_velocity、spawn_angular_velocity、destination、destination_yaw |
| agent_state | 按 Agent 名和时间戳索引；单帧含 transform、position、velocity、angular_velocity、heading_theta、valid、vehicle_class |
| ground_plane | 平面 normal 和 constant；有网格时环境选用网格地面 |
| scene_mesh_path、scene_mesh_transform | 可选地面网格文件及其坐标变换 |

采样时间由 Manager 生成，不包含结束时间。对象记录不足两个采样点时，不生成该对象的轨迹；整个场景的时间范围由主车记录确定。

### 使用示例

```python
# env 已 reset，由环境负责此 Manager 的加载顺序。
manager = env.data_manager
metadata = manager.get_current_scenario_data()
print(metadata["timestamp_range"])
print(metadata["init_state"]["actor"])
print(metadata["agent_state"]["actor"].keys())
```

<a id="api-4-3"></a>

## 5.2.3 AgentManager

### 职责与创建方式

AgentManager 是单个 Agent 的运行管理器，将 Observer 的观测、Policy 的决策和 Controller 的运动连接起来。它还判断 Agent 的出生、碰撞、到达终点等状态，使 Environment 可以用相同的流程推进主车和周边参与者。

BaseEnv 根据主车或参与者配置创建 AgentManager，`reset()` 时创建 Controller，并向 Observer 和 Policy 传入场景数据。主车 Manager 跨场景复用，周边参与者的 Manager 随场景重建。Observer 和 Policy 仅在首次 `reset()` 时创建，后续修改类配置不会重新创建它们。

源码：[streetworld/manager/agent_manager.py](../../../streetworld/manager/agent_manager.py)。

### 配置

构造参数 config 接收 actor_config 或 participant_config 的内容。表中使用完整环境路径，便于在环境配置中修改。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.check_crash` | bool | `True` | 非静态且 ALIVE 的车辆执行碰撞状态检查。 |
| `actor_config.max_step` | int 或 None，环境步 | `10_000` | 该 Agent 的步数上限；不是顶层 max_step。 |
| `actor_config.observer` | Observation 类 | `AssemblyObservation` | 第一次 reset 创建。 |
| `actor_config.observer_config` | dict | `gaussian/navigation/states/surrounding` | 传给 Observer，字段见各 Observation。 |
| `actor_config.policy` | Policy 类 | `EnvInputPolicy` | 第一次 reset 创建；输出交给 Controller.move。 |
| `actor_config.policy_config` | dict | `见各 Policy` | 传给 Policy，也提供 Manager 的 out_of_road_threshold。 |
| `actor_config.controller` | Object 类 | `DefaultVehicle` | 每次 reset 按此类创建 Controller。 |
| `actor_config.controller_config` | dict | 见 [BaseVehicle](object.md#api-7-2) | 物理与出生参数配置。 |
| `actor_config.warmup_step` | int 或 None，环境步 | `None` | 非 None 时创建 ExpertILQRPolicy，eposide_step 小于它时使用专家控制。 |
| `actor_config.policy_config.out_of_road_threshold` | float，m | `5.0` | 地图中搜索附近车道的半径；无地图时比较到记录轨迹采样点的距离。 |
| `participant_config.check_crash` | bool | `True` | 周边车辆的碰撞检查。 |
| `participant_config.max_step` | int 或 None，环境步 | `10_000` | 周边 Agent 的步数上限。 |
| `participant_config.observer` | Observation 类 | `DefaultObservation` | 周边车辆默认不采集观测。 |
| `participant_config.observer_config` | dict | `{}` | 传给周边 Observer。 |
| `participant_config.policy` | Policy 类 | `ReplayPolicy` | 周边车辆默认按记录回放。 |
| `participant_config.policy_config` | dict | `离散动作字段与主车相同` | ReplayPolicy 不读取离散动作字段。 |
| `participant_config.policy_config.discrete_action` | bool | `False` | EnvInputPolicy 的输入模式；默认 ReplayPolicy 不读取。 |
| `participant_config.policy_config.discrete_steering_dim` | int | `5` | EnvInputPolicy 转向档位数；默认 ReplayPolicy 不读取。 |
| `participant_config.policy_config.discrete_throttle_dim` | int | `5` | EnvInputPolicy 油门/制动档位数；默认 ReplayPolicy 不读取。 |
| `participant_config.policy_config.action_check` | bool | `False` | EnvInputPolicy 输入检查；默认 ReplayPolicy 不读取。 |
| `participant_config.controller` | Object 类 | `由元数据类型与尺寸补充` | 车辆选择 Vehicle 类，行人/骑行者使用专用类。 |
| `participant_config.controller_config` | dict | `size=None、enable_reverse=True、spawn_velocity=True、check_crash_world=False` | 场景尺寸覆盖 size；行人/骑行者的 Observer/Policy 由环境指定为 DummyObservation/ReplayPolicy。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config, step_manager)` | `config`：组件配置字典；`step_manager`：StepCounter 实例 | None | 保存配置和时间计数器，将尚未创建的组件引用设为 None。 | 配置需含 max_step、check_crash；组件必填项在首次 reset 时读取。 |
| 实例方法<br>`reset(self, config=None, **kwargs)` | `config`：可选更新配置；`kwargs`：state、init_state、physics_world、render_fn、camera_params、collector、trajdata_map、ground 等运行上下文 | None | 创建 Controller 并初始化 Policy/Observer，准备出生时刻、轨迹和地图。 | kwargs 须包含场景 state/init_state 和组件 reset 所需参数。IDM 路由初始化失败时，按记录路径长度改用 ReplayPolicy 或 TrajectoryIDMPolicy。 |
| 实例方法<br>`step(self, action)` | `action`：外部动作；格式由当前 Policy 决定 | None | 非静态且 ALIVE 时让 active_policy 计算动作，再调用 Controller.move。 | — |
| 实例方法<br>`initialize_state(self)` | — | None | 在 key_step 到达 Policy 出生时刻时挂接 Controller，转为 ALIVE。 | — |
| 实例方法<br>`update_state(self)` | — | None | 依次检查出生、碰撞、Agent 步数、道路范围和目的地，更新状态并清理终止对象。 | — |
| 实例方法<br>`set_state(self, new_state)` | `new_state`：AgentState 状态值 | None | 外部直接设置状态；NOT_SPAWN→ALIVE 时挂接；列出的终止状态清理对象。 | OUT_OF_STEP 不在此方法的清理状态列表中；普通推进由 update_state 处理。 |
| 实例方法<br>`observe(self)` | — | {'observation': 观测或 None} | ALIVE 时采集并缓存 Observer 输出；其他状态返回上次缓存。 | — |
| 实例方法<br>`get_base_state(self, transform=None)` | `transform`：4×4 齐次变换 | dict | 取得世界坐标位姿、运动状态、尺寸、类型和地图车道；静态 Agent 的运动量置零。 | 非 ALIVE 抛 ValueError；transform 参数会被 Controller.transform 覆盖，无法指定采样位姿。 |
| 实例方法<br>`get_observation_spaces(self)` | — | Observer 的空间声明 | 直接返回 observer.observation_space。 | 首次创建 Observer 并完成其所需 reset 后使用。 |
| 实例方法<br>`get_action_spaces(self)` | — | gym.Space | 返回 active_policy.get_input_space。 | 预热期间空间来自专家 Policy；轨迹 Policy 继承的空间仍声明两元素控制量。 |
| 实例方法<br>`get_state(self)` | — | dict（实现未完成） | 导出 Agent 状态，尚未完成。 | BaseManager 没有 get_state，_agent_object 也未定义，调用会抛出 AttributeError。 |
| 实例方法<br>`destroy(self)` | — | None | 已初始化时清理对象和三类组件；未初始化时直接返回。 | — |
| 属性 getter<br>`is_static(self)` | — | bool | 返回当前 Policy 是否把记录轨迹判定为静态。 | — |
| 属性 getter<br>`active_policy(self)` | — | BasePolicy 子类实例 | 预热阶段返回专家 Policy，其余时刻返回配置 Policy。 | — |
| 属性 getter<br>`is_warmup_step(self)` | — | bool | 存在专家 Policy 且 eposide_step < warmup_step 时为 True。 | — |

AgentState 包括 NOT_SPAWN、ALIVE、SUCCESS、OUT_OF_ROAD、OUT_OF_STEP、CRASH_VEHICLE、CRASH_HUMAN、CRASH_OBJECT、CRASH_WORLD 和 IDLE。同一物理步触发多个条件时，reason 由 update_state 的检查顺序决定。结束时销毁物理对象，Manager 保留状态和最后一次观测，供环境返回。

有地图时，检查车辆底面中心附近的车道；没有地图时，检查车辆与记录轨迹点的最小水平距离。get_base_state 查找当前车道的半径固定为 2.25 m，不使用 NavigationObservation 的 current_lane_max_dist。

### 使用示例

```python
# env 已 reset；主车由环境推进，不再单独调用 manager.step。
manager = env.actor_manager
print(manager.state, manager.active_policy.name)
print(manager.get_base_state()["velocity"])
print(manager.is_warmup_step)
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.1 Environment](environment.md) · [下一页：5.3 Observation](observation.md)
