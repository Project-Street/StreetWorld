<a id="launcher-stp3"></a>

# 7.6 ST-P3

[English](../../en/launchers/stp3.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.5 MomAD](momad.md) · [下一页：7.7 OpenDriveVLA](opendrivevla.md)

<a id="launcher-stp3-environment-and-resources"></a>

## 运行环境与资源

安装 PyTorch、PyTorch Lightning、efficientnet-pytorch、fvcore、timm、nuscenes-devkit 和 lyft-dataset-sdk。Launcher 需要 Python 3.10 或更高版本；上游 environment.yml 中的 Python 3.7 环境无法直接使用。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | ST-P3/ | stp3 Python 包与规划器 |
| 模型配置 | checkpoint 内的 cfg | 加载器直接读取 checkpoint 保存的配置 |
| 权重 | ST-P3/ckpts/stp3_nuscenes.ckpt | NuScenes、启用规划的 Lightning checkpoint |
| 依赖说明 | [environment.yml](https://github.com/OpenDriveLab/ST-P3/blob/69aabefd2610951d9e34238142776ed2228673be/environment.yml) | PyTorch Lightning、efficientnet-pytorch、fvcore 等依赖 |

加载器调用 TrainingModule.load_from_checkpoint，再从 trainer.model 读取 cfg。权重内的 DATASET.NAME 须为 nuscenes，PLANNING.ENABLED 须为 True，否则启动时抛出 ValueError。

实现：[stp3/native_agent.py](../../../policy_launcher/stp3/native_agent.py)。

<a id="launcher-stp3-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-stp3-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model stp3 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-stp3-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 缓存 cfg.TIME_RECEPTIVE_FIELD 帧图像和 LiDAR-to-world 历史；历史不足时返回 None，服务端 iLQR 输出零控制。完整历史时由模型规划器返回车辆坐标未来轨迹，点数取 cfg.N_FUTURE_FRAMES、间隔 0.5 s。 |
| 注意事项 | 不能只给图像模型的权重或未启用规划的 checkpoint。时间历史按服务端每次返回的观测累积。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.5 MomAD](momad.md) · [下一页：7.7 OpenDriveVLA](opendrivevla.md)
