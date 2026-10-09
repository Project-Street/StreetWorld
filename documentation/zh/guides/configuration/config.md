<a id="chapter-4"></a>

<a id="section-4-1"></a>

# 4.1 Config 的用途与使用

[English](../../../en/guides/configuration/config.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：3.3 渲染后端示例](../rendering-backends.md) · [下一页：4.2 配置层级与优先级](hierarchy.md)

测试不同驾驶策略时，需要选择场景、调整仿真步长，还可能更换主车的 Policy 或相机设置。StreetWorld 用 [Config](../../../../streetworld/config.py) 保存这些设置，在创建 Environment 时传入。环境再将主车、周边对象和观测各自的配置交给对应组件。

Config 是保存嵌套配置的 Python 类。它接收一个字典，支持深复制和配置合并。`Config()` 类本身只保存传入的内容，不添加环境默认值。

## 创建与传入环境

例如，选择 nuScenes 场景 `0007`，并关闭主车倒车功能：

```python
from streetworld.config import Config

cfg = Config({
    "scene_ids": ["0007"],
    "actor_config": {
        "controller_config": {"enable_reverse": False},
    },
})
```

创建环境时，将 `cfg` 作为 `config` 参数传入，例如 `ScenarioEnv(simulator, config=cfg)`；`simulator` 是[第三章](../simulator-interface.md#section-3-2)中的 SimulatorInterface 实例。完整的环境调用示例见 [3.1](../environment-interface.md#section-3-1)。

## 访问、修改与复制

Config 支持字典和属性两种访问方式。下面修改场景列表，并重新开启倒车：

```python
cfg["scene_ids"] = ["0007", "0008"]
cfg.actor_config.controller_config.enable_reverse = True
```

需要为另一轮测试单独修改配置时，用 `copy()` 深复制一份；`to_dict()` 将最外层容器转换成普通字典：

```python
independent = cfg.copy()
values = cfg.to_dict()
```

`to_dict()` 不复制嵌套内容，嵌套值可能仍是 ConfigDict。访问不存在的字段时，字典方式抛出 KeyError，属性方式抛出 AttributeError。

## 合并配置：merge_from()

运行脚本经常需要在一份已有配置上修改个别字段，例如保留场景和相机设置，只换主车的控制参数。`merge_from()` 将新设置写入已有 Config：同名字段使用新值，其余字段保留。

嵌套字典逐层合并，也可以用点分隔的键直接指定内部字段。下面两种写法都关闭主车倒车，保留 `scene_ids`：

```python
cfg.merge_from({"actor_config": {"controller_config": {"enable_reverse": False}}})
cfg.merge_from({"actor_config.controller_config.enable_reverse": False})
```

列表和数值直接替换。例如，`image_layout` 设置交互环境的画面布局，下面将它改成只显示前视相机：

```python
cfg.merge_from({"image_layout": [["FRONT"]]})
```

`replace_keys` 可以指定整项替换的字段，例如 `replace_keys=["actor_config"]` 会替换整个主车配置，未提供的字段不再保留，因此需要传入完整的主车配置。这个参数只影响当前层，递归合并不会继续传递它。

`allow_list_keys=True` 允许用数字字符串访问列表索引。索引等于列表长度时追加，越界时抛出 KeyError。已有索引的赋值尚未实现，修改它时直接给列表赋值，或替换整个列表。

## 从文件读取

普通数值、字符串和列表可以保存在 JSON 或 YAML 文件中：

```python
cfg = Config.fromfile("simulation.yaml")
```

Observation、Policy、Controller 等类对象在 Python 脚本中设置，见[配置层级示例](hierarchy.md#section-4-2)。`Config.fromfile()` 当前读取 `.py` 文件会在语法检查时抛出 `NameError`。完整方法与实现限制见 [Config 参考](../../reference/config.md)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：3.3 渲染后端示例](../rendering-backends.md) · [下一页：4.2 配置层级与优先级](hierarchy.md)
