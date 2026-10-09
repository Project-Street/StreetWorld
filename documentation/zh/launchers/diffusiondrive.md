<a id="launcher-diffusiondrive"></a>

# 7.9 DiffusionDrive

[English](../../en/launchers/diffusiondrive.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.8 Latent TransFuser](latent_transfuser.md) · [下一页：7.10 SparseDrive](sparsedrive.md)

<a id="launcher-diffusiondrive-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装 PyTorch、MMCV 1.x、MMDetection3D 和项目插件，按 DiffusionDrive 工程要求编译 motion_blocks_v11 等 CUDA 扩展。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | DiffusionDrive/ | 模型及 mmdet3d 插件 |
| 模型配置 | DiffusionDrive/projects/configs/diffusiondrive_configs/diffusiondrive_small_stage2.py | 加载器固定配置 |
| 权重 | DiffusionDrive/ckpts/diffusiondrive_nusc_stage2.pth | 主模型 checkpoint |
| 依赖说明 | [requirement.txt](https://github.com/hustvl/diffusiondrive/blob/ae54fd87b32b3762f20e63ffd0af91d343cade85/requirement.txt) | 模型依赖版本 |

加载器进入工程目录注册插件、创建模型并读取 checkpoint。配置引用的 anchor 等相对资源须放到工程指定位置。

实现：[diffusiondrive/native_agent.py](../../../policy_launcher/diffusiondrive/native_agent.py)。

<a id="launcher-diffusiondrive-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-diffusiondrive-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model diffusiondrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-diffusiondrive-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，经固定 LiDAR-to-ego 变换返回车辆坐标 float32 (6,2)；间隔 0.5 s。 |
| 注意事项 | scene_token 变化时重置时序缓存。主模型、checkpoint 和资源必须与加载器固定的 stage2 配置一致。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.8 Latent TransFuser](latent_transfuser.md) · [下一页：7.10 SparseDrive](sparsedrive.md)
