<a id="chapter-3"></a>

# 3. Interface contracts

[简体中文](../../zh/guides/interfaces.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 2. Architecture](architecture.md) · [Next chapter: 4. Configuration system](configuration.md)

- [3.1 Environment: local and remote calls](#section-3-1)
- [3.2 3D assets and SimulatorInterface](#section-3-2)
- [3.3 Rendering backend examples](#section-3-3)
    - [3.3.1 ST Renderer](#st-renderer)
    - [3.3.2 NuRec](#nurec)

<a id="section-3-1"></a>

## 3.1 Environment: local and remote calls

Environment runs driving episodes: it loads a scene, accepts actions, simulates vehicle motion, and returns observations, reward, and termination flags. A local AD policy calls it directly; a model in a separate process calls the server environment through GrpcClientEnv.

### Local calls

Construct an environment with a SimulatorInterface for scene loading/rendering and an environment configuration. This nuScenes scene `0007` example keeps the vehicle straight with 20% throttle:

```python
from st_renderer import SimulatorInterface
from streetworld.config import Config
from streetworld.envs.scenario_env import ScenarioEnv

env = ScenarioEnv(
    SimulatorInterface("nuscenes"),
    Config({"scene_ids": ["0007"]}),
)
try:
    observation, info = env.reset()
    while True:
        action = [0.0, 0.2]
        observation, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
finally:
    env.close()
```

`reset()` starts an episode and returns the initial observation and scene information. `step(action)` returns the five values below; `close()` releases environment resources.

| Return value | Type and meaning |
| --- | --- |
| `observation` | Ego observation; by default, a dictionary containing `gaussian`, `navigation`, `states`, and `surrounding` |
| `reward` | Numeric reward for this step; see [Reward calculation](#reward-calculation) |
| `terminated` | Boolean indicating that the episode ended, for example due to arrival, collision, leaving the road, or the step limit |
| `truncated` | Boolean indicating that the episode ended at a configured step limit |
| `info` | Dictionary with scene name, timestamps, termination reason, reward components, and related information |

<a id="action-format"></a>

### action: trajectories and control inputs

The ego Policy determines `step(action)`'s input format. EnvInputILQRPolicy and EnvInputPIDPolicy accept future waypoints from an AD policy and convert them to control inputs. EnvInputPolicy accepts steering and throttle/brake directly.

#### Trajectory input

Trajectory Policies such as EnvInputILQRPolicy and EnvInputPIDPolicy accept an `(N, 2)` array. `N` is the number of future points, and each row contains `[x, y]` in meters:

| Component | Meaning |
| --- | --- |
| `x` | Distance along the ego vehicle's forward axis; positive is forward |
| `y` | Lateral distance from the ego vehicle; positive is left |

The coordinates use the ego position at action submission as their origin and rotate with its heading. For example, `[10.0, 2.0]` is a target 10 m ahead and 2 m left. `trajectory_dt` sets the future time of each point: with `0.5 s`, the first point is `0.5 s` ahead and the second is 1 s ahead.

```python
import numpy as np

action = np.array([[2.0, 0.0], [4.0, 0.0], [6.0, 0.5]], dtype=np.float32)
```

Policy computes steering and throttle to track this trajectory. Configure point spacing, the control period, and environment step duration separately; see the [timing example](configuration.md#section-4-5).

#### Control input

EnvInputPolicy uses continuous control by default, accepting `[steering, throttle_brake]` with both values in `[-1, 1]`:

| Component | Meaning |
| --- | --- |
| `steering` | Steering input: `1` is maximum left, `-1` maximum right, and `0` centered. The vehicle's `max_steering` determines the wheel angle |
| `throttle_brake` | Throttle/brake input: positive drives forward, `1` is maximum throttle, and `0` is no throttle. Negative values drive backward when reverse is enabled and apply braking otherwise |

For example, `[0.0, 0.2]` centers steering and applies 20% throttle; `[0.5, 0.0]` steers left at half the maximum angle with no throttle. `actor_config.controller_config.enable_reverse=True` by default, so negative throttle slows a forward-moving vehicle and then reverses it. Input magnitude specifies control effort; actual acceleration also depends on vehicle parameters and motion state.

<a id="observation-data"></a>

### observation: data available to the AD policy

The ego AssemblyObservation combines the default observations. Changing the Observer or its configuration changes the returned fields.

| Field | Contents and format |
| --- | --- |
| `gaussian` | Camera images and parameters; local gaussian['image'][camera_name] has shape `(1, H, W, 3)`, using `uint8` RGB values in 0–255 by default. The first dimension is one frame, H/W are image height/width, and the last dimension contains RGB channels |
| `navigation` | Navigation data including the current road, route, and ego position relative to the route |
| `states` | Ego speed and motion state |
| `surrounding` | Poses, dimensions, and motion state of surrounding vehicles, pedestrians, and other objects |

Positions use meters, velocity `m/s`, acceleration `m/s²`, angular velocity `rad/s`, and angular acceleration rad/s². Heading angles such as `heading_theta` use radians. Vehicle coordinates are X forward, Y left, Z up. SurroundingObservation can return participant data in ego or world coordinates; see the [Observation reference](../reference/observation.md). See [SimulatorInterface](#load-metadata) for camera parameters and pose matrices.

<a id="scenario-info"></a>

### info: scene and runtime information

Both `reset()` and `step()` return `info`, which records scene progress, termination reasons, and reward components.

| Field | Meaning and unit |
| --- | --- |
| `scene_name` | Current scene ID |
| `current_timestamp` | Current scene timestamp in microseconds |
| `relative_timestamp` | Simulation time since the episode began, in microseconds; divide by `1_000_000` for seconds |
| `episode_length` | Completed environment steps in this episode; 0 after reset |
| `reason` | Current ego state; at episode end, this is the termination reason. Values are listed below |
| `episode_reward` | Accumulated episode reward, returned by step |
| `steering`, `throttle_brake` | Current ego steering and throttle/brake inputs, returned by step |
| `step_reward`, `reward_components` | Current reward and component values from the default calculator; `reward_components['total']` is their sum |

<a id="agent-states"></a>

### AgentState and termination reasons

AgentState describes a simulation object's current state. Environment checks the ego state, writes it to `info['reason']`, and determines whether the episode has ended. Values are strings:

| AgentState | `reason` value | Meaning |
| --- | --- | --- |
| `NOT_SPAWN` | `not_spawn` | The object's spawn time has not arrived |
| `ALIVE` | `alive` | The object has spawned and is active |
| `IDLE` | `idle` | The object was placed in an idle state by an external call |
| `SUCCESS` | `arrive_dest` | Policy considers the destination reached; the test depends on the Policy |
| `OUT_OF_ROAD` | `out_of_road` | Road check failed: no nearby lane with a map, or too far from the expert trajectory without a map |
| `OUT_OF_STEP` | `out_of_step` | The environment or ego Agent step limit was reached |
| `CRASH_VEHICLE` | `crash_vehicle` | Collision with a vehicle |
| `CRASH_HUMAN` | `crash_human` | Collision with a pedestrian |
| `CRASH_OBJECT` | `crash_object` | Collision with another traffic object |
| `CRASH_WORLD` | `crash_world` | Collision with scene background geometry or terrain |

Arrival, leaving the road, step limits, and collisions set terminated=True. A step limit also sets `truncated=True`, so both flags can be true. Use `if terminated or truncated` to detect episode end.

`max_step` sets the environment limit; `actor_config.max_step` sets the ego Agent limit. `check_crash` enables ego collision checking, and `check_crash_world` additionally controls background collision checking. Fields such as `crash_vehicle_done` do not participate in this termination logic, so they cannot keep a scene running after collision.

<a id="reward-calculation"></a>

### Calculate and customize rewards
For reinforcement learning, adapt the reward to the training objective by changing the reward calculator or overriding the reward function.
ScenarioEnv uses [RewardCalculator](../../../streetworld/misc/reward_calculator.py). It calls `reset()` at the start of each episode and `compute(env)` to obtain (reward, `reward_info`). Environment merges `reward_info` into `info` and accumulates the per-step reward.

The default reward contains these terms:

| Reward term | Calculation |
| --- | --- |
| `progress`, `reverse` | Reward for forward route progress and a penalty for reversing; route deviation reduces forward reward |
| `position`, `heading` | Penalties when lateral or heading errors exceed their thresholds |
| `ttc` | Estimated time to collision from relative positions and velocities; penalizes risk and grants a safety bonus when conditions permit |
| `collision` | Penalty for collision or leaving the road; default `-50` |
| `success_bonus` | Reward for reaching the destination; default `75` |
| `living_cost` | Constant added on each calculation; current default `0.05` |

Set weights or thresholds such as `progress_reward_weight` and `collision_penalty_weight` in Config; see [ScenarioEnv configuration](../reference/environment.md#api-1-2). To add a reward term, override `_reward_function()` in a ScenarioEnv subclass. This example retains the default reward and penalizes large steering inputs:

```python
from streetworld.envs.scenario_env import ScenarioEnv

class SteeringPenaltyEnv(ScenarioEnv):
    def _reward_function(self):
        reward, info = super()._reward_function()
        penalty = -0.1 * abs(self.actor_controller.steering)
        total = float(reward + penalty)
        info["reward_components"]["steering_penalty"] = penalty
        info["reward_components"]["total"] = total
        info["step_reward"] = total
        return total, info
```

Construct `SteeringPenaltyEnv` in place of `ScenarioEnv`, using the same calls. The method must return a numeric reward and an information dictionary. The new penalty is included in episode_reward.

Alternatively, copy or subclass RewardCalculator, change `compute(env)`, and assign your calculator to `self.reward_calculator` in a custom environment constructor. It must also implement `reset()` to clear episode records and `episode_info()` to return accumulated diagnostics at termination. Config does not currently select a reward calculator class.

<a id="interactive-env"></a>

### InteractiveEnv: images, state, and video

ScenarioEnv returns observations and results. To view images/state or record videos during simulation, create an interactive environment with `make_interactive_env()`:

```python
from streetworld.envs.interactive_env import make_interactive_env
from streetworld.envs.scenario_env import ScenarioEnv

InteractiveScenarioEnv = make_interactive_env(ScenarioEnv)
```

The returned class retains `reset()`, `step()`, and `close()` and manages these UI components:

| Class | Function | Switches and main settings |
| --- | --- | --- |
| WebUI | Displays camera mosaics, speed, and control inputs in a browser; accepts W/A/S/D input | `webui` is enabled by default; `web_host` and `web_port` set the address |
| TUI | Displays the scene queue, runtime state, speed, termination reason, and evaluation metrics in the terminal | `tui` is enabled by default |
| VideoExporter | Saves per-scene MP4 videos, optionally showing speed/angular-velocity history and control inputs beside the images | `video_output_dir` defaults to `videos`; `None` disables recording. `video_hud` controls additional state displays |

After each step, the interactive environment reads camera images from `observation`, arranges them with `image_layout`, and passes images and vehicle state to these components. At scene end, the terminal shows the termination reason and metrics, and the video is written to disk. `close()` shuts down the interfaces and saves unfinished recordings.
The web service starts during environment construction. After reset, it waits for the first `step()` to display camera images. Manual driving requires continuous key handling; see the [browser driving example](../getting-started/index.md#section-1-2). See the [API reference](../reference/environment.md#api-1-3) for all interactive environment settings.

### Remote calls
AD policies and the simulator often have conflicting dependencies. Run each in its own Python environment and exchange simulation observations and inference results between processes.
Start the Environment Server as described in [Chapter 1](../getting-started/index.md#section-1-3), then connect with GrpcClientEnv. The client still uses `reset()`, `step()`, and `close()`; scene loading, vehicle simulation, and rewards run on the server.

```python
import numpy as np
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv("127.0.0.1", 50052, timeout_sec=360.0)
try:
    observation, info = env.reset()
    trajectory = np.array([[0.5 * i, 0.0] for i in range(1, 7)], dtype=np.float32)
    observation, reward, terminated, truncated, info = env.step(trajectory)
finally:
    env.close()
```

This example submits six future position points to the server's default `trajectory` Policy. Replace `trajectory` with your model's prediction from `observation`, then repeat the calls in a loop.

The server configuration selects remote scenes. Client `reset()` currently does not send `seed` or `options` and has no `scene_id` argument. For continuous control, send `[steering, throttle_brake]`; the server restores a one-row, two-column array, and EnvInputPolicy takes that row. Discrete action IDs are not supported by this transport; a nonempty action must contain an even number of elements. Sending `None` also gives the server None.

| Details | Changes in remote calls |
| --- | --- |
| Camera images | Client images have shape `(H, W, 3)`, removing the local frame dimension. Read them as `uint8` RGB; the server must use `clip_rgb=False` |
| Map objects | Objects such as `current_lane` become strings in transmission and cannot be used as local map objects |
| `collision_body` | This observation is not currently transmitted |
| Connections and resources | Client `close()` closes its connection; the server owns shutdown of its simulation and process |

A gRPC message can be at most 200 MiB in either direction. The client restores numeric observation arrays as NumPy arrays; `info` remains a dictionary. See [Environment reference](../reference/environment.md#api-2-1) for the complete client and server APIs.

<a id="section-3-2"></a>

## 3.2 3D assets and SimulatorInterface

SimulatorInterface defines StreetWorld's scene loading and image rendering contract. Dataset assets supply trajectories, camera parameters, maps, and terrain in a common format for Environment. Renderers implement the same interface to generate images from simulated object and camera poses.

Environment calls these methods by convention; each implementation handles its own files, assets, and rendering. Implement the four methods below to add a dataset or renderer, then pass the instance to Environment. See [Rendering backend examples](#section-3-3) for the existing backends.

### The four SimulatorInterface calls

The interface separates loading from rendering. At scene start it reads metadata and loads models; during simulation it updates object poses and renders images repeatedly. The call order is `load_metadata()`, `load_model()`, then repeated `update_scene()` and `render()` calls. Environment uses these method names and does not require a shared base class.

Here `scene_id` denotes the scene identifier passed positionally by Environment. ST Renderer names this argument `scene_name` in both loading methods.

<a id="load-metadata"></a>

#### load_metadata(scene_id)

Environment needs the scene duration, ego starting state, participant tracks, and camera mounts to create a simulation. `load_metadata()` reads this information; rendering models load in the next call.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `scene_id` | Scene identifier; ST Renderer uses a string, while NuRec also accepts a relative Path | Selects the scene to read; see [Scene asset directories](#scene-files) for backend-specific IDs |

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

#### load_model(scene_id)

This call loads scene 3D assets and HD maps and returns the road map. Metadata describes objects, while rendering models generate images; separating them lets Environment read trajectories/calibration before preparing models. StreetWorld currently supports trajdata.VectorMap.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `scene_id` | The same scene ID used in `load_metadata()` | Selects the scene model to load; read that scene's metadata first |

Returns `trajdata.VectorMap` or None. The map supports lane queries, navigation, and road checks; the interface retains its rendering model. ST Renderer loads Gaussian models, while NuRec prepares remote rendering information and builds a VectorMap from XODR.

<a id="update-scene"></a>

#### update_scene(timestamp, object_poses)

Simulated vehicles can deviate from their recorded tracks. Before rendering, Environment supplies the current simulation timestamp and participant poses so images reflect their simulated motion.

| Parameters | Type and unit | Purpose |
| --- | --- | --- |
| `timestamp` | Current scene timestamp, microseconds | Uses the recorded timeline; Environment passes `current_timestamp` rather than the zero-based `relative_timestamp` |
| `object_poses` | {object_id: torch.Tensor}, with each tensor holding a 4×4 pose matrix | Keys match participant IDs in participants. Matrices express simulation world positions and orientations; translation is in meters |

Environment includes active surrounding participants in object_poses. Ego pose is supplied through camera extrinsics and is omitted from this dictionary.

Returns None. The interface retains the timestamp and object poses for render().

<a id="render"></a>

#### render(K, H, W, extrinsics)

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

<a id="section-3-3"></a>

## 3.3 Rendering backend examples

nuScenes and Waymo use ST Renderer on the local GPU. NuRec scenes use a separate rendering service. Pass the selected backend's interface instance to Environment.

<a id="st-renderer"></a>

### 3.3.1 ST Renderer

ST Renderer renders reconstructed nuScenes or Waymo Gaussian scenes on the local GPU. Create a nuScenes interface as follows:

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Use `SimulatorInterface("waymo")` for Waymo. Files are read from the repository's dataset directories by default. For data elsewhere, set `root` to the directory containing scene NPZ files, for example SimulatorInterface("nuscenes", `root`="/path/to/nuscenes").

See [3.3.2 NuRec](#nurec) for its scene format, rendering service installation, and startup.

<a id="scene-files"></a>

### Scene asset directories

The default scene paths under the StreetWorld root are:

```text
data/processed/benchmark/
├── nuscenes/
│   ├── 0007.npz
│   ├── <other_scene_name>.npz
│   └── map_cache.npz
├── waymo/
│   ├── <scene_name>.npz
│   └── ground/<scene_name>.obj
└── NuRec/sample_set/25.07_release/
    └── Batch<number>/<scene_directory>/
        ├── <uuid>.usdz
        └── <uuid>/
            ├── rig_trajectories.json
            ├── sequence_tracks.json
            ├── map.xodr
            └── mesh_ground.ply
```

nuScenes and Waymo scene IDs are NPZ filenames without extensions, for example `0007` and 001-segment-1422926405879888210.

NuRec scene IDs are relative paths beginning with Batch followed by digits, such as Batch0001/<scene_directory>, relative to nurec_root. Each scene directory contains a USDZ file and a UUID subdirectory of the same name with unpacked data.

<a id="nurec"></a>

### 3.3.2 NuRec

[NuRec](https://docs.nvidia.com/nurec/index.html) is NVIDIA's scene reconstruction and rendering tool. It reconstructs camera and lidar recordings into 3D scenes stored as USDZ files. Rendering can change camera and participant poses to generate new views of those scenes.

StreetWorld uses reconstructed NuRec scenes. The [NuRec SimulatorInterface](../../../submodules/nurec_interface/simulator_interface.py) reads local trajectories, camera parameters, and XODR maps, then requests images from the [gRPC rendering service](https://docs.nvidia.com/nurec/api/grpc_api_guide.html).

Run two services: NuRec rendering on port `8080` for SimulatorInterface, and StreetWorld Environment Server on port `50052` for AD policy observations and actions. The renderer uses the `nre-ga:26.04` image; see [NuRec server setup](../../../submodules/nurec_interface/NUREC_GRPC_SERVER_SETUP.md).

#### Enable GPU access in Docker

Install the NVIDIA driver and Docker on the host first. On Ubuntu or Debian, install NVIDIA Container Toolkit:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg2

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

For other systems, follow the [NVIDIA Container Toolkit installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html). Pull the image and check GPU access inside a container:

```bash
docker pull nvcr.io/nvidia/nre/nre-ga:26.04
docker run --rm --gpus all --entrypoint nvidia-smi nvcr.io/nvidia/nre/nre-ga:26.04
```

#### Start the NuRec rendering service

Prepare data under the [scene asset directories](#scene-files). This example uses `Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa` from the submodule guide. Run from the StreetWorld root:

```bash
NUREC_HOST_ROOT="$PWD/data/processed/benchmark/NuRec"
SCENE_USDZ="sample_set/25.07_release/Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa/7e11dcb8-7bce-4972-b998-8626857e92aa.usdz"

docker run -d --name nurec-grpc \
  --shm-size=64g \
  --gpus all \
  --net=host \
  --privileged \
  -v "${NUREC_HOST_ROOT}:/workdir/NuRec:ro" \
  nvcr.io/nvidia/nre/nre-ga:26.04 \
  serve-grpc \
  --artifact-glob "/workdir/NuRec/${SCENE_USDZ}" \
  --host 0.0.0.0 \
  --port 8080 \
  --health-port 8081 \
  --test-scenes-are-valid \
  --enable-editing-actors
```

`NUREC_HOST_ROOT` is the host's NuRec data directory, mounted at `/workdir/NuRec` inside the container. `SCENE_USDZ` is the USDZ path relative to that directory; replace it with your scene's actual file.

`--test-scenes-are-valid` loads and checks scenes before the service starts. `--enable-editing-actors` permits StreetWorld to update participant poses and is required; without it, render requests with object updates return INVALID_ARGUMENT. Port `8081` is for health checks; SimulatorInterface connects to 8080.

Read the startup logs:

```bash
docker logs nurec-grpc
```

Once the service is running, query its loaded scenes from the Python environment where StreetWorld is installed:

```bash
python - <<'PY'
import grpc
from submodules.nurec_interface.nre.grpc.protos import common_pb2, sensorsim_pb2_grpc

channel = grpc.insecure_channel("127.0.0.1:8080", options=(("grpc.enable_http_proxy", 0),))
stub = sensorsim_pb2_grpc.SensorsimServiceStub(channel)
print(list(stub.get_available_scenes(common_pb2.Empty(), timeout=5).scene_ids))
channel.close()
PY
```

The service scene ID is clipgt- followed by the USDZ filename without its extension. This example should return clipgt-7e11dcb8-7bce-4972-b998-8626857e92aa. SimulatorInterface derives the same ID from the local USDZ filename, so local data must match the loaded service scene. Requests for unloaded scenes return NOT_FOUND.

#### Start the StreetWorld Environment Server

After the renderer is ready, start the simulation service with [env_server_scene_config.py](../../../streetworld/examples/env_server_scene_config.py). The scene list contains directories relative to `25.07_release` and must match the loaded USDZ:

```bash
cat > nurec-scenes.txt <<'EOF'
Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa
EOF

python -m streetworld.examples.env_server_scene_config \
  --dataset nurec --scene-config nurec-scenes.txt \
  --nurec-grpc-host 127.0.0.1 --nurec-grpc-port 8080 \
  --nurec-grpc-timeout 600 \
  --host 127.0.0.1 --port 50052 \
  --web-host 127.0.0.1 --web-port 18080
```

You can also run [env_server_easydrive.py](../../../streetworld/examples/env_server_easydrive.py) and select NuRec and the scene in the terminal. Both scripts read `data/processed/benchmark/NuRec/sample_set/25.07_release` and load the camera layout/navigation settings from [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py).

The AD policy connects to 127.0.0.1:50052. Open `http://127.0.0.1:18080` to view images in a browser. Simulation begins when the client calls `reset()` and step(). Both scripts currently use EnvInputPolicy for NuRec, accepting `[steering, throttle_brake]`; for example, `[0.0, 0.2]` keeps steering centered with 20% throttle.

The NuRec branch does not currently apply --ad-policy-config. For a trajectory-predicting AD policy, select EnvInputILQRPolicy or EnvInputPIDPolicy when constructing the environment and match `trajectory_dt` to the model's point interval. See the [configuration example](configuration.md#section-4-5).

To change scenes, stop the Environment Server, remove the rendering container, restart with a new `SCENE_USDZ`, and update the scene list:

```bash
docker rm -f nurec-grpc
```

#### Create the interface in Python

When constructing Environment yourself, pass the interface below; see [3.1](#section-3-1) for calls. Start the NuRec rendering service first:

```python
from submodules.nurec_interface.simulator_interface import SimulatorInterface

simulator = SimulatorInterface(
    nurec_root="data/processed/benchmark/NuRec/sample_set/25.07_release",
    grpc_host="127.0.0.1",
    grpc_port=8080,
    grpc_timeout_s=600.0,
)
```

`nurec_root` points to the local release directory. `grpc_host` and `grpc_port` identify the NuRec rendering service; `grpc_timeout_s` is in seconds. `resolution_scale` scales image resolution and defaults to 1.0. Also merge [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py) so the interactive layout matches NuRec camera names.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous chapter: 2. Architecture](architecture.md) · [Next chapter: 4. Configuration system](configuration.md)
