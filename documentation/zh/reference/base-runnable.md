<a id="api-9-4"></a>

# 6.4 BaseRunnable

[English](../../en/reference/base-runnable.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.3 Randomizable](randomizable.md) · [下一页：7. Policy Launcher 附录](../launchers/index.md)

## 职责与创建方式

BaseRunnable 是定义组件运行生命周期的基础类，将配置、命名、随机参数采样和步进钩子放在同一个接口中。需要实现重置、动作或状态管理的组件可以继承它，共用参数初始化与资源清理逻辑。

构造时先从类的 `PARAMETER_SPACE` 采样，再用传入配置覆盖。具体状态与动作操作由子类实现，生命周期钩子由调用方执行。带物理刚体的对象继承 [BaseObject](object.md#api-7-1)，由后者提供刚体接口。

源码：[streetworld/base_class/base_runnable.py](../../../streetworld/base_class/base_runnable.py)。

## 配置

子类在 PARAMETER_SPACE 中定义采样参数，传入的 config 可以覆盖采样结果。BaseRunnable 不规定业务字段。

## API

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

## 使用示例

```python
from streetworld.base_class.base_runnable import BaseRunnable

obj = BaseRunnable(name="component", random_seed=7, config={"enabled": True})
print(obj.config.enabled)
print(obj.before_step())
obj.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.3 Randomizable](randomizable.md) · [下一页：7. Policy Launcher 附录](../launchers/index.md)
