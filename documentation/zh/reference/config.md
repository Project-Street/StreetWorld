<a id="api-3-1"></a>

# 5.7 Config

[English](../../en/reference/config.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.6 运行辅助组件](runtime.md) · [下一页：6.1 Configurable](configurable.md)

[类名索引：Config](#api-3-1)

## 职责与创建方式

Config 是 StreetWorld 保存和合并配置的容器。Environment、Agent、Observer 和 Policy 的参数分布在不同层级，它支持属性访问和点分键路径，使用户可以在默认配置上只覆盖需要修改的字段。

可以从字典构造，或通过 `Config.fromfile()` 加载 JSON、YAML 配置文件。Python 文件的加载目前会抛出 NameError，详见下表。字段的含义、必填项和生效条件由各组件定义，Config 不进行组件级参数校验；组件在构造或 `reset()` 时读取所需字段。

源码：[streetworld/config.py](../../../streetworld/config.py)。

## 配置

构造参数 cfg_dict 和 kwargs 指定要保存的配置。Config 本身没有额外的业务参数。

## API

| 类别与签名 | 参数 | 返回值 | 行为与调用条件 | 异常与实现状态 |
| --- | --- | --- | --- | --- |
| 构造函数<br>`__init__(self, cfg_dict: Union[Dict, None]=None, **kwargs)` | `cfg_dict`：初始字典；`kwargs`：额外配置项 | None | 用 cfg_dict 创建配置，kwargs 中的同名值覆盖 cfg_dict。 | cfg_dict 非 dict 且非 None 时抛 TypeError；Config 实例也不属于 dict。 |
| 实例方法<br>`keys(self)` | — | dict_keys | 返回顶层键视图。 | — |
| 实例方法<br>`values(self)` | — | dict_values | 返回顶层值视图；嵌套值保持原对象。 | — |
| 实例方法<br>`items(self)` | — | dict_items | 返回顶层键值视图。 | — |
| 实例方法<br>`get(self, key, default=None)` | `key`：配置键；`default`：键不存在时返回的值 | 任意配置值 | 查询顶层键；不解析点分路径。 | — |
| 实例方法<br>`copy(self)` | — | Config | 深复制配置内容。 | 不复制 filename 元信息。 |
| 实例方法<br>`merge_from(self, options: Dict, allow_list_keys: bool=True, replace_keys: list=None)` | `options`：覆盖配置字典；`allow_list_keys`：识别数字索引；`replace_keys`：当前层整项替换键 | None | 原对象合并 options；支持点分路径、递归字典合并和指定层的整项替换。 | 字典覆盖标量等不兼容结构抛 TypeError；列表越界抛 KeyError；已存在列表索引未执行赋值。 |
| 实例方法<br>`to_dict(self)` | — | dict | 转换最外层容器；嵌套容器与原配置共享。 | — |
| 类方法<br>`fromfile(cls, filename: str)` | `filename`：配置文件路径 | Config | 读取 YAML、YML、JSON；文件内容作为配置字典。 | 文件不存在抛 FileNotFoundError；扩展名不支持抛 OSError；Python 文件的语法检查方法引用了作用域内未定义的 ast，会抛出 NameError。 |
| 属性 getter<br>`filename(self)` | — | str 或 None | 读取 _filename；没有该属性时返回 None。 | fromfile 中的 cfg.filename 赋值被 __setattr__ 写入配置键，通常不会设置此属性。 |
| 属性 setter<br>`filename(self, value)` | `value`：待设置的值 | None | 设置 _filename。 | cfg.filename = value 会绕过 setter，将 filename 写成配置键。 |

## 使用示例

```python
from streetworld.config import Config

cfg = Config({"actor_config": {"warmup_step": None}})
cfg.merge_from({"actor_config.warmup_step": 10})
snapshot = cfg.copy()
assert snapshot.actor_config.warmup_step == 10
```

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：5.6 运行辅助组件](runtime.md) · [下一页：6.1 Configurable](configurable.md)
