<a id="section-3-3"></a>

# 3.3 渲染后端示例

[English](../../en/guides/rendering-backends.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md) · [下一页：3.3.2 NuRec](nurec.md)

nuScenes 和 Waymo 使用 ST Renderer 在本机 GPU 上渲染；NuRec 场景由独立服务渲染。选择对应后端后，将接口实例传给 Environment。

- [3.3.1 ST Renderer](#st-renderer)
- [3.3.2 NuRec](nurec.md)
- [场景资产目录](#scene-files)

<a id="st-renderer"></a>

## 3.3.1 ST Renderer

ST Renderer 在本机 GPU 上渲染重建好的 nuScenes 或 Waymo 高斯场景。选择 nuScenes 时这样创建接口：

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Waymo 使用 `SimulatorInterface("waymo")`。默认从仓库下的对应数据目录读取文件；数据放在其他位置时，用 `root` 指定存放场景 NPZ 的目录，例如 `SimulatorInterface("nuscenes", root="/path/to/nuscenes")`。

NuRec 的场景格式、渲染服务安装和启动步骤见 [3.3.2 NuRec](nurec.md)。

<a id="scene-files"></a>

## 场景资产目录

按默认路径运行时，场景文件放在 StreetWorld 根目录下：

```text
data/processed/benchmark/
├── nuscenes/
│   ├── 0007.npz
│   ├── <其他场景名>.npz
│   └── map_cache.npz
├── waymo/
│   ├── <场景名>.npz
│   └── ground/<场景名>.obj
└── NuRec/sample_set/25.07_release/
    └── Batch<编号>/<场景目录>/
        ├── <uuid>.usdz
        └── <uuid>/
            ├── rig_trajectories.json
            ├── sequence_tracks.json
            ├── map.xodr
            └── mesh_ground.ply
```

nuScenes 和 Waymo 的场景 ID 是 NPZ 文件名去掉扩展名，例如 `0007`、`001-segment-1422926405879888210`。

NuRec 的场景 ID 是以 `Batch<数字>` 开头的相对路径，如 `Batch0001/<场景目录>`，相对于 `nurec_root`。每个场景目录包含一个 USDZ 文件，并有同名 UUID 子目录保存解包后的数据。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.2 3D 资产与 SimulatorInterface](simulator-interface.md) · [下一页：3.3.2 NuRec](nurec.md)
