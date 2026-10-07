<a id="launcher-opendrivevla"></a>

# 7.2.6 OpenDriveVLA

[English](../../en/launchers/opendrivevla.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.5 ST-P3](stp3.md) · [下一页：7.2.7 Latent TransFuser](latent_transfuser.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

准备独立的 Python 3.10 环境。安装说明使用 PyTorch 2.1.2、CUDA 12.1、OpenDriveVLA 自带的 MMCV 1.7.2、MMDetection3D 1.0.0rc6 源码和 FlashAttention 2。默认 attn_implementation=flash_attention_2。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | OpenDriveVLA/ | LLaVA 与 UniAD 视觉模块 |
| 模型目录 | OpenDriveVLA/checkpoints/DriveVLA-Qwen2.5-0.5B-Instruct/ | 包含模型配置、tokenizer 与权重的完整目录 |
| 依赖说明 | [Launcher README](../../../policy_launcher/opendrivevla/README.md) | Python 3.10/Torch 2.1.2/CUDA 12.1 的本地构建步骤 |
| 依赖文件 | policy_launcher/opendrivevla/requirements.txt | 模型专用锁定依赖 |

先安装专用 requirements，再按 Launcher README 编译 third_party 下的两个 OpenMMLab 包，并安装与设备匹配的 FlashAttention。checkpoint 必须指向完整模型目录，不能只提供一个 pth 文件。

实现：[opendrivevla/native_agent.py](../../../policy_launcher/opendrivevla/native_agent.py)。

<a id="server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model opendrivevla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。主车历史位置和导航命令用于构造文本问题。 |
| 输出 | 解析模型文本中的六个轨迹点，先按 LiDAR 坐标解读，再转换为车辆坐标 float32 (6,2)；间隔 0.5 s。 |
| 注意事项 | 统一 CLI 不暴露 checkpoint、attn_implementation、max_new_tokens 或 bf16；在 OpenDriveVLANativeAgent 构造参数中设置。代码默认 max_new_tokens=512、bf16=False。文本格式无法解析时直接报错。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.5 ST-P3](stp3.md) · [下一页：7.2.7 Latent TransFuser](latent_transfuser.md)
