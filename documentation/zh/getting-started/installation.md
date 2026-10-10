<a id="chapter-1"></a>

<a id="section-1-1"></a>

# 1.1 安装

[English](../../en/getting-started/installation.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：总目录](../../DOCUMENTATION_ZH.md) · [下一页：1.2 用浏览器驾驶](web-controller.md)

```bash
git clone --recursive https://github.com/Project-Street/StreetWorld.git
cd StreetWorld

conda create -n streetworld python=3.11 'pip>=25.1' -y
conda activate streetworld

python -m pip install --group build
python -m pip install torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
python -m pip install -e . --no-build-isolation
```

场景数据下载链接待发布。默认场景资产的下载与放置参考[场景目录](../guides/rendering-backends.md#scene-files)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：总目录](../../DOCUMENTATION_ZH.md) · [下一页：1.2 用浏览器驾驶](web-controller.md)
