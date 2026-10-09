<a id="launcher-momad"></a>

# 7.5 MomAD

[English](../../en/launchers/momad.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.4 GenAD](genad.md) · [下一页：7.6 ST-P3](stp3.md)

<a id="launcher-momad-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.10 或更高版本，安装 PyTorch、MMCV 1.x、MMDetection、MMDetection3D 和 FlashAttention。MomAD 的 deformable_aggregation CUDA 扩展需在这个模型环境中编译。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | MomAD/open_loop/ | 模型工程根目录 |
| 模型配置 | MomAD/open_loop/projects/configs/MomAD_small_stage2_roboAD.py | 加载器固定使用的配置 |
| 权重 | MomAD/open_loop/ckpt/iter_29300.pth | 主模型 checkpoint |
| 依赖说明 | [quick_start.md](https://github.com/adept-thu/MomAD/blob/7d2247605364e1aba8d7ba4e99f57d01fc452f8c/open_loop/docs/quick_start.md) | 依赖和 deformable_aggregation 编译 |

安装 open_loop/requirement.txt 中的依赖，并在 projects/mmdet3d_plugin/ops 下编译扩展。anchors、kmeans 等相对路径以工程根目录为起点，按上游 quick_start 准备资源。

实现：[momad/native_agent.py](../../../policy_launcher/momad/native_agent.py)。

<a id="launcher-momad-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-momad-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model momad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-momad-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，将固定 LiDAR 坐标变换为车辆坐标 float32 (6,2) 轨迹；采样间隔 0.5 s。 |
| 注意事项 | 切换 scene_token 时清理模型时序缓存。加载器临时切换到 open_loop 目录以解析资源，退出加载后恢复工作目录。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.4 GenAD](genad.md) · [下一页：7.6 ST-P3](stp3.md)
