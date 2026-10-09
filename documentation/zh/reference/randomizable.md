<a id="api-9-3"></a>

# 6.3 Randomizable

[English](../../en/reference/randomizable.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.2 Nameable](nameable.md) · [下一页：6.4 BaseRunnable](base-runnable.md)

## 职责与创建方式

Randomizable 是管理组件随机状态的基类。场景选择、车型参数采样和策略初始化都可能涉及随机选择，它为组件保存自己的随机生成器，并提供种子分配与重设接口，便于在实验中复现同一组随机选择。

构造时传入随机种子，保存 NumPy 随机生成器与 `random_seed`。Manager 调用 `generate_seed()` 为子组件分配种子，调用 `seed()` 会重新创建随机数生成器。

源码：[streetworld/base_class/randomizable.py](../../../streetworld/base_class/randomizable.py)。

## 配置

随机种子由构造参数或 seed() 设置，无需 Config。

## API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, random_seed)` | `random_seed`：随机种子 | None | 通过 get_np_random 创建随机生成器。 | random_seed 使用非负 Python int 或 None；非法输入抛出 TypeError。 |
| 实例方法<br>`seed(self, random_seed)` | `random_seed`：随机种子 | None | 保存新的 random_seed 并重建 RandomState。 | — |
| 实例方法<br>`generate_seed(self)` | — | int | 采样 [0,65536) 的整数种子。 | — |
| 实例方法<br>`destroy(self)` | — | None | 释放随机生成器。 | — |

## 使用示例

```python
from streetworld.base_class.randomizable import Randomizable

rng = Randomizable(7)
first = rng.generate_seed()
rng.seed(7)
assert rng.generate_seed() == first
rng.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.2 Nameable](nameable.md) · [下一页：6.4 BaseRunnable](base-runnable.md)
