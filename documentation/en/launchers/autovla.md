<a id="launcher-autovla"></a>

# 7.2.12 AutoVLA

[简体中文](../../zh/launchers/autovla.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.11 Alpamayo 1.5](alpamayo1.5.md) · [Next: 7.2.13 Epona](epona.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

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

<a id="server-configuration"></a>

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config autovla
```

<a id="launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model autovla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT, FRONT_LEFT, and FRONT_RIGHT cameras, each with 4 frames spaced 0.5 s apart; also reads ego speed, steering, acceleration, and navigation commands |
| Output | Decodes generated action tokens into a float32 (10, 2) trajectory in vehicle coordinates; configured for 0.5 s spacing and a 5 s horizon |
| Notes | The autovla server preset sets warmup_step=4 and both trajectory/control intervals to 0.5 s. Client buffering handles incomplete initial history. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.11 Alpamayo 1.5](alpamayo1.5.md) · [Next: 7.2.13 Epona](epona.md)
