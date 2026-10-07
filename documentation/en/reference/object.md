# 5.5 Object / Controller

[简体中文](../../zh/reference/object.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.4 Policy](policy.md) · [Next: 5.6 Runtime utilities](runtime.md)

See [API reference contents](index.md) for configuration paths and example variables.

On this page

- [5.5.1 BaseObject](#api-7-1)
- [5.5.2 BaseVehicle](#api-7-2)
- [5.5.3 DefaultVehicle](#api-7-3)
- [5.5.4 XLVehicle](#api-7-4)
- [5.5.5 LVehicle](#api-7-5)
- [5.5.6 MVehicle](#api-7-6)
- [5.5.7 SVehicle](#api-7-7)
- [5.5.8 BaseTrafficParticipant](#api-7-8)
- [5.5.9 Pedestrian](#api-7-9)
- [5.5.10 Cyclist](#api-7-10)
- [5.5.11 GroundPlane](#api-7-11)
- [5.5.12 MeshTerrain](#api-7-12)
- [5.5.13 Object module functions](#section-5-5-13)

<a id="api-7-1"></a>

## 5.5.1 BaseObject

### Purpose and construction

BaseObject is the base class for scene objects with physical bodies. Vehicles, participants, and ground need common pose/motion operations and attachment to a physics world; these operations let Managers, Observations, and collision checks work across object types.

It adds `body` operations to BaseRunnable's configuration, naming, and random state. `transform` maps object coordinates to world coordinates, and velocity is in world coordinates. Subclasses create `body`; constructing BaseObject directly does not create a controllable body.

Source: [streetworld/objects/base_object.py](../../../streetworld/objects/base_object.py).

### Configuration

Pass size, name, random_seed, and physics_world through the constructor. Subclasses define physical parameters in PARAMETER_SPACE and Config; BaseObject has no fixed fields.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, physics_world, size=None, name=None, random_seed=None, config=None, escape_random_seed_assertion=False)` | `physics_world`: PhysicsWorld instance; `size`: length/width/height in meters; `name`: instance `name`, generated when None; `random_seed`: random seed; `config`: component configuration; `escape_random_seed_assertion`: skip the non-None seed assertion | None | Initializes configuration, naming, and randomness; stores PhysicsWorld and optional dimensions, with body=None. | Normally requires a non-None random_seed or raises AssertionError. size must be a three-element sequence supporting a truth-value test. |
| Instance method<br>`destroy(self)` | — | None | Performs BaseRunnable configuration, naming, and random-state cleanup. | Does not detach body itself; physical subclasses must do so. |
| Instance method<br>`set_position(self, position)` | `position`: world `position` in meters | None | Sets body world position while preserving rotation. | Requires three components; other lengths raise AssertionError. |
| Instance method<br>`set_heading_theta(self, heading_theta, to_deg=True) -> None` | `heading_theta`: vehicle heading in radians by default; `to_deg`: convert radians to Panda3D degrees when True | None | Sets horizontal heading, converts vehicle +X forward to Panda3D +Y forward, and preserves pitch/roll. | — |
| Instance method<br>`set_transform(self, m)` | `m`: 4×4 vehicle-to-world homogeneous transform | None | Converts the vehicle-coordinate matrix to a Panda3D body transform. | — |
| Instance method<br>`set_velocity(self, velocity)` | `velocity`: world linear `velocity` in m/s | None | Stores previous velocity and sets body velocity; two components retain the current Z velocity. | — |
| Instance method<br>`set_angular_velocity(self, angular_velocity, in_rad=True)` | `angular_velocity`: Z-axis angular velocity in rad/s by default; `in_rad`: whether input uses radians | None | Stores previous angular velocity and sets Z-axis angular velocity; in_rad=False converts degrees/s to rad/s. | — |
| Instance method<br>`rename(self, new_name)` | `new_name`: replacement instance name | None | Updates instance name/id and body name together. | Requires an existing body. |
| Instance method<br>`attachDyWld(self, obj=None)` | `obj`: Bullet node to use, or the object's body when None | None | Attaches the specified node or body to the dynamic Bullet world. | — |
| Instance method<br>`detachDyWld(self, obj=None)` | `obj`: Bullet node to use, or the object's body when None | None | Removes the specified node or body from the dynamic Bullet world. | — |
| Instance method<br>`set_kinematic(self, is_kinematic)` | `is_kinematic`: whether to enable a kinematic body | None | Sets the Bullet kinematic flag; enabling it also clears active/static flags. | — |
| Property getter<br>`position(self)` | — | Panda3D 3D vector, meters | Returns body world position. | — |
| Property getter<br>`heading_theta(self)` | — | float, rad | Converts Panda3D heading to vehicle heading and wraps to [-π, π]. | — |
| Property getter<br>`transform(self)` | — | float32 ndarray(4,4) | Returns the vehicle-to-world homogeneous transform. | — |
| Property getter<br>`velocity(self)` | — | ndarray(3,), m/s | Returns body linear velocity in world coordinates. | — |
| Property getter<br>`angular_velocity(self)` | — | float, rad/s | Returns body Z-axis angular velocity. | — |
| Property getter<br>`angular_acceleration(self)` | — | float, rad/s² | Difference from last_angular_velocity divided by the physics interval. | — |
| Property getter<br>`acceleration(self)` | — | ndarray(3,), m/s² | Returns total Bullet force divided by body mass. | Not applicable to zero-mass static objects; not estimated from velocity changes. |
| Property getter<br>`speed(self)` | — | float, m/s | Horizontal speed magnitude, clipped to [0, 100000]. | — |
| Property getter<br>`speed_km_h(self)` | — | float, km/h | speed × 3.6. | — |
| Property getter<br>`heading(self)` | — | (cosθ, sinθ) | Returns the 2D heading unit vector in world coordinates. | — |

### Example

```python
# The environment is already reset; its Controller inherits the BaseObject pose and motion interface.
controller = env.actor_controller
print(controller.transform)
print(controller.position, controller.heading_theta, controller.speed)
```

<a id="api-7-2"></a>

## 5.5.2 BaseVehicle

### Purpose and construction

BaseVehicle applies Policy steering and throttle/brake commands to a Bullet vehicle model. Dynamics produce subsequent poses and velocities; vehicle subclasses share this control implementation while changing physical parameters.

AgentManager creates the vehicle selected by controller. The model has a box chassis and four wheels; subclasses define dimensions, mass, tire radius, and axle offsets. Usually select [DefaultVehicle](#api-7-3) or S/M/L/XLVehicle.

Source: [streetworld/objects/vehicle/base_vehicle.py](../../../streetworld/objects/vehicle/base_vehicle.py).

### Configuration

The table uses ego paths; surrounding vehicles use participant_config.controller_config. Environment defaults provide enable_reverse, spawn_velocity, and check_crash_world; BaseVehicle does not fill in missing fields.

| Field | Type and unit | Default | Purpose and conditions |
| --- | --- | --- | --- |
| `actor_config.controller_config.size` | Three-element sequence or None, meters | `None` | Extracted by Manager and passed to construction; None uses class dimensions |
| `actor_config.controller_config.enable_reverse` | bool | `True` | With True, negative input applies reverse engine force; with False, it brakes and uses a low-speed dead zone |
| `actor_config.controller_config.spawn_velocity` | bool | `True` | Writes recorded spawn linear/angular velocities during reset |
| `actor_config.controller_config.max_acceleration` | float, m/s² | 15.0 for ego; omitted for surrounding vehicles by default | Limits horizontal velocity changes from the previous physics step; runs only when present, and must be positive |
| `actor_config.controller_config.check_crash_world` | bool | `False` | Checks whether ground contact points are above nearby wheels; uses CUDA |
| `actor_config.controller_config.max_steering` | Number, degrees | Sampled by the vehicle class | Maximum wheel angle for normalized steering; caller settings override sampled values |
| `actor_config.controller_config.max_engine_force` | Number, Bullet force parameter | Sampled by the vehicle class | Maximum engine force per wheel; caller settings override sampled values |
| `actor_config.controller_config.max_brake_force` | Number, Bullet brake parameter | Sampled by the vehicle class | Maximum brake input per wheel, interpreted as a Bullet brake parameter |
| `actor_config.controller_config.max_speed_km_h` | Number, km/h | 80 (vehicle class default) | Stops applying forward engine force above the speed limit |
| `actor_config.controller_config.wheel_friction` | Number | Sampled by the vehicle class | Wheel creation always calls setFrictionSlip(0.5); this field is inactive |

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config: Union[dict, Config], physics_world, size=None, name: str=None, random_seed=None, position=None, heading_theta=None, _calling_reset=True, **kwargs)` | `config`: component configuration; `physics_world`: PhysicsWorld; `size`: length/width/height in meters; `name`: generated when None; `random_seed`: random seed; `position`: world `position` in meters; `heading_theta`: heading in radians by default; `_calling_reset`: call reset after construction; `**kwargs`: keyword arguments | None | Creates chassis/wheels and reads powertrain parameters; calls reset immediately by default. | config must not be None. BaseVehicle itself lacks concrete vehicle constants. Supply valid position and spawn velocities. |
| Instance method<br>`attachDyWld(self)` | — | None | Attaches both chassis body and BulletVehicle to the dynamic world. | — |
| Instance method<br>`detachDyWld(self)` | — | None | Removes BulletVehicle, then chassis body. | — |
| Instance method<br>`reset(self, name=None, random_seed=None, position: np.ndarray=None, heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, *args, **kwargs)` | `name`: generated when None; `random_seed`: random seed; `position`: world `position` in meters; `heading_theta`: heading in radians by default; `velocity`: world linear `velocity` in m/s; `angular_velocity`: Z-axis angular `velocity` in rad/s by default; `*args`: positional arguments; `**kwargs`: keyword arguments | None | Optionally renames/reseeds, resets heading/position, applies spawn velocities when enabled, and clears collision flags. | position is required; velocity is required with spawn_velocity=True. A non-int random_seed raises AssertionError. |
| Instance method<br>`move(self, action=None)` | `action`: external input in the current Policy's format | Control diagnostic dictionary or None | A recorded-state dictionary containing transform/velocity/angular_velocity restores state directly. Otherwise clips control, updates force and steering, and stores the action. | action=None raises TypeError during the membership check. Control mode requires a two-element sequence. |
| Instance method<br>`check_crash_world(self)` | — | None | When enabled, compares contact points to the nearest wheel height and sets crash_world on a hit. | Uses CUDA tensor calculations when contact points exist. |
| Instance method<br>`destroy(self)` | — | None | Performs base cleanup, removes vehicle/chassis, and clears physics references. | — |
| Instance method<br>`set_position(self, position)` | `position`: world `position` in meters | None | Sets three components directly; for a two-element list, appends current Z before setting position. | Two-element NumPy arrays have no append and fail in this branch. Use a full three-component position. |
| Instance method<br>`get_steering_wheel_angle(self)` | — | Wheel angle, radians | steering × max_steering × π/180. | — |
| Instance method<br>`get_longitudinal_acceleration(self)` | — | ndarray(2,) | Returns elementwise multiplication of acceleration[:2] and the 2D heading. | Does not compute a scalar longitudinal acceleration dot product. |
| Property getter<br>`current_action(self)` | — | Two-element control input | Returns the most recent action stored by control-mode move. | The replay branch does not update this queue. |
| Property getter<br>`max_speed_km_h(self)` | — | Configuration value, km/h | Returns max_speed_km_h. | — |

Vehicles sample physical parameters from their class PARAMETER_SPACE, then apply controller_config overrides. The table lists class defaults and sampling ranges. Force fields follow Bullet conventions.

| Vehicle class | Length/width/height, meters | Mass, kg | Maximum wheel angle, degrees | max_engine_force range | max_brake_force range |
| --- | --- | --- | --- | --- | --- |
| DefaultVehicle | 4.515 / 1.852 / 1.19 | 1000 | 40 | 750–850 | 80–120 |
| XLVehicle | 5.74 / 2.3 / 2.8 | 1600 | 35 | 500–700 | 50–100 |
| LVehicle | 4.87 / 2.046 / 1.85 | 1300 | 40 | 450–650 | 60–120 |
| MVehicle | 4.6 / 1.85 / 1.37 | 1200 | 45 | 650–850 | 60–150 |
| SVehicle | 4.3 / 1.7 / 1.7 | 800 | 50 | 350–550 | 35–80 |

The vehicle class also sets tire radius and axle offsets. Control values are clipped to [-1, 1]. With enable_reverse=True, negative throttle_brake can drive backward; consider whether your trajectory model expects stopping or reversing.

### Example

```python
from streetworld.engine.physics_world import PhysicsWorld
from streetworld.objects.vehicle.vehicle_type import DefaultVehicle

world = PhysicsWorld(physics_world_step_size=20_000)
vehicle = DefaultVehicle(config={"enable_reverse": False,
    "spawn_velocity": True, "check_crash_world": False}, physics_world=world,
    random_seed=7, position=[0.0, 0.0, 1.0], heading_theta=0.0,
    velocity=[0.0, 0.0, 0.0])
vehicle.attachDyWld()
vehicle.move([0.0, 0.2])
world.step()
vehicle.destroy()
world.destroy()
```

<a id="api-7-3"></a>

## 5.5.3 DefaultVehicle

### Purpose and construction

DefaultVehicle is the default ego Controller with a fixed vehicle parameter preset. It uses [BaseVehicle](#api-7-2) control and dynamics for running examples or comparing AD policies with the same vehicle.

Select it with `actor_config.controller`; AgentManager constructs it. Default dimensions are 4.515 / 1.852 / 1.19 m, mass 1000 kg, tire radius 0.313 m, and front/rear axle offsets 1.05234 / 1.4166 m.

Source: [streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py).

### Configuration

See [BaseVehicle](#api-7-2) for configuration and actions. controller_config.size overrides dimensions; no additional fields are defined.

### API

Interfaces are inherited from [BaseVehicle](#api-7-2).

### Example

```python
from streetworld.objects.vehicle.vehicle_type import DefaultVehicle

cfg.merge_from({"actor_config.controller": DefaultVehicle})
```

<a id="api-7-4"></a>

## 5.5.4 XLVehicle

### Purpose and construction

XLVehicle is the largest vehicle preset, with a larger body and higher mass. It uses [BaseVehicle](#api-7-2) control; selecting it as Controller allows studies of how vehicle parameters affect driving.

AgentManager constructs it from configuration. Default dimensions are 5.74 / 2.3 / 2.8 m, mass 1600 kg, tire radius 0.37 m, and front/rear axle offsets 1.726 / 1.075 m.

Source: [streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py).

### Configuration

See [BaseVehicle](#api-7-2) for configuration and actions. controller_config.size overrides dimensions; no additional fields are defined.

### API

Interfaces are inherited from [BaseVehicle](#api-7-2).

### Example

```python
from streetworld.objects.vehicle.vehicle_type import XLVehicle

cfg.merge_from({"actor_config.controller": XLVehicle})
```

<a id="api-7-5"></a>

## 5.5.5 LVehicle

### Purpose and construction

LVehicle supplies the large vehicle's chassis, mass, and wheel parameters, with a larger default body than MVehicle. It shares [BaseVehicle](#api-7-2) dynamics and actions and can control ego or surrounding vehicles.

AgentManager creates it. Default dimensions are 4.87 / 2.046 / 1.85 m, mass 1300 kg, tire radius 0.429 m, and front/rear axle offsets 1.5301 / 1.218261 m.

Source: [streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py).

### Configuration

See [BaseVehicle](#api-7-2) for configuration and actions. controller_config.size overrides dimensions; no additional fields are defined.

### API

Interfaces are inherited from [BaseVehicle](#api-7-2).

### Example

```python
from streetworld.objects.vehicle.vehicle_type import LVehicle

cfg.merge_from({"actor_config.controller": LVehicle})
```

<a id="api-7-6"></a>

## 5.5.6 MVehicle

### Purpose and construction

MVehicle supplies a medium-sized body and wheel parameter preset. Select it to change physical parameters while retaining the [BaseVehicle](#api-7-2) control interface.

AgentManager creates it from Controller configuration. Default dimensions are 4.6 / 1.85 / 1.37 m, mass 1200 kg, tire radius 0.39 m, and front/rear axle offsets 1.285 / 1.203 m.

Source: [streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py).

### Configuration

See [BaseVehicle](#api-7-2) for configuration and actions. controller_config.size overrides dimensions; no additional fields are defined.

### API

Interfaces are inherited from [BaseVehicle](#api-7-2).

### Example

```python
from streetworld.objects.vehicle.vehicle_type import MVehicle

cfg.merge_from({"actor_config.controller": MVehicle})
```

<a id="api-7-7"></a>

## 5.5.7 SVehicle

### Purpose and construction

SVehicle represents smaller, lighter vehicles. It uses [BaseVehicle](#api-7-2) dynamics and control so the same Policies can operate this vehicle preset.

AgentManager creates it from configuration. Default dimensions are 4.3 / 1.7 / 1.7 m, mass 800 kg, tire radius 0.376 m, and front/rear axle offsets 1.385 / 1.11 m.

Source: [streetworld/objects/vehicle/vehicle_type.py](../../../streetworld/objects/vehicle/vehicle_type.py).

### Configuration

See [BaseVehicle](#api-7-2) for configuration and actions. controller_config.size overrides dimensions; no additional fields are defined.

### API

Interfaces are inherited from [BaseVehicle](#api-7-2).

### Example

```python
from streetworld.objects.vehicle.vehicle_type import SVehicle

cfg.merge_from({"actor_config.controller": SVehicle})
```

<a id="api-7-8"></a>

## 5.5.8 BaseTrafficParticipant

### Purpose and construction

BaseTrafficParticipant represents pedestrians and cyclists with physical bodies. These participants usually replay recorded tracks, but collision checking still needs their dimensions and poses. The class provides box bodies and recorded-state restoration.

Subclasses set `MASS` and TYPE_NAME. BaseEnv selects them from scene metadata, and AgentManager constructs them. During replay, `move()` applies the recorded `transform` and linear/angular velocities to the body.

Source: [streetworld/objects/traffic_participants/base_traffic_participant.py](../../../streetworld/objects/traffic_participants/base_traffic_participant.py).

### Configuration

BaseEnv reads constructor inputs such as size, position, and velocity from scene metadata. No additional fields are defined; BaseRunnable configuration operations remain available.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, config, physics_world, size, position: Sequence[float], heading_theta: float=0.0, velocity: np.ndarray=None, angular_velocity: float=0.0, random_seed=None, name=None, **kwargs)` | `config`: component configuration; `physics_world`: PhysicsWorld; `size`: length/width/height in meters; `position`: world `position` in meters; `heading_theta`: heading in radians by default; `velocity`: world linear `velocity` in m/s; `angular_velocity`: Z-axis angular `velocity` in rad/s by default; `random_seed`: random seed; `name`: generated when None; `**kwargs`: keyword arguments | None | Creates a collision box from size, sets pose and linear/angular velocities, and assigns the object type. | size, position, and velocity must be valid sequences. Subclasses must define MASS/TYPE_NAME; the BaseObject seed assertion applies. |
| Instance method<br>`reset(self, position: Sequence[float], heading_theta: float=0.0, random_seed=None, name=None, *args, **kwargs)` | `position`: world `position` in meters; `heading_theta`: heading in radians by default; `random_seed`: random seed; `name`: generated when None; `*args`: positional arguments; `**kwargs`: keyword arguments | None | Does nothing. | position/name/seed arguments do not modify the existing object. |
| Instance method<br>`move(self, state_info)` | `state_info`: recorded state dictionary with transform, velocity, and angular_velocity | None | Restores transform, velocity, and angular_velocity from state_info. | Does not accept two-element vehicle controls; missing fields raise KeyError. |
| Instance method<br>`destroy(self)` | — | None | After base cleanup, removes body from the dynamic world and clears its reference. | — |

### Example

```python
# The environment creates pedestrians and cyclists from participants metadata.
for manager in env.agent_managers.values():
    if manager.controller is not None:
        print(manager.controller.metadrive_type)
```

<a id="api-7-9"></a>

## 5.5.9 Pedestrian

### Purpose and construction

Pedestrian replays pedestrian motion and lets collision checking identify vehicle/pedestrian contacts. It uses [BaseTrafficParticipant](#api-7-8) box bodies and state restoration.

BaseEnv selects it for metadata type `pedestrian`; AgentManager creates it with ReplayPolicy and DummyObservation. Mass is 70 kg, type is `MetaDriveType.PEDESTRIAN`, and dimensions come from scene metadata.

Source: [streetworld/objects/traffic_participants/pedestrian.py](../../../streetworld/objects/traffic_participants/pedestrian.py).

### Configuration

See [BaseTrafficParticipant](#api-7-8) for constructor and motion inputs; no additional fields are defined.

### API

Interfaces are inherited from [BaseTrafficParticipant](#api-7-8).

### Example

```python
from streetworld.objects.traffic_participants.pedestrian import Pedestrian

# The environment is already reset and uses ReplayPolicy for this participant type.
objects = [m.controller for m in env.agent_managers.values()
           if isinstance(m.controller, Pedestrian)]
print(len(objects))
```

<a id="api-7-10"></a>

## 5.5.10 Cyclist

### Purpose and construction

Cyclist adds recorded cyclists to traffic replay and vehicle collision checking. It updates pose and velocity through [BaseTrafficParticipant](#api-7-8) state restoration.

BaseEnv selects it for metadata type `cyclist`; AgentManager creates it with ReplayPolicy and DummyObservation. Mass is 80 kg, type is `MetaDriveType.CYCLIST`, and dimensions come from scene metadata.

Source: [streetworld/objects/traffic_participants/cyclist.py](../../../streetworld/objects/traffic_participants/cyclist.py).

### Configuration

See [BaseTrafficParticipant](#api-7-8) for constructor and motion inputs; no additional fields are defined.

### API

Interfaces are inherited from [BaseTrafficParticipant](#api-7-8).

### Example

```python
from streetworld.objects.traffic_participants.cyclist import Cyclist

# The environment is already reset and uses ReplayPolicy for this participant type.
objects = [m.controller for m in env.agent_managers.values()
           if isinstance(m.controller, Cyclist)]
print(len(objects))
```

<a id="api-7-11"></a>

## 5.5.11 GroundPlane

### Purpose and construction

GroundPlane supplies road support and tire contact through an infinite static plane. Use it for scenes where planar terrain is sufficient.

When `scene_mesh_path` is absent, BaseEnv constructs it from ScenarioDataManager's `normal`/constant. Construction creates a static Bullet plane and attaches it to PhysicsWorld.

Source: [streetworld/objects/terrain/ground.py](../../../streetworld/objects/terrain/ground.py).

### Configuration

direction sets the plane normal; constant is the Bullet plane constant, defaulting to 0. Environment reads them from metadata.ground_plane; no separate Config fields are defined.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, physics_world, direction: Sequence[float], constant: float=0.0, random_seed=None, name=None, config=None, **kwargs)` | `physics_world`: PhysicsWorld; `direction`: three-component plane normal; `constant`: BulletPlaneShape plane `constant` in meters; `random_seed`: random seed; `name`: generated when None; `config`: component configuration; `**kwargs`: keyword arguments | None | Creates a static BulletPlaneShape from direction/constant, sets friction to 0.4, and attaches it. | — |
| Instance method<br>`reset(self, random_seed=None, name=None, *args, **kwargs)` | `random_seed`: random seed; `name`: generated when None; `*args`: positional arguments; `**kwargs`: keyword arguments | None | Does nothing; Environment destroys and rebuilds ground when switching scenes. | — |
| Instance method<br>`destroy(self)` | — | None | Performs base cleanup and removes the plane body. | — |

### Example

```python
from streetworld.objects.terrain.ground import GroundPlane

# world is an existing PhysicsWorld; construction attaches the ground automatically.
ground = GroundPlane(world, direction=[0.0, 0.0, 1.0], constant=0.0, random_seed=7)
ground.destroy()
```

<a id="api-7-12"></a>

## 5.5.12 MeshTerrain

### Purpose and construction

MeshTerrain converts a ground triangle mesh into collision terrain. It preserves road elevation and shape so vehicle dynamics can interact with the scene's mesh surface.

BaseEnv creates it when `scene_mesh_path` is supplied. Construction reads vertices/faces/normals, applies `transform`/`scale`/`position`, and creates static Bullet terrain. [CollisionBodyObservation](observation.md#api-5-9) also draws these arrays.

Source: [streetworld/objects/terrain/mesh_terrain.py](../../../streetworld/objects/terrain/mesh_terrain.py).

### Configuration

Pass the file path and transform through construction. BaseEnv uses metadata scene_mesh_path and scene_mesh_transform; no separate Config fields are defined.

### API

| Category and signature | Parameters | Returns | Behavior and conditions | Exceptions and implementation status |
| --- | --- | --- | --- | --- |
| Constructor<br>`__init__(self, physics_world, model_path: str, transform=None, position=(0, 0, 0), scale=1.0, friction=0.8, restitution=0.0, random_seed=None, name='GroundMesh', config=None, **kwargs)` | `physics_world`: PhysicsWorld; `model_path`: ground mesh path; `transform`: 4×4 homogeneous `transform`; `position`: world `position` in meters; `scale`: positive mesh `scale`; `friction`: Bullet `friction`; `restitution`: Bullet `restitution`; `random_seed`: random seed; `name`: generated when None; `config`: component configuration; `**kwargs`: keyword arguments | None | Loads the mesh, creates a zero-mass BulletTriangleMeshShape, sets friction/restitution, and attaches it. | Nonpositive scale or invalid position/transform raises ValueError. File and mesh parsing errors propagate. |
| Instance method<br>`reset(self, random_seed=None, name=None, *args, **kwargs)` | `random_seed`: random seed; `name`: generated when None; `*args`: positional arguments; `**kwargs`: keyword arguments | None | Does nothing; Environment rebuilds the mesh when switching scenes. | — |
| Instance method<br>`destroy(self)` | — | None | Removes the body, clears vertex/face/normal arrays, and performs base cleanup. | — |

Defaults are transform=None, position=(0,0,0), scale=1.0, friction=0.8, and restitution=0.0. Vertices receive transform, scale, and translation in that order; normals receive only the transform's rotation.

### Example

```python
from streetworld.objects.terrain.mesh_terrain import MeshTerrain

# world is an existing PhysicsWorld; use the path to an actual ground mesh.
ground = MeshTerrain(world, model_path="/path/to/mesh_ground.ply", random_seed=7)
ground.destroy()
```

<a id="section-5-5-13"></a>

## 5.5.13 Object module functions

Vehicle selection functions are defined in vehicle/vehicle_type.py.
| Module function<br>`get_vehicle_type(length)` | length: classification length in meters | Vehicle class | Returns SVehicle for length≤4, MVehicle for ≤5.2, LVehicle for ≤6.2, and XLVehicle otherwise. | BaseEnv passes tracking.size[1], the width, when creating surrounding vehicles; this differs from the function's length argument. |
| Module function<br>`random_vehicle_type(np_random, p=None)` | np_random: generator supporting choice; p: optional five-element probability list | Vehicle class | Samples s, m, l, xl, or default with np_random.choice in that order; uniform when p=None. | A nonempty p must contain five values. NumPy raises probability errors such as a sum different from 1. The truth-value test on p cannot be used with an ndarray. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 5.4 Policy](policy.md) · [Next: 5.6 Runtime utilities](runtime.md)
