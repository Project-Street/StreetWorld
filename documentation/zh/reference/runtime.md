# 5.6 运行辅助组件

[English](../../en/reference/runtime.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.5 Object / Controller](object.md) · [下一页：5.7 Config](config.md)

配置字段和示例变量见[配置与示例约定](environment.md#reference-conventions)。

本页目录

- [5.6.1 StepCounter](#api-8-1)
- [5.6.2 PhysicsWorld](#api-8-2)

<a id="api-8-1"></a>

## 5.6.1 StepCounter

### 职责与创建方式

StepCounter 是仿真的时间与步数计数器。一个环境步可以包含多个物理步，Policy 更新和轨迹回放需要使用一致的时间轴；它将物理步数换算为场景时间戳和环境步数，并通过 `key_step` 标记接收新动作的时机。

BaseEnv 创建它时传入物理步长与重复次数，在 `reset()` 时设置场景起止时间。环境每推进一个物理步，就调用一次它的 `step()` 更新计数；实际动力学推进由 PhysicsWorld 执行。

源码：[streetworld/misc/step_counter.py](../../../streetworld/misc/step_counter.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `physics_world_step_size` | 数值，µs | `20_000（环境默认）` | 传入 step_size。 |
| `decision_repeat` | int，物理步数 | `5（环境默认）` | 传入 physical_repeat，必须大于 0。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, step_size, physical_repeat=0)` | `step_size`：物理步长，整数微秒；`physical_repeat`：每个环境步包含的物理步数 | None | 保存 step_size 与 physical_repeat。 | 构造默认 physical_repeat=0；直接读取 key_step/eposide_step 会除零，须显式传正数。 |
| 实例方法<br>`reset(self, timestamp_range, **kwargs)` | `timestamp_range`：开始与结束时间，微秒；`**kwargs`：关键字参数 | None | 保存起止时间，把 physical_step 置为 0。 | timestamp_range 至少含起止两项。 |
| 实例方法<br>`step(self)` | — | None | physical_step 加一。 | 不检查是否超过 end_timestamp。 |
| 属性 getter<br>`relative_timestamp(self)` | — | 数值，µs | physical_step × step_size。 | — |
| 属性 getter<br>`current_timestamp(self)` | — | 数值，µs | begin_timestamp + relative_timestamp。 | — |
| 属性 getter<br>`key_step(self)` | — | bool | physical_step 可整除 physical_repeat 时为 True，包括刚 reset 的时刻。 | — |
| 属性 getter<br>`eposide_step(self)` | — | int | physical_step // physical_repeat；属性名为 eposide_step。 | — |

### 使用示例

```python
from streetworld.misc.step_counter import StepCounter

counter = StepCounter(step_size=20_000, physical_repeat=5)
counter.reset(timestamp_range=[1_000_000, 2_000_000])
for _ in range(5):
    counter.step()
assert counter.relative_timestamp == 100_000
assert counter.eposide_step == 1
```

<a id="api-8-2"></a>

## 5.6.2 PhysicsWorld

### 职责与创建方式

PhysicsWorld 是 StreetWorld 的物理仿真组件，封装 Panda3D 的 BulletWorld，负责动力学积分与碰撞接触计算。车辆、交通参与者和地面需要处于同一个物理世界，才能共同计算运动与接触关系；PhysicsWorld 为这些对象提供统一的物理环境。

BaseEnv 在构造时创建 PhysicsWorld，车辆与地面对象将刚体加入其 `dynamic_world`。每次物理步调用 `step()` 按配置步长推进，重力设置为 `(0, 0, -9.81)`。

源码：[streetworld/engine/physics_world.py](../../../streetworld/engine/physics_world.py)。

### 配置

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `physics_world_step_size` | 数值，µs | `20_000（环境默认）` | BaseEnv 构造时显式传入；类签名默认 0.01 也按微秒解释，即 1e-8 s。 |
| `substep（构造参数）` | 正整数 | `1` | Bullet doPhysics 的最大子步数；当前 BaseEnv 没有对应 Config 字段。 |

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, physics_world_step_size=0.01, substep: int=1)` | `physics_world_step_size`：物理步长，微秒；`substep`：每次 Bullet 推进的最大子步数 | None | 创建 BulletWorld 并设置重力，保存微秒步长和子步数。 | — |
| 实例方法<br>`destroy(self)` | — | None | 清除调试节点、碰撞和过滤回调，释放 world 引用。 | 对象先由所属 Manager 销毁；之后不能继续 step。 |
| 实例方法<br>`step(self)` | — | None | 按 step_size_sec 推进 Bullet，固定子步时长为 step_size_sec/substep。 | substep=0 会除零；环境使用 1。 |
| 属性 getter<br>`step_size_sec(self)` | — | 数值，s | physics_world_step_size × 1e-6。 | — |

### 使用示例

```python
from streetworld.engine.physics_world import PhysicsWorld

world = PhysicsWorld(physics_world_step_size=20_000, substep=1)
world.step()
assert world.step_size_sec == 0.02
world.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.5 Object / Controller](object.md) · [下一页：5.7 Config](config.md)
