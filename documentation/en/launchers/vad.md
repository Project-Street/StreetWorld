<a id="launcher-vad"></a>

# 7.3 VAD

[简体中文](../../zh/launchers/vad.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2 UniAD](uniad.md) · [Next: 7.4 GenAD](genad.md)

<a id="launcher-vad-environment-and-resources"></a>

## Environment and resources

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

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-vad-launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model vad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-vad-input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Selects a pts_bbox.ego_fut_preds mode using ego_fut_cmd, accumulates displacements, and returns a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | Missing cameras or model output fields cause adapter errors; the server must use a trajectory-tracking Policy. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2 UniAD](uniad.md) · [Next: 7.4 GenAD](genad.md)
