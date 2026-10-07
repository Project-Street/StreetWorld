<a id="launcher-genad"></a>

# 7.2.3 GenAD

[简体中文](../../zh/launchers/genad.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.2 VAD](vad.md) · [Next: 7.2.4 MomAD](momad.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, MMSegmentation, MMDetection3D, timm, and nuscenes-devkit as required by GenAD.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | GenAD/ | GenAD project and mmdet3d plugin |
| Model configuration | GenAD/projects/configs/GenAD/GenAD_config.py | Generative planning configuration |
| Weights | GenAD/ckpts/checkpoints.pth | Main model checkpoint |
| Dependency guide | [install.md](https://github.com/wzzheng/GenAD/blob/b16667f4a51612b577360c5df4fcdebc3e6f0d55/docs/install.md) | Model dependencies and CUDA ops |

Save the complete GenAD weights as checkpoints.pth. native_agent.py uses relative paths; update its constructor settings if the filename or location changes. The shared CLI has no checkpoint argument.

Implementation: [genad/native_agent.py](../../../policy_launcher/genad/native_agent.py).

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
  --model genad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Selects an ego_fut_preds mode from the navigation command, accumulates displacements, and converts them to a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | The GenAD dataparser processes inputs and moves them to the model device. Model output must include prediction and command fields in pts_bbox. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.2 VAD](vad.md) · [Next: 7.2.4 MomAD](momad.md)
