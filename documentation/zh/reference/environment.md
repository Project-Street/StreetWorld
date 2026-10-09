# 5.1 Environment

[English](../../en/reference/environment.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5. 组件参考](index.md) · [下一页：5.2 Manager](manager.md)

配置字段和示例变量见[组件参考目录](index.md)。

本页目录

- [5.1.1 BaseEnv](#api-1-1)
- [5.1.2 ScenarioEnv](#api-1-2)
- [5.1.3 InteractiveScenarioEnv](#api-1-3)
- [5.1.4 GrpcClientEnv](#api-2-1)
- [5.1.5 EnvServicer](#api-2-2)
- [5.1.6 Environment 模块函数](#section-5-1-6)

<a id="api-1-1"></a>

## 5.1.1 BaseEnv

### 职责与创建方式

BaseEnv 是 StreetWorld 的仿真环境基类，提供 Gym 风格的 `reset()`、`step()` 和 `close()` 接口。闭环运行需要协调场景加载、策略执行、物理推进和观测采集；BaseEnv 负责这些工作的调用顺序，使 AD policy 可以通过环境接口读取观测、提交动作。

构造时传入 SimulatorInterface 与环境配置，初始化 Manager 和 PhysicsWorld；首次 `reset()` 时加载场景并创建对象。子类需要实现奖励计算，结束场景时还会用到 `reward_calculator`。训练和测评通常使用 [ScenarioEnv](#api-1-2)。

源码：[streetworld/envs/base_env.py](../../../streetworld/envs/base_env.py)。

### 配置

scene_ids、random_scenario、start_scenario_index 和 ego_z_height 由 [ScenarioDataManager](manager.md#api-4-2) 读取。BaseEnv 的顶层配置如下。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `physics_world_step_size` | 数值，µs | `20_000` | 物理步长；同时用于轨迹重采样。实际取整数微秒。 |
| `decision_repeat` | int，物理步数 | `5` | 一个同步 step 推进的物理步数；异步周期由它和物理步长相乘。 |
| `async_mode` | bool | `False` | 后台线程定周期推进；创建后不通过修改配置动态切换。 |
| `max_step` | int 或 None，环境步 | `None` | 环境步数上限；ScenarioEnv 改为 200。 |
| `actor_config` | dict | 见 [AgentManager](manager.md#api-4-3) | 主车的 Observer、Policy、Controller 和状态检查配置。 |
| `participant_config` | dict | 见 [AgentManager](manager.md#api-4-3) | 周边车辆配置；类型、尺寸和记录状态来自场景。 |
| `random_agent_model` | bool | `False` | 创建主车时不使用此开关。 |
| `agent_configs` | dict | `{'default_agent': {'use_special_color': True, 'spawn_lane_index': None}}` | 构造时按整项替换合并；创建主车时不使用其中的字段。 |
| `horizon` | int 或 None | `None` | 步数截断不使用此字段。 |
| `truncate_as_terminate` | bool | `False` | 结束判定不使用此字段；OUT_OF_STEP 可同时返回 terminated 和 truncated。 |
| `disable_collision` | bool | `False` | 创建 Bullet 世界时不使用此字段；碰撞检查由 AgentManager 的 check_crash 控制。 |
| `curriculum_level` | int | `1` | 课程排序尚未接入环境。 |
| `num_workers` | int | `1` | 场景采样未按 worker 划分。 |
| `pstats` | bool | `False` | 尚未启动 Panda3D 性能统计。 |
| `debug` | bool | `False` | 环境初始化不使用此字段设置日志或窗口。 |
| `debug_panda3d` | bool | `False` | 未使用。 |
| `debug_physics_world` | bool | `False` | 未使用；碰撞体画面由 CollisionBodyObservation 提供。 |
| `debug_static_world` | bool | `False` | 未使用。 |
| `log_level` | 日志级别整数 | `logging.INFO` | BaseEnv 设置日志级别的代码已被注释。 |
| `show_coordinates` | bool | `False` | 未使用。 |
| `record_episode` | bool | `False` | reset 保存标志；记录 Manager 的注册与推进尚未接入。 |
| `replay_episode` | 记录数据或 None | `None` | reset 保存是否回放的标志；不是 ReplayPolicy 的选择开关。 |
| `only_reset_when_replay` | bool | `False` | reset 保存标志；对应回放流程未接入。 |
| `force_reuse_object_name` | bool | `False` | 创建对象时未使用。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, model, config: Config=None)` | `model`：实现 SimulatorInterface 调用约定的后端实例；`config`：组件配置字典 | None | 合并默认配置和调用方配置，创建运行组件。 | model 须实现 [SimulatorInterface 接口](../guides/interfaces.md#section-3-2)；缺少 scene_ids 会在 ScenarioDataManager 构造时抛 KeyError。 |
| 类方法<br>`default_config(cls) -> Config` | — | Config | 返回 BASE_DEFAULT_CONFIG 对应的新配置。 | 不含必需的 scene_ids。 |
| 实例方法<br>`eval(self, order=True, repeat_per_scene=1)` | `order`：顺序模式标志；`repeat_per_scene`：场景列表的遍历次数 | None | 交给 ScenarioDataManager 创建评测队列；此后 reset 按队列取场景，不使用 scene_id。 | order=False 只修改随机模式标志，当前不会打乱队列。 |
| 实例方法<br>`reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`：随机种子；None 使用调用方或环境的随机状态；`scene_id`：scene_ids 中的场景 ID；None 由 Manager 选择 | (observation, info) | 加载并重置场景；异步模式提交 reset 请求并等待结果。 | 关闭后抛 RuntimeError；同时存在 reset 请求时抛 RuntimeError；评测队列耗尽抛 LookupError。 |
| 实例方法<br>`step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | `actions`：外部动作；格式由当前 Policy 决定 | (observation, reward, terminated, truncated, info) | 同步模式调用 _step；异步模式更新动作，等待正在执行的 step/reset 完成后读取缓存。 | 需先 reset；异步工作线程异常会在调用方重新抛出。 |
| 实例方法<br>`close(self)` | — | None | 关闭 Agent、地面、物理世界与渲染后端；异步模式等待所属线程完成清理。 | 重复 close 在已关闭分支直接返回；工作线程清理异常向调用方传播。 |
| 实例方法<br>`capture(self, file_name=None)` | `file_name`：输出图像路径；None 自动生成名称 | None | 从 engine 的窗口截取图像并写入文件。 | 当前未创建 engine，调用时抛 AttributeError；浏览器画面和视频使用交互环境的输出功能。 |
| 实例方法<br>`export_scenarios(self, policies: Union[dict, Callable], scenario_index: Union[list, int], max_episode_length=None, verbose=False, suppress_warning=False, render_topdown=False, return_done_info=True, to_dict=True)` | `policies`：动作回调或按 Agent ID 索引的回调字典；`scenario_index`：一个或多个场景索引；`max_episode_length`：单场景步数上限；`verbose`：记录导出进度；`suppress_warning`：关闭长回合提醒；`render_topdown`：绘制俯视图；`return_done_info`：是否附带结束信息；`to_dict`：是否转成字典 | 预期为场景字典，或 (场景字典, 结束信息字典) | 记录运行过程并导出场景。 | 未接入：is_multi_agent、engine 和记录转换函数缺失，且 reset 返回值未按当前接口解包；不能直接使用。 |
| 实例方法<br>`stop(self)` | — | None | 翻转 in_stop 标志。 | 推进循环未读取该标志，调用后仿真继续运行。 |
| 受保护方法<br>`_init_async_state(self)` | — | None | 初始化条件变量、动作缓存、reset 请求和线程异常记录。子类可覆写。 | — |
| 受保护方法<br>`_setup(self, config)` | `config`：组件配置字典 | None | 创建场景管理器、时间计数器、Bullet 世界和主车 AgentManager，注册碰撞回调。 | — |
| 受保护方法<br>`_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`：随机种子；None 使用调用方或环境的随机状态；`scene_id`：scene_ids 中的场景 ID；None 由 Manager 选择 | (observation, info) | 清理上一场景，加载地图、地面和 Agent，重置时间与渲染场景，采集第一帧观测。 | 基类直接使用会遇到未实现的奖励接口。 |
| 受保护方法<br>`_step(self, actions: Union[Union[np.ndarray, list], Dict[AnyStr, Union[list, np.ndarray]], int])` | `actions`：外部动作；格式由当前 Policy 决定 | 五项 step 结果 | 按物理步调用 Policy、推进物理、更新状态，再更新渲染场景并采集观测。 | 同一外部动作传入各 AgentManager，由各自 Policy 解释。 |
| 受保护方法<br>`_reward_function(self, object_id: str) -> Tuple[float, Dict]` | `object_id`：对象 ID | 子类应返回 (float, dict) | 由子类实现奖励计算。 | 基类抛 NotImplementedError；环境调用时不传 object_id，子类覆写时须使用无参数签名。 |
| 受保护方法<br>`_cost_function(self, object_id: str) -> Tuple[float, Dict]` | `object_id`：对象 ID | 子类应返回 (float, dict) | 由子类实现成本计算。 | 基类抛 NotImplementedError；step 未调用此函数。 |
| 受保护方法<br>`_done_function(self)` | — | (bool, dict) | 根据主车状态或环境 max_step 判定终止，info.reason 保存原因；终止时追加奖励累计诊断。 | 依赖 reward_calculator.episode_info()；各 crash_*_done 配置不参与此判定。 |
| 受保护方法<br>`_close(self)` | — | None | 销毁 Agent、地面与 PhysicsWorld，并调用后端 close；交互子类在此基础上关闭 UI。 | — |
| 属性 getter<br>`config(self)` | — | Config | 有场景配置时返回 current_config，否则返回 base_config。 | 返回可变对象。 |
| 属性 getter<br>`scene_id(self) -> str` | — | str | 按当前索引取得场景 ID。 | reset 前索引尚未选定，不用它查询已加载场景。 |
| 属性 getter<br>`actor_manager(self)` | — | AgentManager | 取得主车 Manager。 | — |
| 属性 getter<br>`actor_controller(self)` | — | BaseObject 子类实例 | 取得当前主车 Controller。 | 首次 reset 后可用。 |
| 属性 getter<br>`observations(self)` | — | BaseEnv 自身 | 返回 self。 | 没有返回观测缓存；使用 reset/step 的 observation。 |
| 属性 getter<br>`observation_space(self) -> gym.Space` | — | gym.Space（需定义 is_multi_agent） | 向主车 Manager 查询空间并按单/多 Agent 分支包装。 | 未定义 is_multi_agent，访问时抛出 AttributeError；子 Observer 声明也不一定匹配输出。 |
| 属性 getter<br>`action_space(self) -> gym.Space` | — | gym.Space（需定义 is_multi_agent） | 向主车 Policy 查询空间并按单/多 Agent 分支包装。 | 未定义 is_multi_agent，访问时抛出 AttributeError。 |

### 使用示例

```python
# env 是已创建的 ScenarioEnv 或交互环境。
observation, info = env.reset(scene_id="0007")
print(info["scene_name"], info["current_timestamp"])
observation, reward, terminated, truncated, info = env.step([0.0, 0.0])
env.close()
```

<a id="api-1-2"></a>

## 5.1.2 ScenarioEnv

### 职责与创建方式

ScenarioEnv 是用于在记录场景中训练和测评 AD policy 的 Environment。它在 BaseEnv 的仿真流程中加入奖励计算和驾驶指标统计，将每次交互的驾驶行为汇总为场景结果，供训练算法和 benchmark 使用。

构造时创建 RewardCalculator 与 MetricCalculator，`reset()` 时清空场景统计，每次 `step()` 更新指标，场景结束时汇总指标。奖励计算需要 [NavigationObservation](observation.md#api-5-7)，观测中还需包含 `states`、`navigation` 和 `surrounding`。

源码：[streetworld/envs/scenario_env.py](../../../streetworld/envs/scenario_env.py)。

### 配置

运行参数继承自 BaseEnv。SCENARIO_ENV_CONFIG 增加或覆盖以下字段。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `start_scenario_index` | int | `0` | 场景 Manager 的初始索引，见 [ScenarioDataManager](manager.md#api-4-2)。 |
| `position_deviation_threshold` | float，m | `2.0` | 到导航路径的横向距离超过阈值时开始惩罚。 |
| `position_penalty_gain` | float | `0.2` | 位置偏差超限量的线性惩罚系数。 |
| `position_penalty_max` | float | `0.25` | 位置偏差单步惩罚的最大绝对值。 |
| `heading_deviation_threshold` | float，rad | `0.1` | 相对参考航向的误差阈值；没有专家参考航向时不计算。 |
| `heading_penalty_weight` | float | `0.5` | 航向误差超限部分的惩罚系数。 |
| `heading_penalty_max` | float | `0.5` | 正数时限制航向单步惩罚的最大绝对值。 |
| `progress_reward_weight` | float | `2.0` | 沿导航路径向前进展的奖励系数。 |
| `reverse_penalty_weight` | float | `1.0` | 沿路径倒退距离的惩罚系数。 |
| `progress_deviation_weight` | float | `0.1` | 向前奖励乘 exp(-系数 × 路径偏差)。 |
| `ttc_safe_horizon` | float，s | `4.0` | TTC 低于该值开始安全惩罚，高于该值可获得安全奖励。 |
| `ttc_warn_horizon` | float，s | `2.0` | TTC 低于该值使用高风险惩罚区间。 |
| `ttc_mid_penalty_weight` | float | `0.5` | 警告阈值与安全阈值之间的最大惩罚尺度。 |
| `ttc_high_penalty_weight` | float | `0.8` | 警告阈值以下的最大惩罚尺度。 |
| `ttc_safe_bonus_weight` | float | `0.2` | 安全阈值以上的正奖励尺度。 |
| `ttc_safe_bonus_min_speed` | float，m/s | `0.5` | 与进展阈值共同判断停滞；停滞时取消正 TTC 奖励。 |
| `ttc_safe_bonus_min_progress` | float，m/环境步 | `0.05` | 与速度阈值共同判断停滞。 |
| `living_cost` | float | `0.05` | 源码直接加到总奖励；默认值是正奖励，名称不决定符号。 |
| `collision_penalty_weight` | float | `50.0` | 碰撞、crash_world 或 out_of_road 时扣除此值。 |
| `success_bonus` | float | `75.0` | 主车状态为 SUCCESS 时加入的奖励。 |
| `max_step` | int，环境步 | `200` | 覆盖 BaseEnv 的环境步数上限。 |
| `num_scenarios` | int | `3` | 场景数量由 len(scene_ids) 确定，不使用此字段。 |
| `sequential_seed` | bool | `False` | 全局 seed 更新不使用此字段。 |
| `worker_index` | int | `0` | 场景选择未按 worker 划分。 |
| `num_workers` | int | `1` | 场景选择未按 worker 划分。 |
| `curriculum_level` | int | `1` | 课程排序没有接入。 |
| `episodes_to_evaluate_curriculum` | int 或 None | `None` | 未使用。 |
| `target_success_rate` | float | `0.8` | 未使用。 |
| `store_map` | bool | `True` | 后端直接加载地图，不使用此字段控制缓存。 |
| `store_data` | bool | `True` | Manager 不使用此缓存开关。 |
| `need_lane_localization` | bool | `True` | 此字段不控制车道查询。 |
| `no_map` | bool | `False` | 此字段不会让后端跳过地图加载。 |
| `map_region_size` | 数值 | `1024` | 地图裁剪未使用此字段。 |
| `cull_lanes_outside_map` | bool | `True` | 加载地图时未使用。 |
| `no_traffic` | bool | `False` | 创建 Agent 时不会按此字段过滤周边对象。 |
| `no_static_vehicles` | bool | `False` | 创建 Agent 时不会按此字段过滤静态车辆。 |
| `no_light` | bool | `False` | 环境尚未接入交通灯 Manager。 |
| `reactive_traffic` | bool | `False` | 设置 participant_config.policy 选择 IDM，此字段不生效。 |
| `filter_overlapping_car` | bool | `True` | 创建对象时未使用。 |
| `default_vehicle_in_traffic` | bool | `False` | 创建对象时未使用。 |
| `skip_missing_light` | bool | `True` | 环境尚未接入交通灯 Manager。 |
| `static_traffic_object` | bool | `True` | 创建对象时未使用。 |
| `show_sidewalk` | bool | `False` | 渲染时未使用。 |
| `even_sample_vehicle_class` | 任意或 None | `None` | 已标记弃用，未使用。 |
| `crash_vehicle_cost` | float | `1.0` | 成本函数代码被注释，未进入 step 结果。 |
| `crash_object_cost` | float | `1.0` | 成本函数代码被注释，未进入 step 结果。 |
| `out_of_road_cost` | float | `1.0` | 成本函数代码被注释，未进入 step 结果。 |
| `crash_human_cost` | float | `1.0` | 成本函数代码被注释，未进入 step 结果。 |
| `out_of_route_done` | bool | `False` | 终止判定不使用此字段。 |
| `crash_vehicle_done` | bool | `False` | 终止判定不使用此字段；CRASH_VEHICLE 状态直接终止。 |
| `crash_object_done` | bool | `False` | 终止判定不使用此字段；CRASH_OBJECT 状态直接终止。 |
| `crash_human_done` | bool | `False` | 终止判定不使用此字段；CRASH_HUMAN 状态直接终止。 |
| `relax_out_of_road_done` | bool | `True` | 终止判定不使用此字段；OUT_OF_ROAD 状态直接终止。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, model, config=None)` | `model`：实现 SimulatorInterface 调用约定的后端实例；`config`：组件配置字典 | None | 创建 BaseEnv 运行组件以及奖励、指标计算器。 | — |
| 类方法<br>`default_config(cls)` | — | Config | 在 BaseEnv 默认值上合并 SCENARIO_ENV_CONFIG。 | — |
| 实例方法<br>`get_average_metric(self)` | — | dict[str, float] | 对已完成场景的各项指标求平均，忽略各项 NaN。 | 尚无已完成场景时，访问空列表会抛出 IndexError。 |
| 受保护方法<br>`_reset(self, seed: Union[None, int]=None, scene_id: Union[None, str]=None)` | `seed`：随机种子；None 使用调用方或环境的随机状态；`scene_id`：scene_ids 中的场景 ID；None 由 Manager 选择 | (observation, info) | 先重置奖励，再重置环境；按主车 warmup_step 重置指标并登记起始帧。 | — |
| 受保护方法<br>`_step(self, actions)` | `actions`：外部动作；格式由当前 Policy 决定 | 五项 step 结果 | 推进环境后更新指标；terminated 或 truncated 时完成本场景指标。 | — |
| 受保护方法<br>`_reward_function(self)` | — | (float, dict) | 调用 RewardCalculator.compute；返回奖励、组成项、TTC 和路径偏差等诊断。 | 没有导航 Observer 或有效路径时抛 TypeError/ValueError。 |

总奖励是 living_cost、向前进展、倒退、TTC、位置偏差、航向偏差、碰撞和成功奖励之和。TTC 用对象中心距离除以朝主车接近的相对速度估计，没有考虑车辆矩形的接触时间。无对象靠近时，TTC 为 None，不计算该项奖励。

专家预热结束后开始采集模型控制样本。交接帧用于确定起点，不计入样本。各项指标的计算方式如下。

| 指标 | 当前计算方式 |
| --- | --- |
| NC | 没有 crash_vehicle/human/object/world 原因为 1，发生过为 0；out_of_road 不计为 NC 碰撞 |
| DAC | current_lane 非 None 的模型控制步数占比 |
| TTC | 最小 TTC 为 None 或至少 5 s 的步数占比 |
| COM | 水平加速度模长不超过 2 m/s²，且偏航角速度绝对值不超过 0.5 rad/s 的步数占比 |
| RC | 交接后路线进展 / 交接时剩余路线长度，限制在 [0, 1] |
| RE | 交接后路线进展 / 仿真经过时间，单位 m/s |

COM 检查角速度，计算器中的字段仍名为 yaw_acc_threshold。阈值由 MetricCalculator 设置，环境 Config 未开放这些字段。没有模型控制样本时，DAC/TTC/COM/RE 为 NaN，RC 为 0；剩余路线长度不为正时，RC 为 NaN。

### 使用示例

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

### 职责与创建方式

InteractiveScenarioEnv 是用于观察、操作和调试场景运行的交互式 Environment。它在 ScenarioEnv 上加入 TUI、WebUI、视频录制和轨迹投影，便于查看车辆状态与 AD policy 的规划结果；开启 WebUI 后，也可以通过浏览器驾驶主车。

用 `make_interactive_env(ScenarioEnv)` 创建这个环境类，返回类名为 `InteractiveScenarioEnv`，再像 ScenarioEnv 一样传入 SimulatorInterface 和配置来构造实例。界面与录制功能按配置启用，随环境的重置、步进和关闭更新或释放资源。

源码：[streetworld/envs/interactive_env.py](../../../streetworld/envs/interactive_env.py)。

### 配置

基础运行参数使用原环境的配置。交互环境新增以下字段。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `web_host` | str | `127.0.0.1` | WebUI 绑定主机。 |
| `web_port` | int | `8080` | WebUI 端口，不是 gRPC 端口。 |
| `video_output_dir` | str 或 None | `videos` | 视频输出目录；None 关闭视频。 |
| `video_hud` | bool | `True（读取时默认）` | 是否把车辆状态叠加到视频。 |
| `image_layout` | list[list[str]] | `[['FRONT_LEFT', 'FRONT', 'FRONT_RIGHT'], ['BACK_LEFT', 'BACK', 'BACK_RIGHT']]` | 相机拼接顺序；名称必须存在于 gaussian.image。 |
| `project_trajectory_on_camera` | str 或 None | `None` | 指定相机上的轨迹投影；非二维轨迹动作不绘制。 |
| `history_size` | int | `200` | WebUI 指标曲线保存的历史长度。 |
| `jpeg_quality` | int | `85` | WebUI 初始 JPEG 编码质量。 |
| `max_image_edge` | int，px | `1200` | WebUI 图像最长边上限。 |
| `eval_mode` | bool | `True` | 构造时进入场景评测模式。 |
| `eval_order` | bool | `True` | 传给 eval 的顺序参数。 |
| `eval_repeat_per_scene` | int | `1` | 传给 eval 的重复次数。 |
| `tui` | bool | `True` | 是否创建和启动终端界面。 |
| `webui` | bool | `True` | 是否创建和启动浏览器界面。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, simulator_interface, config=None)` | `simulator_interface`：实现 SimulatorInterface 调用约定的后端实例；`config`：组件配置字典 | None | 创建基类环境；按配置创建 UI/视频组件，并启动 TUI、WebUI 和评测队列。 | 输出启用时 step 需要 gaussian 与 states 观测。 |
| 类方法<br>`default_config(cls)` | — | Config | 在包装基类的默认配置上合并 INTERACTIVE_ENV_CONFIG。 | — |
| 受保护方法<br>`_reset(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | (observation, info) | 刷新界面、写出上场景视频，再重置环境并登记场景。 | 评测队列耗尽时更新 TUI 状态并继续抛 LookupError。 |
| 受保护方法<br>`_step(self, action)` | `action`：外部动作；格式由当前 Policy 决定 | 五项 step 结果 | 消耗 WebUI 接管动作，推进环境，拼接画面并更新 UI/视频；终止时输出指标和视频。 | image_layout 中的相机名称必须存在。 |
| 受保护方法<br>`_close(self)` | — | None | 关闭 TUI、完成尚未写出的视频、关闭 WebUI，再执行基类清理。 | — |

### 使用示例

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

### 职责与创建方式

GrpcClientEnv 是 AD policy 调用远程仿真环境的 Gym 客户端。AD policy 与仿真组件需要不同的 Python 依赖时，可以分别运行两个进程，由客户端保留 `reset()`、`step(action)` 的调用方式，通过 gRPC 交换动作和观测。

构造时连接已启动的 Environment Server，发送 `Reset`、`Step` 请求，将返回的图像和 Struct 观测还原为 Python 数据。场景加载、物理推进和渲染由服务端的 Environment 执行。

源码：[streetworld/envs/grpc_client_env.py](../../../streetworld/envs/grpc_client_env.py)。

### 配置

通过构造参数设置 host、port、timeout_sec 和 auto_wait_ready，无需 Config。传输格式见 [Environment 本地与远程调用](../guides/interfaces.md#section-3-1)。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, host: str='127.0.0.1', port: int=50052, timeout_sec: float=10.0, auto_wait_ready: bool=True)` | `host`：gRPC 服务主机；`port`：gRPC 服务端口；`timeout_sec`：RPC 超时，单位秒；`auto_wait_ready`：构造时是否等待连接 READY | None | 创建无鉴权 gRPC 通道和 stub；按 auto_wait_ready 等待服务 READY。 | 等待超时抛 grpc.FutureTimeoutError；空间声明只是占位。 |
| 实例方法<br>`reset(self, *, seed: Optional[int]=None, options: Optional[Dict[str, Any]]=None) -> Tuple[Any, Dict[str, Any]]` | `seed`：随机种子；None 使用调用方或环境的随机状态；`options`：Gym reset 扩展参数 | (observation, info) | 发送空 Reset 请求；RPC 超时为 timeout_sec 的两倍。 | seed/options 被丢弃；响应 status=True 时抛 RuntimeError；传输失败抛 grpc.RpcError。 |
| 实例方法<br>`step(self, action: Optional[np.ndarray]) -> Tuple[Any, float, bool, bool, Dict[str, Any]]` | `action`：外部动作；格式由当前 Policy 决定 | (observation, float, bool, bool, info) | 把动作展平发送；None 发送空数组；RPC 超时为 timeout_sec。 | 服务端按 (-1,2) 重塑；响应失败抛 RuntimeError，传输失败抛 grpc.RpcError。 |
| 实例方法<br>`close(self) -> None` | — | None | 取消连接状态订阅，关闭 gRPC 通道并清除 channel 引用。 | 只关闭客户端连接；服务端 Environment 继续运行。 |

### 使用示例

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

### 职责与创建方式

EnvServicer 是 Environment Server 的服务端请求处理类，将本地 Environment 暴露给 [GrpcClientEnv](#api-2-1)。它把 RPC 动作转换为环境输入，调用本地的 `reset()` 或 `step()`，再将观测、奖励和结束状态编码为响应，使远程 AD policy 能使用同一个仿真流程。

`serve(env, ...)` 会创建并注册这个实例。它保存传入的 Environment，并用锁串行处理请求，避免多个 RPC 同时修改环境状态。直接调用 `Reset` 或 `Step` 时，需要生成的 Protobuf 请求和 gRPC context。

源码：[streetworld/envs/env_servicer.py](../../../streetworld/envs/env_servicer.py)。

### 配置

监听地址由 serve() 的 host、port 设置。场景和 Policy 沿用本地环境配置，EnvServicer 没有独立 Config。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, env)` | `env`：本地 Environment 实例 | None | 保存 env 并创建互斥锁。 | — |
| 实例方法<br>`Reset(self, request: service_pb2.ResetRequest, context) -> service_pb2.ResetResponse` | `request`：生成的 Protobuf 请求对象；`context`：gRPC ServicerContext | ResetResponse | 锁内调用 env.reset，序列化第一帧和 info。 | 评测队列耗尽转为 status=True/message；其他异常继续传播到 gRPC。 |
| 实例方法<br>`Step(self, request: service_pb2.StepRequest, context) -> service_pb2.StepResponse` | `request`：生成的 Protobuf 请求对象；`context`：gRPC ServicerContext | StepResponse | 锁内将非空动作 reshape(-1,2)，调用 env.step 后序列化结果。 | 奇数个动作元素会抛 ValueError；环境/序列化错误直接传播。 |

### 使用示例

```python
# env 是已创建的本地环境；serve 阻塞到服务退出。
from streetworld.envs.env_servicer import serve

serve(env, host="127.0.0.1", port=50052)
```

<a id="section-5-1-6"></a>

## 5.1.6 Environment 模块函数

make_interactive_env 定义在 interactive_env.py，serve 定义在 env_servicer.py。
| 模块函数<br>`make_interactive_env(env_class)` | env_class：待包装的 Environment 类 | 环境类 | 返回带界面与录制功能的包装类，类名为 Interactive 加原类名；先绑定类名，再构造环境。 | 包装的环境需提供奖励和交互评测所需接口。 |
| 模块函数<br>`serve(env, *, host: str, port: int) -> None` | env：本地环境；host：绑定主机；port：绑定端口 | None | 创建单工作线程 gRPC 服务并阻塞等待；退出时停止 RPC 并在所属线程关闭 env。 | 绑定失败抛 RuntimeError；当前读取 env.config["tui"]，使用纯 ScenarioEnv 时须补 tui=False。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5. 组件参考](index.md) · [下一页：5.2 Manager](manager.md)
