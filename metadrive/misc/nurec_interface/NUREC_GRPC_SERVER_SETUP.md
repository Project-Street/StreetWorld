# NuRec gRPC Server Setup

## 1. Install NVIDIA Container Toolkit

Prerequisites: NVIDIA driver and Docker are already installed.

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg2

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify:

```bash
nvidia-ctk --version
docker info | grep -i nvidia
docker run --rm --gpus all --entrypoint nvidia-smi nvcr.io/nvidia/nre/nre-ga:26.04
```

## 2. Install NuRec gRPC Server

```bash
docker pull nvcr.io/nvidia/nre/nre-ga:26.04
```

## 3. Start Server

Set `NUREC_HOST_ROOT` to the host NuRec root mounted into the container. `SCENE_USDZ` must be the same scene used by the simulator; the server exposes it as `clipgt-<usdz-stem>`.

```bash
NUREC_HOST_ROOT=/nas1/home/fulvchang/data/NuRec
SCENE_USDZ=sample_set/25.07_release/Batch0005/7e11dcb8-7bce-4972-b998-8626857e92aa/7e11dcb8-7bce-4972-b998-8626857e92aa.usdz

docker run -d --name nurec-grpc \
  --shm-size=64g \
  --gpus all \
  --net=host \
  --privileged \
  -v ${NUREC_HOST_ROOT}:/workdir/NuRec:ro \
  nvcr.io/nvidia/nre/nre-ga:26.04 \
  serve-grpc \
  --artifact-glob /workdir/NuRec/${SCENE_USDZ} \
  --host 0.0.0.0 \
  --port 8080 \
  --health-port 8081 \
  --test-scenes-are-valid \
  --enable-editing-actors
```

Verify:

```bash
docker logs -f nurec-grpc
ss -ltnp | grep -E ':8080|:8081'
docker inspect nurec-grpc --format '{{json .Config.Cmd}}'
```

Verify the loaded scene before starting the simulator:

```bash
python - <<'PY'
import grpc
from metadrive.misc.nurec_interface.nre.grpc.protos import common_pb2, sensorsim_pb2_grpc

channel = grpc.insecure_channel("localhost:8080", options=(("grpc.enable_http_proxy", 0),))
stub = sensorsim_pb2_grpc.SensorsimServiceStub(channel)
print(list(stub.get_available_scenes(common_pb2.Empty(), timeout=5).scene_ids))
channel.close()
PY
```

Expected scene id is `clipgt-<usdz-stem>`. If the simulator requests a different scene, the render call fails with `NOT_FOUND`.

`--enable-editing-actors` is required because the simulator sends `DynamicObject` updates. Without it, render fails with `INVALID_ARGUMENT`.

To switch scenes, stop the current container and start it again with the new `SCENE_USDZ`.

Stop:

```bash
docker rm -f nurec-grpc
```
