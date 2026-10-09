<a id="launcher-epona"></a>

# 7.14 Epona

[English](../../en/launchers/epona.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.13 AutoVLA](autovla.md) · [下一页：7.15 OpenEMMA GPT](openemma_gpt.md)

<a id="launcher-epona-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装支持 CUDA 的 PyTorch、Epona 模型和 DCAE tokenizer 依赖。加载器只在 CUDA 上运行，推理使用 bfloat16 autocast。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | Epona/ | 模型、tokenizer 与配置工具 |
| 模型配置 | Epona/configs/dit_config_dcae_nuscenes.py | 默认 condition_frames=10、traj_len=15 |
| 主权重 | Epona/pretrained/epona_nuplan+nusc.pkl | 世界模型/轨迹模型 checkpoint |
| VAE 权重 | Epona/pretrained/dcae_td_20000.pkl | VAETokenizer checkpoint |
| 依赖说明 | [Epona README](https://github.com/Kevin-thu/Epona/blob/69b24c55f5ab8b3ffde8fa55e9f833bfe64d2c68/README.md) | Python 3.10、PyTorch/CUDA 与 requirements.txt |

主权重和 VAE 权重放到表中的 pretrained 目录。加载器覆盖配置中的 VAE 路径，并设置 batch_size=1。gRPC 直接提供观测，上游训练数据集路径不会用于读取这些输入。

实现：[epona/native_agent.py](../../../policy_launcher/epona/native_agent.py)。

<a id="launcher-epona-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config epona
```

<a id="launcher-epona-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model epona --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-epona-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 图像、主车位置和旋转；缓存 condition_frames 帧，当前配置为 10。输入是客户端收到的连续观测帧。 |
| 输出 | 模型 step_eval(..., traj_only=True) 输出 predict_traj，返回其前两维；默认 traj_len=15，服务端 trajectory_dt=0.1 s。 |
| 注意事项 | epona preset 设置 trajectory_dt=0.1 s、warmup_step=10；环境决策周期和 control_dt 仍为 0.5 s，收到的观测为 2 Hz。上游 downsample_fps=10，两处频率设置不同。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.13 AutoVLA](autovla.md) · [下一页：7.15 OpenEMMA GPT](openemma_gpt.md)
