# 1.1 安装

[English](../../en/getting-started/installation.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：总目录](../../DOCUMENTATION_ZH.md) · [下一页：1.2 用浏览器驾驶](web-controller.md)

## 环境要求

- Python 3.10 或更高版本。
- NVIDIA GPU、CUDA Toolkit、OpenGL；无窗口渲染需要 EGL。

## 安装

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

## 检查安装

```bash
python -c "import streetworld, st_renderer, fast_gauss, nvdiffrast.torch, trajdata"
```

场景数据下载链接待发布。已有数据按[场景目录](../guides/rendering-backends.md#scene-files)放置后，运行[浏览器驾驶示例](web-controller.md)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：总目录](../../DOCUMENTATION_ZH.md) · [下一页：1.2 用浏览器驾驶](web-controller.md)
