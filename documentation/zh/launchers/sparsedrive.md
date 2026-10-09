<a id="launcher-sparsedrive"></a>

# 7.10 SparseDrive

[English](../../en/launchers/sparsedrive.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.9 DiffusionDrive](diffusiondrive.md) · [下一页：7.11 Alpamayo 1](alpamayo1.md)

<a id="launcher-sparsedrive-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装 PyTorch、MMCV 1.x、MMDetection 和 SparseDrive 插件，并编译 deformable_aggregation CUDA 扩展。requirement.txt 指定 mmcv_full 1.7.1、mmdet 2.28.2。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | SparseDrive/ | 模型及 mmdet3d 插件 |
| 模型配置 | SparseDrive/projects/configs/sparsedrive_small_stage2.py | 加载器固定配置 |
| 权重 | SparseDrive/ckpt/sparsedrive_stage2.pth | 主模型 checkpoint |
| 依赖说明 | [quick_start.md](https://github.com/swc-17/SparseDrive/blob/ec0225d4b7a2dd7e6ce10179a2b7660dcb74b2f1/docs/quick_start.md) | deformable_aggregation 构建及 anchor 资源 |

在 projects/mmdet3d_plugin/ops 下编译扩展，准备配置引用的 anchor、kmeans 文件。加载器通过 mmdet.models.build_detector 创建模型。

实现：[sparsedrive/native_agent.py](../../../policy_launcher/sparsedrive/native_agent.py)。

<a id="launcher-sparsedrive-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-sparsedrive-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model sparsedrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-sparsedrive-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，转换为车辆坐标 float32 (6,2) 轨迹；间隔 0.5 s。 |
| 注意事项 | 相机投影按 K 与 ego2camera 构建；缺相机、K 尺寸不符或外参不是 4×4 时适配器直接报错。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.9 DiffusionDrive](diffusiondrive.md) · [下一页：7.11 Alpamayo 1](alpamayo1.md)
