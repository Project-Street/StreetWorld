<a id="launcher-genad"></a>

# 7.2.3 GenAD

[English](../../en/launchers/genad.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.2 VAD](vad.md) · [下一页：7.2.4 MomAD](momad.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，按 GenAD 要求安装 PyTorch、MMCV 1.x、MMDetection、MMSegmentation、MMDetection3D、timm 和 nuscenes-devkit。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | GenAD/ | GenAD 项目及 mmdet3d 插件 |
| 模型配置 | GenAD/projects/configs/GenAD/GenAD_config.py | 生成规划配置 |
| 权重 | GenAD/ckpts/checkpoints.pth | 主模型 checkpoint |
| 依赖说明 | [install.md](https://github.com/wzzheng/GenAD/blob/b16667f4a51612b577360c5df4fcdebc3e6f0d55/docs/install.md) | 模型依赖与 CUDA ops |

将完整 GenAD 权重保存为 checkpoints.pth。native_agent.py 按相对路径加载；修改文件名或位置时，同时修改构造配置。统一 CLI 没有 checkpoint 参数。

实现：[genad/native_agent.py](../../../policy_launcher/genad/native_agent.py)。

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
  --model genad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 按导航命令选择 ego_fut_preds 的模式，累加增量并转换为车辆坐标 float32 (6,2) 轨迹；采样间隔 0.5 s。 |
| 注意事项 | 输入先经 GenAD dataparser 处理并移到模型设备；输出格式必须含 pts_bbox 中的预测和命令字段。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.2 VAD](vad.md) · [下一页：7.2.4 MomAD](momad.md)
