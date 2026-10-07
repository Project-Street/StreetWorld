<a id="launcher-alpamayo1"></a>

# 7.2.10 Alpamayo 1

[简体中文](../../zh/launchers/alpamayo1.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.9 SparseDrive](sparsedrive.md) · [Next: 7.2.11 Alpamayo 1.5](alpamayo1.5.md)

Related pages: [Launcher index](index.md) · [Common launch procedure](common.md)

On this page

- [Environment and resources](#environment-and-resources)
- [Server configuration](#server-configuration)
- [Launch command](#launch-command)
- [Inputs, outputs, and limitations](#input-output-and-limits)

<a id="environment-and-resources"></a>

## Environment and resources

Use Python 3.12.x, Torch 2.8.0, Transformers 4.57.1, and FlashAttention; see the local pyproject.toml for versions. The loader requires CUDA and uses bfloat16 inference. The upstream guide lists approximately 24 GB of GPU memory for one sample.

| Item | Value or path | Purpose |
| --- | --- | --- |
| Upstream source | alpamayo1/src/ | Alpamayo model package |
| Model directory | alpamayo1/Alpamayo-R1-10B/ | Complete from_pretrained directory; config.json is required |
| Dependency file | [alpamayo1/pyproject.toml](https://github.com/NVlabs/alpamayo/blob/main/pyproject.toml) | Python 3.12, Torch, and model dependencies |
| Installation guide | [README.md](https://github.com/NVlabs/alpamayo/blob/main/README.md) | Model resources and uv environment setup |

Run these commands from the StreetWorld root to prepare the model environment, then return to the root:

```bash
cd alpamayo1
uv venv --python 3.12 streetworld_model_venv
source streetworld_model_venv/bin/activate
uv sync --active
cd ..
```

Place the complete model in the local directory listed in the table. The loader reads this directory directly and does not switch to a remote model ID.

Implementation: [alpamayo_r1/native_agent.py](../../../policy_launcher/alpamayo_r1/native_agent.py).

<a id="server-configuration"></a>

## Server configuration

Use the [NuRec trajectory server](common.md#alpamayo-trajectory-server) with trajectory_dt=0.1 s, control_dt=0.1 s, and decision_repeat=5. The NuRec CLI defaults to raw input, so select a trajectory Policy first.

<a id="launch-command"></a>

## Launch command

Open another terminal, activate the model environment, and run from the StreetWorld root:

```bash
python -m policy_launcher.launch \
  --model alpamayo1 --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## Inputs, outputs, and limitations

| Item | Requirements |
| --- | --- |
| Input | Four NuRec cameras: camera_cross_left_120fov, camera_front_wide_120fov, camera_cross_right_120fov, and camera_front_tele_30fov. The model uses 16 ego poses and the latest 4 image frames. At startup, it repeats the first frame to fill the history buffer |
| Output | Requires a (64, 3) model trajectory. Launcher retains the first two dimensions as a float32 (64, 2) trajectory in vehicle coordinates, with 0.1 s spacing and a 6.4 s horizon |
| Notes | CUDA only; startup fails if the model directory lacks config.json. Defaults are top_p=0.98 and temperature=0.6, with one trajectory per request. |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 7.2.9 SparseDrive](sparsedrive.md) · [Next: 7.2.11 Alpamayo 1.5](alpamayo1.5.md)
