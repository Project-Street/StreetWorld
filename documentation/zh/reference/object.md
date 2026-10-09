# 5.5 Object / Controller

[English](../../en/reference/object.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.4 Policy](policy.md) · [下一页：5.6 运行辅助组件](runtime.md)

配置字段和示例变量见[配置与示例约定](environment.md#reference-conventions)。

本页目录

- [5.5.1 BaseObject](#api-7-1)
- [5.5.2 BaseVehicle](#api-7-2)
- [5.5.3 DefaultVehicle](#api-7-3)
- [5.5.4 XLVehicle](#api-7-4)
- [5.5.5 LVehicle](#api-7-5)
- [5.5.6 MVehicle](#api-7-6)
- [5.5.7 SVehicle](#api-7-7)
- [5.5.8 BaseTrafficParticipant](#api-7-8)
- [5.5.9 Pedestrian](#api-7-9)
- [5.5.10 Cyclist](#api-7-10)
- [5.5.11 GroundPlane](#api-7-11)
- [5.5.12 MeshTerrain](#api-7-12)
- [5.5.13 Object 模块函数](#section-5-5-13)

<a id="api-7-1"></a>

## 5.5.1 BaseObject

### 职责与创建方式

BaseObject 是带物理刚体的场景对象基类。车辆、交通参与者和地面都需要加入物理世界，并提供一致的位姿与运动接口；它集中定义这些共同操作，使 Manager、Observation 和碰撞检测可以访问不同类型的对象。

它在 BaseRunnable 的配置、名称和随机状态基础上加入刚体接口。`transform` 表示对象坐标系到世界坐标系的变换，速度使用世界坐标。子类负责创建具体的 `body`，直接构造 BaseObject 不会生成可操纵的刚体。

源码：[streetworld/objects/base_object.py](../../../streetworld/objects/base_object.py)。

### 配置

size、name、random_seed 和 physics_world 通过构造参数传入。子类在 PARAMETER_SPACE 和 Config 中定义物理参数，BaseObject 没有固定配置字段。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, physics_world, size=None, name=None, random_seed=None, config=None, escape_random_seed_assertion=False)` | `physics_world`：PhysicsWorld 实例；`size`：长度、宽度、高度，单位米；`name`：实例名称；None 时自动生成；`random_seed`：随机种子；`config`：组件配置字典；`escape_random_seed_assertion`：是否跳过 random_seed 非空断言 | None | 创建配置、名称和随机状态，保存 PhysicsWorld 与可选尺寸；body 暂为 None。 | 通常要求 random_seed 非 None，否则抛 AssertionError；size 使用可判断真假的三元素序列。 |
| 实例方法<br>`destroy(self)` | — | None | 执行 BaseRunnable 的配置、名称、随机状态清理。 | 本类不主动 detach body，物理子类负责。 |
| 实例方法<br>`set_position(self, position)` | `position`：世界坐标位置，单位米 | None | 设置 body 世界位置，保持旋转。 | 要求三个位置分量，长度不符抛 AssertionError。 |
| 实例方法<br>`set_heading_theta(self, heading_theta, to_deg=True) -> None` | `heading_theta`：车辆朝向，默认单位弧度；`to_deg`：True 将弧度输入转换成 Panda3D 使用的度数 | None | 设置水平朝向并转换车辆 +X 与 Panda3D +Y 朝向，保持 pitch/roll。 | — |
| 实例方法<br>`set_transform(self, m)` | `m`：车辆到世界的 4×4 齐次变换 | None | 将车辆坐标约定的 4×4 矩阵转换为 Panda3D body 变换。 | — |
| 实例方法<br>`set_velocity(self, velocity)` | `velocity`：世界坐标线速度，单位 m/s | None | 保存旧速度后设置 body 速度；两元素输入保留原 Z 速度。 | — |
| 实例方法<br>`set_angular_velocity(self, angular_velocity, in_rad=True)` | `angular_velocity`：绕 Z 轴角速度，默认单位 rad/s；`in_rad`：输入是否使用弧度制 | None | 保存旧角速度后设置 Z 轴角速度；in_rad=False 将度/s 转为 rad/s。 | — |
| 实例方法<br>`rename(self, new_name)` | `new_name`：新的实例名称 | None | 同步实例 name/id 和 body 名称。 | 需要已创建 body。 |
| 实例方法<br>`attachDyWld(self, obj=None)` | `obj`：指定 Bullet 节点；None 使用自身 body | None | 把指定节点或自身 body 加入动态 Bullet 世界。 | — |
| 实例方法<br>`detachDyWld(self, obj=None)` | `obj`：指定 Bullet 节点；None 使用自身 body | None | 把指定节点或自身 body 从动态 Bullet 世界移除。 | — |
| 实例方法<br>`set_kinematic(self, is_kinematic)` | `is_kinematic`：是否启用运动学刚体 | None | 设置 Bullet 运动学标志；启用时同时清除 active/static 标志。 | — |
| 属性 getter<br>`position(self)` | — | Panda3D 三维向量，m | 返回 body 的世界位置。 | — |
| 属性 getter<br>`heading_theta(self)` | — | float，rad | 把 Panda3D heading 转回车辆朝向并包裹到 [-π,π]。 | — |
| 属性 getter<br>`transform(self)` | — | float32 ndarray(4,4) | 返回车辆到世界的齐次变换。 | — |
| 属性 getter<br>`velocity(self)` | — | ndarray(3,)，m/s | 返回 body 的世界坐标线速度。 | — |
| 属性 getter<br>`angular_velocity(self)` | — | float，rad/s | 返回 body 绕 Z 轴角速度。 | — |
| 属性 getter<br>`angular_acceleration(self)` | — | float，rad/s² | 当前与 last_angular_velocity 的差除以物理步长。 | — |
| 属性 getter<br>`acceleration(self)` | — | ndarray(3,)，m/s² | 返回 Bullet 总力除以刚体质量。 | 零质量静态对象不适用；并非由速度差估计。 |
| 属性 getter<br>`speed(self)` | — | float，m/s | 水平速度模长，限制在 [0,100000]。 | — |
| 属性 getter<br>`speed_km_h(self)` | — | float，km/h | speed × 3.6。 | — |
| 属性 getter<br>`heading(self)` | — | (cosθ, sinθ) | 返回世界坐标中的二维朝向单位向量。 | — |

### 使用示例

```python
# env 已 reset，Controller 继承 BaseObject 的位姿与运动接口。
controller = env.actor_controller
print(controller.transform)
print(controller.position, controller.heading_theta, controller.speed)
```

<a id="api-7-2"></a>

## 5.5.2 BaseVehicle

### 职责与创建方式

BaseVehicle 是车辆 Controller 的基类，将 Policy 输出的转向和油门/刹车指令施加到 Bullet 车辆模型，使控制动作通过动力学产生后续位姿和速度。不同车型共享这套控制实现，可以在相同的 Policy 接口下更换车辆参数。

AgentManager 根据 `controller` 配置创建具体车型。车辆由盒形底盘和四个车轮组成，车型子类定义尺寸、质量、轮胎半径和轴距，通常选用 [DefaultVehicle](#api-7-3) 或 S/M/L/XLVehicle。

源码：[streetworld/objects/vehicle/base_vehicle.py](../../../streetworld/objects/vehicle/base_vehicle.py)。

### 配置

表中使用主车路径，周边车辆换成 participant_config.controller_config。enable_reverse、spawn_velocity 和 check_crash_world 由环境默认配置提供，BaseVehicle 不会补齐这些字段。

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.controller_config.size` | 三元素序列或 None，m | `None` | Manager 提取后作为构造参数；None 使用车辆类默认尺寸。 |
| `actor_config.controller_config.enable_reverse` | bool | `True` | True 时负控制量施加反向发动机力；False 时负控制量用于制动，低速进入死区。 |
| `actor_config.controller_config.spawn_velocity` | bool | `True` | reset 时写入出生线速度和角速度。 |
| `actor_config.controller_config.max_acceleration` | float，m/s² | `15.0（主车）；周边默认不提供` | 限制前一物理步水平速度变化；存在此字段时才执行，值须正。 |
| `actor_config.controller_config.check_crash_world` | bool | `False` | 检查地面接触点是否高于附近车轮；该检查使用 CUDA。 |
| `actor_config.controller_config.max_steering` | 数值，度 | `由车型采样` | 归一化 steering 的最大轮转角；外部值覆盖采样。 |
| `actor_config.controller_config.max_engine_force` | 数值，Bullet 力参数 | `由车型采样` | 每轮发动机力上限；外部值覆盖采样。 |
| `actor_config.controller_config.max_brake_force` | 数值，Bullet 制动参数 | `由车型采样` | 每轮制动力上限，按 Bullet 的制动参数解释。 |
| `actor_config.controller_config.max_speed_km_h` | 数值，km/h | `80（车型默认）` | 超速时不再施加正向发动机力。 |
| `actor_config.controller_config.wheel_friction` | 数值 | `由车型采样` | 创建轮胎时固定调用 setFrictionSlip(0.5)，此字段不生效。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config: Union[dict, Config], physics_world, size=None, name: str=None, random_seed=None, position=None, heading_theta=None, _calling_reset=True, **kwargs)` | `config`：组件配置字典；`physics_world`：PhysicsWorld 实例；`size`：长度、宽度、高度，单位米；`name`：实例名称；None 时自动生成；`random_seed`：随机种子；`position`：世界坐标位置，单位米；`heading_theta`：车辆朝向，默认单位弧度；`_calling_reset`：构造完成后是否调用 reset；`**kwargs`：关键字参数 | None | 创建底盘与车轮，读取动力参数；默认立即 reset。 | config 必须非 None；直接 BaseVehicle 缺具体车型常量；position 和出生速度需提供有效值。 |
| 实例方法<br>`attachDyWld(self)` | — | None | 同时把底盘 body 和 BulletVehicle 加入动态世界。 | — |
| 实例方法<br>`detachDyWld(self)` | — | None | 先移除 BulletVehicle，再移除底盘。 | — |
| 实例方法<br>`reset(self, name=None, random_seed=None, position: np.ndarray=None, heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, *args, **kwargs)` | `name`：实例名称；None 时自动生成；`random_seed`：随机种子；`position`：世界坐标位置，单位米；`heading_theta`：车辆朝向，默认单位弧度；`velocity`：世界坐标线速度，单位 m/s；`angular_velocity`：绕 Z 轴角速度，默认单位 rad/s；`*args`：位置参数；`**kwargs`：关键字参数 | None | 可改名和 seed，重设航向/位置；按 spawn_velocity 写入速度，清空碰撞标志。 | position 必须提供；spawn_velocity=True 时 velocity 必须提供；random_seed 非 int 抛 AssertionError。 |
| 实例方法<br>`move(self, action=None)` | `action`：外部动作；格式由当前 Policy 决定 | 控制诊断 dict 或 None | 记录状态字典含 transform/velocity/angular_velocity 时直接恢复；否则裁剪控制、更新力与转角并保存动作。 | action=None 时在成员检查处抛出 TypeError；控制模式须两元素序列。 |
| 实例方法<br>`check_crash_world(self)` | — | None | 启用检查时比较地面接触点与最近车轮高度，命中后设置 crash_world。 | 有接触点时执行 CUDA 张量计算。 |
| 实例方法<br>`destroy(self)` | — | None | 执行基础清理，移除车辆和底盘，断开物理引用。 | — |
| 实例方法<br>`set_position(self, position)` | `position`：世界坐标位置，单位米 | None | 三元素直接设置；两元素 list 追加当前 Z 后设置。 | 两元素 NumPy 数组没有 append，会在该分支报错；使用完整三元素位置。 |
| 实例方法<br>`get_steering_wheel_angle(self)` | — | 轮转角数值，rad | steering × max_steering × π/180。 | — |
| 实例方法<br>`get_longitudinal_acceleration(self)` | — | ndarray(2,) | 返回 acceleration[:2] 与二维 heading 逐分量相乘。 | 没有计算纵向加速度的点积标量。 |
| 属性 getter<br>`current_action(self)` | — | 两元素控制量 | 返回最近一次控制模式 move 保存的动作。 | 回放分支不更新该队列。 |
| 属性 getter<br>`max_speed_km_h(self)` | — | 配置值，km/h | 返回 max_speed_km_h。 | — |

车辆先从车型的 PARAMETER_SPACE 采样物理参数，再用 controller_config 覆盖。各车型的默认常量和采样范围如下，force 字段按 Bullet 参数解释。

| 车型 | 长/宽/高，m | 质量，kg | 最大轮转角，度 | max_engine_force 范围 | max_brake_force 范围 |
| --- | --- | --- | --- | --- | --- |
| DefaultVehicle | 4.515 / 1.852 / 1.19 | 1000 | 40 | 750–850 | 80–120 |
| XLVehicle | 5.74 / 2.3 / 2.8 | 1600 | 35 | 500–700 | 50–100 |
| LVehicle | 4.87 / 2.046 / 1.85 | 1300 | 40 | 450–650 | 60–120 |
| MVehicle | 4.6 / 1.85 / 1.37 | 1200 | 45 | 650–850 | 60–150 |
| SVehicle | 4.3 / 1.7 / 1.7 | 800 | 50 | 350–550 | 35–80 |

车型还决定轮胎半径和前后轴距。控制量限制在 [-1,1]。enable_reverse=True 时，负 throttle_brake 可以驱动车辆倒车；设置此字段时需考虑轨迹模型是否要求停车或倒车。

### 使用示例

```python
from streetworld.engine.physics_world import PhysicsWorld
from streetworld.objects.vehicle.vehicle_type import DefaultVehicle

world = PhysicsWorld(physics_world_step_size=20_000)
vehicle = DefaultVehicle(config={"enable_reverse": False,
    "spawn_velocity": True, "check_crash_world": False}, physics_world=world,
    random_seed=7, position=[0.0, 0.0, 1.0], heading_theta=0.0,
    velocity=[0.0, 0.0, 0.0])
vehicle.attachDyWld()
vehicle.move([0.0, 0.2])
world.step()
vehicle.destroy()
world.destroy()
```

<a id="api-7-3"></a>

## 5.5.3 DefaultVehicle

### 职责与创建方式

DefaultVehicle 是主车默认使用的车辆 Controller，提供一套固定的车型参数。它复用 [BaseVehicle](#api-7-2) 的控制与动力学接口，可直接运行示例，也可用于在同一车型下比较不同 AD policy。

通过 `actor_config.controller` 选用，由 AgentManager 创建。默认长/宽/高为 4.515 / 1.852 / 1.19 m，质量 1000 kg，轮胎半径 0.313 m；前、后轴距分量分别为 1.05234 m 和 1.4166 m。

源码：[streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py)。

### 配置

配置和动作接口见 [BaseVehicle](#api-7-2)。通过 controller_config.size 可以覆盖默认尺寸，无额外配置字段。

### API

接口继承自 [BaseVehicle](#api-7-2)。

### 使用示例

```python
from streetworld.objects.vehicle.vehicle_type import DefaultVehicle

cfg.merge_from({"actor_config.controller": DefaultVehicle})
```

<a id="api-7-4"></a>

## 5.5.4 XLVehicle

### 职责与创建方式

XLVehicle 是 XL 档车辆的参数预设，用于表示较大的车身与较高的车辆质量。它沿用 [BaseVehicle](#api-7-2) 的控制实现，用户可以通过 Controller 配置更换车型，研究车辆参数对驾驶行为的影响。

AgentManager 按配置创建实例。默认长/宽/高为 5.74 / 2.3 / 2.8 m，质量 1600 kg，轮胎半径 0.37 m；前、后轴距分量分别为 1.726 m 和 1.075 m。

源码：[streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py)。

### 配置

配置和动作接口见 [BaseVehicle](#api-7-2)。通过 controller_config.size 可以覆盖默认尺寸，无额外配置字段。

### API

接口继承自 [BaseVehicle](#api-7-2)。

### 使用示例

```python
from streetworld.objects.vehicle.vehicle_type import XLVehicle

cfg.merge_from({"actor_config.controller": XLVehicle})
```

<a id="api-7-5"></a>

## 5.5.5 LVehicle

### 职责与创建方式

LVehicle 提供 L 档车辆的底盘、质量和车轮参数，用于为场景中的车辆选择比 M 档更大的默认车身。它共享 [BaseVehicle](#api-7-2) 的动力学模型与动作接口，可作为主车或周边车辆的 Controller。

由 AgentManager 创建，默认长/宽/高为 4.87 / 2.046 / 1.85 m，质量 1300 kg，轮胎半径 0.429 m；前、后轴距分量分别为 1.5301 m 和 1.218261 m。

源码：[streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py)。

### 配置

配置和动作接口见 [BaseVehicle](#api-7-2)。通过 controller_config.size 可以覆盖默认尺寸，无额外配置字段。

### API

接口继承自 [BaseVehicle](#api-7-2)。

### 使用示例

```python
from streetworld.objects.vehicle.vehicle_type import LVehicle

cfg.merge_from({"actor_config.controller": LVehicle})
```

<a id="api-7-6"></a>

## 5.5.6 MVehicle

### 职责与创建方式

MVehicle 是 M 档车辆的参数预设，为车辆 Controller 提供一套中等尺寸的车身和车轮参数。选择它可以更换车辆的物理参数，同时继续使用 [BaseVehicle](#api-7-2) 的控制接口。

由 AgentManager 按 Controller 配置创建，默认长/宽/高为 4.6 / 1.85 / 1.37 m，质量 1200 kg，轮胎半径 0.39 m；前、后轴距分量分别为 1.285 m 和 1.203 m。

源码：[streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py)。

### 配置

配置和动作接口见 [BaseVehicle](#api-7-2)。通过 controller_config.size 可以覆盖默认尺寸，无额外配置字段。

### API

接口继承自 [BaseVehicle](#api-7-2)。

### 使用示例

```python
from streetworld.objects.vehicle.vehicle_type import MVehicle

cfg.merge_from({"actor_config.controller": MVehicle})
```

<a id="api-7-7"></a>

## 5.5.7 SVehicle

### 职责与创建方式

SVehicle 是 S 档车辆的参数预设，用于表示尺寸较小、质量较低的车辆。它采用 [BaseVehicle](#api-7-2) 的动力学与控制接口，使小尺寸车辆也能使用同一套 Policy。

AgentManager 按配置创建实例。默认长/宽/高为 4.3 / 1.7 / 1.7 m，质量 800 kg，轮胎半径 0.376 m；前、后轴距分量分别为 1.385 m 和 1.11 m。

源码：[streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py)。

### 配置

配置和动作接口见 [BaseVehicle](#api-7-2)。通过 controller_config.size 可以覆盖默认尺寸，无额外配置字段。

### API

接口继承自 [BaseVehicle](#api-7-2)。

### 使用示例

```python
from streetworld.objects.vehicle.vehicle_type import SVehicle

cfg.merge_from({"actor_config.controller": SVehicle})
```

<a id="api-7-8"></a>

## 5.5.8 BaseTrafficParticipant

### 职责与创建方式

BaseTrafficParticipant 是行人和骑行者的物理对象基类。这些参与者通常按记录轨迹移动，仿真仍需要根据它们的尺寸与位姿检测车辆碰撞；该类用盒形刚体表示参与者，并提供记录状态恢复接口。

具体子类设置 `MASS` 和 `TYPE_NAME`，BaseEnv 根据场景元数据选择子类，再由 AgentManager 创建对象。回放时，`move()` 将记录中的 `transform`、速度和角速度应用到刚体。

源码：[streetworld/objects/traffic_participants/base_traffic_participant.py](../../../streetworld/objects/traffic_participants/base_traffic_participant.py)。

### 配置

size、position、velocity 等构造参数由 BaseEnv 从场景元数据读取。没有额外配置字段，仍可使用 BaseRunnable 的配置接口。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config, physics_world, size, position: Sequence[float], heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, random_seed=None, name=None, **kwargs)` | `config`：组件配置字典；`physics_world`：PhysicsWorld 实例；`size`：长度、宽度、高度，单位米；`position`：世界坐标位置，单位米；`heading_theta`：车辆朝向，默认单位弧度；`velocity`：世界坐标线速度，单位 m/s；`angular_velocity`：绕 Z 轴角速度，默认单位 rad/s；`random_seed`：随机种子；`name`：实例名称；None 时自动生成；`**kwargs`：关键字参数 | None | 按 size 创建碰撞盒，设置位置、航向、线速度与角速度，标记对象类型。 | size、position、velocity 须为有效序列；具体子类必须定义 MASS/TYPE_NAME；random_seed 遵循 BaseObject 断言。 |
| 实例方法<br>`reset(self, position: Sequence[float], heading_theta: float=0.0, random_seed=None, name=None, *args, **kwargs)` | `position`：世界坐标位置，单位米；`heading_theta`：车辆朝向，默认单位弧度；`random_seed`：随机种子；`name`：实例名称；None 时自动生成；`*args`：位置参数；`**kwargs`：关键字参数 | None | 不执行操作。 | 传入 position/name/seed 不会改变已创建对象。 |
| 实例方法<br>`move(self, state_info)` | `state_info`：含 transform、velocity、angular_velocity 的记录状态字典 | None | 按 state_info 的 transform、velocity、angular_velocity 恢复记录状态。 | 不接受车辆两元素控制量；缺字段抛 KeyError。 |
| 实例方法<br>`destroy(self)` | — | None | 基础清理后从动态世界移除 body 并释放引用。 | — |

### 使用示例

```python
# 行人/骑行者由环境按 participants 元数据自动创建。
for manager in env.agent_managers.values():
    if manager.controller is not None:
        print(manager.controller.metadrive_type)
```

<a id="api-7-9"></a>

## 5.5.9 Pedestrian

### 职责与创建方式

Pedestrian 是场景中的行人物理对象，用于回放行人运动，并让碰撞检测识别车辆与行人的接触。它使用 [BaseTrafficParticipant](#api-7-8) 的盒形刚体与状态恢复接口。

BaseEnv 按场景元数据中的 `pedestrian` 类型选用它，由 AgentManager 创建，并配置 ReplayPolicy 与 DummyObservation。质量为 70 kg，类型为 `MetaDriveType.PEDESTRIAN`，尺寸从场景元数据读取。

源码：[streetworld/objects/traffic_participants/pedestrian.py](../../../streetworld/objects/traffic_participants/pedestrian.py)。

### 配置

构造和动作参数见 [BaseTrafficParticipant](#api-7-8)，无额外配置字段。

### API

接口继承自 [BaseTrafficParticipant](#api-7-8)。

### 使用示例

```python
from streetworld.objects.traffic_participants.pedestrian import Pedestrian

# env 已 reset；环境已经为此类型选择 ReplayPolicy。
objects = [m.controller for m in env.agent_managers.values()
           if isinstance(m.controller, Pedestrian)]
print(len(objects))
```

<a id="api-7-10"></a>

## 5.5.10 Cyclist

### 职责与创建方式

Cyclist 是场景中的骑行者物理对象，用于将记录中的骑行者加入交通回放和车辆碰撞检查。它通过 [BaseTrafficParticipant](#api-7-8) 的状态恢复接口更新位姿与速度。

BaseEnv 根据场景元数据中的 `cyclist` 类型选用它，由 AgentManager 创建，并配置 ReplayPolicy 与 DummyObservation。质量为 80 kg，类型为 `MetaDriveType.CYCLIST`，尺寸从场景元数据读取。

源码：[streetworld/objects/traffic_participants/cyclist.py](../../../streetworld/objects/traffic_participants/cyclist.py)。

### 配置

构造和动作参数见 [BaseTrafficParticipant](#api-7-8)，无额外配置字段。

### API

接口继承自 [BaseTrafficParticipant](#api-7-8)。

### 使用示例

```python
from streetworld.objects.traffic_participants.cyclist import Cyclist

# env 已 reset；环境已经为此类型选择 ReplayPolicy。
objects = [m.controller for m in env.agent_managers.values()
           if isinstance(m.controller, Cyclist)]
print(len(objects))
```

<a id="api-7-11"></a>

## 5.5.11 GroundPlane

### 职责与创建方式

GroundPlane 是平面地形的物理对象，为车辆提供路面支撑与轮胎接触。它用无限静态平面表示路面，适用于以平面近似地形的场景。

场景未提供 `scene_mesh_path` 时，BaseEnv 读取 ScenarioDataManager 生成的 `normal`、`constant` 来创建 GroundPlane。构造时建立静态 Bullet 平面，并将它加入 PhysicsWorld。

源码：[streetworld/objects/terrain/ground.py](../../../streetworld/objects/terrain/ground.py)。

### 配置

direction 指定平面法向，constant 是 Bullet 平面常数，默认为 0。环境从 metadata.ground_plane 读取这些值，无独立 Config 字段。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, physics_world, direction: Sequence[float], constant: float=0.0, random_seed=None, name=None, config=None, **kwargs)` | `physics_world`：PhysicsWorld 实例；`direction`：平面法向量，三个分量；`constant`：BulletPlaneShape 的平面常数，单位米；`random_seed`：随机种子；`name`：实例名称；None 时自动生成；`config`：组件配置字典；`**kwargs`：关键字参数 | None | 按 direction/constant 创建 BulletPlaneShape，设静态与摩擦系数 0.4，并挂接。 | — |
| 实例方法<br>`reset(self, random_seed=None, name=None, *args, **kwargs)` | `random_seed`：随机种子；`name`：实例名称；None 时自动生成；`*args`：位置参数；`**kwargs`：关键字参数 | None | 不执行操作；环境切换场景时销毁并重建地面。 | — |
| 实例方法<br>`destroy(self)` | — | None | 执行基础清理并移除平面 body。 | — |

### 使用示例

```python
from streetworld.objects.terrain.ground import GroundPlane

# world 是已有 PhysicsWorld；构造时自动挂接。
ground = GroundPlane(world, direction=[0.0, 0.0, 1.0], constant=0.0, random_seed=7)
ground.destroy()
```

<a id="api-7-12"></a>

## 5.5.12 MeshTerrain

### 职责与创建方式

MeshTerrain 是将地面三角网格转换为物理碰撞地形的对象，适用于需要保留道路起伏和地面形状的场景。它让车辆与网格路面产生接触，将场景提供的地形用于车辆动力学仿真。

场景提供 `scene_mesh_path` 时，BaseEnv 创建 MeshTerrain。构造时读取顶点、面和法线，应用 `transform`、`scale`、`position` 后创建静态 Bullet 地面；网格数组也供 [CollisionBodyObservation](observation.md#api-5-9) 绘制。

源码：[streetworld/objects/terrain/mesh_terrain.py](../../../streetworld/objects/terrain/mesh_terrain.py)。

### 配置

文件路径和变换通过构造参数传入。BaseEnv 使用元数据的 scene_mesh_path 和 scene_mesh_transform，无独立 Config 字段。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, physics_world, model_path: str, transform=None, position=(0, 0, 0), scale=1.0, friction=0.8, restitution=0.0, random_seed=None, name='GroundMesh', config=None, **kwargs)` | `physics_world`：PhysicsWorld 实例；`model_path`：地面网格文件路径；`transform`：4×4 齐次变换；`position`：世界坐标位置，单位米；`scale`：网格缩放倍率，必须大于零；`friction`：Bullet 摩擦系数；`restitution`：Bullet 恢复系数；`random_seed`：随机种子；`name`：实例名称；None 时自动生成；`config`：组件配置字典；`**kwargs`：关键字参数 | None | 加载网格并创建质量为零的 BulletTriangleMeshShape，设置摩擦/恢复系数并挂接。 | scale≤0，非法 position/transform 抛 ValueError；文件和网格解析异常直接传播。 |
| 实例方法<br>`reset(self, random_seed=None, name=None, *args, **kwargs)` | `random_seed`：随机种子；`name`：实例名称；None 时自动生成；`*args`：位置参数；`**kwargs`：关键字参数 | None | 不执行操作；环境通过重建切换网格。 | — |
| 实例方法<br>`destroy(self)` | — | None | 移除物理刚体，释放顶点/面/法线数组，再执行基础清理。 | — |

默认 transform=None、position=(0,0,0)、scale=1.0、friction=0.8、restitution=0.0。顶点先应用 transform，再缩放、平移；法线只应用 transform 的旋转部分。

### 使用示例

```python
from streetworld.objects.terrain.mesh_terrain import MeshTerrain

# world 是已有 PhysicsWorld，路径指向实际地面网格。
ground = MeshTerrain(world, model_path="/path/to/mesh_ground.ply", random_seed=7)
ground.destroy()
```

<a id="section-5-5-13"></a>

## 5.5.13 Object 模块函数

车型选择函数定义在 vehicle/vehicle_type.py。
| 模块函数<br>`get_vehicle_type(length)` | length：分类使用的长度，m | 车辆类 | length≤4 返回 SVehicle；≤5.2 返回 MVehicle；≤6.2 返回 LVehicle；其余返回 XLVehicle。 | BaseEnv 创建周边车辆时传入 tracking.size[1]，即宽度，与函数要求的长度参数不一致。 |
| 模块函数<br>`random_vehicle_type(np_random, p=None)` | np_random：支持 choice 的随机生成器；p：可选五项概率列表 | 车辆类 | 按 s、m、l、xl、default 顺序用 np_random.choice 采样；p=None 时均匀。 | 非空 p 须有 5 项；和不为 1 等概率错误由 NumPy 抛出；p 的真假检查无法用于 ndarray。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.4 Policy](policy.md) · [下一页：5.6 运行辅助组件](runtime.md)
