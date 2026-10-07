<a id="launcher-stp3"></a>

# 7.2.5 ST-P3

[简体中文](../../zh/launchers/stp3.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.4 MomAD](momad.md) · [Next: 7.2.6 OpenDriveVLA](opendrivevla.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Install PyTorch, PyTorch Lightning, efficientnet-pytorch, fvcore, timm, nuscenes-devkit, and lyft-dataset-sdk. Launcher requires Python 3.10 or later; the upstream Python 3.7 environment.yml cannot run it directly.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | ST-P3/ | stp3 Python package and planner |
| Model configuration | cfg embedded in the checkpoint | The loader reads the checkpoint's saved configuration directly |
| Weights | ST-P3/ckpts/stp3_nuscenes.ckpt | NuScenes Lightning checkpoint with planning enabled |
| Dependency guide | [environment.yml](https://github.com/OpenDriveLab/ST-P3/blob/69aabefd2610951d9e34238142776ed2228673be/environment.yml) | PyTorch Lightning, efficientnet-pytorch, fvcore, and related dependencies |

The loader calls TrainingModule.load_from_checkpoint and reads cfg from trainer.model. DATASET.NAME must be nuscenes and PLANNING.ENABLED must be True, otherwise startup raises ValueError.

Implementation: [stp3/native_agent.py](../../../policy_launcher/stp3/native_agent.py).

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
  --model stp3 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Buffers cfg.TIME_RECEPTIVE_FIELD image frames and LiDAR-to-world history. Returns None until history is complete, causing server iLQR to output zero control. With complete history, the planner returns cfg.N_FUTURE_FRAMES future vehicle-coordinate points at 0.5 s intervals |
| Notes | The checkpoint must include planning; image-only weights or a checkpoint with planning disabled are insufficient. Temporal history accumulates from each server observation. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.4 MomAD](momad.md) · [Next: 7.2.6 OpenDriveVLA](opendrivevla.md)
