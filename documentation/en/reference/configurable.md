<a id="chapter-6"></a>

<a id="api-9-1"></a>

# 6.1 Configurable

[简体中文](../../zh/reference/configurable.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.7 Config](config.md) · [Next: 6.2 Nameable](nameable.md)

Configuration, naming, randomness, and runtime lifecycle each have a base class. Objects with physical bodies inherit BaseObject; components needing only one of these capabilities can inherit the corresponding base class directly.

## Purpose and construction

Configurable manages configuration for component instances. Policies and physical objects need to retain, query, and update their parameters; this base class shares that mechanism while leaving field meanings to each component.

Pass a component dictionary to construct its internal Config. `get_config()` returns a deep copy by default, and `update_config()` merges new settings. Subclasses define the fields.

Source: [streetworld/base_class/configurable.py](../../../streetworld/base_class/configurable.py).

## Configuration

Supply configuration through the config constructor argument; no fixed application fields are defined.

## API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config: Union[Dict, Config]=None)` | `config`: component configuration dictionary | None | Creates an internal Config from the supplied dictionary or an empty dictionary. | Pass a dict or config.to_dict(). Although the signature includes Config, the internal Config(config) rejects a Config instance. |
| Instance method<br>`get_config(self, copy=True) -> Config` | `copy`: whether to return a deep `copy` | Config | With copy=True, returns a deep copy; False returns the internal configuration reference. | — |
| Instance method<br>`update_config(self, config: dict)` | `config`: component configuration dictionary | None | Merges the dictionary into the internal configuration. | Config.merge_from type/list restrictions apply; None also overrides existing values. |
| Instance method<br>`destroy(self)` | — | None | Sets the internal configuration reference to None. | — |
| Property getter<br>`config(self)` | — | Config or None | Returns the internal configuration object; None after destruction. | — |

## Example

```python
from streetworld.base_class.configurable import Configurable

component = Configurable({"limit": 3})
component.update_config({"limit": 5})
snapshot = component.get_config()
assert snapshot.limit == 5
component.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.7 Config](config.md) · [Next: 6.2 Nameable](nameable.md)
