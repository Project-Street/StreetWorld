# StreetWorld

StreetWorld is an open-source driving simulator built on MetaDrive, integrating Gaussian Splatting rendering for photorealistic visualization. It supports loading real-world driving scenarios, remote visualization in client/server mode, and reinforcement learning training.

### Features

- **Photorealistic Rendering**: Integration with Gaussian Splatting for real-world scene visualization
- **Real-World Scenarios**: Load and replay driving scenarios from various datasets (nuScenes, Waymo, StreetStudio, custom datasets)
- **Remote Visualization**: Client/server architecture for remote interactive driving
- **RL Training Ready**: Gymnasium-compatible interface for reinforcement learning
- **Multiple Observations**: Modular observation system (Gaussian, Navigation, State, Surrounding)
- **Flexible Policies**: Support for human control (keyboard/steering wheel/Xbox), replay policies, and custom policies
- **OnSite Integration**: Compatible with OnSite platform for distributed simulation

### Onsite Compatible Branch
This branch includes the compatibility code required for the OnSite competition. Participants should launch the simulator with the **Quick Start** 2 flow below.

We support visual manual driving in two deployment scenarios:

- **Local interaction**: If the simulator is installed on a local Linux machine with a GUI, follow Step 3 in **Quick Start** for interactive manual driving.
- **Remote interaction**: If the simulator is installed on a remote headless Linux system, such as a server, follow Step 4 in **Quick Start** for remote interaction.

After submitting a task on the OnSite platform, the simulator automatically download and caches the 3D Gaussian Splatting model for the corresponding case and then starts the simulation.

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

Place `daemon/` and `config/` in `./onsite`. 

```bash

# For running viewer client in local system only (minimal dependencies for onsite_remote_viewer/viewer_client.py)
pip install -e ".[viewer]" --no-build-isolation --index-url https://pypi.org/simple

# Full stack
# Install PyTorch with CUDA support (You may visit https://pytorch.org/get-started/previous-versions/ to choose a PyTorch version compatible with your Python and CUDA environment).
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121

pip install "git+https://github.com/NVlabs/trajdata.git@a2a54e5"

pip install /PATH_TO/libmulticastnetwork-1.0.2-cp311-cp311-linux_x86_64.whl
pip install /PATH_TO/vts_map-11.2.0.6-cp311-cp311-linux_x86_64.whl

pip install -e ".[full]" --no-build-isolation --index-url https://pypi.org/simple
```

### Get Access to NuRec Model
Register a [HuggingFace](https://huggingface.co/) account.
Go to the [HuggingFace access token](https://huggingface.co/settings/tokens) page and create a new token.
Export the token to your environment as `HF_TOKEN`.

## Quick Start

1. configure the network:

Ensure these fields are correct in onsite/config/common.yaml
```
multicast.config_center_addr
multicast.local_ip
multicast.net_interface_name
multicast.field_id
```

2. Launch the simulator:

```bash
python metadrive/examples/onsite_simulator_launcher.py \
  --onsite_dir $ONSITE_PATH \
  --scene_config_directory configs/nurec
```

3. Local Interaction

If the simulator machine has a GUI, launch the local viewer on the same machine:

```bash
python metadrive/examples/onsite_viewer.py \
  --onsite_dir $ONSITE_PATH \
  --width 1280 \
  --height 720
```

4. Remote Interaction

If the simulator runs on a headless machine, start the viewer server on the same machine that runs the simulator:

```bash
python metadrive/examples/onsite_remote_viewer/viewer_server.py \
  --onsite_dir $ONSITE_PATH \
  --grpc_host <host ip> \
  --grpc_port <host port>
```

Then launch the viewer client on another machine in the same LAN:

```bash
python metadrive/examples/onsite_remote_viewer/viewer_client.py \
  --grpc_host <host ip> \
  --grpc_port <host port> \
  --width 1280 \
  --height 720
```
