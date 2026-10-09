<a id="section-4-1"></a>

# 4.1 Using Config

[简体中文](../../../zh/guides/configuration/config.md)

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4. Configuration system](../configuration.md) · [Next: 4.2 Configuration hierarchy and precedence](hierarchy.md)

Testing AD policies involves selecting scenes, changing simulation timing, and sometimes replacing the ego Policy or camera settings. StreetWorld stores these settings in [Config](../../../../streetworld/config.py), which is passed when constructing Environment. The environment forwards the ego, participant, and observation settings to their components.

Config is a Python container for nested configuration dictionaries, with deep copying and merging. `Config()` stores the supplied values; it does not add environment defaults.

## Create a configuration and pass it to an environment

For example, select nuScenes scene `0007` and disable ego reverse drive:

```python
from streetworld.config import Config

cfg = Config({
    "scene_ids": ["0007"],
    "actor_config": {
        "controller_config": {"enable_reverse": False},
    },
})
```

Pass `cfg` as the environment's `config` argument, for example ScenarioEnv(`simulator`, `config`=`cfg`). Here `simulator` is a SimulatorInterface instance from [Chapter 3](../simulator-interface.md#section-3-2). See [3.1](../environment-interface.md#section-3-1) for a complete environment call example.

## Access, modify, and copy values

Config supports dictionary and attribute access. This example changes the scene list and enables reverse drive again:

```python
cfg["scene_ids"] = ["0007", "0008"]
cfg.actor_config.controller_config.enable_reverse = True
```

Use `copy()` to make an independent deep copy for another experiment. `to_dict()` converts the outermost container to a regular dictionary:

```python
independent = cfg.copy()
values = cfg.to_dict()
```

`to_dict()` does not copy nested values, which may still be ConfigDict instances. Missing fields raise KeyError with dictionary access and AttributeError with attribute access.

## Merge configurations with merge_from()

Launch scripts often modify a few fields in an existing configuration, such as changing control parameters while retaining scenes and cameras. `merge_from()` writes the new settings into the existing Config: supplied values replace matching fields, and other fields remain.

Nested dictionaries merge recursively. Dotted keys can also address nested fields directly. Both examples below disable ego reverse drive while retaining `scene_ids`:

```python
cfg.merge_from({"actor_config": {"controller_config": {"enable_reverse": False}}})
cfg.merge_from({"actor_config.controller_config.enable_reverse": False})
```

Lists and numeric values are replaced directly. For example, `image_layout` controls the interactive environment's camera layout; this change displays only the front camera:

```python
cfg.merge_from({"image_layout": [["FRONT"]]})
```

`replace_keys` selects fields to replace as a whole. For example, `replace_keys=["actor_config"]` replaces the entire ego configuration, removing omitted fields, so supply a complete ego configuration. This argument applies only at the current level and is not passed into recursive merges.

`allow_list_keys=True` permits numeric strings as list indices. An index equal to the list length appends; an out-of-range index raises KeyError. Assignment to an existing index is not implemented. Assign to the list directly or replace the whole list to change an existing entry.

## Load from a file

Save ordinary numeric values, strings, and lists in JSON or YAML:

```python
cfg = Config.fromfile("simulation.yaml")
```

Set class objects such as Observation, Policy, and Controller in Python scripts; see the [configuration hierarchy example](hierarchy.md#section-4-2). `Config.fromfile()` currently raises `NameError` when checking a `.py` file's syntax. See the [Config reference](../../reference/config.md) for all methods and implementation limitations.

---

[Contents](../../../DOCUMENTATION_EN.md) · [Previous: 4. Configuration system](../configuration.md) · [Next: 4.2 Configuration hierarchy and precedence](hierarchy.md)
