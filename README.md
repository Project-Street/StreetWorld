# StreetWorld

StreetWorld is an open-source driving simulator built on MetaDrive with Gaussian Splatting for photorealistic rendering. It supports real-world scenario replay, remote client/server visualization, and RL training.

## Features

- Photorealistic rendering with Gaussian Splatting
- Real-world scenario replay (nuScenes, Waymo, StreetStudio, custom datasets)
- Remote visualization via client/server mode
- Gymnasium-compatible RL interface
- Modular observations (Gaussian, Navigation, State, Surrounding)
- Flexible policies (human control, replay, custom)
- OnSite integration for distributed simulation

## Installation

### Prerequisites

- Python >= 3.8 (3.10 recommended)
- CUDA 12.1 (for GPU acceleration)

### Environment setup

```bash
mamba create -n st-world python=3.10 -y
mamba activate st-world
```

### Install StreetWorld

```bash
# Install PyTorch with CUDA support
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install StreetWorld
pip install -e .[gym]
```

## Quick start

### Local simulation (StreetStudio)

```bash
mamba run -n st-world python -m metadrive.examples.drive_with_streetstudio \
  --transforms /path/to/transforms.json
```

If you are not using `mamba`, run the module with your active Python environment.

## RL training

To train UniAD with RL, apply the patch to the `UniAD_SIM` submodule:

```bash
cd UniAD_SIM && git apply ../uniad.patch
```

## Evaluate other AD policies

1. Install the target AD policy environment per its official guidance.
2. Install StreetWorld gRPC in that environment:

```bash
pip install ./grpc
```

## gRPC mode (client/server)

### Server (simulation host)

```bash
# On server environment
pip install ./grpc/[server]

mamba run -n st-world python -m metadrive.examples.server \
  --transforms /path/to/transforms.json \
  --render-url 127.0.0.1:50051 \
  --port 50062
```

### Client (example)

```bash
# On client environment
pip install ./grpc

mamba run -n st-world python -m metadrive.examples.client \
  --port 50062 \
  --steps 100
```
