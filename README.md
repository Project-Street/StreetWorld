# StreetWorld

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

- Python >= 3.8 (Python 3.11 recommended)
- CUDA >= 11.8 (for GPU acceleration)

### Environment Setup

Create a conda environment:

```bash
conda create -n st-world python=3.11 -y
conda activate st-world
```

### Install StreetWorld

```bash
export ONSITE_PATH=/PATH_TO_ONSITE

# Install PyTorch with CUDA support (You may visit https://pytorch.org/get-started/previous-versions/ to choose a PyTorch version compatible with your Python and CUDA environment).
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121

pip install "git+https://github.com/NVlabs/trajdata.git@a2a54e5"

pip install $ONSITE_PATH/libmulticastnetwork-1.0.2-cp311-cp311-linux_x86_64.whl

# Install StreetWorld
pip install -e . --no-build-isolation --index-url https://pypi.org/simple
```

### Get Access to NuRec Model
Register a [HuggingFace](https://huggingface.co/) account.
Go to [HugginFace Access Token](https://huggingface.co/settings/tokens) page, and create a new one.
`export` the token as `HF_TOKEN` to your environment.


## Quick Start

### OnSite Only

1. Prepare OnSite config:

```bash
# Ensure these fields are correct in onsite/config/common.yaml
# multicast.config_center_addr
# multicast.local_ip
# multicast.net_interface_name
# multicast.field_id
```

2. Launch simulator side (SIMULATOR terminal):

```bash
python metadrive/examples/onsite_simulator_launcher.py \
  --onsite_dir $ONSITE_PATH \
  --scene_config_directory configs/nurec
```

### Launch Viewer Server

```bash
python metadrive/examples/onsite_remote_viewer/viewer_server.py \
  --onsite_dir $ONSITE_PATH \
  --grpc_host <host ip> \
  --grpc_port <host port> \
```

### Launch Viewer Client

```bash
python metadrive/examples/onsite_remote_viewer/viewer_client.py \
  --grpc_host <host ip> \
  --grpc_port <host port> \
  --width 1280 \
  --height 720 \
```
