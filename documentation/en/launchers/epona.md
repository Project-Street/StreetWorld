<a id="launcher-epona"></a>

# 7.14 Epona

[简体中文](../../zh/launchers/epona.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.13 AutoVLA](autovla.md) · [Next: 7.15 OpenEMMA GPT](openemma_gpt.md)

<a id="launcher-epona-environment-and-resources"></a>

## Environment and resources

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

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config epona
```

<a id="launcher-epona-launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model epona --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-epona-input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT images and ego position/rotation; buffers condition_frames successive client observations, currently 10 |
| Output | Calls step_eval(..., traj_only=True) and returns the first two dimensions of predict_traj. Default traj_len is 15; server trajectory_dt is 0.1 s |
| Notes | The epona preset sets trajectory_dt=0.1 s and warmup_step=10. Environment decisions and control_dt remain at 0.5 s, so observations arrive at 2 Hz. The upstream downsample_fps is 10; these rates differ. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.13 AutoVLA](autovla.md) · [Next: 7.15 OpenEMMA GPT](openemma_gpt.md)
