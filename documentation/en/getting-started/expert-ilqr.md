# 1.4 Run Expert iLQR

[简体中文](../../zh/getting-started/expert-ilqr.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.3 Start the Environment Server](environment-server.md) · [Next: 2. Architecture](../guides/architecture.md)

[drive_expert_ilqr.py](../../../streetworld/examples/drive_expert_ilqr.py) shows vehicle simulation while following the expert trajectory. It takes the recorded ego trajectory from a scene and uses iLQR to compute steering and throttle/brake commands that track it.

## Start the server

Create `scenes.txt` with one scene ID per line, for example:

```text
0007
0008
```

Run from the StreetWorld repository root:

```bash
python -m streetworld.examples.drive_expert_ilqr \
  --scene-config scenes.txt \
  --dataset nuscenes \
  --max-steps 1000
```

Scenes run in file order. Use UTF-8 and include only scene IDs, with no blank lines or comments. See [Scene asset directories](../guides/rendering-backends.md#scene-files) for how IDs map to data files.

## During a run

The vehicle starts driving automatically. Open `http://127.0.0.1:8080` to view camera images and vehicle state; videos are saved in videos/. The terminal prints each scene name and its cumulative `reward_sum` at the end. Normal termination or truncation also prints the timestamp and termination reason.

The script proceeds to the next scene and closes the environment after the final one. Each scene executes at most `--max-steps` calls to `step()`; reaching the destination, a collision, or the environment step limit may end it earlier. Press `Ctrl-C` to exit early.

The expert Policy takes up to 30 future trajectory points per update. Both trajectory sampling and control use a `0.1 s` interval. On `env.step(None)`, ExpertILQRPolicy generates a target trajectory from the recording and iLQR tracks it.

## Arguments

| Parameters | Default | Purpose |
| --- | --- | --- |
| `--scene-config` / `-c` | Required | Scene list text file; one ID per line, processed in file order |
| `--dataset` | Required | `nuscenes` or `waymo` |
| `--max-steps` | `1000` | Maximum `step()` calls per scene in this script; the environment's own step limit still applies |
| `--warmup-step` | `None` | Number of initial environment steps controlled by ExpertILQRPolicy |
| `--gui` / `--no-gui` | Enabled | Inactive; this argument does not disable the web page, terminal UI, or video recording |
| `--gui-image-key` | `FRONT` | Inactive; this argument does not change the cameras displayed on the web page |

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 1.3 Start the Environment Server](environment-server.md) · [Next: 2. Architecture](../guides/architecture.md)
