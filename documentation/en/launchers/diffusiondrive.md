<a id="launcher-diffusiondrive"></a>

# 7.2.8 DiffusionDrive

[简体中文](../../zh/launchers/diffusiondrive.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.7 Latent TransFuser](latent_transfuser.md) · [Next: 7.2.9 SparseDrive](sparsedrive.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Use Python 3.10 or later, PyTorch, MMCV 1.x, MMDetection3D, and the project plugins. Compile CUDA extensions such as motion_blocks_v11 as required by DiffusionDrive.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | DiffusionDrive/ | Model and mmdet3d plugin |
| Model configuration | DiffusionDrive/projects/configs/diffusiondrive_configs/diffusiondrive_small_stage2.py | Configuration fixed by the loader |
| Weights | DiffusionDrive/ckpts/diffusiondrive_nusc_stage2.pth | Main model checkpoint |
| Dependency guide | [requirement.txt](https://github.com/hustvl/diffusiondrive/blob/ae54fd87b32b3762f20e63ffd0af91d343cade85/requirement.txt) | Model dependency versions |

The loader enters the project directory, registers plugins, builds the model, and loads its checkpoint. Put relative resources such as anchors at the locations required by the configuration.

Implementation: [diffusiondrive/native_agent.py](../../../policy_launcher/diffusiondrive/native_agent.py).

<a id="server-configuration"></a>

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model diffusiondrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning, applies a fixed LiDAR-to-ego transform, and returns a float32 (6, 2) trajectory in vehicle coordinates with 0.5 s spacing |
| Notes | Temporal caches reset when scene_token changes. The model, checkpoint, and resources must match the loader's fixed Stage 2 configuration. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.7 Latent TransFuser](latent_transfuser.md) · [Next: 7.2.9 SparseDrive](sparsedrive.md)
