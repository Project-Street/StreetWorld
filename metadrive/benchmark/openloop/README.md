# Open-loop WOD inference

This folder contains scripts for running open-loop inference on Waymo E2E
test-last frames and exporting Waymo submission shards.

## UniAD WOD last-frame inference

`predict_wod_last_uniad.py` runs UniAD on extracted Waymo E2E last-frame data and
writes JSON predictions. Use `export_wod_submission.py` in a separate Python
environment to convert the JSON into Waymo submission shards.

## VAD WOD last-frame inference

`predict_wod_last_vad.py` runs VAD on extracted Waymo E2E last-frame data and
writes JSON predictions that can also be converted with
`export_wod_submission.py`.

### Requirements

-- CUDA-enabled PyTorch (UniAD dataparser uses CUDA tensors)

### Usage

```bash
python predict_wod_last_uniad.py \
  --input_dir ../../../../data/WOD-E2E-test-last \
  --output_dir ../../../../submodules/ml-sharp/wod-test/output \
  --output_name uniad_predictions.json \
  --camera_source waymo
```

```bash
python predict_wod_last_vad.py \
  --input_dir ../../../../data/WOD-E2E-test-last \
  --output_dir ../../../../submodules/ml-sharp/wod-test/output \
  --output_name vad_predictions.json \
  --camera_source waymo
```

Use `--camera_source nuscenes` to load global camera params from
`submodules/ml-sharp/nuscenes_camera_info.npz` (override with
`--nuscenes_camera_path`).

```bash
python export_wod_submission.py \
  --input_json ../../../../submodules/ml-sharp/wod-test/output/uniad_predictions.json \
  --output_dir ../../../../submodules/ml-sharp/wod-test/output \
  --num_shards 1
```

### Output

JSON predictions are written to:

```
<output_dir>/uniad_predictions.json
```

Submission shards are written to:

```
<output_dir>/MySubmission/part0
```
