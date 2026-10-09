<a id="launcher-openemma_llava"></a>

# 7.17 OpenEMMA LLaVA

[简体中文](../../zh/launchers/openemma_llava.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.16 OpenEMMA Qwen](openemma_qwen.md) · [Next: 7.18 OpenEMMA Llama](openemma_llama.md)

<a id="launcher-openemma_llava-environment-and-resources"></a>

## Environment and resources

Place OpenEMMA source at the StreetWorld root, including llava.model.builder. Install PyTorch, Transformers, CUDA, and image-processing dependencies from OpenEMMA/requirements.txt.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Launcher implementation | policy_launcher/openemma/native_agent.py | Shared OpenEMMANativeAgent; subclasses select the backend |
| Backend implementation | policy_launcher/openemma/backbone.py | Model loading and generation |
| Default model name | liuhaotian/llava-v1.6-mistral-7b | Default model_id in code; not changed through the shared CLI |
| Dependency guide | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | Backend dependency list |

The loader adds OpenEMMA/ to the Python path and creates llava-v1.6-mistral-7b. Prepare the model resources listed in the table; update backbone.py's source_root if the source directory moves.

Implementation: [openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py).

<a id="launcher-openemma_llava-server-configuration"></a>

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llava-launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model openemma_llava --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llava-input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | FRONT image, ego motion state, and navigation hints; buffers 10 frames with motion_dt=0.5 s. Until history is complete, returns warmup_action as a (1, 2) array; server expert warmup overrides these initial actions |
| Output | Parses future speed/curvature and integrates at prediction_dt=0.5 s into a vehicle-coordinate (N, 2) trajectory. The prompt asks for 10 points; the parser requires at least 2 |
| Notes | Only the latest image is used, and tensors move to GPU with .cuda(). The shared --device is not passed to the model. Set CUDA_VISIBLE_DEVICES before launch to select visible GPUs. The openemma preset uses warmup_step=10. Invalid replies are retried; if trajectory parsing fails and a previous trajectory exists, it is reused. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.16 OpenEMMA Qwen](openemma_qwen.md) · [Next: 7.18 OpenEMMA Llama](openemma_llama.md)
