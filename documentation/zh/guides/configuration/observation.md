<a id="section-4-4"></a>

# 4.4 Observer 配置

[English](../../../en/guides/configuration/observation.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.3 Environment 与 Agent 的常用参数](environment-agent.md) · [下一页：4.5 Policy 与 Controller 配置](policy-controller.md)

驾驶程序通常既要读取相机图像，也要知道主车速度和导航目标。这些数据分别由对应的 Observation 生成。`actor_config.observer` 选择主车的观测类，`actor_config.observer_config` 设置它的参数。

主车默认使用 [AssemblyObservation](../../reference/observation.md#api-5-4)，负责把多个 Observation 组合起来。它按照配置创建子观测，获取观测时分别调用这些实例，再以配置中的名称为键组成一个字典。这样，驾驶程序一次调用 `reset()` 或 `step()`，就能取得图像、导航、车辆状态和周边对象；每种观测仍可以单独设置参数。

## 默认观测配置

下面展开 [BASE_DEFAULT_CONFIG](../../../../streetworld/configs/default_config.py) 中的完整主车观测配置：

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

## 默认轨迹配置中的观测设置

[DEFAULT_POLICY_CONFIG_0_5S](../../../../streetworld/configs/default_policy_config.py) 用于接收模型轨迹，合并到环境默认配置后，仍保留上面的四种观测：

```python
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

这份配置将 `navigation.forecast_type` 改为 `step`、`forecast_value` 改为 `6`，并设置 `path_interval=0.5`，按 0.5 秒间隔重采样记录路径后查询前方第六个路径点。相机没有单独覆盖，GaussianObservation 继续使用场景的相机参数。`project_trajectory_on_camera="FRONT"` 选择在网页的前视画面上叠加轨迹，不修改相机参数。

## 设置 GaussianObservation 的相机

需要改变相机的分辨率、焦距或安装位置时，设置 `gaussian.cameras`。例如，仓库的 [TRANSFUSER_CONFIG](../../../../streetworld/configs/transfuser_config.py) 设置了三台前视相机：

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

`image_layout` 只设置网页怎样拼接这些图像，不改变观测输出的相机。布局中的名称要与实际相机一致。同批 ST Renderer 相机使用相同的 H、W；NuRec 的鱼眼相机需要额外标定，沿用场景参数可以保留这些数据，见[相机接口](../simulator-interface.md#render)。

各子观测的完整输出和 API 见 [Observation 参考](../../reference/observation.md)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.3 Environment 与 Agent 的常用参数](environment-agent.md) · [下一页：4.5 Policy 与 Controller 配置](policy-controller.md)
