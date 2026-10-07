# 5.3 Observation

[English](../../en/reference/observation.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.2 Manager](manager.md) · [下一页：5.4 Policy](policy.md)

配置字段和示例变量见[组件参考目录](index.md)。

本页目录

- [5.3.1 BaseObservation](#api-5-1)
- [5.3.2 DummyObservation](#api-5-2)
- [5.3.3 DefaultObservation](#api-5-3)
- [5.3.4 AssemblyObservation](#api-5-4)
- [5.3.5 GaussianObservation](#api-5-5)
- [5.3.6 StateObservation](#api-5-6)
- [5.3.7 NavigationObservation](#api-5-7)
- [5.3.8 SurroundingObservation](#api-5-8)
- [5.3.9 CollisionBodyObservation](#api-5-9)

<a id="api-5-1"></a>

## 5.3.1 BaseObservation

### 职责与创建方式

BaseObservation 是将仿真数据转换为 Agent 输入的观测基类。相机图像、车辆状态和导航信息需要不同的采集方式；它规定共同的观测接口，让 AgentManager 可以按相同流程调用这些组件，也方便用户添加新的观测类型。

子类实现 `observe()` 和 `observation_space`，并在 `reset()` 中接收所需的场景数据。AgentManager 先调用 `reset()` 传入 Controller 等对象，再调用 `observe()` 采集观测；基类构造时保存配置副本。

源码：[streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py)。

### 配置

子类通过 config 设置所需字段，reset 接收场景和对象信息。BaseObservation 不规定业务配置。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config)` | `config`：组件配置字典 | None | 首次初始化时深复制配置。 | — |
| 实例方法<br>`observe(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | 由子类定义 | 观测采样接口。 | 基类抛 NotImplementedError。 |
| 实例方法<br>`reset(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | None | 接收场景上下文的扩展钩子；基类不执行操作。 | — |
| 实例方法<br>`destroy(self)` | — | None | 资源清理扩展钩子；基类不执行操作。 | — |
| 属性 getter<br>`observation_space(self)` | — | 由子类定义 | 观测空间接口。 | 基类抛 NotImplementedError。 |

### 使用示例

```python
import gymnasium as gym
from streetworld.obs.observation_base import BaseObservation

class SpeedObservation(BaseObservation):
    def reset(self, controller, **kwargs):
        self.controller = controller

    def observe(self):
        return float(self.controller.speed)

    @property
    def observation_space(self):
        return gym.spaces.Box(0.0, float("inf"), shape=())
```

<a id="api-5-2"></a>

## 5.3.2 DummyObservation

### 职责与创建方式

DummyObservation 是供轨迹回放对象使用的空观测组件。回放对象从记录中取得运动状态，仍需满足 AgentManager 的 Observer 调用接口；DummyObservation 用空字典完成这一接口，适合无需采集观测的参与者。

BaseEnv 为行人和骑行者配置 DummyObservation，并与 ReplayPolicy 配合使用。也可以直接构造实例；构造时会记录一条警告，`observe()` 返回空字典。

源码：[streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py)。

### 配置

无需额外配置。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config=None)` | `config`：组件配置字典 | None | 初始化空观测组件。同时记录 DummyObservation 警告。 | — |
| 实例方法<br>`observe(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 每次返回 {}。 | — |
| 属性 getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | 声明 [0,1] 的一维 Box。 | observe 返回空字典，与该空间声明不一致。 |

### 使用示例

```python
from streetworld.obs.observation_base import DummyObservation

observer = DummyObservation({})
print(observer.observe())
```

<a id="api-5-3"></a>

## 5.3.3 DefaultObservation

### 职责与创建方式

DefaultObservation 是默认周边车辆使用的空观测组件。默认 ReplayPolicy 按记录轨迹更新车辆，使用空观测即可让这些车辆沿用 AgentManager 的调用流程。

它由参与者配置中的 `observer` 指定，通常在 AgentManager 首次 `reset()` 时创建，`observe()` 返回空字典。与 [DummyObservation](#api-5-2) 相比，它构造时不记录空观测警告。

源码：[streetworld/obs/observation_base.py](../../../streetworld/obs/observation_base.py)。

### 配置

无需额外配置。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config=None)` | `config`：组件配置字典 | None | 初始化空观测组件。config 为 None 时使用空字典。 | — |
| 实例方法<br>`observe(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 每次返回 {}。 | — |
| 属性 getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | 声明 [0,1] 的一维 Box。 | observe 返回空字典，与该空间声明不一致。 |

### 使用示例

```python
from streetworld.obs.observation_base import DefaultObservation

observer = DefaultObservation({})
print(observer.observe())
```

<a id="api-5-4"></a>

## 5.3.4 AssemblyObservation

### 职责与创建方式

AssemblyObservation 是组合多个 Observer 的观测组件。一个 AD policy 往往同时需要相机、车辆状态和导航输入，它按配置将各类观测组成一个字典，用户可以增删或替换其中的 Observer，而保留其他观测的采集方式。

构造时按 `observer_class` 创建子 Observer，`observe()` 将各自的结果放到对应名称下，例如 `gaussian`、`states` 和 `navigation`。`reset()` 向所有子 Observer 传入相同的场景参数；自定义 Observer 可用 `**kwargs` 接收未使用的参数。

源码：[streetworld/obs/assembly_obs.py](../../../streetworld/obs/assembly_obs.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer` | Observation 类 | `AssemblyObservation` | 选择组合观测。 |
| `actor_config.observer_config.<名称>.observer_class` | Observation 类 | `必填` | 创建该子 Observer；配置键 <名称> 同时是输出字典键。 |
| `actor_config.observer_config.<名称>.<字段>` | 由子 Observer 定义 | `见各子类` | 去除 observer_class 后，剩余配置传给子 Observer 构造函数。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config: Dict[str, Any])` | `config`：组件配置字典 | None | 逐项创建子 Observer，并保存名称与类的对应关系。 | 子项缺少 observer_class 时抛 ValueError；不接受 obsever_class 拼写。 |
| 实例方法<br>`reset(self, **kwargs)` | `**kwargs`：关键字参数 | None | 将所有 kwargs 原样传给每个子 Observer.reset。 | 没有按参数签名过滤 kwargs；子类不接受的参数会抛 TypeError。 |
| 实例方法<br>`observe(self)` | — | dict[str, observation] | 逐项调用 observe，将结果按配置名称返回。 | — |
| 实例方法<br>`destroy(self)` | — | None | 销毁各子 Observer，清空容器。 | — |
| 属性 getter<br>`observation_space(self)` | — | gym.spaces.Dict | 按名称组合空间；子 Observer 返回普通空间字典时再包装为 gym.spaces.Dict。 | 不校验各子空间与实际输出是否一致。 |

### 使用示例

```python
from streetworld.obs.assembly_obs import AssemblyObservation
from streetworld.obs.observation_base import DefaultObservation

observer = AssemblyObservation({"empty": {"observer_class": DefaultObservation}})
observer.reset()
assert observer.observe() == {"empty": {}}
observer.destroy()
```

<a id="api-5-5"></a>

## 5.3.5 GaussianObservation

### 职责与创建方式

GaussianObservation 是为视觉 AD policy 生成相机输入的观测组件。主车执行动作后会改变位姿，它据此更新相机外参并渲染图像，使下一次决策使用车辆当前视角的观测，形成视觉输入与车辆运动之间的闭环。

AgentManager 在 `reset()` 时传入 Controller、渲染函数和相机参数；`observe()` 调用 SimulatorInterface 的 `render()`，返回图像与相机信息。默认相机来自场景元数据，设置 `cameras` 后使用配置的相机。

源码：[streetworld/obs/gaussian_obs.py](../../../streetworld/obs/gaussian_obs.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer_config.gaussian.clip_rgb` | bool | `False（环境默认；类构造必填）` | 选择图像缓存 dtype 和空间范围；True 将缓存改为 float32，但不会把 RGB 除以 255。 |
| `actor_config.observer_config.gaussian.cameras` | dict | `{}` | 为空时使用元数据；非空时以这组相机替换元数据相机。 |
| `actor_config.observer_config.gaussian.cameras.<相机>.H` | int，px | `必填` | 图像高度。 |
| `actor_config.observer_config.gaussian.cameras.<相机>.W` | int，px | `必填` | 图像宽度。 |
| `actor_config.observer_config.gaussian.cameras.<相机>.focal` | float，px | `必填` | 焦距，K 中 fx、fy 取相同值，主点位于图像中心。 |
| `actor_config.observer_config.gaussian.cameras.<相机>.offset` | 三元素序列，m | `必填` | 相机中心在车辆坐标系中的位置。 |
| `actor_config.observer_config.gaussian.cameras.<相机>.hpr` | 三元素序列，度 | `必填` | heading/pitch/roll，使用 ZYX 旋转构建外参。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config)` | `config`：组件配置字典 | None | 保存 clip_rgb 和配置相机。 | 缺少 clip_rgb 抛 KeyError。 |
| 实例方法<br>`reset(self, controller, render_fn, camera_params, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`render_fn`：SimulatorInterface.render 或同签名渲染回调；`camera_params`：场景元数据中的相机参数字典；`**kwargs`：关键字参数 | None | 建立相机内外参、批量 render 参数及每台相机的图像缓存。 | 元数据缺少 K/H/W/ego2camera 或配置相机缺少必填参数时抛 ValueError。 |
| 实例方法<br>`an_observation_shape(self, h, w)` | `h`：图像高度，像素；`w`：图像宽度，像素 | (1, h, w, 3) | 返回含单帧维的 RGB 形状。 | — |
| 实例方法<br>`observe(self)` | — | {'camera_info': dict, 'image': dict} | 用当前主车 transform 计算世界到相机的变换，调用后端 render，并更新图像与相机参数。 | 须先 reset；图像沿用内部缓存，需保留历史帧时由调用方复制。 |
| 实例方法<br>`destroy(self)` | — | None | 释放图像缓存引用。 | 渲染后端资源由 Environment.close 处理。 |
| 属性 getter<br>`observation_space(self)` | — | dict[str, Box] | 每台相机声明一个图像空间；clip_rgb=False 时为 uint8 [0,255]。 | 仅包含图像，没有 camera_info；clip_rgb=True 声明 [0,1] 但未归一化实际图像。 |

image 保存 `{相机名: ndarray(1,H,W,3)}`，camera_info 保存 `{相机名: {K, H, W, ego2camera, extra?}}`。K 为 3×3 内参，ego2camera 为 4×4 外参。元数据中的 extra 会传给渲染后端，例如 NuRec 的 logical_id；手动配置相机时只生成 K、H、W 和 ego2camera。

通过 gRPC 传输图像时，服务端设置 clip_rgb=False，以 uint8 RGB 字节输出。同批 ST Renderer 相机使用相同的 H、W，见 [ST Renderer 接口约定](../guides/simulator-interface.md#render)。

### 使用示例

```python
# cfg 是环境完整配置；在构造环境前修改。
cfg.merge_from({"actor_config.observer_config.gaussian.cameras": {
    "FRONT": {"H": 480, "W": 960, "focal": 760.0,
              "offset": [1.3, 0.0, 2.3], "hpr": [0.0, 0.0, 0.0]},
}})
cfg.merge_from({"image_layout": [["FRONT"]]})
```

<a id="api-5-6"></a>

## 5.3.6 StateObservation

### 职责与创建方式

StateObservation 是提供 Agent 自身运动状态的观测组件。AD policy 需要当前位置、速度与转向等信息来作出决策，奖励和评测指标也需要这些状态；它将物理对象的状态整理为可直接读取的观测字段。

`reset()` 时接收 Controller 与 `collector`，`observe()` 从收集结果中找到当前 Controller，读取位姿、速度、加速度、转向和车道信息。默认配置将它放在 AssemblyObservation 的 `states` 字段下。

源码：[streetworld/obs/state_obs.py](../../../streetworld/obs/state_obs.py)。

### 配置

reset 时传入 Controller 和 collector，无需额外配置。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config=None)` | `config`：组件配置字典 | None | 初始化 Controller/collector 引用和空间声明常量。 | — |
| 实例方法<br>`reset(self, controller, collector, seed=None, **kwargs)` | `controller`：当前 Agent 的 Controller 实例；`collector`：无参回调，返回对象 ID 到基础状态的字典；`seed`：随机种子；None 使用调用方或环境的随机状态；`**kwargs`：关键字参数 | None | 保存 Controller 与对象采集回调。 | seed 未使用。 |
| 实例方法<br>`observe(self)` | — | dict | 采集主车状态；字段、单位和形状见下表。 | collector 必须包含当前 Controller，且 Controller 提供车辆转向/加速度方法；缺失时会报错。 |
| 实例方法<br>`destroy(self)` | — | None | 清空 Controller 与 collector 引用。 | — |
| 属性 getter<br>`observation_space(self)` | — | gym.spaces.Dict | 声明 position(2)、velocity(2) 和 heading_theta 标量。 | 实际输出采用 ego_pos、linear_velocity 等字段，与该空间声明不一致。 |

| 字段 | 类型、单位与含义 |
| --- | --- |
| ego_pos | float32 (3,)，主车世界坐标，m |
| ego_rot | float32 (3,)，旋转矩阵转换为 XYZ 欧拉角，rad |
| heading_theta | float，水平朝向，rad |
| ego_steer | float，归一化转向 × 最大轮转角，rad |
| linear_velocity | float32 (3,)，世界坐标线速度，m/s |
| ego_velo | float，水平速度模长，m/s |
| linear_acceleration | float32 (3,)，前两项来自 Controller.get_longitudinal_acceleration，第三项为 0 |
| accelerate | float32 (3,)，Bullet 总力除以质量得到的世界坐标加速度，m/s² |
| angular_velocity | float32 (3,)，只有 Z 分量为偏航角速度，rad/s |
| angular_acceleration | float32 (3,)，只有 Z 分量为偏航角加速度，rad/s² |
| current_lane | 本地 RoadLane 对象或 None；gRPC 传输后对象变为字符串 |

get_longitudinal_acceleration 将水平加速度与 heading 逐分量相乘，返回两元素向量，没有计算纵向加速度的点积标量。

### 使用示例

```python
# observation 来自 env.reset 或 env.step。
states = observation["states"]
print(states["ego_pos"], states["ego_velo"])
print(states["heading_theta"], states["ego_steer"])
```

<a id="api-5-7"></a>

## 5.3.7 NavigationObservation

### 职责与创建方式

NavigationObservation 是提供行驶路线与目标点的观测组件。相机和车辆状态不能单独确定任务要求的路线，它为 AD policy 提供路径、前方目标点和转向提示，也为路径奖励与行驶进度计算提供参考。

`reset()` 时根据配置从记录轨迹、地图车道或投影到车道中心的记录轨迹生成路径；`observe()` 根据当前车辆位置更新目标点与转向提示。AgentManager 负责传入 Controller、记录状态和地图，路径生成中的随机选择由 Randomizable 管理。

源码：[streetworld/obs/navigation_obs.py](../../../streetworld/obs/navigation_obs.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer_config.navigation.navigating_type` | str | `snap_lane（环境）；expert_following（类）` | expert_following、lane_following 或 snap_lane。 |
| `actor_config.observer_config.navigation.forecast_type` | str | `distance` | distance 按米向前查询；step 按路径点索引向前查询。 |
| `actor_config.observer_config.navigation.forecast_value` | 数值，m 或点数 | `20.0` | 决定目标点向前查询量；默认轨迹 preset 改为 step/6。 |
| `actor_config.observer_config.navigation.path_interval` | float 或 None，m 或 s | `None` | distance 模式按弧长重采样；step 模式下记录路径按秒重采样。lane_following 只接入 distance 重采样。 |
| `actor_config.observer_config.navigation.lateral_offset` | float，m | `2.0` | 目标点相对当前朝向的横向偏移阈值，用于左右转提示。 |
| `actor_config.observer_config.navigation.current_lane_max_dist` | float，m | `2.25` | 出生车道与路径点投影时的地图查询半径。 |
| `actor_config.observer_config.navigation.snap_lane_interval` | float | `2.0（环境默认）` | 未使用；路径采样由 path_interval 设置。 |
| `actor_config.observer_config.navigation.carla_style_target` | dict 或 None | `None` | snap_lane 路线额外提供 Carla 风格的目标点；配置时需包含列出的全部子项。 |
| `actor_config.observer_config.navigation.carla_style_target.hop_resolution` | float，m | `必填；TransFuser preset 为 1.0` | 路线加密点间距。 |
| `actor_config.observer_config.navigation.carla_style_target.sample_factor` | float，m | `必填；TransFuser preset 为 50.0` | 路线分段降采样的累计距离阈值。 |
| `actor_config.observer_config.navigation.carla_style_target.min_distance` | float，m | `必填；TransFuser preset 为 7.5` | 消费已接近路线点的距离阈值。 |
| `actor_config.observer_config.navigation.carla_style_target.max_distance` | float，m | `必填；TransFuser preset 为 50.0` | 向前检查路线点的距离上限。 |
| `actor_config.observer_config.navigation.carla_style_target.road_option_angle_threshold` | float，度 | `必填；TransFuser preset 为 35.0` | 以相邻线段转角标记分段边界。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config)` | `config`：组件配置字典 | None | 保存导航与目标点配置，初始化路径和随机状态。 | — |
| 实例方法<br>`reset(self, trajdata_map: VectorMap, init_state, state, controller, seed=None, **kwargs)` | `trajdata_map`：当前场景的 trajdata.VectorMap；无地图时为 None；`init_state`：出生与终点信息字典；`state`：按微秒时间戳索引的记录状态字典；`controller`：当前 Agent 的 Controller 实例；`seed`：随机种子；None 使用调用方或环境的随机状态；`**kwargs`：关键字参数 | None | 按 navigating_type 创建路径，保存终点和地图 location。 | lane_following/snap_lane 需要 VectorMap；无出生车道时 lane_following 抛 RuntimeError；未知类型抛 ValueError。 |
| 实例方法<br>`observe(self)` | — | dict | 查询目标点与转向提示，返回整条路径及 location。 | 须先 reset；未知 forecast_type 抛 ValueError；仅 snap_lane 路径生成 carla_style_target。 |
| 实例方法<br>`destroy(self)` | — | None | 释放路径、参考轨迹、Controller、地图和场景引用。 | — |
| 实例方法<br>`get_reference_state(self, idx)` | `idx`：导航路径索引 | dict 或 None | 取得路径索引处专家速度、角速度、航向与位置；索引限制到有效范围。 | 仅 expert_following 构建专家参考；其他模式返回 None。 |
| 属性 getter<br>`observation_space(self)` | — | Discrete(3) | 声明转向提示空间。 | 实际 observe 返回完整字典，转向值为 -1/0/1，声明也没有映射该取值。 |

| 字段 | 类型、坐标与含义 |
| --- | --- |
| navigating_type | 当前导航模式字符串 |
| turn_signal | -1 右转、0 直行、1 左转；由目标点的车辆坐标横向偏移决定 |
| waypoint | 世界坐标 (N,2) 路径，m |
| cummulative_length | 长度 N 的累计路程，m；保留源码中的这个拼写 |
| target_waypoint | 世界坐标 (2,) 目标点，m |
| location | 地图 location 字符串，无地图时 None |
| carla_style_target | 可选世界坐标 (2,) 目标点，m |

lane_following 从出生车道沿后继车道延伸约 200 m，在分叉处随机选择。snap_lane 找不到车道时保留原记录点。expert_following 和 lane_following 的路径可能经过 Savitzky–Golay 平滑，snap_lane 使用投影后的点。

### 使用示例

```python
# cfg 是环境完整配置；expert_following 不要求地图。
cfg.merge_from({
    "actor_config.observer_config.navigation.navigating_type": "expert_following",
    "actor_config.observer_config.navigation.forecast_type": "step",
    "actor_config.observer_config.navigation.forecast_value": 6,
    "actor_config.observer_config.navigation.path_interval": 0.5,
})
```

<a id="api-5-8"></a>

## 5.3.8 SurroundingObservation

### 职责与创建方式

SurroundingObservation 是提供周边交通参与者状态的观测组件。跟车策略需要其他对象的位置、速度和尺寸，评测指标也需要这些数据判断碰撞风险；它从仿真对象收集周边状态，供 Policy 和指标计算使用。

`reset()` 时接收当前 Controller 与 `collector`，采集时排除自身，按配置转换坐标并过滤距离。默认配置将结果放在 AssemblyObservation 的 `surrounding` 字段下。

源码：[streetworld/obs/surrounding_obs.py](../../../streetworld/obs/surrounding_obs.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer_config.surrounding.coordinate_mode` | str | `agent（环境默认；类构造必填）` | agent 输出车辆坐标；world 输出世界坐标。非 agent 字符串均使用世界坐标分支。 |
| `actor_config.observer_config.surrounding.ignore_dist` | float 或 None，m | `None` | 仅保留三维位置距离不超过此值的对象；距离过滤使用 CUDA 张量。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config)` | `config`：组件配置字典 | None | 读取坐标模式与可选距离阈值。 | 缺少 coordinate_mode 抛 KeyError。 |
| 实例方法<br>`reset(self, collector, controller, **kwargs)` | `collector`：无参回调，返回对象 ID 到基础状态的字典；`controller`：当前 Agent 的 Controller 实例；`**kwargs`：关键字参数 | None | 保存对象采集回调和当前 Controller。 | — |
| 实例方法<br>`observe(self)` | — | dict[str, dict] | 按对象 ID 返回周边状态；agent 模式旋转速度/加速度并计算相对位姿与航向。 | 有距离过滤且存在周边对象时需要 CUDA；速度只是换坐标，没有减去主车速度。 |
| 实例方法<br>`destroy(self)` | — | None | 释放 Controller 与 collector 引用。 | — |
| 属性 getter<br>`observation_space(self)` | — | Box(shape=(1,), float32) | 为可变对象数量提供占位声明。 | 实际输出是按对象 ID 索引的字典，不能按该 Box 验证。 |

每个对象返回 transform(4,4)、position(3,)、velocity(3,)、acceleration(3,)、heading_theta、angular_velocity、angular_acceleration、current_lane、covered_lanes、size(长/宽/高) 和 type。位置单位为 m，其余单位见[观测格式与单位](../guides/environment-interface.md#observation-data)。车道字段保留地图对象引用，不随坐标模式转换。

IDMPolicy 和 TrajectoryIDMPolicy 按世界坐标读取周边位置与速度，使用它们时设置 coordinate_mode="world"。主车的默认场景指标用车辆坐标计算 TTC，保留 agent 模式。

### 使用示例

```python
# observation 来自已 reset 的环境。
for object_id, state in observation["surrounding"].items():
    print(object_id, state["position"], state["velocity"], state["type"])
```

<a id="api-5-9"></a>

## 5.3.9 CollisionBodyObservation

### 职责与创建方式

CollisionBodyObservation 是将物理碰撞几何绘制为相机图像的观测组件，用于检查碰撞盒的尺寸、位置和地面接触是否正确。它显示仿真实际使用的对象几何，便于将碰撞检测结果与相机画面中的车辆位置进行核对。

通过 Observer 配置加入环境，`reset()` 时接收 Controller、对象收集函数和地面。它用 Panda3D 绘制碰撞盒与地形，在专用渲染线程中管理资源，调用 `destroy()` 时关闭线程并释放资源。

源码：[streetworld/obs/collision_body_obs.py](../../../streetworld/obs/collision_body_obs.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.observer_config.collision_body.observer_class` | Observation 类 | `需显式添加 CollisionBodyObservation` | 把此子 Observer 加入 AssemblyObservation。 |
| `actor_config.observer_config.collision_body.cameras` | 非空 dict | `必填` | 相机名称到相机配置的映射。 |
| `actor_config.observer_config.collision_body.cameras.<相机>.H` | 正整数，px | `必填` | 图像高度，bool 不作为整数接受。 |
| `actor_config.observer_config.collision_body.cameras.<相机>.W` | 正整数，px | `必填` | 图像宽度，bool 不作为整数接受。 |
| `actor_config.observer_config.collision_body.cameras.<相机>.focal` | 正有限数值，px | `必填` | 针孔相机焦距。 |
| `actor_config.observer_config.collision_body.cameras.<相机>.offset` | 三个有限值，m | `必填` | 车辆坐标中的相机位置；在主车尺寸包围盒外时绘制主车自身。 |
| `actor_config.observer_config.collision_body.cameras.<相机>.hpr` | 三个有限值，度 | `必填` | 与 GaussianObservation 相同的 ZYX 朝向约定。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config: Mapping[str, Any])` | `config`：组件配置字典 | None | 校验并保存相机配置，暂不创建渲染线程。 | 缺相机/必填项、非法数值抛 ValueError；相机项非映射或 H/W 非整数抛 TypeError。 |
| 实例方法<br>`reset(self, controller: Any, collector: Any, ground: Any, **kwargs) -> None` | `controller`：当前 Agent 的 Controller 实例；`collector`：无参回调，返回对象 ID 到基础状态的字典；`ground`：当前 GroundPlane 或 MeshTerrain；`**kwargs`：关键字参数 | None | 保存 Controller/collector，创建渲染线程并更新地面快照，决定各相机是否绘制主车。 | ground 只接受 GroundPlane 或 MeshTerrain。 |
| 实例方法<br>`observe(self) -> Dict[str, np.ndarray]` | — | dict[str, ndarray(H,W,3)] | 按当前物理对象位姿渲染 RGB uint8；车辆、行人、骑行者使用不同颜色。 | reset 前或 collector 缺主车抛 RuntimeError；未知对象类型抛 ValueError。 |
| 实例方法<br>`destroy(self) -> None` | — | None | 关闭渲染线程并清理引用。 | — |
| 属性 getter<br>`observation_space(self) -> gym.spaces.Dict` | — | gym.spaces.Dict | 每台相机为 Box(0,255,(H,W,3),uint8)。 | — |

碰撞体图像不包含 GaussianObservation 的单帧维。默认 WebUI 的 image_layout 只拼接 gaussian.image，不显示 collision_body。gRPC 不传输这组观测，本地读取 observation["collision_body"]。

### 使用示例

```python
from streetworld.obs.collision_body_obs import CollisionBodyObservation

# 在构造环境前向完整 cfg 添加子 Observer。
cfg.merge_from({"actor_config.observer_config.collision_body": {
    "observer_class": CollisionBodyObservation,
    "cameras": {"CHASE": {"H": 480, "W": 640, "focal": 420.0,
                           "offset": [-8.0, 0.0, 4.0], "hpr": [0.0, 15.0, 0.0]}},
}})
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.2 Manager](manager.md) · [下一页：5.4 Policy](policy.md)
