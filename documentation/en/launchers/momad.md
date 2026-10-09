<a id="launcher-momad"></a>

# 7.5 MomAD

[简体中文](../../zh/launchers/momad.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.4 GenAD](genad.md) · [Next: 7.6 ST-P3](stp3.md)

<a id="launcher-momad-environment-and-resources"></a>

## Environment and resources

Use Python 3.10 or later and install PyTorch, MMCV 1.x, MMDetection, MMDetection3D, and FlashAttention. Compile MomAD's deformable_aggregation CUDA extension in this model environment.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | MomAD/open_loop/ | Model project root |
| Model configuration | MomAD/open_loop/projects/configs/MomAD_small_stage2_roboAD.py | Configuration fixed by the loader |
| Weights | MomAD/open_loop/ckpt/iter_29300.pth | Main model checkpoint |
| Dependency guide | [quick_start.md](https://github.com/adept-thu/MomAD/blob/7d2247605364e1aba8d7ba4e99f57d01fc452f8c/open_loop/docs/quick_start.md) | Dependencies and deformable_aggregation build |

Install open_loop/requirement.txt and compile the extension under projects/mmdet3d_plugin/ops. Resources such as anchors and kmeans resolve relative to the project root; prepare them using the upstream quick_start.

Implementation: [momad/native_agent.py](../../../policy_launcher/momad/native_agent.py).

<a id="launcher-momad-server-configuration"></a>

## Server configuration

Run this command in the simulation terminal, then select scenes:

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config default
```

<a id="launcher-momad-launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model momad --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-momad-input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Six cameras: FRONT, FRONT_RIGHT, FRONT_LEFT, BACK, BACK_LEFT, BACK_RIGHT, with their K/ego2camera parameters |
| Output | Reads img_bbox.final_planning, converts from a fixed LiDAR frame to vehicle coordinates, and returns a float32 (6, 2) trajectory with 0.5 s spacing |
| Notes | Changing scene_token clears the model's temporal cache. The loader temporarily enters open_loop to resolve resources, then restores the working directory. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.4 GenAD](genad.md) · [Next: 7.6 ST-P3](stp3.md)
