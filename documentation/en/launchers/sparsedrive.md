<a id="launcher-sparsedrive"></a>

# 7.2.9 SparseDrive

[简体中文](../../zh/launchers/sparsedrive.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.8 DiffusionDrive](diffusiondrive.md) · [Next: 7.2.10 Alpamayo 1](alpamayo1.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, and the SparseDrive plugin. Compile deformable_aggregation CUDA ops. requirement.txt specifies mmcv_full 1.7.1 and mmdet 2.28.2.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | SparseDrive/ | Model and mmdet3d plugin |
| Model configuration | SparseDrive/projects/configs/sparsedrive_small_stage2.py | Configuration fixed by the loader |
| Weights | SparseDrive/ckpt/sparsedrive_stage2.pth | Main model checkpoint |
| Dependency guide | [quick_start.md](https://github.com/swc-17/SparseDrive/blob/ec0225d4b7a2dd7e6ce10179a2b7660dcb74b2f1/docs/quick_start.md) | deformable_aggregation build and anchor resources |

Compile the extension under projects/mmdet3d_plugin/ops and prepare the configured anchor/kmeans files. The loader builds the model with mmdet.models.build_detector.

Implementation: [sparsedrive/native_agent.py](../../../policy_launcher/sparsedrive/native_agent.py).

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
  --model sparsedrive --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning and returns a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | Camera projection is built from K and ego2camera. Missing cameras, incorrect K dimensions, or non-4×4 extrinsics cause adapter errors. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.8 DiffusionDrive](diffusiondrive.md) · [Next: 7.2.10 Alpamayo 1](alpamayo1.md)
