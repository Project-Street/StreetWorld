<a id="launcher-alpamayo1"></a>

# 7.11 Alpamayo 1

[English](../../en/launchers/alpamayo1.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.10 SparseDrive](sparsedrive.md) · [下一页：7.12 Alpamayo 1.5](alpamayo1.5.md)

<a id="launcher-alpamayo1-environment-and-resources"></a>

## 运行环境与资源

使用 Python 3.12.x、Torch 2.8.0、Transformers 4.57.1 和 FlashAttention，版本要求见本地 pyproject.toml。加载器只接受 CUDA，以 bfloat16 推理；上游安装说明给出的单样本显存要求约为 24 GB。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | alpamayo1/src/ | Alpamayo 模型包 |
| 模型目录 | alpamayo1/Alpamayo-R1-10B/ | 完整 from_pretrained 目录，必须有 config.json |
| 依赖文件 | [alpamayo1/pyproject.toml](https://github.com/NVlabs/alpamayo/blob/main/pyproject.toml) | Python 3.12、Torch 和模型依赖 |
| 安装说明 | [README.md](https://github.com/NVlabs/alpamayo/blob/main/README.md) | 模型资源与 uv 环境准备 |

在 StreetWorld 根目录运行以下命令，准备模型环境后回到根目录：

```bash
cd alpamayo1
uv venv --python 3.12 streetworld_model_venv
source streetworld_model_venv/bin/activate
uv sync --active
cd ..
```

完整模型放入表中的本地目录。加载器直接读取这个目录，不会自动改用远程模型 ID。

实现：[alpamayo_r1/native_agent.py](../../../policy_launcher/alpamayo_r1/native_agent.py)。

<a id="launcher-alpamayo1-server-configuration"></a>

## 服务端配置

使用 [NuRec 轨迹服务端](common.md#alpamayo-trajectory-server)，设置 trajectory_dt=0.1 s、control_dt=0.1 s、decision_repeat=5。NuRec CLI 的默认分支使用原始输入 Policy，需要先切换为轨迹 Policy。

<a id="launcher-alpamayo1-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model alpamayo1 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-alpamayo1-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | camera_cross_left_120fov、camera_front_wide_120fov、camera_cross_right_120fov、camera_front_tele_30fov 四个 NuRec 相机。模型使用 16 帧主车位姿历史和最近 4 帧相机图像；启动时重复第一帧填满历史缓存。 |
| 输出 | 模型必须返回 (64,3) 轨迹，Launcher 保留前两维为车辆坐标 float32 (64,2)，间隔 0.1 s、预测范围 6.4 s。 |
| 注意事项 | 只接受 CUDA 设备，模型目录缺 config.json 时启动失败。默认采样 top_p=0.98、temperature=0.6，每次一条轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.10 SparseDrive](sparsedrive.md) · [下一页：7.12 Alpamayo 1.5](alpamayo1.5.md)
