<a id="section-3-2"></a>

# 3.2 3D assets and SimulatorInterface

[简体中文](../../zh/guides/simulator-interface.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.1 Environment: local and remote calls](environment-interface.md) · [Next: 3.3 Rendering backend examples](rendering-backends.md)

SimulatorInterface defines StreetWorld's scene loading and image rendering contract. Dataset assets supply trajectories, camera parameters, maps, and terrain in a common format for Environment. Renderers implement the same interface to generate images from simulated object and camera poses.

Environment calls these methods by convention; each implementation handles its own files, assets, and rendering. Implement the four methods below to add a dataset or renderer, then pass the instance to Environment. See [Rendering backend examples](rendering-backends.md#section-3-3) for the existing backends.

## The four SimulatorInterface calls

The interface separates loading from rendering. At scene start it reads metadata and loads models; during simulation it updates object poses and renders images repeatedly. The call order is `load_metadata()`, `load_model()`, then repeated `update_scene()` and `render()` calls. Environment uses these method names and does not require a shared base class.

Here `scene_id` denotes the scene identifier passed positionally by Environment. ST Renderer names this argument `scene_name` in both loading methods.

<a id="load-metadata"></a>

### load_metadata(scene_id)

Environment needs the scene duration, ego starting state, participant tracks, and camera mounts to create a simulation. `load_metadata()` reads this information; rendering models load in the next call.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `scene_id` | Scene identifier; ST Renderer uses a string, while NuRec also accepts a relative Path | Selects the scene to read; see [Scene asset directories](rendering-backends.md#scene-files) for backend-specific IDs |

Returns a six-element tuple in this fixed order:

```python
(timestamp_range, camera_params, ego_poses, participants,
 scene_mesh_path, scene_mesh_transform)
```

| Return value | Type and unit | Purpose |
| --- | --- | --- |
| `timestamp_range` | [start_time, end_time], integer microseconds | Recorded time range; the environment samples at the physics interval, excluding the end timestamp |
| `camera_params` | {camera_name: parameter_dict} | Each camera requires `K`, a 3×3 intrinsic matrix with focal lengths/principal point in pixels; `H`/`W`, integer image height/width; and `ego2camera`, a 4×4 ego-to-camera transform. `extra` can hold backend-specific calibration |
| `ego_poses` | {integer_microsecond_timestamp: 4×4_pose} | Recorded ego trajectory; each matrix maps vehicle coordinates into the simulation world, with translation in meters |
| `participants` | {object_id: {'poses': pose_dict, 'size': [length, width, height], 'type': object_type}} | Surrounding participants; `poses` follow the ego trajectory's timestamp and matrix conventions. Dimensions are in meters; type selects a vehicle, pedestrian, cyclist, or other simulation object |
| `scene_mesh_path` | Path to an OBJ (`.obj`) or PLY (`.ply`) triangle mesh, or `None` | Terrain mesh for physics simulation; the environment creates a plane when no mesh is supplied. Waymo currently uses OBJ, and NuRec uses PLY |
| `scene_mesh_transform` | 4×4 mesh-to-simulation-world transform, or `None` | Places the terrain mesh; `None` applies no additional transform |

A pose matrix uses its upper-left 3×3 block for rotation and the first three entries of its last column for translation. Ego poses, participant poses, and maps must share simulation world coordinates. Vehicle axes are X forward, Y left, Z up; camera axes are X right, Y down, Z forward.

Environment adjusts the recorded ego origin for vehicle height and updates camera extrinsics accordingly. Map queries use the center of the vehicle's bottom face. Keep pose and extrinsic origins consistent when extending the interface or positioning cameras.

<a id="load-model"></a>

### load_model(scene_id)

This call loads scene 3D assets and HD maps and returns the road map. Metadata describes objects, while rendering models generate images; separating them lets Environment read trajectories/calibration before preparing models. StreetWorld currently supports trajdata.VectorMap.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `scene_id` | The same scene ID used in `load_metadata()` | Selects the scene model to load; read that scene's metadata first |

Returns `trajdata.VectorMap` or None. The map supports lane queries, navigation, and road checks; the interface retains its rendering model. ST Renderer loads Gaussian models, while NuRec prepares remote rendering information and builds a VectorMap from XODR.

<a id="update-scene"></a>

### update_scene(timestamp, object_poses)

Simulated vehicles can deviate from their recorded tracks. Before rendering, Environment supplies the current simulation timestamp and participant poses so images reflect their simulated motion.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `timestamp` | Current scene timestamp, microseconds | Uses the recorded timeline; Environment passes `current_timestamp` rather than the zero-based `relative_timestamp` |
| `object_poses` | {object_id: torch.Tensor}, with each tensor holding a 4×4 pose matrix | Keys match participant IDs in participants. Matrices express simulation world positions and orientations; translation is in meters |

Environment includes active surrounding participants in object_poses. Ego pose is supplied through camera extrinsics and is omitted from this dictionary.

Returns None. The interface retains the timestamp and object poses for render().

<a id="render"></a>

### render(K, H, W, extrinsics)

`render()` generates camera images from the saved scene state and the supplied camera parameters. Cameras are processed in a batch: the ith parameter set corresponds to the ith returned image.

For a batch of B cameras:

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `K` | `(B, 3, 3)` intrinsic matrices; Environment passes `torch.float32` tensors | Each camera's focal lengths and principal point in pixels; ST Renderer requires Torch tensors, while NuRec also accepts NumPy arrays |
| `H` | List of B integers, pixels | Height of each image |
| `W` | List of B integers, pixels | Width of each image |
| `extrinsics` | `(B, 4, 4)` simulation-world-to-camera transforms; Environment passes `torch.float32` tensors | Each camera's position and orientation in the current scene; ST Renderer requires Torch tensors, while NuRec also accepts NumPy arrays |

Camera extrinsics are ego2camera @ inverse(ego_vehicle_to_world_pose). Recompute them after ego motion to render from the new vehicle position.

Returns B `uint8` RGB images with values in 0–255, each shaped (H[i], W[i], 3). ST Renderer returns a `(B, H, W, 3)` NumPy array and requires equal H/W within a batch; NuRec returns a list of images. GaussianObservation reads them in camera order and adds the local frame dimension.

Some NuRec cameras use the `ftheta` fisheye model. Their calibration cannot be described by `K` alone, so NuRec `render()` also accepts `extra` for camera names, model types, and calibration.

`extra` is a list of length B in the same order as K. Each camera dictionary contains:

| Field | Meaning |
| --- | --- |
| `logical_id` | NuRec camera name, for example `camera_front_wide_120fov` |
| `type` | Camera model: `pinhole` or `ftheta` for fisheye cameras |
| `parameters` | Original `ftheta` calibration, including principal point and polynomial coefficients; pinhole cameras use `K` and do not need this field |

Environment supplies `extra` automatically. NuRec `load_metadata()` reads it from `rig_trajectories.json` into `camera_params`, then GaussianObservation passes it to render(). When calling NuRec `render()` directly, supply `extra` dictionaries in camera order. Omitting `extra`, or setting an entry to `None`, selects a pinhole model and `camera_front_tele_30fov` for that entry. See [parse_camera_params()](../../../submodules/nurec_interface/nurec_parser.py).

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.1 Environment: local and remote calls](environment-interface.md) · [Next: 3.3 Rendering backend examples](rendering-backends.md)
