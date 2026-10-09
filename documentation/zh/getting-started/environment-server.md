<a id="section-1-3"></a>

# 1.3 启动 Environment Server

[English](../../en/getting-started/environment-server.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.2 用浏览器驾驶](web-controller.md) · [下一页：1.4 运行 Expert iLQR](expert-ilqr.md)

AD policy与StreetWorld仿真器往往存在环境依赖的冲突，所以最好的实践是将AD policy与StreetWorld分别配置在两个环境中，并通过进程间通信完成仿真与推理的闭环。
要让自己的AD Policy控制 StreetWorld，可以先把仿真启动为 Environment Server进程。服务端负责加载场景、渲染相机画面和物理仿真，监听车辆的仿真请求，AD Policy在另一个进程通过 gRPC 接收观测、提交推理出的轨迹。这样，仿真和模型可以分别运行在各自的环境中。

[env_server_easydrive.py](../../../streetworld/examples/env_server_easydrive.py) 提供终端场景选择界面，适合手动选一批场景来测试模型。需要反复运行固定场景列表时，使用本页后面的 [env_server_scene_config.py](#scene-list-server)。

## 启动

在安装了 StreetWorld 的环境中，从仓库根目录运行：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 \
  --web-host 127.0.0.1 --web-port 18080
```

在终端选择 nuScenes、Waymo 或 NuRec，再按标签筛选场景。用上下方向键移动，按 Enter 选中条目，移到 Continue 后按 Enter 进入下一页。场景选项来自 `catalog/`，对应的数据需要提前准备。

完成选择后，服务端监听 `127.0.0.1:50052`，等待客户端调用。默认采用同步模式，每收到一次 `step()` 请求才推进一个仿真步。

## 连接客户端

先用下面的客户端代码检查连接。它适用于选择了 nuScenes 或 Waymo、使用默认轨迹配置的服务端。在另一个终端从 StreetWorld 根目录运行：

```bash
python - <<'PY'
import numpy as np
from streetworld.envs.grpc_client_env import GrpcClientEnv

env = GrpcClientEnv("127.0.0.1", 50052, timeout_sec=360.0)
try:
    observation, info = env.reset()
    # 以车辆当前位置为原点，给出向前行驶的六个目标点。
    trajectory = np.array([[0.5 * i, 0.0] for i in range(1, 7)], dtype=np.float32)
    observation, reward, terminated, truncated, info = env.step(trajectory)
    print(info["scene_name"], reward, terminated, truncated)
finally:
    env.close()
PY
```

这段代码先用 `reset()` 加载一个场景，再提交一次手工构造的轨迹，打印场景名、奖励和结束状态。默认服务端将这六个点解释为每隔 `0.5 s` 的未来位置，并推进 `0.5 s` 仿真时间。

接入模型时，用模型根据 `observation` 预测的轨迹替换 `trajectory`，循环调用 `step()`；场景结束后，再调用 `reset()` 加载下一个场景。已有模型的依赖、权重和启动命令见 [Policy Launcher 附录](../launchers/index.md)。

## 运行后

打开 `http://127.0.0.1:18080` 查看模型驾驶时的相机画面和车辆状态。服务端刚启动时，页面显示 `Waiting for policy reset/step...`；客户端执行第一步 `step()` 后才会出现画面。视频保存到 `videos/`。

gRPC 地址用于客户端连接，网页地址用于浏览器查看。客户端示例退出后，服务端会继续等待请求；在服务端终端按 `Ctrl-C` 关闭。

## env_server_easydrive.py 参数

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `--host`、`--port` | `127.0.0.1`、`50052` | 客户端连接的 StreetWorld gRPC 地址 |
| `--web-host`、`--web-port` | `127.0.0.1`、`18080` | 浏览器查看画面的地址 |
| `--ad-policy-config` | `default` | 匹配模型所需的观测和时间周期；专用值为 `autovla`、`epona`、`openemma`、`transfuser`、`latent_transfuser` |
| `--video-output-dir` | `videos` | 视频保存目录 |
| `--async-mode` | 未开启 | 模型推理期间也推进仿真，详见[同步与异步](../guides/architecture/execution-mode.md#section-2-6) |
| `--nurec-grpc-host`、`--nurec-grpc-port` | `127.0.0.1`、`8080` | 选择 NuRec 时，连接 NuRec 渲染服务的地址 |
| `--nurec-grpc-timeout` | `600.0 s` | NuRec 渲染请求超时 |

<a id="scene-list-server"></a>

## 指定场景列表

批量测试或重复比较模型时，可以把要运行的场景保存在 `scenes.txt`，每行一个场景 ID：

```text
0007
0008
```

用 [env_server_scene_config.py](../../../streetworld/examples/env_server_scene_config.py) 启动服务端，就能直接按文件中的顺序运行，省去每次手动选择：

```bash
python -m streetworld.examples.env_server_scene_config \
  --scene-config scenes.txt --dataset nuscenes \
  --host 127.0.0.1 --port 50052 --web-port 18080
```

`--scene-config` 指向 UTF-8 文本文件。文件中只写场景 ID，不要加入空行或注释。这两个服务端提供相同的 gRPC 接口，客户端的连接方式相同。

## env_server_scene_config.py 参数

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `--scene-config` / `-c` | 必填 | 场景列表文本文件，每行一个场景 ID |
| `--dataset` | 必填 | `nuscenes`、`waymo` 或 `nurec` |
| `--host`、`--port` | `127.0.0.1`、`50052` | 客户端连接的 StreetWorld gRPC 地址 |
| `--web-host`、`--web-port` | `127.0.0.1`、`18080` | 浏览器查看画面的地址 |
| `--ad-policy-config` | `default` | 匹配模型所需的观测和时间周期；专用值为 `autovla`、`epona`、`openemma`、`transfuser`、`latent_transfuser` |
| `--video-output-dir` | `videos` | 视频保存目录 |
| `--async-mode` | 未开启 | 模型推理期间也推进仿真，详见[同步与异步](../guides/architecture/execution-mode.md#section-2-6) |
| `--nurec-grpc-host`、`--nurec-grpc-port` | `127.0.0.1`、`8080` | 选择 NuRec 时，连接 NuRec 渲染服务的地址 |
| `--nurec-grpc-timeout` | `600.0 s` | NuRec 渲染请求超时 |

nuScenes 和 Waymo 使用本地 ST Renderer，`--ad-policy-config` 在这两个数据集下生效。NuRec 需要另行启动渲染服务；该分支默认使用原始控制输入 Policy，接入轨迹模型时还需配置轨迹 Policy，见[NuRec 启动步骤](../guides/rendering-backends.md#nurec)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.2 用浏览器驾驶](web-controller.md) · [下一页：1.4 运行 Expert iLQR](expert-ilqr.md)
