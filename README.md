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
pip install -e ".[viewer]" --no-build-isolation

# Full stack
# Install PyTorch with CUDA support (You may visit https://pytorch.org/get-started/previous-versions/ to choose a PyTorch version compatible with your Python and CUDA environment).
pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121

pip install "git+https://github.com/NVlabs/trajdata.git@a2a54e5"

pip install /PATH_TO/libmulticastnetwork-1.0.2a1-cp311-cp311-linux_x86_64.whl
pip install /PATH_TO/vts_map-11.2.0.6-cp311-cp311-linux_x86_64.whl

pip install -e ".[full]" --no-build-isolation
```

## Quick Start

1. configure the network:

Ensure these fields are correct in onsite/config/common.yaml
```
multicast.local_ip
multicast.net_interface_name

daemon.server.account
daemon.server.password
```

2. Launch the simulator:

```bash
python metadrive/examples/onsite_simulator_launcher.py \
  --scene_config_directory configs/nurec \
  --nurec-data-directory data/NuRec
```

Optional: In default, after submitting a new case on the OnSite platform, the simulator automatically download and caches the data of the case from Aliyun. We provide optional approach that you can download all available NuRec scenes from Aliyun and generate simulator metadata before launch any case, so you do not need to fetch data from Aliyun again each time a new scene starts:

```bash
python metadrive/examples/prepare_nurec_scenes.py \
  --nurec-root data/NuRec
``` 

Optional: by default, the launch script automatically starts a daemon process when no daemon is running on the system. In rare cases, if the script exits unexpectedly, the daemon process may not shut down correctly. You can also choose to start the OnSite daemon manually before launching the simulator:

```bash
cd onsite/daemon
LD_LIBRARY_PATH="$(pwd)/Lib:${LD_LIBRARY_PATH}" ./daemon
```

If the daemon is already running, `onsite_simulator_launcher.py` skips starting a second daemon process.

3. Local Interaction

If the simulator machine has a GUI, launch the local viewer on the same machine:

```bash
python metadrive/examples/onsite_viewer.py \
  --width 1600 \
  --height 900
```

4. Remote Interaction

If the simulator runs on a headless machine, start the viewer server on the same machine that runs the simulator:

```bash
python metadrive/examples/onsite_remote_viewer/viewer_server.py \
  --grpc_host <host ip> \
  --grpc_port <host port>
```

Then launch the viewer client on another machine in the same LAN:

```bash
python metadrive/examples/onsite_remote_viewer/viewer_client.py \
  --grpc_host <host ip> \
  --grpc_port <host port> \
  --width 1600 \
  --height 900
```
