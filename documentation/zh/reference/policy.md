# 5.4 Policy

[English](../../en/reference/policy.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.3 Observation](observation.md) · [下一页：5.5 Object / Controller](object.md)

配置字段和示例变量见[组件参考目录](index.md)。

本页目录

- [5.4.1 BasePolicy](#api-6-1)
- [5.4.2 EnvInputPolicy](#api-6-2)
- [5.4.3 EnvInputPIDPolicy](#api-6-3)
- [5.4.4 EnvInputILQRPolicy](#api-6-4)
- [5.4.5 ExpertILQRPolicy](#api-6-5)
- [5.4.6 ReplayPolicy](#api-6-6)
- [5.4.7 IDMPolicy](#api-6-7)
- [5.4.8 TrajectoryIDMPolicy](#api-6-8)
- [5.4.9 Policy 模块函数](#section-5-4-9)

<a id="api-6-1"></a>

## 5.4.1 BasePolicy

### 职责与创建方式

BasePolicy 是将控制策略接入 Agent 运行流程的基类。外部动作、轨迹跟踪、记录回放和规则策略都通过 `act()` 向 Controller 提交控制量或记录状态，AgentManager 因此可以用同一个调用接口运行不同的 Policy。

AgentManager 构造 Policy 时传入 StepCounter 与配置，`reset()` 时传入 Controller、记录状态和随机种子。BasePolicy 保存这些运行数据，并提供出生、到达终点与动作诊断接口。Manager 每个物理步调用 `act()`，具体 Policy 决定是否只在 `key_step` 更新控制量。

源码：[streetworld/policy/base_policy.py](../../../streetworld/policy/base_policy.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.out_of_road_threshold` | float，m | `5.0` | Policy 保存此值；AgentManager 也读取它检查道路范围。 |
| `actor_config.policy_config.arrive_speed_threshold` | float，m/s | `10.0` | 目的地判定允许的当前速度与记录终点速度差。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None)` | `step_manager`：StepCounter 实例；`config`：组件配置字典 | None | 保存 StepCounter，创建配置与随机状态，初始化 action_info。 | 必须传入配置字典；config=None 时在 config.get 处抛出 AttributeError。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 保存 Controller/轨迹/目的地并设 seed；确定出生时间、终点速度和轨迹是否静态。 | 至少有一个 valid 状态，否则抛 ValueError；init_state 需含 destination 和 destination_yaw。 |
| 实例方法<br>`act(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | None（基类） | 子类计算并返回 Controller 动作，基类 act 不执行操作。 | 基类返回 None，运行策略须覆写 act。 |
| 实例方法<br>`get_action_info(self)` | — | dict | 深复制当前 action_info。 | — |
| 实例方法<br>`destroy(self)` | — | None | 清空配置与随机生成器。 | — |
| 类方法<br>`get_input_space(cls)` | — | Box(-1,1,(2,),float32) | 默认声明归一化转向与油门/制动输入。 | 轨迹子类未覆写该空间声明。 |
| 实例方法<br>`get_state(self)` | — | dict | 返回 get_action_info() 的深复制。 | — |
| 属性 getter<br>`is_arrive(self)` | — | bool | 非静态对象越过终点纵向平面、横向偏差≤20 m、速度误差≤arrive_speed_threshold 时为真。 | — |
| 属性 getter<br>`is_spawned(self)` | — | bool | 当前时间不早于记录轨迹的第一帧时为真。 | — |
| 属性 getter<br>`name(self)` | — | str | 返回 Policy 类名。 | — |

记录轨迹的平均速度小于 0.01 m/s 时，static=True。AgentManager 不对静态对象调用 act，基础 is_arrive 也返回 False。

reset 的 state 为 `{timestamp: {position, velocity, heading_theta, angular_velocity, transform, valid, ...}}`。init_state 至少提供出生位置、出生航向和终点。

### 使用示例

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

### 职责与创建方式

EnvInputPolicy 是接收外部车辆控制量的 Policy。AD policy 或浏览器已经给出转向和油门/刹车指令时，可以用它将 `env.step(action)` 的输入交给 Controller，适用于直接控制车辆的训练和交互驾驶。

通过 Agent 的 `policy` 配置选用，由 AgentManager 创建。每个环境步在 `key_step` 接收新动作，其余物理步复用 `last_action`；离散动作会按配置转换为连续控制量。

源码：[streetworld/policy/env_input_policy.py](../../../streetworld/policy/env_input_policy.py)。

### 配置

同时使用 BasePolicy 的通用配置。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.discrete_action` | bool | `False（环境默认；类构造必填）` | False 接收两元素控制；True 接收一个组合离散索引。 |
| `actor_config.policy_config.discrete_steering_dim` | int | `5（环境默认；类构造必填）` | 离散转向档位数，按 [-1,1] 等间距映射；需大于 1。 |
| `actor_config.policy_config.discrete_throttle_dim` | int | `5（环境默认；类构造必填）` | 离散油门/制动档位数，按 [-1,1] 等间距映射；需大于 1。 |
| `actor_config.policy_config.action_check` | bool | `False（环境默认）` | EnvInputPolicy.act 在转换前用 get_input_space.contains 断言输入。 |
| `actor_config.policy_config.controller` | str | `keyboard（主车环境默认）` | Policy 不读取此字段、不监听键盘；浏览器动作由交互环境提交。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`：StepCounter 实例；`config`：组件配置字典；`enable_expert`：保存的标志；当前 EnvInputPolicy 不读取它来切换控制 | None | 读取离散设置，建立档位间隔，初始化零动作。 | 缺必填项抛 KeyError；档位数为 1 会除零；enable_expert 仅保存，预热切换由 AgentManager 负责。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 执行 BasePolicy.reset 并清空 last_action。 | — |
| 实例方法<br>`act(self, action, *args, **kwargs)` | `action`：外部动作；格式由当前 Policy 决定；`*args`：位置参数；`**kwargs`：关键字参数 | 两元素控制量 | key_step 读取动作；二维 NumPy 动作取第一行；离散索引转为连续控制。 | action_check 失败抛 AssertionError；不会把 None 自动转成有效车辆控制。 |
| 实例方法<br>`get_input_space(self)` | — | Box 或 Discrete | 连续模式为 Box(-1,1,(2,),float32)；离散模式为转向档位数×油门档位数的 Discrete。 | — |

离散动作 k 的转向档位为 `k % discrete_steering_dim`，油门档位为 `k // discrete_steering_dim`，分别线性映射到 [-1,1]。正转向表示向左，负 throttle_brake 是制动还是倒车，由 Controller.enable_reverse 决定。

### 使用示例

```python
from streetworld.policy.env_input_policy import EnvInputPolicy

cfg.merge_from({"actor_config.policy": EnvInputPolicy,
                "actor_config.policy_config.discrete_action": False})
# 用此 cfg 创建并 reset 环境后：
# observation, reward, terminated, truncated, info = env.step([0.1, 0.3])
```

<a id="api-6-3"></a>

## 5.4.3 EnvInputPIDPolicy

### 职责与创建方式

EnvInputPIDPolicy 是用 PID 跟踪外部规划轨迹的 Policy。输出未来路径点的 AD policy 需要将轨迹转换为车辆可执行的转向和油门/刹车指令，它承担这一转换，便于通过 `env.step(trajectory)` 测试轨迹规划结果。

它扩展 [EnvInputPolicy](#api-6-2)，接收车辆坐标系中的未来轨迹。在 `key_step` 将新轨迹按 `control_dt` 重采样；后续控制更新将缓存轨迹转换到当前车辆坐标系，移除已执行的点，再计算 PID 控制量。

源码：[streetworld/policy/env_input_pid_policy.py](../../../streetworld/policy/env_input_pid_policy.py)。

### 配置

构造时仍需提供 EnvInputPolicy 的离散配置字段，但 act 按轨迹计算控制，不做离散转换和 action_check。环境没有为它提供默认 preset，示例中的 PID 增益需按车辆调整。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.smooth` | bool | `必填；默认轨迹 preset 为 False` | 对补上原点后的轨迹 X/Y 分量分别做 5 点加权平滑。 |
| `actor_config.policy_config.trajectory_dt` | float，s | `必填；默认轨迹 preset 为 0.5` | 预测点的采样时间间隔；第一点在一个 trajectory_dt 之后。 |
| `actor_config.policy_config.control_dt` | float，s | `必填；默认轨迹 preset 为 0.5` | 重采样与控制更新时间；须为物理步长整数倍，应与环境决策周期一致。 |
| `actor_config.policy_config.turn_controller` | 三元素序列 | `必填` | 转向 PID 的 Kp、Ki、Kd。 |
| `actor_config.policy_config.speed_controller` | 三元素序列 | `必填` | 速度 PID 的 Kp、Ki、Kd。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`：StepCounter 实例；`config`：组件配置字典；`enable_expert`：保存的标志；当前 EnvInputPolicy 不读取它来切换控制 | None | 初始化 EnvInputPolicy、轨迹配置和两个 PIDController。 | 缺字段抛 KeyError；control_dt 不是物理步长整数倍抛 ValueError。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 重置基础轨迹信息、缓存变换、控制时间与 PID 状态。 | — |
| 实例方法<br>`act(self, action, *args, **kwargs)` | `action`：外部动作；格式由当前 Policy 决定；`*args`：位置参数；`**kwargs`：关键字参数 | (steering, throttle_brake) | 以头两个重采样点的中点控制转向、点间距离决定期望速度；超速时返回 -1 制动指令。 | None 返回 (0,0)；有效重采样轨迹至少需要两个点；静止/零期望速度可能导致除零。 |

### 使用示例

```python
from streetworld.policy.env_input_pid_policy import EnvInputPIDPolicy

cfg.merge_from({"actor_config.policy": EnvInputPIDPolicy,
    "actor_config.policy_config": {
        "smooth": False, "trajectory_dt": 0.5, "control_dt": 0.1,
        "turn_controller": [1.25, 0.75, 0.3],
        "speed_controller": [5.0, 0.5, 1.0],
    },
})
# 默认物理步长 0.02 s × decision_repeat 5 = control_dt 0.1 s。
```

<a id="api-6-4"></a>

## 5.4.4 EnvInputILQRPolicy

### 职责与创建方式

EnvInputILQRPolicy 是用 iLQR 跟踪外部规划轨迹的 Policy。它根据车辆当前状态和运动模型求解一段控制序列，将 AD policy 输出的路径点转换为车辆指令，适用于需要考虑轴距、转向与加速度约束的轨迹跟踪。

通过 Agent 的 `policy` 配置选用，扩展 [EnvInputPolicy](#api-6-2) 的轨迹输入处理。求解模型读取车辆轴距和最大轮转角，使用平面位置、航向、速度与轮转角组成的五维状态；首个控制量归一化为 Controller 接收的转向和油门/刹车动作。

源码：[streetworld/policy/env_input_ilqr_policy.py](../../../streetworld/policy/env_input_ilqr_policy.py)。

### 配置

构造时仍需提供 EnvInputPolicy 的离散配置字段，但 act 不做离散转换和 action_check。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.smooth` | bool | `必填；默认轨迹 preset 为 False` | 对补上原点后的轨迹 X/Y 分量分别做 5 点加权平滑。 |
| `actor_config.policy_config.trajectory_dt` | float，s | `必填；默认轨迹 preset 为 0.5` | 预测点的采样时间间隔；第一点在一个 trajectory_dt 之后。 |
| `actor_config.policy_config.control_dt` | float，s | `必填；默认轨迹 preset 为 0.5` | 重采样与控制更新时间；须为物理步长整数倍，应与环境决策周期一致。 |
| `actor_config.policy_config.max_acceleration` | float，m/s² | `必填；默认轨迹 preset 为 3.0` | iLQR 加速度约束，以及加速度转归一化油门/制动的比例。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`：StepCounter 实例；`config`：组件配置字典；`enable_expert`：保存的标志；当前 EnvInputPolicy 不读取它来切换控制 | None | 保存轨迹控制配置和 iLQR warm-start 参数。 | 缺字段抛 KeyError；control_dt 不是物理步长整数倍抛 ValueError。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 读取车辆轴距和转角限制，创建求解参数并清空轨迹缓存。 | Controller 需要 FRONT_WHEELBASE/REAR_WHEELBASE/max_steering；max_steering 通过 .item() 读取。 |
| 实例方法<br>`act(self, action, *args, **kwargs)` | `action`：外部动作；格式由当前 Policy 决定；`*args`：位置参数；`**kwargs`：关键字参数 | (steering, throttle_brake) | 重采样轨迹并求解 iLQR；两个控制更新之间复用 last_action。 | None 返回 (0,0)；非空输入须为可 reshape 的 NumPy 数组，并提供足够的未来采样点。 |
| 受保护方法<br>`_xy_transform(self)` | — | ndarray(3,3) | 从 Controller.transform 取 X/Y 齐次变换，供轨迹缓存与专家子类调用。 | — |

求解器最多迭代 100 次，收敛阈值为 1e-6，最大求解时间为 0.1 s。状态代价、输入代价和 warm-start 参数固定在类中，环境 Config 未开放这些字段。

control_dt 要与 `physics_world_step_size × decision_repeat × 1e-6` 相等。构造函数只检查它是否为物理步长的整数倍，源码注明其他决策周期组合仍有问题。

### 使用示例

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
# 用此 cfg 创建并 reset 环境后提交 N×2 float32 轨迹：
# trajectory = np.array([[2.0, 0.0], [4.0, 0.0], [6.0, 0.2]], dtype=np.float32)
# observation, reward, terminated, truncated, info = env.step(trajectory)
```

<a id="api-6-5"></a>

## 5.4.5 ExpertILQRPolicy

### 职责与创建方式

ExpertILQRPolicy 是以记录中的专家轨迹为参考的驾驶 Policy。它用车辆控制跟踪参考路径，可用于检查场景和控制流程是否能连续运行，也用于正式接入 AD policy 前的预热驾驶。

它从记录轨迹选取未来路径点，转换到车辆坐标系，再交给 [EnvInputILQRPolicy](#api-6-4) 跟踪。可以将它配置为主车 Policy；设置 `warmup_step` 后，AgentManager 也会创建一个 ExpertILQRPolicy 来控制预热阶段。

源码：[streetworld/policy/expert_ilqr_policy.py](../../../streetworld/policy/expert_ilqr_policy.py)。

### 配置

通用配置继承自 EnvInputPolicy 和 BasePolicy。设置 warmup_step 时，还需提供专家策略要求的 trajectory_dt、control_dt 等字段。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.trajectory_steps` | 正整数，点数 | `10` | 每次最多选取的未来记录点数量。 |
| `actor_config.policy_config.trajectory_dt` | float，s | `必填` | 记录路径的重采样间隔；至少一微秒。 |
| `actor_config.policy_config.control_dt` | float，s | `必填` | 沿用 iLQR 控制周期要求。 |
| `actor_config.policy_config.smooth` | bool | `强制 False` | 构造时覆盖调用方值。 |
| `actor_config.policy_config.max_acceleration` | float，m/s² | `强制 3.2` | 构造时覆盖调用方值。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None, enable_expert=True)` | `step_manager`：StepCounter 实例；`config`：组件配置字典；`enable_expert`：保存的标志；当前 EnvInputPolicy 不读取它来切换控制 | None | 覆盖 smooth/max_acceleration 后初始化 iLQR，读取 trajectory_steps。 | config=None 在 dict(config) 处抛 TypeError；trajectory_steps<1 抛 ValueError；仍需父类必填配置。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 初始化 iLQR，按有效记录时间重采样专家路径，并保留终点时间。 | 没有有效记录点，或 trajectory_dt 小于一微秒时抛 ValueError。 |
| 实例方法<br>`act(self, action=None, *args, **kwargs)` | `action`：外部动作；格式由当前 Policy 决定；`*args`：位置参数；`**kwargs`：关键字参数 | (steering, throttle_brake) | 忽略外部 action，选择当前时间之后的未来记录点；只有一个未来点时复制成两个供跟踪。 | 没有未来点或前方点时标记到达并返回上次控制量。 |
| 属性 getter<br>`is_arrive(self)` | — | bool | 已标记到达或当前时间到达记录终点时为 True。 | — |

### 使用示例

```python
from streetworld.policy.expert_ilqr_policy import ExpertILQRPolicy

cfg.merge_from({"actor_config.policy": ExpertILQRPolicy,
    "actor_config.policy_config": {"trajectory_dt": 0.1,
                                   "control_dt": 0.1, "trajectory_steps": 30}})
# 用此 cfg 创建并 reset 后，env.step(None) 由专家自行生成路径。
```

<a id="api-6-6"></a>

## 5.4.6 ReplayPolicy

### 职责与创建方式

ReplayPolicy 是复现记录运动的回放 Policy。闭环测评主车时，可以用它保持周边交通参与者的记录轨迹，使场景中的背景交通按原始时间轴运行。它是周边参与者的默认 Policy。

`reset()` 将 Controller 设为运动学刚体，`act()` 按当前仿真时间返回记录状态，Controller 据此恢复位姿和速度。AgentManager 负责传入重采样后的轨迹与 StepCounter。

源码：[streetworld/policy/replay_policy.py](../../../streetworld/policy/replay_policy.py)。

### 配置

使用 BasePolicy 配置，无额外字段。participant_config 中的离散动作字段对 ReplayPolicy 无效。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 执行基础 reset，启用 kinematic，记录轨迹末端时间。 | — |
| 实例方法<br>`act(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict 或 None | 按当前微秒时间戳返回记录帧；valid=False 时返回 None。 | 时间戳必须存在，否则抛 KeyError；车辆 move 无法处理 None 记录帧。 |
| 属性 getter<br>`is_arrive(self)` | — | bool | 到达记录轨迹末端时间时为 True。 | — |

### 使用示例

```python
from streetworld.policy.replay_policy import ReplayPolicy

cfg.merge_from({"participant_config.policy": ReplayPolicy})
# 回放对象的 state 由 ScenarioDataManager 重采样到同一物理步时间轴。
```

<a id="api-6-7"></a>

## 5.4.7 IDMPolicy

### 职责与创建方式

IDMPolicy 是基于车道地图与 Intelligent Driver Model（IDM）的规则驾驶 Policy。它根据前车间距和相对速度调整加减速，用于让交通车辆沿地图路线行驶并对周边车流作出响应；换道行为由配置控制。

`reset()` 时根据 trajdata VectorMap 的车道拓扑生成路线，需要地图能够匹配出生点和终点。运行时读取 `states` 与世界坐标下的 `surrounding` 观测，计算纵向控制量和转向，再交给车辆 Controller。

源码：[streetworld/policy/idm_policy.py](../../../streetworld/policy/idm_policy.py)。

### 配置

表中使用周边 Agent 的路径。配置主车时将前缀换成 actor_config，通用字段见 [BasePolicy](#api-6-1)。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `participant_config.policy_config.disable_idm_deceleration` | bool | `False` | 是否禁止 IDM 的减速输出。 |
| `participant_config.policy_config.enable_lane_change` | bool | `True` | 是否启用相邻车道超车策略。 |
| `participant_config.policy_config.normal_speed` | float，km/h | `30.0` | 正常巡航目标速度。 |
| `participant_config.policy_config.creep_speed` | float，km/h | `5.0` | 缓行目标速度。 |
| `participant_config.policy_config.max_long_dist` | float，m | `30.0` | 前后车搜索的最大纵向范围。 |
| `participant_config.policy_config.safe_lane_change_distance` | float，m | `15.0` | 换道时前后安全距离。 |
| `participant_config.policy_config.current_lane_max_dist` | float，m | `2.25` | 路由初始化时匹配出生与终点车道的距离阈值。 |
| `participant_config.policy_config.lane_change_speed_increase` | float，km/h | `10.0` | 换道收益速度阈值。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None)` | `step_manager`：StepCounter 实例；`config`：组件配置字典 | None | 保存 IDM 配置，创建航向/横向 PID 与路由状态。 | — |
| 实例方法<br>`reset(self, controller, seed, state, init_state, trajdata_map=None, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`trajdata_map`：当前场景的 trajdata.VectorMap；无地图时为 None；`**kwargs`：关键字参数 | None | 校验车辆与地图，定位车道并创建到记录终点的道路路线，重置 PID 和换道计时。 | 非车辆或没有地图抛 ValueError；车道/路由初始化失败抛 IDMRouteInitializationError。 |
| 实例方法<br>`act(self, observation, *args, **kwargs)` | `observation`：Observer 的最近一次输出；具体必需字段见本 Policy 的输入约定；`*args`：位置参数；`**kwargs`：关键字参数 | [steering, throttle_brake] | key_step 解析世界坐标 states/surrounding，沿当前路线选目标车道并计算控制。 | 缺观测抛 ValueError/KeyError；运行车道拓扑异常可抛 IDMLaneRuntimeError；current_lane=None 时返回零控制，记录 idm_out_of_road。 |

act 读取 states 中的 ego_pos、heading_theta、linear_velocity、current_lane 等字段，以及 surrounding 中的世界坐标位置、速度、size 和车道信息。StateObservation 需要车辆 Controller，行人和骑行者使用回放。

AgentManager 捕获 IDMRouteInitializationError 后，按有效记录路径长度选择替代策略：不足 5 m 时使用 ReplayPolicy，否则使用 TrajectoryIDMPolicy。直接调用 IDMPolicy.reset 时，异常仍会抛出。

### 使用示例

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

### 职责与创建方式

TrajectoryIDMPolicy 是沿记录路径行驶的 IDM 跟车 Policy。它保留场景记录中的路线，同时根据周边对象的位置和速度调整加减速，适合用记录轨迹限定路线、又需要跟车响应的交通车辆。

`reset()` 时从有效记录状态生成世界坐标路径，运行时使用世界坐标下的 `surrounding` 观测计算 IDM 控制量。路线来自记录轨迹，本类不生成地图路线或执行换道。

源码：[streetworld/policy/trajectory_idm_policy.py](../../../streetworld/policy/trajectory_idm_policy.py)。

### 配置

主车配置将路径前缀换成 actor_config，通用字段见 [BasePolicy](#api-6-1)。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `participant_config.policy_config.front_distance` | float，m | `5.0` | 与前方车辆的期望最小间距；非车辆使用固定 2 m。 |
| `participant_config.policy_config.react_time` | float，s | `1.0` | 跟车期望时间间隔。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_manager, config=None)` | `step_manager`：StepCounter 实例；`config`：组件配置字典 | None | 保存跟车配置，从 25–50 km/h 采样速度上限。 | 速度采样通过独立 gym Box，未使用 BasePolicy.np_random 的 seed。 |
| 实例方法<br>`reset(self, controller, seed, state, init_state, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`state`：按微秒时间戳索引的记录状态字典；`init_state`：出生与终点信息字典；`**kwargs`：关键字参数 | None | 校验车辆，提取 valid 路径点并计算弧长与曲率半径。 | 非车辆、少于三个有效点或零长度路径抛 ValueError。 |
| 实例方法<br>`act(self, observation, *args, **kwargs)` | `observation`：Observer 的最近一次输出；具体必需字段见本 Policy 的输入约定；`*args`：位置参数；`**kwargs`：关键字参数 | (steering, throttle_brake) | key_step 根据路径曲率和前车间距计算加减速，朝前方路径点控制转向。 | 缺 surrounding 抛 KeyError；找不到前方路径点抛 RuntimeError；周边位置/速度必须是世界坐标。 |

目标速度取随机速度上限与曲率限速中的较小值。加速度归一化使用 Controller 的 MASS、max_engine_force、max_brake_force 和 TIRE_RADIUS，转向归一化使用 max_steering。

### 使用示例

```python
from streetworld.policy.trajectory_idm_policy import TrajectoryIDMPolicy

# 保留 IDMPolicy 示例中的 states/surrounding(world) 观测配置。
cfg.merge_from({"participant_config.policy": TrajectoryIDMPolicy,
                "participant_config.policy_config.front_distance": 5.0,
                "participant_config.policy_config.react_time": 1.0})
```

<a id="section-5-4-9"></a>

## 5.4.9 Policy 模块函数

[env_input_pid_policy.py](../../../streetworld/policy/env_input_pid_policy.py) 和 [env_input_ilqr_policy.py](../../../streetworld/policy/env_input_ilqr_policy.py) 各自定义了 smooth_1d，签名和实现相同，均使用下表的调用方式。

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 模块函数<br>`smooth_1d(arr, kernel_size=5)` | arr：一维数值序列；kernel_size：核大小，默认 5 | float32 ndarray | 边界复制填充后卷积平滑；kernel_size=5 使用 [1,4,6,4,1]，其他值使用均匀权重。 | 输入需一维非空序列，核大小为正整数；偶数核的输出长度会多一项。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.3 Observation](observation.md) · [下一页：5.5 Object / Controller](object.md)
