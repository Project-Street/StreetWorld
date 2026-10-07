<a id="launcher-latent_transfuser"></a>

# 7.2.7 Latent TransFuser

[English](../../en/launchers/latent_transfuser.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.6 OpenDriveVLA](opendrivevla.md) · [下一页：7.2.8 DiffusionDrive](diffusiondrive.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

安装 PyTorch、timm、torch-scatter、MMCV、MMSegmentation、MMDetection 等 TransFuser 依赖。Launcher 使用 team_code_transfuser 的模型与数据处理代码，场景加载和物理推进由 StreetWorld 服务端执行。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | TransFuser/team_code_transfuser/ | LidarCenterNet 与控制器代码 |
| 模型目录 | TransFuser/model_ckpt/models_2022/latentTF/ | args.txt 和至少一个 *.pth |
| 模型参数 | 模型目录内 args.txt | JSON 配置，backbone 必须为 latentTF |
| 依赖说明 | [TransFuser README](https://github.com/autonomousvision/transfuser/blob/9d413b2ad2d2d56c112b34a4a799be081800d77f/README.md) | 模型依赖、torch-scatter 和 OpenMMLab ops |

模型目录需要 args.txt 和 *.pth 权重。加载器默认加载目录中的全部权重并平均预测，args.txt 的 backbone 必须为 latentTF。缺少权重或 backbone 不匹配时启动失败。

实现：[latent_transfuser/native_agent.py](../../../policy_launcher/latent_transfuser/native_agent.py)。

<a id="server-configuration"></a>

## 服务端配置

使用 [Latent TransFuser 控制量服务端](common.md#latent-control-server)，明确设置 EnvInputPolicy。--ad-policy-config latent_transfuser 只配置相机和导航，主车 Policy 仍为 iLQR。

<a id="launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model latent_transfuser --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT_LEFT、FRONT、FRONT_RIGHT，主车速度，以及 navigation.carla_style_target。使用 TransFuser preset 的 480×960、焦距 760 px、位置 (1.3,0,2.3) 三相机。 |
| 输出 | 模型生成路径后在客户端执行 PID，predict_action 返回 (steering, throttle_brake) 两个归一化控制量。 |
| 注意事项 | 服务端使用 EnvInputPolicy 接收控制量。brake=True 时 Launcher 返回 throttle_brake=0.0，不返回负制动值。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.6 OpenDriveVLA](opendrivevla.md) · [下一页：7.2.8 DiffusionDrive](diffusiondrive.md)
