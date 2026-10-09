<a id="api-3-1"></a>

# 5.7 Config

[简体中文](../../zh/reference/config.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.6 Runtime utilities](runtime.md) · [Next: 6.1 Configurable](configurable.md)

[Class index: Config](#api-3-1)

## Purpose and construction

Config stores and merges StreetWorld settings. Environment, Agent, Observer, and Policy parameters live at different levels; attribute access and dotted paths let users override selected fields in a default configuration.

Construct it from a dictionary or load JSON/YAML with Config.fromfile(). Python file loading currently raises NameError, as detailed below. Components define field meanings, required values, and conditions; Config does not validate component parameters. Components read them during construction or reset().

Source: [streetworld/config.py](../../../streetworld/config.py).

## Configuration

cfg_dict and kwargs specify the stored configuration; Config has no additional application parameters.

## API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, cfg_dict: Union[Dict, None]=None, **kwargs)` | `cfg_dict`: initial dictionary; `kwargs`: additional settings | None | Creates configuration from cfg_dict; matching kwargs override its values. | A cfg_dict that is neither dict nor None raises TypeError. Config instances are not dicts. |
| Instance method<br>`keys(self)` | — | dict_keys | Returns a view of top-level keys. | — |
| Instance method<br>`values(self)` | — | dict_values | Returns a view of top-level values; nested objects retain their identity. | — |
| Instance method<br>`items(self)` | — | dict_items | Returns a view of top-level key/value pairs. | — |
| Instance method<br>`get(self, key, default=None)` | `key`: configuration `key`; `default`: value for a missing `key` | Any configuration value | Queries a top-level key; does not resolve dotted paths. | — |
| Instance method<br>`copy(self)` | — | Config | Deep-copies configuration contents. | Does not copy filename metadata. |
| Instance method<br>`merge_from(self, options: Dict, allow_list_keys: bool=True, replace_keys: list=None)` | `options`: override dictionary; `allow_list_keys`: enable numeric indices; `replace_keys`: fields to replace entirely at this level | None | Merges options in place; supports dotted paths, recursive dictionary merges, and whole-field replacement at the specified level. | Incompatible structures such as a dictionary overriding a scalar raise TypeError. Out-of-range list indices raise KeyError. Assignment to existing list indices is not implemented. |
| Instance method<br>`to_dict(self)` | — | dict | Converts the outermost container; nested containers are shared with the original. | — |
| Class method<br>`fromfile(cls, filename: str)` | `filename`: configuration file path | Config | Reads YAML, YML, or JSON into a configuration dictionary. | Missing files raise FileNotFoundError; unsupported extensions raise OSError. Python syntax checking references ast outside its scope and raises NameError. |
| Property getter<br>`filename(self)` | — | str or None | Reads _filename; returns None if absent. | fromfile assigns cfg.filename through __setattr__, which writes a configuration key and usually leaves this property unset. |
| Property setter<br>`filename(self, value)` | `value`: `value` to set | None | Sets _filename. | cfg.filename = value bypasses the setter and writes filename as a configuration key. |

## Example

```python
from streetworld.config import Config

cfg = Config({"actor_config": {"warmup_step": None}})
cfg.merge_from({"actor_config.warmup_step": 10})
snapshot = cfg.copy()
assert snapshot.actor_config.warmup_step == 10
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.6 Runtime utilities](runtime.md) · [Next: 6.1 Configurable](configurable.md)
