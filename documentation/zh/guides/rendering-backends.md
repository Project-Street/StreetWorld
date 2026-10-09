<a id="section-3-3"></a>

# 3.3 渲染后端示例

[English](../../en/guides/rendering-backends.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md) · [下一页：4.1 Config 的用途与使用](configuration/config.md)

nuScenes 和 Waymo 使用 ST Renderer 在本机 GPU 上渲染；NuRec 场景由独立服务渲染。选择对应后端后，将接口实例传给 Environment。

<a id="st-renderer"></a>

## ST Renderer

ST Renderer 在本机 GPU 上渲染重建好的 nuScenes 或 Waymo 高斯场景。选择 nuScenes 时这样创建接口：

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Waymo 使用 `SimulatorInterface("waymo")`。默认从仓库下的对应数据目录读取文件；数据放在其他位置时，用 `root` 指定存放场景 NPZ 的目录，例如 `SimulatorInterface("nuscenes", root="/path/to/nuscenes")`。

NuRec 的场景格式、渲染服务安装和启动步骤见 [NuRec](#nurec)。

<a id="scene-files"></a>

## 场景资产目录

按默认路径运行时，场景文件放在 StreetWorld 根目录下：

```text
data/processed/benchmark/
├── nuscenes/
│   ├── 0007.npz
│   ├── <其他场景名>.npz
│   └── map_cache.npz
├── waymo/
│   ├── <场景名>.npz
│   └── ground/<场景名>.obj
└── NuRec/sample_set/25.07_release/
    └── Batch<编号>/<场景目录>/
        ├── <uuid>.usdz
        └── <uuid>/
            ├── rig_trajectories.json
            ├── sequence_tracks.json
            ├── map.xodr
            └── mesh_ground.ply
```

nuScenes 和 Waymo 的场景 ID 是 NPZ 文件名去掉扩展名，例如 `0007`、`001-segment-1422926405879888210`。

NuRec 的场景 ID 是以 `Batch<数字>` 开头的相对路径，如 `Batch0001/<场景目录>`，相对于 `nurec_root`。每个场景目录包含一个 USDZ 文件，并有同名 UUID 子目录保存解包后的数据。

<a id="nurec"></a>

## NuRec

[NuRec](https://docs.nvidia.com/nurec/index.html) 是 NVIDIA 提供的场景重建与渲染工具。它将采集的相机、激光雷达数据重建成三维场景，保存为 USDZ 文件。渲染时可以改变相机和交通对象的位姿，从这些场景生成新的画面。

StreetWorld 使用已经重建好的 NuRec 场景。[NuRec SimulatorInterface](../../../submodules/nurec_interface/simulator_interface.py) 读取本地轨迹、相机参数和 XODR 地图，并通过 [gRPC 渲染服务](https://docs.nvidia.com/nurec/api/grpc_api_guide.html) 请求图像。

运行时需要启动两个服务：NuRec 渲染服务监听 `8080`，供 SimulatorInterface 请求图像；StreetWorld Environment Server 监听 `50052`，供 AD policy 获取观测和提交动作。渲染服务使用 `nre-ga:26.04` 镜像，详见 [NuRec 服务配置说明](../../../submodules/nurec_interface/NUREC_GRPC_SERVER_SETUP.md)。

### 配置 Docker 的 GPU 支持

主机需要先安装 NVIDIA 驱动和 Docker。Ubuntu / Debian 上安装 NVIDIA Container Toolkit：

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

其他系统的安装方式见 [NVIDIA Container Toolkit 安装文档](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)。拉取镜像，并检查容器能否使用 GPU：

```bash
docker pull nvcr.io/nvidia/nre/nre-ga:26.04
docker run --rm --gpus all --entrypoint nvidia-smi nvcr.io/nvidia/nre/nre-ga:26.04
```

### 启动 NuRec 渲染服务

数据按[场景资产目录](#scene-files)准备。下面以子模块说明中的 `Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa` 场景为例，在 StreetWorld 根目录执行：

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

`NUREC_HOST_ROOT` 是主机上的 NuRec 数据目录，挂载后在容器里对应 `/workdir/NuRec`。`SCENE_USDZ` 是相对于这个目录的 USDZ 路径；运行自己的场景时，将它换成实际文件。

`--test-scenes-are-valid` 会在服务上线前加载并检查场景。`--enable-editing-actors` 允许 StreetWorld 更新交通对象的位姿，必须开启；缺少它时，带对象更新的渲染请求会报 `INVALID_ARGUMENT`。`8081` 是健康检查端口，SimulatorInterface 连接的是 `8080`。

查看启动日志：

```bash
docker logs nurec-grpc
```

服务启动后，在安装了 StreetWorld 的 Python 环境中查询已加载的场景：

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

服务端的场景 ID 是 `clipgt-<USDZ 文件名去掉扩展名>`。上面的示例应返回 `clipgt-7e11dcb8-7bce-4972-b998-8626857e92aa`。SimulatorInterface 会从本地 USDZ 文件名生成同一个 ID，因此本地数据与渲染服务必须使用同一场景；请求了未加载的场景会报 `NOT_FOUND`。

### 启动 StreetWorld Environment Server

渲染服务就绪后，在 StreetWorld 环境中用 [env_server_scene_config.py](../../../streetworld/examples/env_server_scene_config.py) 启动仿真服务。场景列表写相对于 `25.07_release` 的目录，与上面加载的 USDZ 对应：

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

也可以运行 [env_server_easydrive.py](../../../streetworld/examples/env_server_easydrive.py)，在终端选择 NuRec 和对应场景。两个入口都读取仓库下的 `data/processed/benchmark/NuRec/sample_set/25.07_release`，并加载 [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py) 中的相机拼图布局和导航设置。

AD policy 连接 `127.0.0.1:50052`；浏览器打开 `http://127.0.0.1:18080` 查看画面。客户端开始调用 `reset()`、`step()` 后，仿真才会运行。当前这两个入口的 NuRec 分支使用 EnvInputPolicy，`step()` 接收 `[steering, throttle_brake]`，例如 `[0.0, 0.2]` 表示直行并使用 20% 的油门。

NuRec 分支目前不应用 `--ad-policy-config`。接入输出轨迹的 AD policy 时，需要在创建环境的代码中将主车 Policy 改为 EnvInputILQRPolicy 或 EnvInputPIDPolicy，并让 `trajectory_dt` 与模型的轨迹采样间隔一致，设置方法见[配置示例](configuration/policy-controller.md#section-4-5)。

更换场景时，先结束 Environment Server，再删除渲染容器，然后用新的 `SCENE_USDZ` 重新启动，并修改场景列表：

```bash
docker rm -f nurec-grpc
```

### 在代码中创建接口

自行创建 Environment 时，将下面的接口实例传给环境，调用方式见 [3.1](environment-interface.md#section-3-1)。NuRec 渲染服务需要提前启动：

```python
from submodules.nurec_interface.simulator_interface import SimulatorInterface

simulator = SimulatorInterface(
    nurec_root="data/processed/benchmark/NuRec/sample_set/25.07_release",
    grpc_host="127.0.0.1",
    grpc_port=8080,
    grpc_timeout_s=600.0,
)
```

`nurec_root` 指向本地 release 目录，`grpc_host`、`grpc_port` 指向 NuRec 渲染服务，`grpc_timeout_s` 的单位为秒。`resolution_scale` 控制图像分辨率缩放，默认 `1.0`。创建环境时还应合并 [NUREC_CONFIG](../../../streetworld/configs/nurec_config.py)，使交互界面的相机布局与 NuRec 的相机名一致。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md) · [下一页：4.1 Config 的用途与使用](configuration/config.md)
