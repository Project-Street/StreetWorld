<a id="api-9-2"></a>

# 6.2 Nameable

[简体中文](../../zh/reference/nameable.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.1 Configurable](configurable.md) · [Next: 6.3 Randomizable](randomizable.md)

## Purpose and construction

Nameable provides object names and IDs for registration, cleanup, and logging. It uses consistent `name` and `id` fields so Managers and callers can identify instances.

Pass `name` at construction, or omit it to generate a UUID string. `id` equals `name`; `rename()` updates both.

Source: [streetworld/base_class/nameable.py](../../../streetworld/base_class/nameable.py).

## Configuration

The name constructor argument sets the name; no Config is needed.

## API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, name=None)` | `name`: instance `name`; generated automatically when None | None | Sets name and id=name. | — |
| Instance method<br>`rename(self, new_name)` | `new_name`: replacement instance name | None | Replaces name and id together. | — |
| Instance method<br>`destroy(self)` | — | None | Sets name and id to None. | — |
| Property getter<br>`class_name(self)` | — | str | Returns the actual instance class name. | — |

## Example

```python
from streetworld.base_class.nameable import Nameable

obj = Nameable("actor")
obj.rename("ego")
assert obj.name == obj.id == "ego"
obj.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.1 Configurable](configurable.md) · [Next: 6.3 Randomizable](randomizable.md)
