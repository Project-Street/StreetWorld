<a id="chapter-3"></a>

# 3. 接口约定

[English](../../en/guides/interfaces.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一章：2. 整体结构](architecture.md) · [下一章：4. 配置系统](configuration.md)

- [3.1 Environment：本地与远程调用](#section-3-1)
- [3.2 3D 资产与 SimulatorInterface](#section-3-2)
- [3.3 渲染后端示例](#section-3-3)
    - [3.3.1 ST Renderer](#st-renderer)
    - [3.3.2 NuRec](#nurec)

<a id="section-3-1"></a>

## 3.1 Environment：本地与远程调用

Environment 用于运行驾驶测试。它载入场景，接收驾驶动作，计算车辆运动，再返回新的观测、奖励和结束状态。驾驶程序根据这些结果决定下一步怎么开；本地程序直接调用环境，独立运行的模型则通过 `GrpcClientEnv` 调用服务端环境。

### 本地调用

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

### action：轨迹与控制量

`step(action)` 的输入由主车的 Policy 决定。EnvInputILQRPolicy、EnvInputPIDPolicy 可以用于AD policy的推理，直接接收未来轨迹 (waypoint) 并转化为控制量，EnvInputPolicy 接收转向和油门/制动。

#### 轨迹输入

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

Policy 根据这条轨迹计算转向和油门，交给车辆执行。点的采样间隔、策略的控制周期和每个环境步的时长分别设置，见[时间配置示例](configuration.md#section-4-5)。

#### 控制输入

默认 EnvInputPolicy 使用连续控制，接收长度为 2 的 `[steering, throttle_brake]`，两个值的范围都是 `[-1, 1]`：

| 分量 | 含义 |
| --- | --- |
| `steering` | 转向力度；`1` 为最大左转，`-1` 为最大右转，`0` 为方向回正；实际转角由车辆的 `max_steering` 决定 |
| `throttle_brake` | 油门/制动力度；正值向前驱动，`1` 为最大油门，`0` 为不加油；负值在允许倒车时向后驱动，关闭倒车时用于制动 |

例如 `[0.0, 0.2]` 表示方向回正、使用 20% 的油门，`[0.5, 0.0]` 表示向左转到最大转角的一半、松开油门。默认 `actor_config.controller_config.enable_reverse=True`，负油门会使正在前进的车辆减速并倒车。控制量的绝对值表示输入力度，车辆的实际加速度还受车辆参数和运动状态影响。

<a id="observation-data"></a>

### observation：驾驶程序能读到什么

默认观测由主车的 AssemblyObservation 组合而成。更换 Observer 或配置后，字段会相应变化。

| 字段 | 内容与格式 |
| --- | --- |
| `gaussian` | 相机图像和相机参数；`gaussian['image'][相机名]` 在本地为 `(1, H, W, 3)`，默认 `uint8` RGB，像素值为 0–255；1 表示一帧，H、W 是图像高、宽，3 是 RGB 三个颜色通道 |
| `navigation` | 当前道路、行驶路线和主车相对路线的位置等导航信息 |
| `states` | 主车速度、运动状态等信息 |
| `surrounding` | 周边车辆、行人等对象的位姿、尺寸和运动状态 |

位置单位是米，速度是 `m/s`，加速度是 `m/s²`，角速度是 `rad/s`，角加速度是 `rad/s²`，`heading_theta` 等方向角使用弧度。车辆自身的坐标为 X 向前、Y 向左、Z 向上；SurroundingObservation 可设置输出的周围对象坐标是位于自车坐标系或世界坐标系，见[Observation 参考](../reference/observation.md)。相机参数与位姿矩阵的格式见[SimulatorInterface](#load-metadata)。

<a id="scenario-info"></a>

### info：场景与运行信息

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

### AgentState 与结束原因

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

### 奖励计算与修改
奖励函数的设计对于强化学习训练非常关键。研究者可以根据自己的需要，修改重写reward类或函数。
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

修改已有项的权重或阈值，在 Config 中设置 `progress_reward_weight`、`collision_penalty_weight` 等字段即可，完整字段见 [ScenarioEnv 配置](../reference/environment.md#api-1-2)。新增计算逻辑，可以在 ScenarioEnv 子类中覆写 `_reward_function()`。例如，设计一个保留默认奖励，再对大幅转向扣分的reward：

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

### InteractiveEnv：看画面、状态和录像

普通 ScenarioEnv 返回观测和运行结果。需要一边运行一边查看画面、状态或保存视频时，用 `make_interactive_env()` 为它创建交互环境：

```python
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.scenario_env import ScenarioEnv

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
```

返回的类仍有原环境的 `reset()`、`step()`、`close()`接口，并管理下面三个UI示例：

| 类 | 提供的功能 | 开关与主要配置 |
| --- | --- | --- |
| WebUI | 在浏览器中显示相机拼图、车速和控制量，接收 W/A/S/D 输入 | `webui`，默认开启；地址由 `web_host`、`web_port` 设置 |
| TUI | 在终端显示场景队列、运行状态、车速、结束原因和评测指标 | `tui`，默认开启 |
| VideoExporter | 按场景保存 MP4，可在相机画面旁显示速度、角速度历史和控制量 | `video_output_dir`，默认 `videos`；设为 `None` 不录制，`video_hud` 控制附加状态显示 |

每一步完成后，交互环境从 `observation` 取相机图像，按 `image_layout` 拼接，再把画面和车辆状态交给这些类。场景结束时，终端显示结束原因和评测结果，视频写入文件。调用 `close()` 时关闭界面并保存尚未写出的录像。
网页服务在创建环境时启动，场景刚 reset 时会等待第一步画面；执行 `step()` 后才显示新的相机图像。手动驾驶需要持续接收按键的运行方式，见[浏览器驾驶示例](../getting-started/index.md#section-1-2)。交互环境的完整配置见[组件参考](../reference/environment.md#api-1-3)。

### 远程调用
AD policy与仿真器往往存在环境依赖的冲突，所以最好的实践是将AD policy与仿真器分别配置在两个环境中，并通过进程间通信完成仿真与推理的闭环。
模型与仿真分别运行时，先按[第一章](../getting-started/index.md#section-1-3)启动 Environment Server，再用 GrpcClientEnv 连接。客户端仍然调用 `reset()`、`step()`、`close()`；加载场景、运行车辆和计算奖励都在服务端完成。

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

这个例子对应服务端默认的轨迹策略，提交六个未来位置点。模型接入后，根据 `observation` 生成自己的轨迹，替换 `trajectory` 并循环调用即可。

远程场景由服务端配置选择。客户端 `reset()` 的 `seed` 和 `options` 当前不会发往服务端，也不提供指定 `scene_id` 的参数。远程连续控制可提交 `[steering, throttle_brake]`；服务端把它恢复成一行两列，EnvInputPolicy 取这一行作为控制量。离散动作编号当前不适用这条传输接口，非空动作的元素总数必须是偶数。传 `None` 时，服务端也收到 `None`。

| 内容 | 远程调用时的变化 |
| --- | --- |
| 相机图像 | 客户端的单相机数组为 `(H, W, 3)`，去掉了本地的首个帧维；按 `uint8` RGB 读取，服务端需使用 `clip_rgb=False` |
| 地图对象 | `current_lane` 等对象传回时会变成字符串，不能作为本地地图对象继续调用 |
| `collision_body` | 当前不传输这个观测 |
| 连接与资源 | 客户端 `close()` 关闭连接；服务端仿真和进程由服务端关闭 |

单条 gRPC 消息的收发上限为 200 MiB。其他观测中的数值数组由客户端恢复为 NumPy 数组，`info` 仍以字典返回。客户端类和服务端的完整 API 见[Environment 参考](../reference/environment.md#api-2-1)。

<a id="section-3-2"></a>

## 3.2 3D 资产与 SimulatorInterface

SimulatorInterface 是 StreetWorld 对场景加载和图像渲染的接口约定。不同数据集的场景资产按这套约定提供轨迹、相机参数、地图和地形，就能以相同的数据格式交给 Environment。不同渲染器实现这套接口后，也可以根据仿真中的对象位置和相机位置生成画面。

Environment 按约定调用这些方法，具体实现自行读取数据文件、加载资产和渲染图像。接入新的数据集或渲染器时，实现下面四个方法，再把实例传给 Environment。仓库已有后端的创建与启动方法见[渲染后端示例](#section-3-3)。

### SimulatorInterface 的四个调用

接口将加载与渲染分开：开始一个场景时读取元数据和模型，运行期间更新对象位置并反复获取图像。四个方法的调用顺序是 `load_metadata()`、`load_model()`，随后重复 `update_scene()`、`render()`。Environment 按方法名调用，不要求接口继承公共基类。

下面用 `scene_id` 表示场景标识。Environment 将它作为位置参数传入；ST Renderer 的两个加载方法中，这个参数名为 `scene_name`。

<a id="load-metadata"></a>

#### load_metadata(scene_id)

Environment 需要知道场景持续多久、主车从哪里出发、周边有哪些对象，以及相机安装在哪里，才能创建仿真。这些信息由 `load_metadata()` 读取；渲染模型在下一步加载。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `scene_id` | 场景标识；ST Renderer 使用字符串，NuRec 也接受相对 Path | 指定要读取的场景；两种后端的 ID 写法见[场景目录](#scene-files) |

返回六元组，顺序固定：

```python
(timestamp_range, camera_params, ego_poses, participants,
 scene_mesh_path, scene_mesh_transform)
```

| 返回项 | 类型与单位 | 用途 |
| --- | --- | --- |
| `timestamp_range` | `[开始时间, 结束时间]`，整数微秒 | 场景的记录时间范围；环境按物理步长采样，不包含结束时刻 |
| `camera_params` | `{相机名: 参数字典}` | 每台相机需要 `K`：3×3 内参矩阵，焦距与主点以像素表示；`H`、`W`：图像高、宽，整数像素；`ego2camera`：4×4 车辆到相机的变换；`extra` 可存后端专用相机参数 |
| `ego_poses` | `{整数微秒时间戳: 4×4 位姿}` | 主车记录轨迹；矩阵将车辆坐标变换到仿真世界坐标，平移以米表示 |
| `participants` | `{对象ID: {'poses': 位姿字典, 'size': [长, 宽, 高], 'type': 类型}}` | 周边交通对象；`poses` 与主车轨迹使用相同的时间和矩阵约定，尺寸以米表示，类型用于选择车辆、行人或骑行者等仿真对象 |
| `scene_mesh_path` | OBJ（`.obj`）或 PLY（`.ply`）三角网格文件路径，或 `None` | 为物理仿真提供地形网格；没有网格时环境会创建平面地形。当前 Waymo 使用 OBJ，NuRec 使用 PLY。 |
| `scene_mesh_transform` | 4×4 网格到仿真世界的变换，或 `None` | 将地形网格放到对应位置；`None` 表示不附加变换 |

位姿矩阵的左上 3×3 部分表示旋转，最后一列的前三个数表示位置。主车位姿、周边对象位姿和道路地图要使用同一套仿真世界坐标。车辆自身的坐标为 X 向前、Y 向左、Z 向上，相机坐标为 X 向右、Y 向下、Z 向前。

Environment 读取后会按车辆高度修正主车记录原点，并一起调整相机外参。查询道路地图时使用车辆底面中心。扩展接口或设置相机位置时，要保持位姿和外参的原点一致。

<a id="load-model"></a>

#### load_model(scene_id)

这一步加载场景3D资产与高精地图，并返回道路地图。元数据描述场景中的对象，渲染模型用于生成图像；将两者分开，环境就能先读取轨迹和相机参数，再准备模型。目前StreetWorld支持的地图为 `trajdata.VectorMap`。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `scene_id` | 与 `load_metadata()` 相同的场景 ID | 指定要加载模型的场景；必须先读取该场景的元数据 |

返回值为 `trajdata.VectorMap` 或 `None`。地图供车道查询、导航和道路检查使用，渲染模型由接口自身保存。ST Renderer 加载场景中的高斯模型；NuRec 准备远程渲染所需的场景信息，并从 XODR 构建 VectorMap。

<a id="update-scene"></a>

#### update_scene(timestamp, object_poses)

仿真中的车辆可能偏离记录轨迹。每次获取画面前，Environment 用这个方法告诉渲染器当前的仿真时间和周边对象位置，让画面反映它们在仿真中的运动。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `timestamp` | 当前场景时间戳，微秒 | 与记录数据使用同一条时间轴；这里传入 `current_timestamp`，不是从零开始的 `relative_timestamp` |
| `object_poses` | `{对象 ID: torch.Tensor}`；每个张量是 4×4 的位姿矩阵 | 字典的键与 `participants` 中的对象 ID 一致；矩阵表示该对象在仿真世界中的位置和朝向，平移单位为米 |

Environment 将仍在运行的周边对象放入 `object_poses`。主车的位置通过相机外参传给渲染器，不放进这个字典。

返回 `None`。接口保存时间和对象位姿，供后续 `render()` 使用。

<a id="render"></a>

#### render(K, H, W, extrinsics)

相机观测需要从主车当前的位置拍摄。`render()` 根据前一步保存的场景状态，以及本次传入的相机参数生成图像。它按批次处理相机，输入中的第 i 组参数对应返回的第 i 张图像。

设本次渲染 B 台相机：

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `K` | `(B, 3, 3)` 内参矩阵；Environment 传入 `torch.float32` 张量 | 每台相机的焦距与主点，单位为像素；ST Renderer 要求 Torch 张量，NuRec 也接受 NumPy 数组 |
| `H` | 长度为 B 的整数列表，像素 | 每张图像的高度 |
| `W` | 长度为 B 的整数列表，像素 | 每张图像的宽度 |
| `extrinsics` | `(B, 4, 4)` 仿真世界到相机的变换；Environment 传入 `torch.float32` 张量 | 决定每台相机在当前场景中的位置和朝向；ST Renderer 要求 Torch 张量，NuRec 也接受 NumPy 数组 |

相机外参由 `ego2camera @ inverse(主车的车辆到世界位姿)` 得到。主车移动后重新计算它，就能从新的车辆位置获取画面。

返回 B 张 `uint8` RGB 图像，像素值为 0–255，每张形状为 `(H[i], W[i], 3)`。当前 ST Renderer 返回 `(B, H, W, 3)` 的 NumPy 数组，同批相机必须使用相同的 H、W；NuRec 返回图像列表。GaussianObservation 按相机顺序读取这些图像，再为本地观测加上首个帧维。

NuRec 的部分相机使用 `ftheta` 鱼眼模型。它们的成像需要额外的标定数据，不能只用内参矩阵 `K` 描述。因此，NuRec 的 `render()` 还接受 `extra` 参数，用来传递相机名称、模型类型和标定参数。

`extra` 是长度为 B 的列表，与 `K` 使用相同的相机顺序。每台相机的参数字典包含：

| 字段 | 含义 |
| --- | --- |
| `logical_id` | NuRec 场景中的相机名，例如 `camera_front_wide_120fov` |
| `type` | 相机模型；`pinhole` 表示针孔模型，`ftheta` 表示鱼眼模型 |
| `parameters` | `ftheta` 相机的原始标定参数，包括主点、多项式系数等；针孔相机使用 `K`，不需要这个字段 |

正常通过 Environment 获取观测时，无需手工填写 `extra`。NuRec 的 `load_metadata()` 从 `rig_trajectories.json` 读取这些数据，放进每台相机的 `camera_params`，GaussianObservation 再将它们传给 `render()`。直接调用 NuRec 的 `render()` 时，应按相机顺序传入这些 `extra` 字典。不传 `extra` 或某项为 `None` 时，该项使用针孔模型和相机名 `camera_front_tele_30fov`。参数读取代码见 [parse_camera_params()](../../../submodules/nurec_interface/nurec_parser.py)。

<a id="section-3-3"></a>

## 3.3 渲染后端示例

nuScenes 和 Waymo 使用 ST Renderer 在本机 GPU 上渲染；NuRec 场景由独立服务渲染。选择对应后端后，将接口实例传给 Environment。

<a id="st-renderer"></a>

### 3.3.1 ST Renderer

ST Renderer 在本机 GPU 上渲染重建好的 nuScenes 或 Waymo 高斯场景。选择 nuScenes 时这样创建接口：

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Waymo 使用 `SimulatorInterface("waymo")`。默认从仓库下的对应数据目录读取文件；数据放在其他位置时，用 `root` 指定存放场景 NPZ 的目录，例如 `SimulatorInterface("nuscenes", root="/path/to/nuscenes")`。

NuRec 的场景格式、渲染服务安装和启动步骤见 [3.3.2 NuRec](#nurec)。

<a id="scene-files"></a>

### 场景资产目录

按默认路径运行时，场景文件放在 StreetWorld 根目录下：

```text
data/processed/benchmark/
├── nuscenes/
│   ├── 0007.npz
│   ├── <其他场景名>.npz
│   └── map_cache.npz
├── waymo/
│   ├── <场景名>.npz
│   └── ground/<场景名>.obj
└── NuRec/sample_set/25.07_release/
    └── Batch<编号>/<场景目录>/
        ├── <uuid>.usdz
        └── <uuid>/
            ├── rig_trajectories.json
            ├── sequence_tracks.json
            ├── map.xodr
            └── mesh_ground.ply
```

nuScenes 和 Waymo 的场景 ID 是 NPZ 文件名去掉扩展名，例如 `0007`、`001-segment-1422926405879888210`。

NuRec 的场景 ID 是以 `Batch<数字>` 开头的相对路径，如 `Batch0001/<场景目录>`，相对于 `nurec_root`。每个场景目录包含一个 USDZ 文件，并有同名 UUID 子目录保存解包后的数据。

<a id="nurec"></a>

### 3.3.2 NuRec

[NuRec](https://docs.nvidia.com/nurec/index.html) 是 NVIDIA 提供的场景重建与渲染工具。它将采集的相机、激光雷达数据重建成三维场景，保存为 USDZ 文件。渲染时可以改变相机和交通对象的位姿，从这些场景生成新的画面。

StreetWorld 使用已经重建好的 NuRec 场景。[NuRec SimulatorInterface](../../../submodules/nurec_interface/simulator_interface.py) 读取本地轨迹、相机参数和 XODR 地图，并通过 [gRPC 渲染服务](https://docs.nvidia.com/nurec/api/grpc_api_guide.html) 请求图像。

运行时需要启动两个服务：NuRec 渲染服务监听 `8080`，供 SimulatorInterface 请求图像；StreetWorld Environment Server 监听 `50052`，供 AD policy 获取观测和提交动作。渲染服务使用 `nre-ga:26.04` 镜像，详见 [NuRec 服务配置说明](../../../submodules/nurec_interface/NUREC_GRPC_SERVER_SETUP.md)。

#### 配置 Docker 的 GPU 支持

主机需要先安装 NVIDIA 驱动和 Docker。Ubuntu / Debian 上安装 NVIDIA Container Toolkit：

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg2

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

其他系统的安装方式见 [NVIDIA Container Toolkit 安装文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。拉取镜像，并检查容器能否使用 GPU：

```bash
docker pull nvcr.io/nvidia/nre/nre-ga:26.04
docker run --rm --gpus all --entrypoint nvidia-smi nvcr.io/nvidia/nre/nre-ga:26.04
```

#### 启动 NuRec 渲染服务

数据按[场景资产目录](#scene-files)准备。下面以子模块说明中的 `Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa` 场景为例，在 StreetWorld 根目录执行：

```bash
NUREC_HOST_ROOT="$PWD/data/processed/benchmark/NuRec"
SCENE_USDZ="sample_set/25.07_release/Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa/7e11dcb8-7bce-4972-b998-8626857e92aa.usdz"

docker run -d --name nurec-grpc \
  --shm-size=64g \
  --gpus all \
  --net=host \
  --privileged \
  -v "${NUREC_HOST_ROOT}:/workdir/NuRec:ro" \
  nvcr.io/nvidia/nre/nre-ga:26.04 \
  serve-grpc \
  --artifact-glob "/workdir/NuRec/${SCENE_USDZ}" \
  --host 0.0.0.0 \
  --port 8080 \
  --health-port 8081 \
  --test-scenes-are-valid \
  --enable-editing-actors
```

`NUREC_HOST_ROOT` 是主机上的 NuRec 数据目录，挂载后在容器里对应 `/workdir/NuRec`。`SCENE_USDZ` 是相对于这个目录的 USDZ 路径；运行自己的场景时，将它换成实际文件。

`--test-scenes-are-valid` 会在服务上线前加载并检查场景。`--enable-editing-actors` 允许 StreetWorld 更新交通对象的位姿，必须开启；缺少它时，带对象更新的渲染请求会报 `INVALID_ARGUMENT`。`8081` 是健康检查端口，SimulatorInterface 连接的是 `8080`。

查看启动日志：

```bash
docker logs nurec-grpc
```

服务启动后，在安装了 StreetWorld 的 Python 环境中查询已加载的场景：

```bash
python - <<'PY'
import grpc
from submodules.nurec_interface.nre.grpc.protos import common_pb2, sensorsim_pb2_grpc

channel = grpc.insecure_channel("127.0.0.1:8080", options=(("grpc.enable_http_proxy", 0),))
stub = sensorsim_pb2_grpc.SensorsimServiceStub(channel)
print(list(stub.get_available_scenes(common_pb2.Empty(), timeout=5).scene_ids))
channel.close()
PY
```

服务端的场景 ID 是 `clipgt-<USDZ 文件名去掉扩展名>`。上面的示例应返回 `clipgt-7e11dcb8-7bce-4972-b998-8626857e92aa`。SimulatorInterface 会从本地 USDZ 文件名生成同一个 ID，因此本地数据与渲染服务必须使用同一场景；请求了未加载的场景会报 `NOT_FOUND`。

#### 启动 StreetWorld Environment Server

渲染服务就绪后，在 StreetWorld 环境中用 [env_server_scene_config.py](../../../streetworld/examples/env_server_scene_config.py) 启动仿真服务。场景列表写相对于 `25.07_release` 的目录，与上面加载的 USDZ 对应：

```bash
cat > nurec-scenes.txt <<'EOF'
Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa
EOF

python -m streetworld.examples.env_server_scene_config \
  --dataset nurec --scene-config nurec-scenes.txt \
  --nurec-grpc-host 127.0.0.1 --nurec-grpc-port 8080 \
  --nurec-grpc-timeout 600 \
  --host 127.0.0.1 --port 50052 \
  --web-host 127.0.0.1 --web-port 18080
```

也可以运行 [env_server_easydrive.py](../../../streetworld/examples/env_server_easydrive.py)，在终端选择 NuRec 和对应场景。两个入口都读取仓库下的 `data/processed/benchmark/NuRec/sample_set/25.07_release`，并加载 [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py) 中的相机拼图布局和导航设置。

AD policy 连接 `127.0.0.1:50052`；浏览器打开 `http://127.0.0.1:18080` 查看画面。客户端开始调用 `reset()`、`step()` 后，仿真才会运行。当前这两个入口的 NuRec 分支使用 EnvInputPolicy，`step()` 接收 `[steering, throttle_brake]`，例如 `[0.0, 0.2]` 表示直行并使用 20% 的油门。

NuRec 分支目前不应用 `--ad-policy-config`。接入输出轨迹的 AD policy 时，需要在创建环境的代码中将主车 Policy 改为 EnvInputILQRPolicy 或 EnvInputPIDPolicy，并让 `trajectory_dt` 与模型的轨迹采样间隔一致，设置方法见[配置示例](configuration.md#section-4-5)。

更换场景时，先结束 Environment Server，再删除渲染容器，然后用新的 `SCENE_USDZ` 重新启动，并修改场景列表：

```bash
docker rm -f nurec-grpc
```

#### 在代码中创建接口

自行创建 Environment 时，将下面的接口实例传给环境，调用方式见 [3.1](#section-3-1)。NuRec 渲染服务需要提前启动：

```python
from submodules.nurec_interface.simulator_interface import SimulatorInterface

simulator = SimulatorInterface(
    nurec_root="data/processed/benchmark/NuRec/sample_set/25.07_release",
    grpc_host="127.0.0.1",
    grpc_port=8080,
    grpc_timeout_s=600.0,
)
```

`nurec_root` 指向本地 release 目录，`grpc_host`、`grpc_port` 指向 NuRec 渲染服务，`grpc_timeout_s` 的单位为秒。`resolution_scale` 控制图像分辨率缩放，默认 `1.0`。创建环境时还应合并 [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py)，使交互界面的相机布局与 NuRec 的相机名一致。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一章：2. 整体结构](architecture.md) · [下一章：4. 配置系统](configuration.md)
