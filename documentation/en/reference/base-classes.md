<a id="chapter-6"></a>

# 6. Base classes

[简体中文](../../zh/reference/base-classes.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.7 Config](config.md) · [Next: 7. Policy Launcher appendix](../launchers/index.md)

On this page

- [6.1 Configurable](#api-9-1)
- [6.2 Nameable](#api-9-2)
- [6.3 Randomizable](#api-9-3)
- [6.4 BaseRunnable](#api-9-4)

Configuration, naming, randomness, and runtime lifecycle each have a base class. Objects with physical bodies inherit BaseObject; components needing only one of these capabilities can inherit the corresponding base class directly.

<a id="api-9-1"></a>

## 6.1 Configurable

### Purpose and construction

Configurable manages configuration for component instances. Policies and physical objects need to retain, query, and update their parameters; this base class shares that mechanism while leaving field meanings to each component.

Pass a component dictionary to construct its internal Config. `get_config()` returns a deep copy by default, and `update_config()` merges new settings. Subclasses define the fields.

Source: [streetworld/base_class/configurable.py](../../../streetworld/base_class/configurable.py).

### Configuration

Supply configuration through the config constructor argument; no fixed application fields are defined.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config: Union[Dict, Config]=None)` | `config`: component configuration dictionary | None | Creates an internal Config from the supplied dictionary or an empty dictionary. | Pass a dict or config.to_dict(). Although the signature includes Config, the internal Config(config) rejects a Config instance. |
| Instance method<br>`get_config(self, copy=True) -> Config` | `copy`: whether to return a deep `copy` | Config | With copy=True, returns a deep copy; False returns the internal configuration reference. | — |
| Instance method<br>`update_config(self, config: dict)` | `config`: component configuration dictionary | None | Merges the dictionary into the internal configuration. | Config.merge_from type/list restrictions apply; None also overrides existing values. |
| Instance method<br>`destroy(self)` | — | None | Sets the internal configuration reference to None. | — |
| Property getter<br>`config(self)` | — | Config or None | Returns the internal configuration object; None after destruction. | — |

### Example

```python
from streetworld.base_class.configurable import Configurable

component = Configurable({"limit": 3})
component.update_config({"limit": 5})
snapshot = component.get_config()
assert snapshot.limit == 5
component.destroy()
```

<a id="api-9-2"></a>

## 6.2 Nameable

### Purpose and construction

Nameable provides object names and IDs for registration, cleanup, and logging. It uses consistent `name` and `id` fields so Managers and callers can identify instances.

Pass `name` at construction, or omit it to generate a UUID string. `id` equals `name`; `rename()` updates both.

Source: [streetworld/base_class/nameable.py](../../../streetworld/base_class/nameable.py).

### Configuration

The name constructor argument sets the name; no Config is needed.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, name=None)` | `name`: instance `name`; generated automatically when None | None | Sets name and id=name. | — |
| Instance method<br>`rename(self, new_name)` | `new_name`: replacement instance name | None | Replaces name and id together. | — |
| Instance method<br>`destroy(self)` | — | None | Sets name and id to None. | — |
| Property getter<br>`class_name(self)` | — | str | Returns the actual instance class name. | — |

### Example

```python
from streetworld.base_class.nameable import Nameable

obj = Nameable("actor")
obj.rename("ego")
assert obj.name == obj.id == "ego"
obj.destroy()
```

<a id="api-9-3"></a>

## 6.3 Randomizable

### Purpose and construction

Randomizable manages a component's random state. Scene selection, vehicle parameter sampling, and policy initialization may use randomness; each component gets its own generator and seed/reset interface for reproducible choices.

Construction takes a seed and stores a NumPy random generator and random_seed. Managers use `generate_seed()` to assign child seeds; `seed()` recreates the generator.

Source: [streetworld/base_class/randomizable.py](../../../streetworld/base_class/randomizable.py).

### Configuration

Set the seed through construction or seed(); no Config is needed.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, random_seed)` | `random_seed`: random seed | None | Creates the random generator through get_np_random. | random_seed must be a nonnegative Python int or None; invalid input raises TypeError. |
| Instance method<br>`seed(self, random_seed)` | `random_seed`: random seed | None | Stores random_seed and rebuilds RandomState. | — |
| Instance method<br>`generate_seed(self)` | — | int | Samples an integer seed from [0, 65536). | — |
| Instance method<br>`destroy(self)` | — | None | Releases the random generator. | — |

### Example

```python
from streetworld.base_class.randomizable import Randomizable

rng = Randomizable(7)
first = rng.generate_seed()
rng.seed(7)
assert rng.generate_seed() == first
rng.destroy()
```

<a id="api-9-4"></a>

## 6.4 BaseRunnable

### Purpose and construction

BaseRunnable defines a component lifecycle with configuration, naming, random parameter sampling, and step hooks. Components implementing reset, actions, or state management can reuse its initialization and cleanup.

Construction samples the class `PARAMETER_SPACE`, then applies caller configuration. Subclasses implement state and action operations; callers execute lifecycle hooks. Objects with physical bodies inherit [BaseObject](object.md#api-7-1) for body operations.

Source: [streetworld/base_class/base_runnable.py](../../../streetworld/base_class/base_runnable.py).

### Configuration

Subclasses define sampled parameters in PARAMETER_SPACE; config overrides them. BaseRunnable does not prescribe application fields.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, name=None, random_seed=None, config=None)` | `name`: instance `name`, generated when None; `random_seed`: random seed; `config`: component configuration dictionary | None | Initializes naming, randomness, and configuration; samples PARAMETER_SPACE, then merges config. | PARAMETER_SPACE must be a ParameterSpace, otherwise AssertionError is raised. Caller values, including None, override matching sampled values. |
| Instance method<br>`get_state(self) -> Dict` | — | dict, implemented by subclasses | Exports state; implemented by subclasses. | The base implementation raises NotImplementedError. |
| Instance method<br>`set_state(self, state: Dict)` | `state`: `state` dictionary to restore | None | Restores state; implemented by subclasses. | The base implementation raises NotImplementedError. |
| Instance method<br>`before_step(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Pre-step extension hook; the base implementation returns {}. | — |
| Instance method<br>`set_action(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | None | Sets actions; implemented by subclasses. | The base implementation raises NotImplementedError. |
| Instance method<br>`step(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Simulation advancement hook; the base implementation returns {}. | — |
| Instance method<br>`after_step(self, *args, **kwargs)` | `*args`: positional arguments; `**kwargs`: keyword arguments | dict | Post-step extension hook; the base implementation returns {}. | — |
| Instance method<br>`reset(self, random_seed=None, *args, **kwargs)` | `random_seed`: random seed; `*args`: positional arguments; `**kwargs`: keyword arguments | None | Calls the actual instance's __init__ again with random_seed and the remaining arguments. | Supply all arguments required by the subclass constructor; this invokes construction again. |
| Instance method<br>`sample_parameters(self)` | — | None | Generates a sampling seed, reseeds the class parameter space, and merges sampled parameters into configuration. | — |
| Instance method<br>`destroy(self)` | — | None | Clears configuration, random state, names, and the PARAMETER_SPACE random generator. | — |

### Example

```python
from streetworld.base_class.base_runnable import BaseRunnable

obj = BaseRunnable(name="component", random_seed=7, config={"enabled": True})
print(obj.config.enabled)
print(obj.before_step())
obj.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.7 Config](config.md) · [Next: 7. Policy Launcher appendix](../launchers/index.md)
