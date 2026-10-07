# 1.1 Installation

[简体中文](../../zh/getting-started/installation.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: Contents](../../DOCUMENTATION_EN.md) · [Next: 1.2 Drive in the browser](web-controller.md)

## Requirements

- Python 3.10 or later.
- NVIDIA GPU, CUDA Toolkit, and OpenGL; headless rendering requires EGL.

## Installation

```bash
conda create -n streetworld python=3.10 -y
conda activate streetworld

git clone --recursive https://github.com/Project-Street/StreetWorld.git
cd StreetWorld

python -m pip install -e ./trajdata
python -m pip install -e .
python -m pip install -e ./submodules/fast-gauss-paral
python -m pip install -e ./submodules/st-renderer
python -m pip install scipy matplotlib fastapi uvicorn setuptools wheel ninja
python -m pip install git+https://github.com/NVlabs/nvdiffrast.git --no-build-isolation
```

## Verify the installation

```bash
python -c "import streetworld, st_renderer, fast_gauss, nvdiffrast.torch, trajdata"
```

Scene download links will be released later. If you already have the data, place it under the [scene asset directories](../guides/rendering-backends.md#scene-files), then run the [browser driving example](web-controller.md).

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: Contents](../../DOCUMENTATION_EN.md) · [Next: 1.2 Drive in the browser](web-controller.md)
