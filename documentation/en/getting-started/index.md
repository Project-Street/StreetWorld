<a id="chapter-1"></a>

# 1. Installation and quick start

[简体中文](../../zh/getting-started/index.md)

[Contents](../../DOCUMENTATION_EN.md) · [Next chapter: 2. Architecture](../guides/architecture.md)

- [1.1 Installation](#section-1-1)
- [1.2 Drive in the browser](#section-1-2)
- [1.3 Start the Environment Server](#section-1-3)
- [1.4 Run Expert iLQR](#section-1-4)

<a id="section-1-1"></a>

## 1.1 Installation

### Requirements

- Python 3.10 or later.
- NVIDIA GPU, CUDA Toolkit, and OpenGL; headless rendering requires EGL.

### Installation

```bash
conda create -n streetworld python=3.10 -y
conda activate streetworld

git clone --recursive https://github.com/Project-Street/StreetWorld.git
cd StreetWorld

python -m pip install -e ./trajdata
python -m pip install -e .
python -m pip install -e ./submodules/fast-gauss-paral
python -m pip install -e ./submodules/st-renderer
python -m pip install scipy matplotlib fastapi uvicorn setuptools wheel ninja
python -m pip install git+https://github.com/NVlabs/nvdiffrast.git --no-build-isolation
```

### Verify the installation

```bash
python -c "import streetworld, st_renderer, fast_gauss, nvdiffrast.torch, trajdata"
```

Scene download links will be released later. If you already have the data, place it under the [scene asset directories](../guides/interfaces.md#scene-files), then run the [browser driving example](#section-1-2).

<a id="section-1-2"></a>

## 1.2 Drive in the browser

This example lets you view a simulated scene in a browser and use W/A/S/D to steer, accelerate, and brake. Start here to check the camera views and try vehicle control.

[env_easydrive_web_controller.py](../../../streetworld/examples/env_easydrive_web_controller.py) starts the simulation and web page locally. Scenes run continuously, with browser key presses controlling the vehicle.

### Start the server

After [installation](#section-1-1), run from the StreetWorld root:

```bash
python -m streetworld.examples.env_easydrive_web_controller
```

The terminal shows the same scene selector as the Environment Server. Select nuScenes or Waymo, then the desired scene tags. Move with the up and down arrows; press Enter to select or deselect an item. Move to Continue and press Enter to proceed. The script starts the selected scenes after selection is complete.

### During a run

Open http://127.0.0.1:8080. The page shows camera views, speed, steering, and other state. Click the browser window to focus it, then use these keys:

| Key | Action |
| --- | --- |
| W | Apply throttle to accelerate forward |
| S | Apply reverse drive; when moving forward, slow down first, then reverse |
| A | Steer left |
| D | Steer right |

The web page's `throttle_brake` value ranges from `-1` to 1. A value of `1` applies maximum throttle, `0` applies no throttle, and negative values apply reverse drive or braking. Keys use pressed/released states: holding W sends `1`, holding S sends `-1`, and releasing them returns the value to 0.

Reverse is enabled by default, so S applies reverse drive. Set `actor_config.controller_config.enable_reverse` to `False` to make S apply braking instead. Steering values `1`, `-1`, and `0` mean maximum left, maximum right, and centered `steering`; A sends `1` and D sends -1.

Scenes run in sequence, switching automatically after each scene ends. Videos are saved in videos/. After the last scene, the web page remains available. Press `Ctrl-C` in the script terminal to exit.

### Arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--web-host`, `--web-port` | `127.0.0.1`, `8080` | Web page listening address |
| `--video-output-dir` | `videos` | Video output directory |

<a id="section-1-3"></a>

## 1.3 Start the Environment Server

AD policies and StreetWorld often require incompatible dependencies. Run them in separate Python environments and connect the simulation and inference processes through inter-process communication.
To control StreetWorld with your own AD policy, start the simulation as an Environment Server. The server loads scenes, renders camera images, and runs vehicle dynamics. The AD policy runs in another process, receives observations through gRPC, and submits its predicted trajectory.

[env_server_easydrive.py](../../../streetworld/examples/env_server_easydrive.py) provides a terminal scene selector for choosing a batch of scenes to test. To repeat runs with a fixed scene list, use [env_server_scene_config.py](#scene-list-server) below.

### Start the server

From the repository root, run this command in the environment where StreetWorld is installed:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 \
  --web-host 127.0.0.1 --web-port 18080
```

Select nuScenes, Waymo, or NuRec in the terminal, then filter scenes by tag. Move with the up and down arrows, press Enter to select an item, then move to Continue and press Enter to proceed. Scene choices come from `catalog/`; prepare the corresponding data before starting.

After selection, the server listens on `127.0.0.1:50052` for client requests. Synchronous mode is the default: simulation advances one environment step for each `step()` request.

### Connect a client

Check the connection with the following client. This example assumes a nuScenes or Waymo server using the default trajectory configuration. Run it from the StreetWorld root in another terminal:

```bash
python - <<'PY'
import numpy as np
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv("127.0.0.1", 50052, timeout_sec=360.0)
try:
    observation, info = env.reset()
    # Six forward target points, with the current vehicle position as the origin.
    trajectory = np.array([[0.5 * i, 0.0] for i in range(1, 7)], dtype=np.float32)
    observation, reward, terminated, truncated, info = env.step(trajectory)
    print(info["scene_name"], reward, terminated, truncated)
finally:
    env.close()
PY
```

The client loads a scene with `reset()`, submits a manually constructed trajectory, and prints the scene name, reward, and termination flags. The default server interprets the six points as future positions spaced `0.5 s` apart and advances simulation by 0.5 s.

To connect a model, replace `trajectory` with the `trajectory` predicted from `observation` and call `step()` in a loop. After a scene ends, call `reset()` to load the next one. See the [Policy Launcher appendix](../launchers/index.md) for supported models, dependencies, weights, and commands.

### During a run

Open `http://127.0.0.1:18080` to view camera images and vehicle state. At startup, the page shows `Waiting for policy reset/step...`; images appear after the client's first `step()` call. Videos are saved in videos/.

Clients connect to the gRPC address; the browser uses the web address. The server continues waiting for requests after this client exits. Press `Ctrl-C` in the server terminal to close it.

### env_server_easydrive.py arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--host`, `--port` | `127.0.0.1`, `50052` | StreetWorld gRPC address used by the client |
| `--web-host`, `--web-port` | `127.0.0.1`, `18080` | Web address for viewing simulation images |
| `--ad-policy-config` | `default` | Matches observations and timing to the model; dedicated values are `autovla`, `epona`, `openemma`, `transfuser`, and `latent_transfuser` |
| `--video-output-dir` | `videos` | Video output directory |
| `--async-mode` | Disabled | Advances simulation during model inference; see [Synchronous and asynchronous execution](../guides/architecture.md#section-2-6) |
| `--nurec-grpc-host`, `--nurec-grpc-port` | `127.0.0.1`, `8080` | NuRec rendering service address when NuRec is selected |
| `--nurec-grpc-timeout` | `600.0 s` | Timeout for NuRec rendering requests |

<a id="scene-list-server"></a>

### Specify a scene list

For batch evaluation or repeated model comparisons, save scene IDs in `scenes.txt`, one per line:

```text
0007
0008
```

Start the server with [env_server_scene_config.py](../../../streetworld/examples/env_server_scene_config.py) to run scenes in file order without selecting them manually each time:

```bash
python -m streetworld.examples.env_server_scene_config \
  --scene-config scenes.txt --dataset nuscenes \
  --host 127.0.0.1 --port 50052 --web-port 18080
```

`--scene-config` takes a UTF-8 text file containing only scene IDs, with no blank lines or comments. Both server scripts expose the same gRPC interface, so clients connect in the same way.

### env_server_scene_config.py arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--scene-config` / `-c` | Required | Scene list text file with one scene ID per line |
| `--dataset` | Required | `nuscenes`, `waymo`, or `nurec` |
| `--host`, `--port` | `127.0.0.1`, `50052` | StreetWorld gRPC address used by the client |
| `--web-host`, `--web-port` | `127.0.0.1`, `18080` | Web address for viewing simulation images |
| `--ad-policy-config` | `default` | Matches observations and timing to the model; dedicated values are `autovla`, `epona`, `openemma`, `transfuser`, and `latent_transfuser` |
| `--video-output-dir` | `videos` | Video output directory |
| `--async-mode` | Disabled | Advances simulation during model inference; see [Synchronous and asynchronous execution](../guides/architecture.md#section-2-6) |
| `--nurec-grpc-host`, `--nurec-grpc-port` | `127.0.0.1`, `8080` | NuRec rendering service address when NuRec is selected |
| `--nurec-grpc-timeout` | `600.0 s` | Timeout for NuRec rendering requests |

nuScenes and Waymo use the local ST Renderer, and `--ad-policy-config` applies to these datasets. NuRec requires a separate rendering service. Its server branch defaults to a raw-control Policy; trajectory models also require a trajectory Policy configuration. See [NuRec setup](../guides/interfaces.md#nurec).

<a id="section-1-4"></a>

## 1.4 Run Expert iLQR

[drive_expert_ilqr.py](../../../streetworld/examples/drive_expert_ilqr.py) shows vehicle simulation while following the expert trajectory. It takes the recorded ego trajectory from a scene and uses iLQR to compute steering and throttle/brake commands that track it.

### Start the server

Create `scenes.txt` with one scene ID per line, for example:

```text
0007
0008
```

Run from the StreetWorld repository root:

```bash
python -m streetworld.examples.drive_expert_ilqr \
  --scene-config scenes.txt \
  --dataset nuscenes \
  --max-steps 1000
```

Scenes run in file order. Use UTF-8 and include only scene IDs, with no blank lines or comments. See [Scene asset directories](../guides/interfaces.md#scene-files) for how IDs map to data files.

### During a run

The vehicle starts driving automatically. Open `http://127.0.0.1:8080` to view camera images and vehicle state; videos are saved in videos/. The terminal prints each scene name and its cumulative `reward_sum` at the end. Normal termination or truncation also prints the timestamp and termination reason.

The script proceeds to the next scene and closes the environment after the final one. Each scene executes at most `--max-steps` calls to `step()`; reaching the destination, a collision, or the environment step limit may end it earlier. Press `Ctrl-C` to exit early.

The expert Policy takes up to 30 future trajectory points per update. Both trajectory sampling and control use a `0.1 s` interval. On `env.step(None)`, ExpertILQRPolicy generates a target trajectory from the recording and iLQR tracks it.

### Arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--scene-config` / `-c` | Required | Scene list text file; one ID per line, processed in file order |
| `--dataset` | Required | `nuscenes` or `waymo` |
| `--max-steps` | `1000` | Maximum `step()` calls per scene in this script; the environment's own step limit still applies |
| `--warmup-step` | `None` | Number of initial environment steps controlled by ExpertILQRPolicy |
| `--gui` / `--no-gui` | Enabled | Inactive; this argument does not disable the web page, terminal UI, or video recording |
| `--gui-image-key` | `FRONT` | Inactive; this argument does not change the cameras displayed on the web page |

---

[Contents](../../DOCUMENTATION_EN.md) · [Next chapter: 2. Architecture](../guides/architecture.md)
