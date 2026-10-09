<a id="section-7-2"></a>

# 7.2 Launch instructions by model

[简体中文](../../zh/launchers/policies.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.1 Common launch procedure](common.md) · [Next: Contents](../../DOCUMENTATION_EN.md)

The shared CLI selects models with --model. It does not provide --checkpoint, --config, or --model-root; change file paths in the corresponding NativeAgent constructor settings.

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

### Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x CUDA ops, MMDetection, MMSegmentation, and MMDetection3D, then register the UniAD plugin. INSTALL.md specifies Torch 2.0.1/CUDA 11.8, mmcv-full 1.6.1, mmdet 2.26.0, mmsegmentation 0.29.1, and mmdet3d 1.0.0rc6.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | UniAD_SIM/ | UniAD vision and planning components |
| Model configuration | UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py | Stage 2 closed-loop planning configuration |
| Weights | UniAD_SIM/ckpts/uniad_base_e2e.pth | Main model checkpoint |
| Dependency guide | [INSTALL.md](../../../UniAD_SIM/docs/INSTALL.md) | Model dependencies and CUDA build requirements |

Place the Stage 2 weights at the ckpts path in the table. native_agent.py uses relative AD_root, configuration, and weight paths; launch from the StreetWorld root.

Implementation: [uniad/native_agent.py](../../../policy_launcher/uniad/native_agent.py).

<a id="launcher-uniad-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-uniad-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model uniad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-uniad-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads planning.result_planning.sdc_traj and converts it to a float32 (6, 2) future trajectory in vehicle coordinates, sampled at 0.5 s by default |
| Notes | The model retains temporal state. Video and WebUI are enabled by default and run in the simulation environment. |

<a id="launcher-vad"></a>

## 7.2.2 VAD

