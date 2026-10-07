<a id="launcher-uniad"></a>

# 7.2.1 UniAD

[简体中文](../../zh/launchers/uniad.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.1 Common launch procedure](common.md) · [Next: 7.2.2 VAD](vad.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x CUDA ops, MMDetection, MMSegmentation, and MMDetection3D, then register the UniAD plugin. INSTALL.md specifies Torch 2.0.1/CUDA 11.8, mmcv-full 1.6.1, mmdet 2.26.0, mmsegmentation 0.29.1, and mmdet3d 1.0.0rc6.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | UniAD_SIM/ | UniAD vision and planning components |
| Model configuration | UniAD_SIM/projects/configs/stage2_e2e/base_e2e.py | Stage 2 closed-loop planning configuration |
| Weights | UniAD_SIM/ckpts/uniad_base_e2e.pth | Main model checkpoint |
| Dependency guide | [INSTALL.md](../../../UniAD_SIM/docs/INSTALL.md) | Model dependencies and CUDA build requirements |

Place the Stage 2 weights at the ckpts path in the table. native_agent.py uses relative AD_root, configuration, and weight paths; launch from the StreetWorld root.

Implementation: [uniad/native_agent.py](../../../policy_launcher/uniad/native_agent.py).

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
  --model uniad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads planning.result_planning.sdc_traj and converts it to a float32 (6, 2) future trajectory in vehicle coordinates, sampled at 0.5 s by default |
| Notes | The model retains temporal state. Video and WebUI are enabled by default and run in the simulation environment. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.1 Common launch procedure](common.md) · [Next: 7.2.2 VAD](vad.md)
