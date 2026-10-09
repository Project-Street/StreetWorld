<a id="launcher-latent_transfuser"></a>

# 7.8 Latent TransFuser

[简体中文](../../zh/launchers/latent_transfuser.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.7 OpenDriveVLA](opendrivevla.md) · [Next: 7.9 DiffusionDrive](diffusiondrive.md)

<a id="launcher-latent_transfuser-environment-and-resources"></a>

## Environment and resources

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

## Server configuration

Use the [Latent TransFuser control-input server](common.md#latent-control-server) and explicitly select EnvInputPolicy. --ad-policy-config latent_transfuser only sets cameras/navigation and leaves the ego Policy as iLQR.

<a id="launcher-latent_transfuser-launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model latent_transfuser --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-latent_transfuser-input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT_LEFT, FRONT, FRONT_RIGHT, ego speed, and navigation.carla_style_target. Uses the TransFuser preset's three 480×960 cameras, focal length 760 px, at (1.3,0,2.3) |
| Output | The model predicts a path, then client-side PID computes control. predict_action returns normalized (steering, throttle_brake) |
| Notes | The server receives control through EnvInputPolicy. When brake=True, Launcher returns throttle_brake=0.0 rather than a negative braking value. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.7 OpenDriveVLA](opendrivevla.md) · [Next: 7.9 DiffusionDrive](diffusiondrive.md)
