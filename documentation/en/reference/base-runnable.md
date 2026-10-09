<a id="api-9-4"></a>

# 6.4 BaseRunnable

[简体中文](../../zh/reference/base-runnable.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.3 Randomizable](randomizable.md) · [Next: 7. Policy Launcher appendix](../launchers/index.md)

## Purpose and construction

BaseRunnable defines a component lifecycle with configuration, naming, random parameter sampling, and step hooks. Components implementing reset, actions, or state management can reuse its initialization and cleanup.

Construction samples the class `PARAMETER_SPACE`, then applies caller configuration. Subclasses implement state and action operations; callers execute lifecycle hooks. Objects with physical bodies inherit [BaseObject](object.md#api-7-1) for body operations.

Source: [streetworld/base_class/base_runnable.py](../../../streetworld/base_class/base_runnable.py).

## Configuration

Subclasses define sampled parameters in PARAMETER_SPACE; config overrides them. BaseRunnable does not prescribe application fields.

## API

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

## Example

```python
from streetworld.base_class.base_runnable import BaseRunnable

obj = BaseRunnable(name="component", random_seed=7, config={"enabled": True})
print(obj.config.enabled)
print(obj.before_step())
obj.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.3 Randomizable](randomizable.md) · [Next: 7. Policy Launcher appendix](../launchers/index.md)
