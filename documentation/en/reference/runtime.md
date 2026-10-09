# 5.6 Runtime utilities

[简体中文](../../zh/reference/runtime.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.5 Object / Controller](object.md) · [Next: 5.7 Config](config.md)

See [configuration and example conventions](environment.md#reference-conventions).

On this page

- [5.6.1 StepCounter](#api-8-1)
- [5.6.2 PhysicsWorld](#api-8-2)

<a id="api-8-1"></a>

## 5.6.1 StepCounter

### Purpose and construction

StepCounter tracks simulation time and step counts. An environment step can contain several physics steps, so policy updates and trajectory replay need a common timeline. It converts physics steps to timestamps and environment steps, and `key_step` marks when a new action is due.

BaseEnv constructs it with the physics interval and repetition count, then sets the scene time range on reset(). Each physics step calls its `step()` to update the count; PhysicsWorld performs the actual integration.

Source: [streetworld/misc/step_counter.py](../../../streetworld/misc/step_counter.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `physics_world_step_size` | Number, µs | 20_000 (environment default) | Passed as step_size |
| `decision_repeat` | int, physics steps | 5 (environment default) | Passed as physical_repeat; must be positive |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, step_size, physical_repeat=0)` | `step_size`: physics interval in integer microseconds; `physical_repeat`: physics steps per environment step | None | Stores step_size and physical_repeat. | The constructor defaults to physical_repeat=0, so reading key_step or eposide_step divides by zero. Supply a positive value. |
| Instance method<br>`reset(self, timestamp_range, **kwargs)` | `timestamp_range`: start/end times in microseconds; `**kwargs`: keyword arguments | None | Stores the time range and resets physical_step to 0. | timestamp_range must contain at least start and end values. |
| Instance method<br>`step(self)` | — | None | Increments physical_step. | Does not check end_timestamp. |
| Property getter<br>`relative_timestamp(self)` | — | Number, µs | physical_step × step_size. | — |
| Property getter<br>`current_timestamp(self)` | — | Number, µs | begin_timestamp + relative_timestamp. | — |
| Property getter<br>`key_step(self)` | — | bool | True when physical_step is divisible by physical_repeat, including immediately after reset. | — |
| Property getter<br>`eposide_step(self)` | — | int | physical_step // physical_repeat; the property is spelled eposide_step. | — |

### Example

```python
from streetworld.misc.step_counter import StepCounter

counter = StepCounter(step_size=20_000, physical_repeat=5)
counter.reset(timestamp_range=[1_000_000, 2_000_000])
for _ in range(5):
    counter.step()
assert counter.relative_timestamp == 100_000
assert counter.eposide_step == 1
```

<a id="api-8-2"></a>

## 5.6.2 PhysicsWorld

### Purpose and construction

PhysicsWorld wraps Panda3D's BulletWorld for dynamics integration and collision/contact calculations. Vehicles, participants, and ground share this world so their motion and contact can be simulated together.

BaseEnv creates PhysicsWorld during construction. Vehicles and ground attach bodies to dynamic_world. Each physics step calls `step()` using the configured interval; gravity is (0, 0, -9.81).

Source: [streetworld/engine/physics_world.py](../../../streetworld/engine/physics_world.py).

### Configuration

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `physics_world_step_size` | Number, µs | 20_000 (environment default) | Passed explicitly by BaseEnv. The class default 0.01 is also interpreted as microseconds, equivalent to 1e-8 s |
| substep (constructor argument) | Positive integer | `1` | Maximum Bullet doPhysics substeps; BaseEnv has no corresponding Config field |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, physics_world_step_size=0.01, substep: int=1)` | `physics_world_step_size`: physics interval in microseconds; `substep`: maximum substeps per Bullet update | None | Creates BulletWorld, sets gravity, and stores the microsecond interval and substep count. | — |
| Instance method<br>`destroy(self)` | — | None | Clears debug nodes and contact/filter callbacks, then releases the world reference. | Managers must destroy their objects first; step cannot be called afterward. |
| Instance method<br>`step(self)` | — | None | Advances Bullet by step_size_sec with a fixed substep interval of step_size_sec/substep. | substep=0 causes division by zero; Environment uses 1. |
| Property getter<br>`step_size_sec(self)` | — | Number, seconds | physics_world_step_size × 1e-6. | — |

### Example

```python
from streetworld.engine.physics_world import PhysicsWorld

world = PhysicsWorld(physics_world_step_size=20_000, substep=1)
world.step()
assert world.step_size_sec == 0.02
world.destroy()
```

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.5 Object / Controller](object.md) · [Next: 5.7 Config](config.md)
