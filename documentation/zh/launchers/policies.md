<a id="section-7-2"></a>

# 7.2 各模型启动说明

[English](../../en/launchers/policies.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.1 统一启动流程](common.md) · [下一页：总目录](../../DOCUMENTATION_ZH.md)

统一命令行通过 --model 选择模型，不提供 --checkpoint、--config 或 --model-root。文件路径在对应 NativeAgent 的构造配置中修改。

- [7.2.1 UniAD](#launcher-uniad)
- [7.2.2 VAD](#launcher-vad)
- [7.2.3 GenAD](#launcher-genad)
- [7.2.4 MomAD](#launcher-momad)
- [7.2.5 ST-P3](#launcher-stp3)
- [7.2.6 OpenDriveVLA](#launcher-opendrivevla)
- [7.2.7 Latent TransFuser](#launcher-latent_transfuser)
- [7.2.8 DiffusionDrive](#launcher-diffusiondrive)
- [7.2.9 SparseDrive](#launcher-sparsedrive)
- [7.2.10 Alpamayo 1](#launcher-alpamayo1)
- [7.2.11 Alpamayo 1.5](#launcher-alpamayo1-5)
- [7.2.12 AutoVLA](#launcher-autovla)
- [7.2.13 Epona](#launcher-epona)
- [7.2.14 OpenEMMA GPT](#launcher-openemma_gpt)
- [7.2.15 OpenEMMA Qwen](#launcher-openemma_qwen)
- [7.2.16 OpenEMMA LLaVA](#launcher-openemma_llava)
- [7.2.17 OpenEMMA Llama](#launcher-openemma_llama)

<a id="launcher-uniad"></a>

## 7.2.1 UniAD

<a id="launcher-uniad-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-uniad-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model uniad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-uniad-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 planning.result_planning.sdc_traj，转换为车辆坐标 float32 (6,2) 未来轨迹；默认采样间隔 0.5 s。 |
| 注意事项 | 模型自身保留时序状态。默认配置启用视频和 WebUI；它们仍运行在仿真环境。 |

<a id="launcher-vad"></a>

## 7.2.2 VAD

<a id="launcher-vad-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-vad-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model vad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-vad-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 从 pts_bbox.ego_fut_preds 按 ego_fut_cmd 选模式，累加增量后返回 float32 (6,2) 车辆坐标轨迹；采样间隔 0.5 s。 |
| 注意事项 | 缺相机或模型输出字段时适配器直接报错；服务端须使用轨迹跟踪 Policy。 |

<a id="launcher-genad"></a>

## 7.2.3 GenAD

<a id="launcher-genad-environment-and-resources"></a>

### 运行环境与资源

使用 Python 3.10 或更高版本，按 GenAD 要求安装 PyTorch、MMCV 1.x、MMDetection、MMSegmentation、MMDetection3D、timm 和 nuscenes-devkit。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | GenAD/ | GenAD 项目及 mmdet3d 插件 |
| 模型配置 | GenAD/projects/configs/GenAD/GenAD_config.py | 生成规划配置 |
| 权重 | GenAD/ckpts/checkpoints.pth | 主模型 checkpoint |
| 依赖说明 | [install.md](https://github.com/wzzheng/GenAD/blob/b16667f4a51612b577360c5df4fcdebc3e6f0d55/docs/install.md) | 模型依赖与 CUDA ops |

将完整 GenAD 权重保存为 checkpoints.pth。native_agent.py 按相对路径加载；修改文件名或位置时，同时修改构造配置。统一 CLI 没有 checkpoint 参数。

实现：[genad/native_agent.py](../../../policy_launcher/genad/native_agent.py)。

<a id="launcher-genad-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-genad-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model genad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-genad-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 按导航命令选择 ego_fut_preds 的模式，累加增量并转换为车辆坐标 float32 (6,2) 轨迹；采样间隔 0.5 s。 |
| 注意事项 | 输入先经 GenAD dataparser 处理并移到模型设备；输出格式必须含 pts_bbox 中的预测和命令字段。 |

<a id="launcher-momad"></a>

## 7.2.4 MomAD

<a id="launcher-momad-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-momad-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model momad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-momad-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，将固定 LiDAR 坐标变换为车辆坐标 float32 (6,2) 轨迹；采样间隔 0.5 s。 |
| 注意事项 | 切换 scene_token 时清理模型时序缓存。加载器临时切换到 open_loop 目录以解析资源，退出加载后恢复工作目录。 |

<a id="launcher-stp3"></a>

## 7.2.5 ST-P3

<a id="launcher-stp3-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-stp3-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model stp3 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-stp3-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 缓存 cfg.TIME_RECEPTIVE_FIELD 帧图像和 LiDAR-to-world 历史；历史不足时返回 None，服务端 iLQR 输出零控制。完整历史时由模型规划器返回车辆坐标未来轨迹，点数取 cfg.N_FUTURE_FRAMES、间隔 0.5 s。 |
| 注意事项 | 不能只给图像模型的权重或未启用规划的 checkpoint。时间历史按服务端每次返回的观测累积。 |

<a id="launcher-opendrivevla"></a>

## 7.2.6 OpenDriveVLA

<a id="launcher-opendrivevla-environment-and-resources"></a>

### 运行环境与资源

准备独立的 Python 3.10 环境。安装说明使用 PyTorch 2.1.2、CUDA 12.1、OpenDriveVLA 自带的 MMCV 1.7.2、MMDetection3D 1.0.0rc6 源码和 FlashAttention 2。默认 attn_implementation=flash_attention_2。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | OpenDriveVLA/ | LLaVA 与 UniAD 视觉模块 |
| 模型目录 | OpenDriveVLA/checkpoints/DriveVLA-Qwen2.5-0.5B-Instruct/ | 包含模型配置、tokenizer 与权重的完整目录 |
| 依赖说明 | [Launcher README](../../../policy_launcher/opendrivevla/README.md) | Python 3.10/Torch 2.1.2/CUDA 12.1 的本地构建步骤 |
| 依赖文件 | policy_launcher/opendrivevla/requirements.txt | 模型专用锁定依赖 |

先安装专用 requirements，再按 Launcher README 编译 third_party 下的两个 OpenMMLab 包，并安装与设备匹配的 FlashAttention。checkpoint 必须指向完整模型目录，不能只提供一个 pth 文件。

实现：[opendrivevla/native_agent.py](../../../policy_launcher/opendrivevla/native_agent.py)。

<a id="launcher-opendrivevla-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-opendrivevla-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model opendrivevla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-opendrivevla-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。主车历史位置和导航命令用于构造文本问题。 |
| 输出 | 解析模型文本中的六个轨迹点，先按 LiDAR 坐标解读，再转换为车辆坐标 float32 (6,2)；间隔 0.5 s。 |
| 注意事项 | 统一 CLI 不暴露 checkpoint、attn_implementation、max_new_tokens 或 bf16；在 OpenDriveVLANativeAgent 构造参数中设置。代码默认 max_new_tokens=512、bf16=False。文本格式无法解析时直接报错。 |

<a id="launcher-latent_transfuser"></a>

## 7.2.7 Latent TransFuser

<a id="launcher-latent_transfuser-environment-and-resources"></a>

### 运行环境与资源

安装 PyTorch、timm、torch-scatter、MMCV、MMSegmentation、MMDetection 等 TransFuser 依赖。Launcher 使用 team_code_transfuser 的模型与数据处理代码，场景加载和物理推进由 StreetWorld 服务端执行。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | TransFuser/team_code_transfuser/ | LidarCenterNet 与控制器代码 |
| 模型目录 | TransFuser/model_ckpt/models_2022/latentTF/ | args.txt 和至少一个 *.pth |
| 模型参数 | 模型目录内 args.txt | JSON 配置，backbone 必须为 latentTF |
| 依赖说明 | [TransFuser README](https://github.com/autonomousvision/transfuser/blob/9d413b2ad2d2d56c112b34a4a799be081800d77f/README.md) | 模型依赖、torch-scatter 和 OpenMMLab ops |

模型目录需要 args.txt 和 *.pth 权重。加载器默认加载目录中的全部权重并平均预测，args.txt 的 backbone 必须为 latentTF。缺少权重或 backbone 不匹配时启动失败。

实现：[latent_transfuser/native_agent.py](../../../policy_launcher/latent_transfuser/native_agent.py)。

<a id="launcher-latent_transfuser-server-configuration"></a>

### 服务端配置

使用 [Latent TransFuser 控制量服务端](common.md#latent-control-server)，明确设置 EnvInputPolicy。--ad-policy-config latent_transfuser 只配置相机和导航，主车 Policy 仍为 iLQR。

<a id="launcher-latent_transfuser-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model latent_transfuser --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-latent_transfuser-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT_LEFT、FRONT、FRONT_RIGHT，主车速度，以及 navigation.carla_style_target。使用 TransFuser preset 的 480×960、焦距 760 px、位置 (1.3,0,2.3) 三相机。 |
| 输出 | 模型生成路径后在客户端执行 PID，predict_action 返回 (steering, throttle_brake) 两个归一化控制量。 |
| 注意事项 | 服务端使用 EnvInputPolicy 接收控制量。brake=True 时 Launcher 返回 throttle_brake=0.0，不返回负制动值。 |

<a id="launcher-diffusiondrive"></a>

## 7.2.8 DiffusionDrive

<a id="launcher-diffusiondrive-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-diffusiondrive-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model diffusiondrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-diffusiondrive-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，经固定 LiDAR-to-ego 变换返回车辆坐标 float32 (6,2)；间隔 0.5 s。 |
| 注意事项 | scene_token 变化时重置时序缓存。主模型、checkpoint 和资源必须与加载器固定的 stage2 配置一致。 |

<a id="launcher-sparsedrive"></a>

## 7.2.9 SparseDrive

<a id="launcher-sparsedrive-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-sparsedrive-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model sparsedrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-sparsedrive-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_RIGHT、FRONT_LEFT、BACK、BACK_LEFT、BACK_RIGHT 六相机，及其 K/ego2camera。 |
| 输出 | 读取 img_bbox.final_planning，转换为车辆坐标 float32 (6,2) 轨迹；间隔 0.5 s。 |
| 注意事项 | 相机投影按 K 与 ego2camera 构建；缺相机、K 尺寸不符或外参不是 4×4 时适配器直接报错。 |

<a id="launcher-alpamayo1"></a>

## 7.2.10 Alpamayo 1

<a id="launcher-alpamayo1-environment-and-resources"></a>

### 运行环境与资源

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

### 服务端配置

使用 [NuRec 轨迹服务端](common.md#alpamayo-trajectory-server)，设置 trajectory_dt=0.1 s、control_dt=0.1 s、decision_repeat=5。NuRec CLI 的默认分支使用原始输入 Policy，需要先切换为轨迹 Policy。

<a id="launcher-alpamayo1-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model alpamayo1 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-alpamayo1-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | camera_cross_left_120fov、camera_front_wide_120fov、camera_cross_right_120fov、camera_front_tele_30fov 四个 NuRec 相机。模型使用 16 帧主车位姿历史和最近 4 帧相机图像；启动时重复第一帧填满历史缓存。 |
| 输出 | 模型必须返回 (64,3) 轨迹，Launcher 保留前两维为车辆坐标 float32 (64,2)，间隔 0.1 s、预测范围 6.4 s。 |
| 注意事项 | 只接受 CUDA 设备，模型目录缺 config.json 时启动失败。默认采样 top_p=0.98、temperature=0.6，每次一条轨迹。 |

<a id="launcher-alpamayo1-5"></a>

## 7.2.11 Alpamayo 1.5

<a id="launcher-alpamayo1-5-environment-and-resources"></a>

### 运行环境与资源

使用 Python 3.12.x、Torch 2.8.0、Transformers 4.57.1 和 FlashAttention，版本要求见本地 pyproject.toml。加载器只接受 CUDA，以 bfloat16 推理；上游安装说明给出的单样本显存要求约为 24 GB。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | alpamayo1.5/src/ | Alpamayo 模型包 |
| 模型目录 | alpamayo1.5/model/ | 完整 from_pretrained 目录，必须有 config.json |
| 依赖文件 | [alpamayo1.5/pyproject.toml](https://github.com/NVlabs/alpamayo1.5/blob/87fb9036aac318535a7a0d9e739a5476ceea8b4e/pyproject.toml) | Python 3.12、Torch 和模型依赖 |
| 安装说明 | [README.md](https://github.com/NVlabs/alpamayo1.5/blob/87fb9036aac318535a7a0d9e739a5476ceea8b4e/README.md) | 模型资源与 uv 环境准备 |

在 StreetWorld 根目录运行以下命令，准备模型环境后回到根目录：

```bash
cd alpamayo1.5
uv venv --python 3.12 streetworld_model_venv
source streetworld_model_venv/bin/activate
uv sync --active
cd ..
```

完整模型放入表中的本地目录。加载器直接读取这个目录，不会自动改用远程模型 ID。

实现：[alpamayo1_5/native_agent.py](../../../policy_launcher/alpamayo1_5/native_agent.py)。

<a id="launcher-alpamayo1-5-server-configuration"></a>

### 服务端配置

使用 [NuRec 轨迹服务端](common.md#alpamayo-trajectory-server)，设置 trajectory_dt=0.1 s、control_dt=0.1 s、decision_repeat=5。NuRec CLI 的默认分支使用原始输入 Policy，需要先切换为轨迹 Policy。

<a id="launcher-alpamayo1-5-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model alpamayo1.5 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-alpamayo1-5-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | camera_cross_left_120fov、camera_front_wide_120fov、camera_cross_right_120fov、camera_front_tele_30fov 四个 NuRec 相机。模型使用 16 帧主车位姿历史和最近 4 帧相机图像；启动时重复第一帧填满历史缓存。 |
| 输出 | 模型必须返回 (64,3) 轨迹，Launcher 保留前两维为车辆坐标 float32 (64,2)，间隔 0.1 s、预测范围 6.4 s。 |
| 注意事项 | 只接受 CUDA 设备，模型目录缺 config.json 时启动失败。1.5 还向模型传 camera_indices=(0,1,2,6)。 |

<a id="launcher-autovla"></a>

## 7.2.12 AutoVLA

<a id="launcher-autovla-environment-and-resources"></a>

### 运行环境与资源

安装 PyTorch、支持 Qwen2.5-VL 的 Transformers、qwen_vl_utils、PyTorch Lightning 和 AutoVLA 项目依赖。除主 checkpoint 外，还需准备基础模型和动作 codebook。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | AutoVLA/ | AutoVLA 和 navsim 路径 |
| 模型配置 | AutoVLA/config/eval/qwen2.5-vl-3B-nusc-sft-eval.yaml | 视频、动作词表与采样设置 |
| 主权重 | AutoVLA/checkpoints/AutoVLA/AutoVLA_PDMS_89.ckpt | AutoVLA checkpoint |
| 基础模型 | AutoVLA/Qwen2.5-VL-3B-Instruct/ | 配置 model.pretrained_model_path |
| 动作词表 | AutoVLA/codebook_cache/agent_vocab.pkl | 配置 model.codebook_cache_path |
| 依赖说明 | [AutoVLA README](https://github.com/ucla-mobility/AutoVLA/blob/ba34eed74ce6729e7986592d0e66cbaca397b4fa/README.md) | 模型环境和项目依赖 |

配置中的 pretrained_model_path、codebook_cache_path 相对于 AutoVLA 根目录解析。模型配置和主 checkpoint 使用 native_agent.py 指定的路径。

实现：[autovla/native_agent.py](../../../policy_launcher/autovla/native_agent.py)。

<a id="launcher-autovla-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config autovla
```

<a id="launcher-autovla-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model autovla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-autovla-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_LEFT、FRONT_RIGHT 三相机；各相机维护 4 帧、间隔 0.5 s 的视频历史。还读取主车速度、转向、加速度和导航命令。 |
| 输出 | 生成动作 token 后解码为车辆坐标 float32 (10,2) 轨迹；模型配置为 0.5 s 间隔、5 s 范围。 |
| 注意事项 | autovla 服务端 preset 设置 warmup_step=4，轨迹与控制间隔均为 0.5 s。初始化历史不足的帧由客户端缓存逻辑处理。 |

<a id="launcher-epona"></a>

## 7.2.13 Epona

<a id="launcher-epona-environment-and-resources"></a>

### 运行环境与资源

使用 Python 3.10 或更高版本，安装支持 CUDA 的 PyTorch、Epona 模型和 DCAE tokenizer 依赖。加载器只在 CUDA 上运行，推理使用 bfloat16 autocast。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | Epona/ | 模型、tokenizer 与配置工具 |
| 模型配置 | Epona/configs/dit_config_dcae_nuscenes.py | 默认 condition_frames=10、traj_len=15 |
| 主权重 | Epona/pretrained/epona_nuplan+nusc.pkl | 世界模型/轨迹模型 checkpoint |
| VAE 权重 | Epona/pretrained/dcae_td_20000.pkl | VAETokenizer checkpoint |
| 依赖说明 | [Epona README](https://github.com/Kevin-thu/Epona/blob/69b24c55f5ab8b3ffde8fa55e9f833bfe64d2c68/README.md) | Python 3.10、PyTorch/CUDA 与 requirements.txt |

主权重和 VAE 权重放到表中的 pretrained 目录。加载器覆盖配置中的 VAE 路径，并设置 batch_size=1。gRPC 直接提供观测，上游训练数据集路径不会用于读取这些输入。

实现：[epona/native_agent.py](../../../policy_launcher/epona/native_agent.py)。

<a id="launcher-epona-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config epona
```

<a id="launcher-epona-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model epona --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-epona-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 图像、主车位置和旋转；缓存 condition_frames 帧，当前配置为 10。输入是客户端收到的连续观测帧。 |
| 输出 | 模型 step_eval(..., traj_only=True) 输出 predict_traj，返回其前两维；默认 traj_len=15，服务端 trajectory_dt=0.1 s。 |
| 注意事项 | epona preset 设置 trajectory_dt=0.1 s、warmup_step=10；环境决策周期和 control_dt 仍为 0.5 s，收到的观测为 2 Hz。上游 downsample_fps=10，两处频率设置不同。 |

<a id="launcher-openemma_gpt"></a>

## 7.2.14 OpenEMMA GPT

<a id="launcher-openemma_gpt-environment-and-resources"></a>

### 运行环境与资源

安装 openai 和 Pillow，在 OPENAI_API_KEY 中设置 API 密钥。Launcher 通过 OpenAI SDK 请求模型，默认模型名见表。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | gpt-4o-2024-11-20 | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

在运行 Launcher 的终端设置 OPENAI_API_KEY。修改模型名时，设置 OpenEMMANativeAgent 的构造参数 model_id；统一 CLI 未提供这个参数。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_gpt-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_gpt-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_gpt --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_gpt-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | GPT 请求包含图像与文本；每轮规划分别生成场景描述、关注对象、驾驶意图和未来速度/曲率。--device 对此后端不生效。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

<a id="launcher-openemma_qwen"></a>

## 7.2.15 OpenEMMA Qwen

<a id="launcher-openemma_qwen-environment-and-resources"></a>

### 运行环境与资源

安装 PyTorch、Transformers、Accelerate、qwen_vl_utils 和 Pillow。加载器使用 Qwen2VLForConditionalGeneration，设置 bfloat16、sdpa 和 device_map="auto"。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | Qwen/Qwen2-VL-7B-Instruct | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

下载表中的 Hugging Face 模型或准备本地缓存。模型配置的 model_type 必须是 qwen2_vl，加载器会检查这一项。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_qwen-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_qwen-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_qwen --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_qwen-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用历史中的最后一张，运动提示使用十帧历史。--device 没有传给此类，设备由 device_map="auto" 决定。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

<a id="launcher-openemma_llava"></a>

## 7.2.16 OpenEMMA LLaVA

<a id="launcher-openemma_llava-environment-and-resources"></a>

### 运行环境与资源

将 OpenEMMA 源码放在 StreetWorld 根目录，其中提供 llava.model.builder。按 OpenEMMA/requirements.txt 安装 PyTorch、Transformers、CUDA 和图像处理依赖。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | liuhaotian/llava-v1.6-mistral-7b | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

加载器将 OpenEMMA/ 添加到 Python 路径，以 llava-v1.6-mistral-7b 名称创建模型。按表准备模型资源；移动源码目录时，修改 backbone.py 的 source_root。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_llava-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llava-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_llava --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llava-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用最后一张，张量通过 .cuda() 移到 GPU；统一 --device 没有传入模型。需要指定可见 GPU 时在启动进程前设置 CUDA_VISIBLE_DEVICES。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

<a id="launcher-openemma_llama"></a>

## 7.2.17 OpenEMMA Llama

<a id="launcher-openemma_llama-environment-and-resources"></a>

### 运行环境与资源

安装 PyTorch、支持 MllamaForConditionalGeneration 的 Transformers、Accelerate 和 Pillow。加载器使用 bfloat16、device_map="auto"。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | meta-llama/Llama-3.2-11B-Vision-Instruct | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

准备完整的 Llama 3.2 Vision 模型，并确认账户具有访问权限。加载器通过 AutoProcessor 和 MllamaForConditionalGeneration.from_pretrained 读取表中的模型名。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_llama-server-configuration"></a>

### 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llama-launch-command"></a>

### 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_llama --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llama-input-output-and-limits"></a>

### 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用最后一张，文本包含十帧运动历史。--device 没有传给此类，设备由模型加载器决定。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.1 统一启动流程](common.md) · [下一页：总目录](../../DOCUMENTATION_ZH.md)
