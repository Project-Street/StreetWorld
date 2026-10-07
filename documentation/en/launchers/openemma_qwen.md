<a id="launcher-openemma_qwen"></a>

# 7.2.15 OpenEMMA Qwen

[简体中文](../../zh/launchers/openemma_qwen.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.14 OpenEMMA GPT](openemma_gpt.md) · [Next: 7.2.16 OpenEMMA LLaVA](openemma_llava.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Install PyTorch, Transformers, Accelerate, qwen_vl_utils, and Pillow. The loader uses Qwen2VLForConditionalGeneration with bfloat16, sdpa, and device_map="auto".

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | Qwen/Qwen2-VL-7B-Instruct | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

Download the Hugging Face model in the table or prepare a local cache. The loader checks that model_type is qwen2_vl.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="server-configuration"></a>

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_qwen --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | Only the latest image is used; the motion prompt uses ten frames. --device is not passed to this backend, so device_map="auto" selects devices. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.14 OpenEMMA GPT](openemma_gpt.md) · [Next: 7.2.16 OpenEMMA LLaVA](openemma_llava.md)
