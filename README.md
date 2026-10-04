# VAD branch
This branch is specifically used for VAD fine-tuning and inference. Main instruction are provided in main branch

```
git clone https://github.com/Project-Street/StreetWorld.git --recursve
git switch vad
# cd rl_framework && git pull && git switch vad

git clone https://github.com/hustvl/VAD.git
```

## prepare VAD Environment
Download [Vad python environment]() and place it in `./` as `vad.tar.gz`

Build docker image from `rl_framework/dockerfile`:
```bash
docker build -f rl_framework/dockerfile -t stwd-vad:latest .
```

Download [VAD Model](https://drive.google.com/file/d/1FLX-4LVm4z-RskghFbxGuYlcYOQmV5bS/view?usp=sharing) and place it in `./VAD/ckpts`

## Run

**Launch simulator server**
```
python -m streetworld.examples.env_server_easydrive  -c <scene_config_dir> --host <host ip> --port <port> --max-workers 1
```

**drive in VAD** (run in Docker)
```
docker run --rm -it --gpus all -v ${PWD}:/workspace -w /workspace stwd-vad:latest \
python -m rl_framework.run_vad_grpc_rollout --host <host ip> --port <port> --episodes 1 --timeout 100
```

**Fine-tuning VAD** (run in Docker)
```
docker run --rm -it --gpus all -v ${PWD}:/workspace -w /workspace stwd-vad:latest \
python -m rl_framework.run_vad_training --with-eval --grpc-host <host ip> --grpc-port <port> --grpc-timeout-sec 100
```
