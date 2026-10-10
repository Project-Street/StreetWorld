<a id="chapter-3"></a>

<a id="section-3-1"></a>

# 3.1 Environment：本地与远程调用

[English](../../en/guides/environment-interface.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：2. 整体结构](architecture.md) · [下一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md)

Environment 提供 AD policy 与仿真交互的接口。它加载场景，接收动作并推进车辆运动，返回观测、奖励和结束状态。

## 本地调用

创建环境时，传入负责加载和渲染场景的 SimulatorInterface，以及环境配置。下面以 nuScenes 场景 `0007` 为例，让车辆保持直行并使用 20% 的油门：

```python
from st_renderer import SimulatorInterface
from streetworld.config import Config
from streetworld.envs.scenario_env import ScenarioEnv

env = ScenarioEnv(
    SimulatorInterface("nuscenes"),
    Config({"scene_ids": ["0007"]}),
)
try:
    observation, info = env.reset()
    while True:
        action = [0.0, 0.2]
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
finally:
    env.close()
```

`reset()` 开始一轮测试，返回初始观测和场景信息。`step(action)` 提交动作并返回下面五项结果，`close()` 释放环境资源。

| 返回项 | 类型与含义 |
| --- | --- |
| `observation` | 主车的观测；默认是包含 `gaussian`、`navigation`、`states`、`surrounding` 的字典 |
| `reward` | 当前一步的数值奖励，计算方式见[奖励计算](#reward-calculation) |
| `terminated` | 布尔值；本轮已经结束，例如到达终点、碰撞、离开道路或步数耗尽 |
| `truncated` | 布尔值；本轮因为达到设定的步数上限而结束 |
| `info` | 字典；包含场景名、时间、结束原因和奖励分项等信息 |

<a id="action-format"></a>

## action：轨迹与控制量

`step(action)` 的输入格式由主车的 Policy 决定。AD policy 输出未来轨迹（waypoints）时，使用 EnvInputILQRPolicy 或 EnvInputPIDPolicy 将轨迹转换为转向和油门；直接输出控制量时，使用 EnvInputPolicy 接收转向和油门/制动。

### 轨迹输入

EnvInputILQRPolicy、EnvInputPIDPolicy 等轨迹策略接收 `(N, 2)` 的数组。`N` 是未来轨迹点的数量，每一行的两个数依次为 `[x, y]`，单位是米：

| 分量 | 含义 |
| --- | --- |
| `x` | 沿主车前进方向的距离，向前为正 |
| `y` | 沿主车横向的距离，向左为正 |

这些坐标以提交动作时的主车位置为原点，并随主车朝向旋转。例如 `[10.0, 2.0]` 表示位于主车前方 10 米、左侧 2 米的目标点。每个点对应的未来时间由策略的 `trajectory_dt` 决定；若为 `0.5 s`，第一个点对应 0.5 秒后，第二个点对应 1 秒后。

```python
import numpy as np

action = np.array([[2.0, 0.0], [4.0, 0.0], [6.0, 0.5]], dtype=np.float32)
```

Policy 根据这条轨迹计算转向和油门，交给车辆执行。点的采样间隔、策略的控制周期和每个环境步的时长分别设置，见[时间配置示例](configuration/policy-controller.md#section-4-5)。

### 控制输入

默认 EnvInputPolicy 使用连续控制，接收长度为 2 的 `[steering, throttle_brake]`，两个值的范围都是 `[-1, 1]`：

| 分量 | 含义 |
| --- | --- |
| `steering` | 转向力度；`1` 为最大左转，`-1` 为最大右转，`0` 为方向回正；实际转角由车辆的 `max_steering` 决定 |
| `throttle_brake` | 油门/制动力度；正值向前驱动，`1` 为最大油门，`0` 为不加油；负值在允许倒车时向后驱动，关闭倒车时用于制动 |

例如 `[0.0, 0.2]` 表示方向回正、使用 20% 的油门，`[0.5, 0.0]` 表示向左转到最大转角的一半、松开油门。默认 `actor_config.controller_config.enable_reverse=True`，负油门会使正在前进的车辆减速并倒车。控制量的绝对值表示输入力度，车辆的实际加速度还受车辆参数和运动状态影响。

<a id="observation-data"></a>

## observation：AD policy 接收的观测

默认观测由主车的 AssemblyObservation 组合而成。更换 Observer 或配置后，字段会相应变化。

| 字段 | 内容与格式 |
| --- | --- |
| `gaussian` | 相机图像和相机参数；`gaussian['image'][相机名]` 在本地为 `(1, H, W, 3)`，默认 `uint8` RGB，像素值为 0–255；1 表示一帧，H、W 是图像高、宽，3 是 RGB 三个颜色通道 |
| `navigation` | 当前道路、行驶路线和主车相对路线的位置等导航信息 |
| `states` | 主车速度、运动状态等信息 |
| `surrounding` | 周边车辆、行人等对象的位姿、尺寸和运动状态 |

位置单位是米，速度是 `m/s`，加速度是 `m/s²`，角速度是 `rad/s`，角加速度是 `rad/s²`，`heading_theta` 等方向角使用弧度。车辆自身的坐标为 X 向前、Y 向左、Z 向上；SurroundingObservation 可设置输出的周围对象坐标是位于自车坐标系或世界坐标系，见[Observation 参考](../reference/observation.md)。相机参数与位姿矩阵的格式见[SimulatorInterface](simulator-interface.md#load-metadata)。

<a id="scenario-info"></a>

## info：场景与运行信息

`info` 用于了解当前运行到了哪里、为什么结束，以及奖励由哪些项组成。`reset()` 和 `step()` 都返回它。

| 字段 | 含义与单位 |
| --- | --- |
| `scene_name` | 当前场景 ID |
| `current_timestamp` | 当前场景的时间戳，单位为微秒 |
| `relative_timestamp` | 本轮开始后经过的仿真时间，单位为微秒；除以 `1_000_000` 得到秒 |
| `episode_length` | 本轮已完成的环境步数，reset 后为 0 |
| `reason` | 主车当前状态；本轮结束时，它就是结束原因，取值见下一节 |
| `episode_reward` | 本轮累计奖励，step 时返回 |
| `steering`、`throttle_brake` | 主车当前使用的转向和油门/制动控制量，step 时返回 |
| `step_reward`、`reward_components` | 默认奖励计算器提供的当前奖励及分项值，`reward_components['total']` 为总和 |

<a id="agent-states"></a>

## AgentState 与结束原因

AgentState 记录一个仿真对象当前处于什么状态。Environment 检查主车的状态，将它写进 `info['reason']`，再决定这一轮是否结束。它的取值是字符串：

| AgentState | `reason` 的值 | 含义 |
| --- | --- | --- |
| `NOT_SPAWN` | `not_spawn` | 尚未到达该对象的出场时间 |
| `ALIVE` | `alive` | 对象已经出场，正在运行 |
| `IDLE` | `idle` | 对象被外部调用设为停止状态 |
| `SUCCESS` | `arrive_dest` | 策略判定已到达目标；判定方式由 Policy 决定 |
| `OUT_OF_ROAD` | `out_of_road` | 道路检查不通过；有地图时附近找不到车道，无地图时距离专家轨迹过远 |
| `OUT_OF_STEP` | `out_of_step` | 已达到环境或主车设置的步数上限 |
| `CRASH_VEHICLE` | `crash_vehicle` | 与车辆碰撞 |
| `CRASH_HUMAN` | `crash_human` | 与行人碰撞 |
| `CRASH_OBJECT` | `crash_object` | 与其他交通对象碰撞 |
| `CRASH_WORLD` | `crash_world` | 与场景背景或地形碰撞 |

到达目标、离开道路、步数耗尽或碰撞时，`terminated=True`。步数耗尽时还会设置 `truncated=True`，所以此时两个值同时为真；程序用 `if terminated or truncated` 判断是否结束即可。

环境的步数上限由 `max_step` 设置，主车还有 `actor_config.max_step`。碰撞检测是否启用由主车的 `check_crash` 控制；背景碰撞还取决于车辆的 `check_crash_world`。`crash_vehicle_done` 等同名配置目前不参与这段结束判断，不能通过它们让碰撞后的场景继续运行。

<a id="reward-calculation"></a>

## 奖励计算与修改

强化学习训练通过奖励定义优化目标。可以调整已有奖励项的权重和阈值，也可以重写奖励函数，加入自己的评价项。

ScenarioEnv 使用 [RewardCalculator](../../../streetworld/misc/reward_calculator.py) 计算奖励。每轮开始时调用它的 `reset()` 清空记录，每次计算时调用 `compute(env)`，得到 `(reward, reward_info)`；Environment 将 `reward_info` 合并进 `info`，并累加每一步的 reward。

默认奖励包括以下项：

| 奖励项 | 计算内容 |
| --- | --- |
| `progress`、`reverse` | 沿路线前进的奖励和向后运动的扣分；偏离路线会减小前进奖励 |
| `position`、`heading` | 距离参考路线、朝向偏差超过阈值后的扣分 |
| `ttc` | 根据与周边对象的相对位置和速度估计碰撞还有多久；危险时扣分，满足条件时给安全奖励 |
| `collision` | 碰撞或离开道路的扣分，默认为 `-50` |
| `success_bonus` | 到达目标的奖励，默认为 `75` |
| `living_cost` | 每次计算时加入的固定项，当前默认值为 `0.05` |

修改已有项的权重或阈值，在 Config 中设置 `progress_reward_weight`、`collision_penalty_weight` 等字段即可，完整字段见 [ScenarioEnv 配置](../reference/environment.md#api-1-2)。新增计算逻辑时，可以在 ScenarioEnv 子类中覆写 `_reward_function()`。下面的例子保留默认奖励，并按转向力度追加扣分：

```python
from streetworld.envs.scenario_env import ScenarioEnv

class SteeringPenaltyEnv(ScenarioEnv):
    def _reward_function(self):
        reward, info = super()._reward_function()
        penalty = -0.1 * abs(self.actor_controller.steering)
        total = float(reward + penalty)
        info["reward_components"]["steering_penalty"] = penalty
        info["reward_components"]["total"] = total
        info["step_reward"] = total
        return total, info
```

创建环境时用 `SteeringPenaltyEnv` 替换 `ScenarioEnv`，调用方式相同。这个方法必须返回奖励数值和信息字典；新增扣分会计入环境的 `episode_reward`。

另一种方式是复制或继承 RewardCalculator，修改 `compute(env)`，然后在自定义环境的构造函数中将 `self.reward_calculator` 换成自己的计算器实例。计算器还要提供 `reset()` 和 `episode_info()`：前者清空本轮记录，后者在结束时返回累计诊断。当前没有通过 Config 直接选择奖励计算器类的字段。

<a id="interactive-env"></a>

## InteractiveEnv：看画面、状态和录像

普通 ScenarioEnv 返回观测和运行结果。需要一边运行一边查看画面、状态或保存视频时，用 `make_interactive_env()` 为它创建交互环境：

```python
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.scenario_env import ScenarioEnv

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
```

返回的类保留原环境的 `reset()`、`step()`、`close()` 接口，并管理以下组件：

| 类 | 提供的功能 | 开关与主要配置 |
| --- | --- | --- |
| WebUI | 在浏览器中显示相机拼图、车速和控制量，接收 W/A/S/D 输入 | `webui`，默认开启；地址由 `web_host`、`web_port` 设置 |
| TUI | 在终端显示场景队列、运行状态、车速、结束原因和评测指标 | `tui`，默认开启 |
| VideoExporter | 按场景保存 MP4，可在相机画面旁显示速度、角速度历史和控制量 | `video_output_dir`，默认 `videos`；设为 `None` 不录制，`video_hud` 控制附加状态显示 |

每一步完成后，交互环境从 `observation` 取相机图像，按 `image_layout` 拼接，再把画面和车辆状态交给这些类。场景结束时，终端显示结束原因和评测结果，视频写入文件。调用 `close()` 时关闭界面并保存尚未写出的录像。

网页服务在创建环境时启动，调用 `reset()` 后会等待第一步画面；执行 `step()` 后才显示新的相机图像。手动驾驶需要持续接收按键输入，见[浏览器驾驶示例](../getting-started/web-controller.md#section-1-2)。交互环境的完整配置见[组件参考](../reference/environment.md#api-1-3)。

## 远程调用

AD policy 与仿真器的依赖版本可能冲突。可将它们分别安装在两个 Python 环境中，通过 gRPC 交换观测与动作，完成闭环仿真。

先按[第一章](../getting-started/environment-server.md#section-1-3)启动 Environment Server，再用 GrpcClientEnv 连接。客户端仍然调用 `reset()`、`step()`、`close()`；加载场景、运行车辆和计算奖励都在服务端完成。

```python
import numpy as np
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv("127.0.0.1", 50052, timeout_sec=360.0)
try:
    observation, info = env.reset()
    trajectory = np.array([[0.5 * i, 0.0] for i in range(1, 7)], dtype=np.float32)
    observation, reward, terminated, truncated, info = env.step(trajectory)
finally:
    env.close()
```

这个例子对应服务端默认的轨迹策略，提交六个未来位置点。接入 AD policy 后，根据 `observation` 生成轨迹，替换 `trajectory` 并循环调用即可。

远程场景由服务端配置选择。客户端 `reset()` 的 `seed` 和 `options` 当前不会发往服务端，也不提供指定 `scene_id` 的参数。远程连续控制可提交 `[steering, throttle_brake]`；服务端把它恢复成一行两列，EnvInputPolicy 取这一行作为控制量。离散动作编号当前不适用这条传输接口，非空动作的元素总数必须是偶数。传 `None` 时，服务端也收到 `None`。

| 内容 | 远程调用时的变化 |
| --- | --- |
| 相机图像 | 客户端的单相机数组为 `(H, W, 3)`，去掉了本地的首个帧维；按 `uint8` RGB 读取，服务端需使用 `clip_rgb=False` |
| 地图对象 | `current_lane` 等对象传回时会变成字符串，不能作为本地地图对象继续调用 |
| `collision_body` | 当前不传输这个观测 |
| 连接与资源 | 客户端 `close()` 关闭连接；服务端仿真和进程由服务端关闭 |

单条 gRPC 消息的收发上限为 200 MiB。其他观测中的数值数组由客户端恢复为 NumPy 数组，`info` 仍以字典返回。客户端类和服务端的完整 API 见[Environment 参考](../reference/environment.md#api-2-1)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：2. 整体结构](architecture.md) · [下一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md)
