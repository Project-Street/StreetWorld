<a id="chapter-6"></a>

<a id="api-9-1"></a>

# 6.1 Configurable

[English](../../en/reference/configurable.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.7 Config](config.md) · [下一页：6.2 Nameable](nameable.md)

配置、命名、随机数和运行生命周期各有一个基础类。有物理刚体的对象继承 BaseObject；只需要其中某项能力的组件，可直接继承对应基础类。

## 职责与创建方式

Configurable 是为组件实例管理配置的基类。Policy 和物理对象都需要保存自己的参数，并提供查询与更新入口；继承它可以共用配置管理逻辑，让具体组件专注于字段的含义和使用。

构造时传入组件配置字典，由它创建内部 Config。`get_config()` 默认返回深复制，`update_config()` 合并新参数；具体字段由子类定义。

源码：[streetworld/base_class/configurable.py](../../../streetworld/base_class/configurable.py)。

## 配置

通过构造参数 config 传入配置，没有固定的业务字段。

## API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, config: Union[Dict, Config]=None)` | `config`：组件配置字典 | None | 用 config 字典或空字典创建内部 Config。 | 传入 dict 或 config.to_dict()。虽然签名包含 Config，内部 Config(config) 会拒绝 Config 实例。 |
| 实例方法<br>`get_config(self, copy=True) -> Config` | `copy`：是否返回配置的深复制 | Config | copy=True 深复制，False 返回内部配置引用。 | — |
| 实例方法<br>`update_config(self, config: dict)` | `config`：组件配置字典 | None | 把字典合并进内部配置。 | 继承 Config.merge_from 的类型/列表约束；None 值也会覆盖原值。 |
| 实例方法<br>`destroy(self)` | — | None | 将内部配置引用置为 None。 | — |
| 属性 getter<br>`config(self)` | — | Config 或 None | 返回内部配置原对象；销毁后为 None。 | — |

## 使用示例

```python
from streetworld.base_class.configurable import Configurable

component = Configurable({"limit": 3})
component.update_config({"limit": 5})
snapshot = component.get_config()
assert snapshot.limit == 5
component.destroy()
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.7 Config](config.md) · [下一页：6.2 Nameable](nameable.md)
