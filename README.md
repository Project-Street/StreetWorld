# StreetWorld

> This code integrates rl training framework and sharp-video scenes.

StreetWorld is an open-source driving simulator built on MetaDrive, integrating Gaussian Splatting rendering for photorealistic visualization. It supports loading real-world driving scenarios, remote visualization in client/server mode, and reinforcement learning training.

## Features

- **Photorealistic Rendering**: Integration with Gaussian Splatting for real-world scene visualization
- **Real-World Scenarios**: Load and replay driving scenarios from various datasets (nuScenes, Waymo, StreetStudio, custom datasets)
- **Remote Visualization**: Client/server architecture for remote interactive driving
- **RL Training Ready**: Gymnasium-compatible interface for reinforcement learning
- **Multiple Observations**: Modular observation system (Gaussian, Navigation, State, Surrounding)
- **Flexible Policies**: Support for human control (keyboard/steering wheel/Xbox), replay policies, and custom policies
- **OnSite Integration**: Compatible with OnSite platform for distributed simulation

## Installation

### Prerequisites

- Python >= 3.8 (Python 3.10 recommended)
- CUDA 12.1 (for GPU acceleration)

### Environment Setup

Create a conda environment:

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


## Quick Start

### StreetStudio Integration

Load and replay scenarios from StreetStudio transforms.json:

```bash
mamba run -n st-world python -m metadrive.examples.drive_with_streetstudio \
  --transforms /path/to/transforms.json
```

## RL Training

To train UniAD with RL, please apply the patch to UniAD_SIM submodule.

```bash
cd UniAD_SIM && git apply ../uniad.patch
```

## gRPC Mode

### As Server

Run gRPC server for remote RL training:

```bash
# On server environment
pip install ./grpc/[server]

mamba run -n st-world python -m metadrive.examples.server \
  --transforms /path/to/transforms.json \
  --render-url 127.0.0.1:50051 \
  --port 50062
```

### As Client (example script)

Connect to gRPC server:

```bash
# On client environment
pip install ./grpc

mamba run -n st-world python -m metadrive.examples.client \
  --port 50062 \
  --steps 100
```
