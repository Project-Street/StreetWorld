<a id="api-9-2"></a>

# 6.2 Nameable

[English](../../en/reference/nameable.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.1 Configurable](configurable.md) · [下一页：6.3 Randomizable](randomizable.md)

## 职责与创建方式

Nameable 是为对象提供名称与 ID 的基类。Manager 需要按 ID 登记和清理对象，日志也需要标识对象实例；它用固定的 `name`、`id` 字段统一这些标识，供对象管理与查询使用。

构造时可传入 `name`，未传入时使用自动生成的 UUID 字符串，`id` 与 `name` 相同。调用 `rename()` 会同时更新这两个属性。

源码：[streetworld/base_class/nameable.py](../../../streetworld/base_class/nameable.py)。

## 配置

名称由构造参数 name 设置，无需 Config。

## API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, name=None)` | `name`：实例名称；None 时自动生成 | None | 设置 name，并令 id=name。 | — |
| 实例方法<br>`rename(self, new_name)` | `new_name`：新的实例名称 | None | 同步替换 name/id。 | — |
| 实例方法<br>`destroy(self)` | — | None | 将 name/id 置为 None。 | — |
| 属性 getter<br>`class_name(self)` | — | str | 返回实际实例类名。 | — |

## 使用示例

```python
from streetworld.base_class.nameable import Nameable

obj = Nameable("actor")
obj.rename("ego")
assert obj.name == obj.id == "ego"
obj.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：6.1 Configurable](configurable.md) · [下一页：6.3 Randomizable](randomizable.md)
