<a id="chapter-1"></a>

<a id="section-1-1"></a>

# 1.1 Installation

[简体中文](../../zh/getting-started/installation.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: Contents](../../DOCUMENTATION_EN.md) · [Next: 1.2 Drive in the browser](web-controller.md)

```bash
git clone --recursive https://github.com/Project-Street/StreetWorld.git
cd StreetWorld

conda create -n streetworld python=3.11 'pip>=25.1' -y
conda activate streetworld

python -m pip install --group build
python -m pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
python -m pip install -e . --no-build-isolation
```

Scene download links will be released later. See [scene asset directories](../guides/rendering-backends.md#scene-files) for downloading and placing the default scene assets.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: Contents](../../DOCUMENTATION_EN.md) · [Next: 1.2 Drive in the browser](web-controller.md)