<a id="launcher-vad-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, MMSegmentation, MMDetection3D, timm, and nuscenes-devkit. Build CUDA ops against matching PyTorch/CUDA versions. The upstream Python 3.8 environment cannot run Launcher.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | VAD/ | VAD project and mmdet3d plugin |
| Model configuration | VAD/projects/configs/VAD/VAD_base_stage_2.py | Stage 2 model and test configuration |
| Weights | VAD/ckpts/VAD_base.pth | Main model checkpoint |
| Dependency guide | [install.md](https://github.com/hustvl/VAD/blob/1688c4b1c3a9e2e7873ca9700ff8058170c0e3c8/docs/install.md) | PyTorch/MMCV/MMDetection3D environment requirements |

Configuration and weights load relative to the StreetWorld root. Evaluation requires the complete VAD checkpoint listed in the table.

Implementation: [vad/native_agent.py](../../../policy_launcher/vad/native_agent.py).

<a id="launcher-vad-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-vad-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model vad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-vad-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Selects a pts_bbox.ego_fut_preds mode using ego_fut_cmd, accumulates displacements, and returns a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | Missing cameras or model output fields cause adapter errors; the server must use a trajectory-tracking Policy. |

<a id="launcher-genad"></a>

## 7.2.3 GenAD

<a id="launcher-genad-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, MMSegmentation, MMDetection3D, timm, and nuscenes-devkit as required by GenAD.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | GenAD/ | GenAD project and mmdet3d plugin |
| Model configuration | GenAD/projects/configs/GenAD/GenAD_config.py | Generative planning configuration |
| Weights | GenAD/ckpts/checkpoints.pth | Main model checkpoint |
| Dependency guide | [install.md](https://github.com/wzzheng/GenAD/blob/b16667f4a51612b577360c5df4fcdebc3e6f0d55/docs/install.md) | Model dependencies and CUDA ops |

Save the complete GenAD weights as checkpoints.pth. native_agent.py uses relative paths; update its constructor settings if the filename or location changes. The shared CLI has no checkpoint argument.

Implementation: [genad/native_agent.py](../../../policy_launcher/genad/native_agent.py).

<a id="launcher-genad-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-genad-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model genad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-genad-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Selects an ego_fut_preds mode from the navigation command, accumulates displacements, and converts them to a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | The GenAD dataparser processes inputs and moves them to the model device. Model output must include prediction and command fields in pts_bbox. |

<a id="launcher-momad"></a>

## 7.2.4 MomAD

<a id="launcher-momad-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, MMDetection3D, and FlashAttention. Compile MomAD's deformable_aggregation CUDA extension in this model environment.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | MomAD/open_loop/ | Model project root |
| Model configuration | MomAD/open_loop/projects/configs/MomAD_small_stage2_roboAD.py | Configuration fixed by the loader |
| Weights | MomAD/open_loop/ckpt/iter_29300.pth | Main model checkpoint |
| Dependency guide | [quick_start.md](https://github.com/adept-thu/MomAD/blob/7d2247605364e1aba8d7ba4e99f57d01fc452f8c/open_loop/docs/quick_start.md) | Dependencies and deformable_aggregation build |

Install open_loop/requirement.txt and compile the extension under projects/mmdet3d_plugin/ops. Resources such as anchors and kmeans resolve relative to the project root; prepare them using the upstream quick_start.

Implementation: [momad/native_agent.py](../../../policy_launcher/momad/native_agent.py).

<a id="launcher-momad-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-momad-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model momad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-momad-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning, converts from a fixed LiDAR frame to vehicle coordinates, and returns a float32 (6, 2) trajectory with 0.5 s spacing |
| Notes | Changing scene_token clears the model's temporal cache. The loader temporarily enters open_loop to resolve resources, then restores the working directory. |

<a id="launcher-stp3"></a>

## 7.2.5 ST-P3

<a id="launcher-stp3-environment-and-resources"></a>

### Environment and resources

Install PyTorch, PyTorch Lightning, efficientnet-pytorch, fvcore, timm, nuscenes-devkit, and lyft-dataset-sdk. Launcher requires Python 3.10 or later; the upstream Python 3.7 environment.yml cannot run it directly.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | ST-P3/ | stp3 Python package and planner |
| Model configuration | cfg embedded in the checkpoint | The loader reads the checkpoint's saved configuration directly |
| Weights | ST-P3/ckpts/stp3_nuscenes.ckpt | NuScenes Lightning checkpoint with planning enabled |
| Dependency guide | [environment.yml](https://github.com/OpenDriveLab/ST-P3/blob/69aabefd2610951d9e34238142776ed2228673be/environment.yml) | PyTorch Lightning, efficientnet-pytorch, fvcore, and related dependencies |

The loader calls TrainingModule.load_from_checkpoint and reads cfg from trainer.model. DATASET.NAME must be nuscenes and PLANNING.ENABLED must be True, otherwise startup raises ValueError.

Implementation: [stp3/native_agent.py](../../../policy_launcher/stp3/native_agent.py).

<a id="launcher-stp3-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-stp3-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model stp3 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-stp3-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Buffers cfg.TIME_RECEPTIVE_FIELD image frames and LiDAR-to-world history. Returns None until history is complete, causing server iLQR to output zero control. With complete history, the planner returns cfg.N_FUTURE_FRAMES future vehicle-coordinate points at 0.5 s intervals |
| Notes | The checkpoint must include planning; image-only weights or a checkpoint with planning disabled are insufficient. Temporal history accumulates from each server observation. |

<a id="launcher-opendrivevla"></a>

## 7.2.6 OpenDriveVLA

<a id="launcher-opendrivevla-environment-and-resources"></a>

### Environment and resources

Prepare a separate Python 3.10 environment. The guide uses PyTorch 2.1.2, CUDA 12.1, OpenDriveVLA's MMCV 1.7.2 and MMDetection3D 1.0.0rc6 source, and FlashAttention 2. The default attn_implementation is flash_attention_2.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | OpenDriveVLA/ | LLaVA and UniAD vision modules |
| Model directory | OpenDriveVLA/checkpoints/DriveVLA-Qwen2.5-0.5B-Instruct/ | Complete directory containing model configuration, tokenizer, and weights |
| Dependency guide | [Launcher README](../../../policy_launcher/opendrivevla/README.md) | Local build steps for Python 3.10/Torch 2.1.2/CUDA 12.1 |
| Dependency file | policy_launcher/opendrivevla/requirements.txt | Model-specific pinned dependencies |

Install the dedicated requirements, compile the two OpenMMLab packages under third_party as described in the Launcher README, and install FlashAttention for the device. checkpoint must be a complete model directory, not a single pth file.

Implementation: [opendrivevla/native_agent.py](../../../policy_launcher/opendrivevla/native_agent.py).

<a id="launcher-opendrivevla-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-opendrivevla-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model opendrivevla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-opendrivevla-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, and BACK_RIGHT, with K/ego2camera. Ego position history and navigation commands form the text prompt |
| Output | Parses six trajectory points from generated text, interprets them in LiDAR coordinates, and converts to a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | The shared CLI does not expose checkpoint, attn_implementation, max_new_tokens, or bf16; set them in OpenDriveVLANativeAgent. Defaults are max_new_tokens=512 and bf16=False. Unparseable model text raises an error. |

<a id="launcher-latent_transfuser"></a>

## 7.2.7 Latent TransFuser

<a id="launcher-latent_transfuser-environment-and-resources"></a>

### Environment and resources

Install TransFuser dependencies including PyTorch, timm, torch-scatter, MMCV, MMSegmentation, and MMDetection. Launcher uses team_code_transfuser for model/data processing; the StreetWorld server loads scenes and advances physics.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | TransFuser/team_code_transfuser/ | LidarCenterNet and controller code |
| Model directory | TransFuser/model_ckpt/models_2022/latentTF/ | args.txt and at least one *.pth file |
| Model parameters | args.txt inside the model directory | JSON configuration; backbone must be latentTF |
| Dependency guide | [TransFuser README](https://github.com/autonomousvision/transfuser/blob/9d413b2ad2d2d56c112b34a4a799be081800d77f/README.md) | Model dependencies, torch-scatter, and OpenMMLab ops |

The model directory must contain args.txt and *.pth weights. By default, the loader loads all weights in the directory and averages predictions. args.txt must select backbone=latentTF. Missing weights or a different backbone cause startup failure.

Implementation: [latent_transfuser/native_agent.py](../../../policy_launcher/latent_transfuser/native_agent.py).

<a id="launcher-latent_transfuser-server-configuration"></a>

### Server configuration

Use the [Latent TransFuser control-input server](common.md#latent-control-server) and explicitly select EnvInputPolicy. --ad-policy-config latent_transfuser only sets cameras/navigation and leaves the ego Policy as iLQR.

<a id="launcher-latent_transfuser-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model latent_transfuser --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-latent_transfuser-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT_LEFT, FRONT, FRONT_RIGHT, ego speed, and navigation.carla_style_target. Uses the TransFuser preset's three 480×960 cameras, focal length 760 px, at (1.3,0,2.3) |
| Output | The model predicts a path, then client-side PID computes control. predict_action returns normalized (steering, throttle_brake) |
| Notes | The server receives control through EnvInputPolicy. When brake=True, Launcher returns throttle_brake=0.0 rather than a negative braking value. |

<a id="launcher-diffusiondrive"></a>

## 7.2.8 DiffusionDrive

<a id="launcher-diffusiondrive-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later, PyTorch, MMCV 1.x, MMDetection3D, and the project plugins. Compile CUDA extensions such as motion_blocks_v11 as required by DiffusionDrive.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | DiffusionDrive/ | Model and mmdet3d plugin |
| Model configuration | DiffusionDrive/projects/configs/diffusiondrive_configs/diffusiondrive_small_stage2.py | Configuration fixed by the loader |
| Weights | DiffusionDrive/ckpts/diffusiondrive_nusc_stage2.pth | Main model checkpoint |
| Dependency guide | [requirement.txt](https://github.com/hustvl/diffusiondrive/blob/ae54fd87b32b3762f20e63ffd0af91d343cade85/requirement.txt) | Model dependency versions |

The loader enters the project directory, registers plugins, builds the model, and loads its checkpoint. Put relative resources such as anchors at the locations required by the configuration.

Implementation: [diffusiondrive/native_agent.py](../../../policy_launcher/diffusiondrive/native_agent.py).

<a id="launcher-diffusiondrive-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-diffusiondrive-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model diffusiondrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-diffusiondrive-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning, applies a fixed LiDAR-to-ego transform, and returns a float32 (6, 2) trajectory in vehicle coordinates with 0.5 s spacing |
| Notes | Temporal caches reset when scene_token changes. The model, checkpoint, and resources must match the loader's fixed Stage 2 configuration. |

<a id="launcher-sparsedrive"></a>

## 7.2.9 SparseDrive

<a id="launcher-sparsedrive-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, and the SparseDrive plugin. Compile deformable_aggregation CUDA ops. requirement.txt specifies mmcv_full 1.7.1 and mmdet 2.28.2.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | SparseDrive/ | Model and mmdet3d plugin |
| Model configuration | SparseDrive/projects/configs/sparsedrive_small_stage2.py | Configuration fixed by the loader |
| Weights | SparseDrive/ckpt/sparsedrive_stage2.pth | Main model checkpoint |
| Dependency guide | [quick_start.md](https://github.com/swc-17/SparseDrive/blob/ec0225d4b7a2dd7e6ce10179a2b7660dcb74b2f1/docs/quick_start.md) | deformable_aggregation build and anchor resources |

Compile the extension under projects/mmdet3d_plugin/ops and prepare the configured anchor/kmeans files. The loader builds the model with mmdet.models.build_detector.

Implementation: [sparsedrive/native_agent.py](../../../policy_launcher/sparsedrive/native_agent.py).

<a id="launcher-sparsedrive-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-sparsedrive-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model sparsedrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-sparsedrive-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning and returns a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | Camera projection is built from K and ego2camera. Missing cameras, incorrect K dimensions, or non-4×4 extrinsics cause adapter errors. |

<a id="launcher-alpamayo1"></a>

## 7.2.10 Alpamayo 1

<a id="launcher-alpamayo1-environment-and-resources"></a>

### Environment and resources

Use Python 3.12.x, Torch 2.8.0, Transformers 4.57.1, and FlashAttention; see the local pyproject.toml for versions. The loader requires CUDA and uses bfloat16 inference. The upstream guide lists approximately 24 GB of GPU memory for one sample.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | alpamayo1/src/ | Alpamayo model package |
| Model directory | alpamayo1/Alpamayo-R1-10B/ | Complete from_pretrained directory; config.json is required |
| Dependency file | [alpamayo1/pyproject.toml](https://github.com/NVlabs/alpamayo/blob/main/pyproject.toml) | Python 3.12, Torch, and model dependencies |
| Installation guide | [README.md](https://github.com/NVlabs/alpamayo/blob/main/README.md) | Model resources and uv environment setup |

Run these commands from the StreetWorld root to prepare the model environment, then return to the root:

```bash
cd alpamayo1
uv venv --python 3.12 streetworld_model_venv
source streetworld_model_venv/bin/activate
uv sync --active
cd ..
```

Place the complete model in the local directory listed in the table. The loader reads this directory directly and does not switch to a remote model ID.

Implementation: [alpamayo_r1/native_agent.py](../../../policy_launcher/alpamayo_r1/native_agent.py).

<a id="launcher-alpamayo1-server-configuration"></a>

### Server configuration

Use the [NuRec trajectory server](common.md#alpamayo-trajectory-server) with trajectory_dt=0.1 s, control_dt=0.1 s, and decision_repeat=5. The NuRec CLI defaults to raw input, so select a trajectory Policy first.

<a id="launcher-alpamayo1-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model alpamayo1 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-alpamayo1-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Four NuRec cameras: camera_cross_left_120fov, camera_front_wide_120fov, camera_cross_right_120fov, and camera_front_tele_30fov. The model uses 16 ego poses and the latest 4 image frames. At startup, it repeats the first frame to fill the history buffer |
| Output | Requires a (64, 3) model trajectory. Launcher retains the first two dimensions as a float32 (64, 2) trajectory in vehicle coordinates, with 0.1 s spacing and a 6.4 s horizon |
| Notes | CUDA only; startup fails if the model directory lacks config.json. Defaults are top_p=0.98 and temperature=0.6, with one trajectory per request. |

<a id="launcher-alpamayo1-5"></a>

## 7.2.11 Alpamayo 1.5

<a id="launcher-alpamayo1-5-environment-and-resources"></a>

### Environment and resources

Use Python 3.12.x, Torch 2.8.0, Transformers 4.57.1, and FlashAttention; see the local pyproject.toml for versions. The loader requires CUDA and uses bfloat16 inference. The upstream guide lists approximately 24 GB of GPU memory for one sample.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | alpamayo1.5/src/ | Alpamayo model package |
| Model directory | alpamayo1.5/model/ | Complete from_pretrained directory; config.json is required |
| Dependency file | [alpamayo1.5/pyproject.toml](https://github.com/NVlabs/alpamayo1.5/blob/87fb9036aac318535a7a0d9e739a5476ceea8b4e/pyproject.toml) | Python 3.12, Torch, and model dependencies |
| Installation guide | [README.md](https://github.com/NVlabs/alpamayo1.5/blob/87fb9036aac318535a7a0d9e739a5476ceea8b4e/README.md) | Model resources and uv environment setup |

Run these commands from the StreetWorld root to prepare the model environment, then return to the root:

```bash
cd alpamayo1.5
uv venv --python 3.12 streetworld_model_venv
source streetworld_model_venv/bin/activate
uv sync --active
cd ..
```

Place the complete model in the local directory listed in the table. The loader reads this directory directly and does not switch to a remote model ID.

Implementation: [alpamayo1_5/native_agent.py](../../../policy_launcher/alpamayo1_5/native_agent.py).

<a id="launcher-alpamayo1-5-server-configuration"></a>

### Server configuration

Use the [NuRec trajectory server](common.md#alpamayo-trajectory-server) with trajectory_dt=0.1 s, control_dt=0.1 s, and decision_repeat=5. The NuRec CLI defaults to raw input, so select a trajectory Policy first.

<a id="launcher-alpamayo1-5-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model alpamayo1.5 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-alpamayo1-5-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Four NuRec cameras: camera_cross_left_120fov, camera_front_wide_120fov, camera_cross_right_120fov, and camera_front_tele_30fov. The model uses 16 ego poses and the latest 4 image frames. At startup, it repeats the first frame to fill the history buffer |
| Output | Requires a (64, 3) model trajectory. Launcher retains the first two dimensions as a float32 (64, 2) trajectory in vehicle coordinates, with 0.1 s spacing and a 6.4 s horizon |
| Notes | CUDA only; startup fails if the model directory lacks config.json. Version 1.5 also passes camera_indices=(0,1,2,6) to the model. |

<a id="launcher-autovla"></a>

## 7.2.12 AutoVLA

<a id="launcher-autovla-environment-and-resources"></a>

### Environment and resources

Install PyTorch, Transformers with Qwen2.5-VL support, qwen_vl_utils, PyTorch Lightning, and AutoVLA dependencies. Prepare the base model and action codebook in addition to the main checkpoint.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | AutoVLA/ | AutoVLA and navsim paths |
| Model configuration | AutoVLA/config/eval/qwen2.5-vl-3B-nusc-sft-eval.yaml | Video, action vocabulary, and sampling settings |
| Main weights | AutoVLA/checkpoints/AutoVLA/AutoVLA_PDMS_89.ckpt | AutoVLA checkpoint |
| Base model | AutoVLA/Qwen2.5-VL-3B-Instruct/ | Configured by model.pretrained_model_path |
| Action codebook | AutoVLA/codebook_cache/agent_vocab.pkl | Configured by model.codebook_cache_path |
| Dependency guide | [AutoVLA README](https://github.com/ucla-mobility/AutoVLA/blob/ba34eed74ce6729e7986592d0e66cbaca397b4fa/README.md) | Model environment and project dependencies |

pretrained_model_path and codebook_cache_path are resolved relative to the AutoVLA root. native_agent.py specifies the model configuration and main checkpoint paths.

Implementation: [autovla/native_agent.py](../../../policy_launcher/autovla/native_agent.py).

<a id="launcher-autovla-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config autovla
```

<a id="launcher-autovla-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model autovla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-autovla-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT, FRONT_LEFT, and FRONT_RIGHT cameras, each with 4 frames spaced 0.5 s apart; also reads ego speed, steering, acceleration, and navigation commands |
| Output | Decodes generated action tokens into a float32 (10, 2) trajectory in vehicle coordinates; configured for 0.5 s spacing and a 5 s horizon |
| Notes | The autovla server preset sets warmup_step=4 and both trajectory/control intervals to 0.5 s. Client buffering handles incomplete initial history. |

<a id="launcher-epona"></a>

## 7.2.13 Epona

<a id="launcher-epona-environment-and-resources"></a>

### Environment and resources

Use Python 3.10 or later, CUDA-enabled PyTorch, Epona, and DCAE tokenizer dependencies. The loader requires CUDA and uses bfloat16 autocast for inference.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | Epona/ | Model, tokenizer, and configuration utilities |
| Model configuration | Epona/configs/dit_config_dcae_nuscenes.py | Defaults: condition_frames=10, traj_len=15 |
| Main weights | Epona/pretrained/epona_nuplan+nusc.pkl | World/trajectory model checkpoint |
| VAE weights | Epona/pretrained/dcae_td_20000.pkl | VAETokenizer checkpoint |
| Dependency guide | [Epona README](https://github.com/Kevin-thu/Epona/blob/69b24c55f5ab8b3ffde8fa55e9f833bfe64d2c68/README.md) | Python 3.10, PyTorch/CUDA, and requirements.txt |

Place the main and VAE weights in the pretrained directories listed in the table. The loader overrides the VAE path and sets batch_size=1. Observations arrive through gRPC; upstream training dataset paths are not used for these inputs.

Implementation: [epona/native_agent.py](../../../policy_launcher/epona/native_agent.py).

<a id="launcher-epona-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config epona
```

<a id="launcher-epona-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model epona --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-epona-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT images and ego position/rotation; buffers condition_frames successive client observations, currently 10 |
| Output | Calls step_eval(..., traj_only=True) and returns the first two dimensions of predict_traj. Default traj_len is 15; server trajectory_dt is 0.1 s |
| Notes | The epona preset sets trajectory_dt=0.1 s and warmup_step=10. Environment decisions and control_dt remain at 0.5 s, so observations arrive at 2 Hz. The upstream downsample_fps is 10; these rates differ. |

<a id="launcher-openemma_gpt"></a>

## 7.2.14 OpenEMMA GPT

<a id="launcher-openemma_gpt-environment-and-resources"></a>

### Environment and resources

Install openai and Pillow, and set OPENAI_API_KEY. Launcher calls the model through the OpenAI SDK; the table lists the default model name.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | gpt-4o-2024-11-20 | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

Set OPENAI_API_KEY in the Launcher terminal. Change the model name through the OpenEMMANativeAgent model_id constructor argument; the shared CLI does not expose it.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="launcher-openemma_gpt-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_gpt-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_gpt --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_gpt-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | GPT requests include images and text. Each planning cycle separately generates a scene description, relevant objects, driving intent, and future speed/curvature. --device does not affect this backend. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

<a id="launcher-openemma_qwen"></a>

## 7.2.15 OpenEMMA Qwen

<a id="launcher-openemma_qwen-environment-and-resources"></a>

### Environment and resources

Install PyTorch, Transformers, Accelerate, qwen_vl_utils, and Pillow. The loader uses Qwen2VLForConditionalGeneration with bfloat16, sdpa, and device_map="auto".

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | Qwen/Qwen2-VL-7B-Instruct | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

Download the Hugging Face model in the table or prepare a local cache. The loader checks that model_type is qwen2_vl.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="launcher-openemma_qwen-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_qwen-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_qwen --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_qwen-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | Only the latest image is used; the motion prompt uses ten frames. --device is not passed to this backend, so device_map="auto" selects devices. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

<a id="launcher-openemma_llava"></a>

## 7.2.16 OpenEMMA LLaVA

<a id="launcher-openemma_llava-environment-and-resources"></a>

### Environment and resources

Place OpenEMMA source at the StreetWorld root, including llava.model.builder. Install PyTorch, Transformers, CUDA, and image-processing dependencies from OpenEMMA/requirements.txt.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | liuhaotian/llava-v1.6-mistral-7b | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

The loader adds OpenEMMA/ to the Python path and creates llava-v1.6-mistral-7b. Prepare the model resources listed in the table; update backbone.py's source_root if the source directory moves.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="launcher-openemma_llava-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llava-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_llava --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llava-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | Only the latest image is used, and tensors move to GPU with .cuda(). The shared --device is not passed to the model. Set CUDA_VISIBLE_DEVICES before launch to select visible GPUs. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

<a id="launcher-openemma_llama"></a>

## 7.2.17 OpenEMMA Llama

<a id="launcher-openemma_llama-environment-and-resources"></a>

### Environment and resources

Install PyTorch, Transformers with MllamaForConditionalGeneration, Accelerate, and Pillow. The loader uses bfloat16 and device_map="auto".

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | meta-llama/Llama-3.2-11B-Vision-Instruct | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

Prepare a complete Llama 3.2 Vision model and obtain access to it. The loader uses AutoProcessor and MllamaForConditionalGeneration.from_pretrained with the model name in the table.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="launcher-openemma_llama-server-configuration"></a>

### Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llama-launch-command"></a>

### Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_llama --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llama-input-output-and-limits"></a>

### Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | Only the latest image is used; the prompt includes ten motion frames. --device is not passed to this backend, so the loader selects devices. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.1 Common launch procedure](common.md) · [Next: Contents](../../DOCUMENTATION_EN.md)
