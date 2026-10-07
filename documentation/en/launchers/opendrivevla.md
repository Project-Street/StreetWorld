<a id="launcher-opendrivevla"></a>

# 7.2.6 OpenDriveVLA

[简体中文](../../zh/launchers/opendrivevla.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.5 ST-P3](stp3.md) · [Next: 7.2.7 Latent TransFuser](latent_transfuser.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Prepare a separate Python 3.10 environment. The guide uses PyTorch 2.1.2, CUDA 12.1, OpenDriveVLA's MMCV 1.7.2 and MMDetection3D 1.0.0rc6 source, and FlashAttention 2. The default attn_implementation is flash_attention_2.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | OpenDriveVLA/ | LLaVA and UniAD vision modules |
| Model directory | OpenDriveVLA/checkpoints/DriveVLA-Qwen2.5-0.5B-Instruct/ | Complete directory containing model configuration, tokenizer, and weights |
| Dependency guide | [Launcher README](../../../policy_launcher/opendrivevla/README.md) | Local build steps for Python 3.10/Torch 2.1.2/CUDA 12.1 |
| Dependency file | policy_launcher/opendrivevla/requirements.txt | Model-specific pinned dependencies |

Install the dedicated requirements, compile the two OpenMMLab packages under third_party as described in the Launcher README, and install FlashAttention for the device. checkpoint must be a complete model directory, not a single pth file.

Implementation: [opendrivevla/native_agent.py](../../../policy_launcher/opendrivevla/native_agent.py).

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
  --model opendrivevla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, and BACK_RIGHT, with K/ego2camera. Ego position history and navigation commands form the text prompt |
| Output | Parses six trajectory points from generated text, interprets them in LiDAR coordinates, and converts to a float32 (6, 2) vehicle-coordinate trajectory with 0.5 s spacing |
| Notes | The shared CLI does not expose checkpoint, attn_implementation, max_new_tokens, or bf16; set them in OpenDriveVLANativeAgent. Defaults are max_new_tokens=512 and bf16=False. Unparseable model text raises an error. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.5 ST-P3](stp3.md) · [Next: 7.2.7 Latent TransFuser](latent_transfuser.md)
