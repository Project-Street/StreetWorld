<a id="api-9-3"></a>

# 6.3 Randomizable

[简体中文](../../zh/reference/randomizable.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.2 Nameable](nameable.md) · [Next: 6.4 BaseRunnable](base-runnable.md)

## Purpose and construction

Randomizable manages a component's random state. Scene selection, vehicle parameter sampling, and policy initialization may use randomness; each component gets its own generator and seed/reset interface for reproducible choices.

Construction takes a seed and stores a NumPy random generator and random_seed. Managers use `generate_seed()` to assign child seeds; `seed()` recreates the generator.

Source: [streetworld/base_class/randomizable.py](../../../streetworld/base_class/randomizable.py).

## Configuration

Set the seed through construction or seed(); no Config is needed.

## API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, random_seed)` | `random_seed`: random seed | None | Creates the random generator through get_np_random. | random_seed must be a nonnegative Python int or None; invalid input raises TypeError. |
| Instance method<br>`seed(self, random_seed)` | `random_seed`: random seed | None | Stores random_seed and rebuilds RandomState. | — |
| Instance method<br>`generate_seed(self)` | — | int | Samples an integer seed from [0, 65536). | — |
| Instance method<br>`destroy(self)` | — | None | Releases the random generator. | — |

## Example

```python
from streetworld.base_class.randomizable import Randomizable

rng = Randomizable(7)
first = rng.generate_seed()
rng.seed(7)
assert rng.generate_seed() == first
rng.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 6.2 Nameable](nameable.md) · [Next: 6.4 BaseRunnable](base-runnable.md)
