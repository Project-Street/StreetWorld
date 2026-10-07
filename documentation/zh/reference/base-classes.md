<a id="chapter-6"></a>

# 6. 基础类

[English](../../en/reference/base-classes.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.7 Config](config.md) · [下一页：7. Policy Launcher 附录](../launchers/index.md)

本页目录

- [6.1 Configurable](#api-9-1)
- [6.2 Nameable](#api-9-2)
- [6.3 Randomizable](#api-9-3)
- [6.4 BaseRunnable](#api-9-4)

配置、命名、随机数和运行生命周期各有一个基础类。有物理刚体的对象继承 BaseObject；只需要其中某项能力的组件，可直接继承对应基础类。

<a id="api-9-1"></a>

## 6.1 Configurable

### 职责与创建方式

Configurable 是为组件实例管理配置的基类。Policy 和物理对象都需要保存自己的参数，并提供查询与更新入口；继承它可以共用配置管理逻辑，让具体组件专注于字段的含义和使用。

构造时传入组件配置字典，由它创建内部 Config。`get_config()` 默认返回深复制，`update_config()` 合并新参数；具体字段由子类定义。

源码：[streetworld/base_class/configurable.py](../../../streetworld/base_class/configurable.py)。

### 配置

通过构造参数 config 传入配置，没有固定的业务字段。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config: Union[Dict, Config]=None)` | `config`：组件配置字典 | None | 用 config 字典或空字典创建内部 Config。 | 传入 dict 或 config.to_dict()。虽然签名包含 Config，内部 Config(config) 会拒绝 Config 实例。 |
| 实例方法<br>`get_config(self, copy=True) -> Config` | `copy`：是否返回配置的深复制 | Config | copy=True 深复制，False 返回内部配置引用。 | — |
| 实例方法<br>`update_config(self, config: dict)` | `config`：组件配置字典 | None | 把字典合并进内部配置。 | 继承 Config.merge_from 的类型/列表约束；None 值也会覆盖原值。 |
| 实例方法<br>`destroy(self)` | — | None | 将内部配置引用置为 None。 | — |
| 属性 getter<br>`config(self)` | — | Config 或 None | 返回内部配置原对象；销毁后为 None。 | — |

### 使用示例

```python
from streetworld.base_class.configurable import Configurable

component = Configurable({"limit": 3})
component.update_config({"limit": 5})
snapshot = component.get_config()
assert snapshot.limit == 5
component.destroy()
```

<a id="api-9-2"></a>

## 6.2 Nameable

### 职责与创建方式

Nameable 是为对象提供名称与 ID 的基类。Manager 需要按 ID 登记和清理对象，日志也需要标识对象实例；它用固定的 `name`、`id` 字段统一这些标识，供对象管理与查询使用。

构造时可传入 `name`，未传入时使用自动生成的 UUID 字符串，`id` 与 `name` 相同。调用 `rename()` 会同时更新这两个属性。

源码：[streetworld/base_class/nameable.py](../../../streetworld/base_class/nameable.py)。

### 配置

名称由构造参数 name 设置，无需 Config。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, name=None)` | `name`：实例名称；None 时自动生成 | None | 设置 name，并令 id=name。 | — |
| 实例方法<br>`rename(self, new_name)` | `new_name`：新的实例名称 | None | 同步替换 name/id。 | — |
| 实例方法<br>`destroy(self)` | — | None | 将 name/id 置为 None。 | — |
| 属性 getter<br>`class_name(self)` | — | str | 返回实际实例类名。 | — |

### 使用示例

```python
from streetworld.base_class.nameable import Nameable

obj = Nameable("actor")
obj.rename("ego")
assert obj.name == obj.id == "ego"
obj.destroy()
```

<a id="api-9-3"></a>

## 6.3 Randomizable

### 职责与创建方式

Randomizable 是管理组件随机状态的基类。场景选择、车型参数采样和策略初始化都可能涉及随机选择，它为组件保存自己的随机生成器，并提供种子分配与重设接口，便于在实验中复现同一组随机选择。

构造时传入随机种子，保存 NumPy 随机生成器与 `random_seed`。Manager 调用 `generate_seed()` 为子组件分配种子，调用 `seed()` 会重新创建随机数生成器。

源码：[streetworld/base_class/randomizable.py](../../../streetworld/base_class/randomizable.py)。

### 配置

随机种子由构造参数或 seed() 设置，无需 Config。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, random_seed)` | `random_seed`：随机种子 | None | 通过 get_np_random 创建随机生成器。 | random_seed 使用非负 Python int 或 None；非法输入抛出 TypeError。 |
| 实例方法<br>`seed(self, random_seed)` | `random_seed`：随机种子 | None | 保存新的 random_seed 并重建 RandomState。 | — |
| 实例方法<br>`generate_seed(self)` | — | int | 采样 [0,65536) 的整数种子。 | — |
| 实例方法<br>`destroy(self)` | — | None | 释放随机生成器。 | — |

### 使用示例

```python
from streetworld.base_class.randomizable import Randomizable

rng = Randomizable(7)
first = rng.generate_seed()
rng.seed(7)
assert rng.generate_seed() == first
rng.destroy()
```

<a id="api-9-4"></a>

## 6.4 BaseRunnable

### 职责与创建方式

BaseRunnable 是定义组件运行生命周期的基础类，将配置、命名、随机参数采样和步进钩子放在同一个接口中。需要实现重置、动作或状态管理的组件可以继承它，共用参数初始化与资源清理逻辑。

构造时先从类的 `PARAMETER_SPACE` 采样，再用传入配置覆盖。具体状态与动作操作由子类实现，生命周期钩子由调用方执行。带物理刚体的对象继承 [BaseObject](object.md#api-7-1)，由后者提供刚体接口。

源码：[streetworld/base_class/base_runnable.py](../../../streetworld/base_class/base_runnable.py)。

### 配置

子类在 PARAMETER_SPACE 中定义采样参数，传入的 config 可以覆盖采样结果。BaseRunnable 不规定业务字段。

### API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, name=None, random_seed=None, config=None)` | `name`：实例名称；None 时自动生成；`random_seed`：随机种子；`config`：组件配置字典 | None | 初始化名称/随机状态/参数配置，从 PARAMETER_SPACE 采样，再合并 config。 | PARAMETER_SPACE 必须是 ParameterSpace，否则抛 AssertionError；同名外部值包括 None 都会覆盖采样。 |
| 实例方法<br>`get_state(self) -> Dict` | — | dict（由子类实现） | 由子类实现状态导出。 | 基类抛 NotImplementedError。 |
| 实例方法<br>`set_state(self, state: Dict)` | `state`：待恢复的状态字典 | None | 由子类实现状态恢复。 | 基类抛 NotImplementedError。 |
| 实例方法<br>`before_step(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 步进前扩展钩子；基类返回 {}。 | — |
| 实例方法<br>`set_action(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | None | 由子类实现动作设置。 | 基类抛 NotImplementedError。 |
| 实例方法<br>`step(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 运行推进扩展钩子；基类返回 {}。 | — |
| 实例方法<br>`after_step(self, *args, **kwargs)` | `*args`：位置参数；`**kwargs`：关键字参数 | dict | 步进后扩展钩子；基类返回 {}。 | — |
| 实例方法<br>`reset(self, random_seed=None, *args, **kwargs)` | `random_seed`：随机种子；`*args`：位置参数；`**kwargs`：关键字参数 | None | 以 random_seed 和其余参数重新调用实际实例的 __init__。 | 子类构造需要的参数必须一并传入；会重新调用构造函数。 |
| 实例方法<br>`sample_parameters(self)` | — | None | 生成采样种子，重设类参数空间的随机状态，将采样结果合并到配置。 | — |
| 实例方法<br>`destroy(self)` | — | None | 清理配置、随机状态、名称及 PARAMETER_SPACE 的随机生成器。 | — |

### 使用示例

```python
from streetworld.base_class.base_runnable import BaseRunnable

obj = BaseRunnable(name="component", random_seed=7, config={"enabled": True})
print(obj.config.enabled)
print(obj.before_step())
obj.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.7 Config](config.md) · [下一页：7. Policy Launcher 附录](../launchers/index.md)
