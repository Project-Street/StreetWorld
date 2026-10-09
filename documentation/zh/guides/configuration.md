<a id="chapter-4"></a>

# 4. 配置系统

[English](../../en/guides/configuration.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一章：3. 接口约定](interfaces.md) · [下一章：5. 组件参考](../reference/index.md)

- [4.1 Config 的用途与使用](#section-4-1)
- [4.2 配置层级与优先级](#section-4-2)
- [4.3 Environment 与 Agent 的常用参数](#section-4-3)
- [4.4 Observer 配置](#section-4-4)
- [4.5 Policy 与 Controller 配置](#section-4-5)

<a id="section-4-1"></a>

## 4.1 Config 的用途与使用

测试不同驾驶策略时，需要选择场景、调整仿真步长，还可能更换主车的 Policy 或相机设置。StreetWorld 用 [Config](../../../streetworld/config.py) 保存这些设置，在创建 Environment 时传入。环境再将主车、周边对象和观测各自的配置交给对应组件。

Config 是保存嵌套配置的 Python 类。它接收一个字典，支持深复制和配置合并。`Config()` 类本身只保存传入的内容，不添加环境默认值。

### 创建与传入环境

例如，选择 nuScenes 场景 `0007`，并关闭主车倒车功能：

```python
from streetworld.config import Config

cfg = Config({
    "scene_ids": ["0007"],
    "actor_config": {
        "controller_config": {"enable_reverse": False},
    },
})
```

创建环境时，将 `cfg` 作为 `config` 参数传入，例如 `ScenarioEnv(simulator, config=cfg)`；`simulator` 是[第三章](interfaces.md#section-3-2)中的 SimulatorInterface 实例。完整的环境调用示例见 [3.1](interfaces.md#section-3-1)。

### 访问、修改与复制

Config 支持字典和属性两种访问方式。下面修改场景列表，并重新开启倒车：

```python
cfg["scene_ids"] = ["0007", "0008"]
cfg.actor_config.controller_config.enable_reverse = True
```

需要为另一轮测试单独修改配置时，用 `copy()` 深复制一份；`to_dict()` 将最外层容器转换成普通字典：

```python
independent = cfg.copy()
values = cfg.to_dict()
```

`to_dict()` 不复制嵌套内容，嵌套值可能仍是 ConfigDict。访问不存在的字段时，字典方式抛出 KeyError，属性方式抛出 AttributeError。

### 合并配置：merge_from()

运行脚本经常需要在一份已有配置上修改个别字段，例如保留场景和相机设置，只换主车的控制参数。`merge_from()` 将新设置写入已有 Config：同名字段使用新值，其余字段保留。

嵌套字典逐层合并，也可以用点分隔的键直接指定内部字段。下面两种写法都关闭主车倒车，保留 `scene_ids`：

```python
cfg.merge_from({"actor_config": {"controller_config": {"enable_reverse": False}}})
cfg.merge_from({"actor_config.controller_config.enable_reverse": False})
```

列表和数值直接替换。例如，`image_layout` 设置交互环境的画面布局，下面将它改成只显示前视相机：

```python
cfg.merge_from({"image_layout": [["FRONT"]]})
```

`replace_keys` 可以指定整项替换的字段，例如 `replace_keys=["actor_config"]` 会替换整个主车配置，未提供的字段不再保留，因此需要传入完整的主车配置。这个参数只影响当前层，递归合并不会继续传递它。

`allow_list_keys=True` 允许用数字字符串访问列表索引。索引等于列表长度时追加，越界时抛出 KeyError。已有索引的赋值尚未实现，修改它时直接给列表赋值，或替换整个列表。

### 从文件读取

普通数值、字符串和列表可以保存在 JSON 或 YAML 文件中：

```python
cfg = Config.fromfile("simulation.yaml")
```

Observation、Policy、Controller 等类对象在 Python 脚本中设置，见[配置层级示例](#section-4-2)。`Config.fromfile()` 当前读取 `.py` 文件会在语法检查时抛出 `NameError`。完整方法与实现限制见 [Config 参考](../reference/config.md)。

<a id="section-4-2"></a>

## 4.2 配置层级与优先级

下面配置主车使用 iLQR 跟踪轨迹，每个环境步模拟 `0.5 s`，并关闭倒车。先取得 ScenarioEnv 的默认配置，再写入本次测试的设置：

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.policy.env_input_ilqr_policy import EnvInputILQRPolicy

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "scene_ids": ["0007"],
    "decision_repeat": 25,
    "actor_config": {
        "policy": EnvInputILQRPolicy,
        "policy_config": {
            "smooth": False,
            "max_acceleration": 3.0,
            "trajectory_dt": 0.5,
            "control_dt": 0.5,
        },
        "controller_config": {"enable_reverse": False},
    },
})
```

顶层的 `scene_ids` 和 `decision_repeat` 是环境参数，分别指定运行哪个场景、每步推进多少个物理小步。`actor_config` 是主车 AgentManager 的配置：`policy` 指定策略类，`policy_config` 传给这个策略，`controller_config` 传给车辆对象。`observer` 和 `observer_config` 同样分别指定观测类和它的参数，本例沿用默认值。

周边交通对象使用 `participant_config`，与主车的配置层级相同。例如，主车可以用 EnvInputILQRPolicy 跟踪模型轨迹，周边车辆仍用默认 ReplayPolicy 按记录轨迹回放。不同对象的 Policy、Observer 和 Controller 可以分别选择。

### 默认值和运行配置

基础参数来自 [BASE_DEFAULT_CONFIG](../../../streetworld/configs/default_config.py)。ScenarioEnv 在此基础上加入 [SCENARIO_ENV_CONFIG](../../../streetworld/configs/default_scenario_config.py)；交互环境再加入 [INTERACTIVE_ENV_CONFIG](../../../streetworld/envs/interactive_env.py)。构造环境时，最后合并调用者传入的配置，同名字段以传入值为准。

例如，上例没有修改观测设置，主车就使用默认 AssemblyObservation；`decision_repeat` 则由默认的 `5` 改为 `25`。调用 `default_config()` 得到类的默认值。运行时用 `env.config` 查看当前配置；加载场景后，它返回 ScenarioDataManager 保存的场景配置副本。

### 启动脚本中的合并顺序

Environment Server 的 nuScenes / Waymo 分支依次合并 [DEFAULT_POLICY_CONFIG_0_5S](../../../streetworld/configs/default_policy_config.py)、`--ad-policy-config` 指定的模型配置和命令行设置，再将结果传入环境。后合并的同名字段覆盖前面的值，例如 `--web-port` 会覆盖配置中的网页端口。

NuRec 分支先根据命令行生成环境配置，再合并 [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py)，设置 NuRec 的相机布局和导航方式。这个分支不应用 `--ad-policy-config`，默认使用原始控制输入 Policy，运行步骤见[NuRec 示例](interfaces.md#nurec)。

<a id="section-4-3"></a>

## 4.3 Environment 与 Agent 的常用参数

环境参数控制整个场景怎样运行；Agent 参数控制单个对象。下表使用基础环境的默认值，启动脚本或模型配置可以覆盖它们。

### Environment

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | 必填 | 要运行的场景 ID；格式取决于数据集，见[场景目录](interfaces.md#scene-files) |
| `random_scenario` | bool | `True` | 非评测模式且没有显式指定场景时，随机选择场景；`False` 按列表顺序循环 |
| `physics_world_step_size` | 数值，微秒 | `20_000` | 每个物理小步推进的仿真时间，即 `0.02 s` |
| `decision_repeat` | int，物理步数 | `5` | 每个环境步包含的物理小步数；默认每步模拟 `0.1 s` |
| `max_step` | int 或 None，环境步数 | `None` | 一轮测试的环境步数上限；`None` 不设置这一层的限制，主车仍受自己的 `max_step` 限制 |
| `async_mode` | bool | `False` | 是否在等待驾驶输入期间继续仿真，见[同步与异步](architecture.md#section-2-6) |

### Agent

主车使用 `actor_config`，周边对象使用 `participant_config`。两者都由 AgentManager 读取；下面列主车路径：

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.max_step` | int 或 None，环境步数 | `10_000` | 主车运行步数上限；达到上限后结束本轮 |
| `actor_config.check_crash` | bool | `True` | 是否检测该对象的碰撞；主车碰撞时会产生对应的结束原因 |
| `actor_config.warmup_step` | int 或 None，环境步数 | `None` | 设置数值后，前若干步由 ExpertILQRPolicy 跟随记录轨迹，之后切换到配置的 Policy |

完整字段见 [Environment](../reference/environment.md) 和 [AgentManager](../reference/manager.md#api-4-3)。结束状态见 [AgentState](interfaces.md#agent-states)。

<a id="section-4-4"></a>

## 4.4 Observer 配置

驾驶程序通常既要读取相机图像，也要知道主车速度和导航目标。这些数据分别由对应的 Observation 生成。`actor_config.observer` 选择主车的观测类，`actor_config.observer_config` 设置它的参数。

主车默认使用 [AssemblyObservation](../reference/observation.md#api-5-4)，负责把多个 Observation 组合起来。它按照配置创建子观测，获取观测时分别调用这些实例，再以配置中的名称为键组成一个字典。这样，驾驶程序一次调用 `reset()` 或 `step()`，就能取得图像、导航、车辆状态和周边对象；每种观测仍可以单独设置参数。

### 默认观测配置

下面展开 [BASE_DEFAULT_CONFIG](../../../streetworld/configs/default_config.py) 中的完整主车观测配置：

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.gaussian_obs import GaussianObservation
from streetworld.obs.navigation_obs import NavigationObservation
from streetworld.obs.state_obs import StateObservation
from streetworld.obs.surrounding_obs import SurroundingObservation

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "actor_config": {
        "observer": AssemblyObservation,
        "observer_config": {
            "gaussian": {
                "observer_class": GaussianObservation,
                "clip_rgb": False,
            },
            "navigation": {
                "observer_class": NavigationObservation,
                "navigating_type": "snap_lane",
                "forecast_type": "distance",
                "forecast_value": 20.0,
                "lateral_offset": 2.0,
                "snap_lane_interval": 2.0,
                "current_lane_max_dist": 2.25,
            },
            "states": {
                "observer_class": StateObservation,
            },
            "surrounding": {
                "observer_class": SurroundingObservation,
                "coordinate_mode": "agent",
                "ignore_dist": None,
            },
        },
    },
})
```

`gaussian`、`navigation`、`states`、`surrounding` 是子观测的名称，也就是返回字典中的四个键。每项的 `observer_class` 指定要创建的类，其余字段传给这个类。例如，`clip_rgb` 只传给 GaussianObservation，`coordinate_mode` 只传给 SurroundingObservation。

用这份配置创建环境后，从 `reset()` 的返回值中读取它们：

```python
observation, info = env.reset()
images = observation["gaussian"]["image"]
speed = observation["states"]["ego_velo"]
target = observation["navigation"]["target_waypoint"]
objects = observation["surrounding"]
```

`images` 是按相机名索引的图像字典，本地每张图像的形状为 `(1, H, W, 3)`；`speed` 是主车速度，单位为 `m/s`；`target` 是世界坐标中的二维导航目标，单位为米；`objects` 按周边对象 ID 索引，默认将位姿和速度转换到主车坐标系。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer` | 类对象 | `AssemblyObservation` | 创建并组合子观测 |
| `actor_config.observer_config.<观测名>.observer_class` | 类对象 | 各观测对应的类 | 指定该子项使用的观测类；每个子项必须提供 |
| `actor_config.observer_config.gaussian.clip_rgb` | bool | `False` | `False` 输出 `uint8` RGB，像素值为 0–255；`True` 使用 `float32`，当前代码不除以 255；gRPC 图像传输使用 `False` |
| `actor_config.observer_config.gaussian.cameras` | dict | `{}` | 空字典或未提供时，使用场景记录的全部相机；非空字典指定本次使用的全部相机 |
| `actor_config.observer_config.navigation.navigating_type` | str | `snap_lane` | 将记录路径投影到地图车道；`expert_following` 沿记录路径，`lane_following` 沿地图车道 |
| `actor_config.observer_config.navigation.forecast_type` | str | `distance` | 导航目标的查询方式；`distance` 按距离向前查询，`step` 按路径点索引向前查询 |
| `actor_config.observer_config.navigation.forecast_value` | 数值，米或点数 | `20.0` | 默认向前查询约 20 米；`step` 模式下表示向前查询的路径点数 |
| `actor_config.observer_config.navigation.path_interval` | float 或 None，米或秒 | `None` | 路径重采样间隔；`distance` 按米，`step` 模式下记录路径按秒重采样 |
| `actor_config.observer_config.navigation.lateral_offset` | float，米 | `2.0` | 导航目标在主车坐标系中的横向偏移超过该值时，产生左转或右转提示 |
| `actor_config.observer_config.navigation.current_lane_max_dist` | float，米 | `2.25` | 出生车道与路径点投影时的地图查询半径 |
| `actor_config.observer_config.navigation.snap_lane_interval` | float | `2.0` | 当前代码未读取；路径采样使用 `path_interval` |
| `actor_config.observer_config.surrounding.coordinate_mode` | str | `agent` | `agent` 输出主车坐标系中的对象位姿、线速度和线加速度；`world` 输出世界坐标系中的值 |
| `actor_config.observer_config.surrounding.ignore_dist` | float 或 None，米 | `None` | 只输出距离主车不超过该值的对象；默认不按距离过滤 |

### 默认轨迹配置中的观测设置

[DEFAULT_POLICY_CONFIG_0_5S](../../../streetworld/configs/default_policy_config.py) 用于接收模型轨迹，合并到环境默认配置后，仍保留上面的四种观测：

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

这份配置将 `navigation.forecast_type` 改为 `step`、`forecast_value` 改为 `6`，并设置 `path_interval=0.5`，按 0.5 秒间隔重采样记录路径后查询前方第六个路径点。相机没有单独覆盖，GaussianObservation 继续使用场景的相机参数。`project_trajectory_on_camera="FRONT"` 选择在网页的前视画面上叠加轨迹，不修改相机参数。

### 设置 GaussianObservation 的相机

需要改变相机的分辨率、焦距或安装位置时，设置 `gaussian.cameras`。例如，仓库的 [TRANSFUSER_CONFIG](../../../streetworld/configs/transfuser_config.py) 设置了三台前视相机：

```python
cfg.merge_from({
    "actor_config.observer_config.gaussian.cameras": {
        "FRONT_LEFT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (60.0, 0.0, 0.0),
        },
        "FRONT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (0.0, 0.0, 0.0),
        },
        "FRONT_RIGHT": {
            "H": 480, "W": 960, "focal": 760.0,
            "offset": (1.3, 0.0, 2.3), "hpr": (-60.0, 0.0, 0.0),
        },
    },
    "image_layout": [["FRONT_LEFT", "FRONT", "FRONT_RIGHT"]],
})
```

三台相机都在车辆坐标系的 `(1.3, 0.0, 2.3) m` 处，每张图像为 `480 × 960` 像素；相机分别朝向左前方、正前方和右前方。设置非空 `cameras` 后，GaussianObservation 只渲染其中列出的相机。这个例子因此只输出三台前视相机。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer_config.gaussian.cameras.<相机名>.H` | int，像素 | 自定义相机时必填 | 图像高度 |
| `actor_config.observer_config.gaussian.cameras.<相机名>.W` | int，像素 | 自定义相机时必填 | 图像宽度 |
| `actor_config.observer_config.gaussian.cameras.<相机名>.focal` | float，像素 | 自定义相机时必填 | 水平与垂直焦距；主点设为图像中心 |
| `actor_config.observer_config.gaussian.cameras.<相机名>.hpr` | 三元素序列，度 | 自定义相机时必填 | 航向、俯仰、滚转；零值表示相机朝车辆前方，正航向朝左 |
| `actor_config.observer_config.gaussian.cameras.<相机名>.offset` | 三元素序列，米 | 自定义相机时必填 | 相机在车辆坐标系中的位置，X 向前、Y 向左、Z 向上 |

`image_layout` 只设置网页怎样拼接这些图像，不改变观测输出的相机。布局中的名称要与实际相机一致。同批 ST Renderer 相机使用相同的 H、W；NuRec 的鱼眼相机需要额外标定，沿用场景参数可以保留这些数据，见[相机接口](interfaces.md#render)。

各子观测的完整输出和 API 见 [Observation 参考](../reference/observation.md)。

<a id="section-4-5"></a>

## 4.5 Policy 与 Controller 配置

驾驶程序向 `step()` 传入动作，Policy 将动作变成控制或移动指令，Controller 执行这些指令。基础配置中，主车使用 EnvInputPolicy，接收转向和油门/制动；周边对象使用 ReplayPolicy，按记录轨迹回放。

### EnvInputILQRPolicy：跟踪模型轨迹

模型输出未来的 `(x, y)` 轨迹时，用 EnvInputILQRPolicy 计算转向和油门/制动。`actor_config.policy` 选择策略类，`actor_config.policy_config` 设置策略参数。输入点位于主车坐标系，格式见 [action](interfaces.md#action-format)。

从仓库的默认轨迹配置开始：

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg = ScenarioEnv.default_config()
cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

这份配置将主车 Policy 设为 EnvInputILQRPolicy，并提供它需要的参数。接入模型时，需要先核对两个时间间隔：

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.trajectory_dt` | float，秒 | 该轨迹配置为 `0.5` | 模型预测点的采样间隔；第一点对应当前时间之后一个间隔的位置 |
| `actor_config.policy_config.control_dt` | float，秒 | 该轨迹配置为 `0.5` | iLQR 更新车辆控制的周期；必须为物理步长的整数倍，当前实现还要求与环境步时长相等 |

一个环境步的时长是 `physics_world_step_size × decision_repeat / 1_000_000` 秒。默认物理步长为 `0.02 s`，这份轨迹配置使用 `decision_repeat=25`，所以每步模拟 `0.5 s`，对应 `control_dt=0.5`。

`trajectory_dt` 由模型输出决定，可以与控制周期不同。例如，模型仍按 `0.5 s` 间隔输出轨迹点，但希望每次 `step()` 只推进 `0.1 s`，就保留 `trajectory_dt=0.5`，一起修改环境步和控制周期：

```python
cfg.merge_from({
    "decision_repeat": 5,
    "actor_config.policy_config.control_dt": 0.1,
})
```

仓库的 `DEFAULT_POLICY_CONFIG_0_1S` 使用的就是这组时间设置。EnvInputILQRPolicy 的完整配置和 API 见 [Policy 参考](../reference/policy.md#api-6-4)。

### Controller：执行车辆控制

Controller 是场景中实际运动的对象，例如车辆、行人或骑行者。`actor_config.controller` 指定主车对象的类，`actor_config.controller_config` 设置尺寸、动力和碰撞检查等参数。周边对象的类型和尺寸由场景元数据补充。

主车默认使用 DefaultVehicle。下面关闭倒车，并将车辆水平速度变化的加速度上限设为 `3 m/s²`：

```python
cfg.merge_from({
    "actor_config.controller_config.enable_reverse": False,
    "actor_config.controller_config.max_acceleration": 3.0,
})
```

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.controller` | 类对象 | `DefaultVehicle` | 主车的仿真对象类；具体车型决定底盘、质量、轮胎等参数 |
| `actor_config.controller_config.size` | `[长, 宽, 高]` 或 None，米 | `None` | 设置主车尺寸；`None` 使用车型默认尺寸 |
| `actor_config.controller_config.enable_reverse` | bool | `True` | 是否允许负油门向后驱动；`False` 时负输入用于制动 |
| `actor_config.controller_config.spawn_velocity` | bool | `True` | 是否按记录的初始速度和角速度创建车辆 |
| `actor_config.controller_config.max_acceleration` | float，m/s² | 主车 `15.0` | 限制车辆水平速度变化；周边对象默认不提供此项 |
| `actor_config.controller_config.max_steering` | 数值，度 | 由车型采样 | 转向控制量为 `1` 或 `-1` 时对应的最大车轮转角 |
| `actor_config.controller_config.check_crash_world` | bool | `False` | 是否检查车辆与背景、地形的碰撞；还需开启 Agent 的 `check_crash` |

Policy 中的 `max_acceleration` 限制轨迹求解，Controller 中的同名字段限制车辆运动时的速度变化，两者需要分别设置。各对象的完整配置和车型参数见 [Object / Controller 参考](../reference/object.md)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一章：3. 接口约定](interfaces.md) · [下一章：5. 组件参考](../reference/index.md)
