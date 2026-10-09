<a id="launcher-uniad"></a>

# 7.2 UniAD

[English](../../en/launchers/uniad.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.1 统一启动流程](common.md) · [下一页：7.3 VAD](vad.md)

<a id="launcher-uniad-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装 PyTorch、MMCV 1.x CUDA ops、MMDetection、MMSegmentation、MMDetection3D，并注册 UniAD 插件。INSTALL.md 给出的依赖版本为 Torch 2.0.1/CUDA 11.8、mmcv-full 1.6.1、mmdet 2.26.0、mmsegmentation 0.29.1、mmdet3d 1.0.0rc6。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | UniAD_SIM/ | UniAD 视觉与规划组件 |
| 模型配置 | UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py | stage2 闭环规划配置 |
| 权重 | UniAD_SIM/ckpts/uniad_base_e2e.pth | 主模型 checkpoint |
| 依赖说明 | [INSTALL.md](../../../UniAD_SIM/docs/INSTALL.md) | 模型依赖和 CUDA 构建要求 |

将 stage2 权重放入表中的 ckpts 路径。native_agent.py 的 AD_root、配置和权重都使用相对路径，启动时进入 StreetWorld 根目录。

实现：[uniad/native_agent.py](../../../policy_launcher/uniad/native_agent.py)。

<a id="launcher-uniad-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-uniad-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model uniad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-uniad-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 planning.result_planning.sdc_traj，转换为车辆坐标 float32 (6,2) 未来轨迹；默认采样间隔 0.5 s。 |
| 注意事项 | 模型自身保留时序状态。默认配置启用视频和 WebUI；它们仍运行在仿真环境。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.1 统一启动流程](common.md) · [下一页：7.3 VAD](vad.md)
