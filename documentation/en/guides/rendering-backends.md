<a id="section-3-3"></a>

# 3.3 Rendering backend examples

[简体中文](../../zh/guides/rendering-backends.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.2 3D assets and SimulatorInterface](simulator-interface.md) · [Next: 4. Configuration system](configuration.md)

nuScenes and Waymo use ST Renderer on the local GPU. NuRec scenes use a separate rendering service. Pass the selected backend's interface instance to Environment.

<a id="st-renderer"></a>

## 3.3.1 ST Renderer

ST Renderer renders reconstructed nuScenes or Waymo Gaussian scenes on the local GPU. Create a nuScenes interface as follows:

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Use `SimulatorInterface("waymo")` for Waymo. Files are read from the repository's dataset directories by default. For data elsewhere, set `root` to the directory containing scene NPZ files, for example SimulatorInterface("nuscenes", `root`="/path/to/nuscenes").

See [3.3.2 NuRec](#nurec) for its scene format, rendering service installation, and startup.

<a id="scene-files"></a>

## Scene asset directories

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

## 3.3.2 NuRec

[NuRec](https://docs.nvidia.com/nurec/index.html) is NVIDIA's scene reconstruction and rendering tool. It reconstructs camera and lidar recordings into 3D scenes stored as USDZ files. Rendering can change camera and participant poses to generate new views of those scenes.

StreetWorld uses reconstructed NuRec scenes. The [NuRec SimulatorInterface](../../../submodules/nurec_interface/simulator_interface.py) reads local trajectories, camera parameters, and XODR maps, then requests images from the [gRPC rendering service](https://docs.nvidia.com/nurec/api/grpc_api_guide.html).

Run two services: NuRec rendering on port `8080` for SimulatorInterface, and StreetWorld Environment Server on port `50052` for AD policy observations and actions. The renderer uses the `nre-ga:26.04` image; see [NuRec server setup](../../../submodules/nurec_interface/NUREC_GRPC_SERVER_SETUP.md).

### Enable GPU access in Docker

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

### Start the NuRec rendering service

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

### Start the StreetWorld Environment Server

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

The NuRec branch does not currently apply --ad-policy-config. For a trajectory-predicting AD policy, select EnvInputILQRPolicy or EnvInputPIDPolicy when constructing the environment and match `trajectory_dt` to the model's point interval. See the [configuration example](configuration/policy-controller.md#section-4-5).

To change scenes, stop the Environment Server, remove the rendering container, restart with a new `SCENE_USDZ`, and update the scene list:

```bash
docker rm -f nurec-grpc
```

### Create the interface in Python

When constructing Environment yourself, pass the interface below; see [3.1](environment-interface.md#section-3-1) for calls. Start the NuRec rendering service first:

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

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.2 3D assets and SimulatorInterface](simulator-interface.md) · [Next: 4. Configuration system](configuration.md)
