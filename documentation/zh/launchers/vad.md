<a id="launcher-vad"></a>

# 7.3 VAD

[English](../../en/launchers/vad.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2 UniAD](uniad.md) · [下一页：7.4 GenAD](genad.md)

<a id="launcher-vad-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装 PyTorch、MMCV 1.x、MMDetection、MMSegmentation、MMDetection3D、timm 和 nuscenes-devkit。CUDA ops 的构建版本须匹配 PyTorch/CUDA。上游安装文件中的 Python 3.8 无法运行 Launcher。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | VAD/ | VAD 项目及 mmdet3d 插件 |
| 模型配置 | VAD/projects/configs/VAD/VAD_base_stage_2.py | stage2 模型结构与测试配置 |
| 权重 | VAD/ckpts/VAD_base.pth | 主模型 checkpoint |
| 依赖说明 | [install.md](https://github.com/hustvl/VAD/blob/1688c4b1c3a9e2e7873ca9700ff8058170c0e3c8/docs/install.md) | PyTorch/MMCV/MMDetection3D 环境要求 |

配置和权重按相对于 StreetWorld 根目录的路径加载。评测需要表中的完整 VAD checkpoint。

实现：[vad/native_agent.py](../../../policy_launcher/vad/native_agent.py)。

<a id="launcher-vad-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-vad-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model vad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-vad-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 从 pts_bbox.ego_fut_preds 按 ego_fut_cmd 选模式，累加增量后返回 float32 (6,2) 车辆坐标轨迹；采样间隔 0.5 s。 |
| 注意事项 | 缺相机或模型输出字段时适配器直接报错；服务端须使用轨迹跟踪 Policy。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2 UniAD](uniad.md) · [下一页：7.4 GenAD](genad.md)
