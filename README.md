# VAD branch
This branch is specifically used for VAD fine-tuning and inference. Main instruction are provided in main branch

```
git clone https://github.com/Project-Street/StreetWorld.git --recursve
git switch vad
# cd policy_launcher && git pull

git clone https://github.com/hustvl/VAD.git
```

## prepare VAD Environment
Download [Vad python environment]() and place it in `./` as `vad.tar.gz`

Build docker image from `policy_launcher/dockerfile`:
```bash
docker build -f policy_launcher/dockerfile -t stwd-vad:latest .
```

Download [VAD Model](https://drive.google.com/file/d/1FLX-4LVm4z-RskghFbxGuYlcYOQmV5bS/view?usp=sharing) and place it in `./VAD/ckpts`

## Run

**Launch simulator server**
```
python -m streetworld.examples.env_server_easydrive --host <host ip> --port <port>
```

Select a `nuScenes`, `Waymo`, or `NuRec` catalog in the interactive interface.

To load scenes from a text file containing one scene name per line instead:

```bash
python -m streetworld.examples.env_server_scene_config --scene-config <scenes.txt> --dataset <nuscenes|waymo|nurec> --host <host ip> --port <port>
```

The backend is selected automatically from `--dataset`.

**drive in VAD** (run in Docker)
```
docker run --rm -it --gpus all -v ${PWD}:/workspace -w /workspace stwd-vad:latest \
python -m policy_launcher.launch --model vad --host <host ip> --port <port> --timeout 100
```
