<a id="section-3-3"></a>

# 3.3 Rendering backend examples

[简体中文](../../zh/guides/rendering-backends.md)

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.2 3D assets and SimulatorInterface](simulator-interface.md) · [Next: 3.3.2 NuRec](nurec.md)

nuScenes and Waymo use ST Renderer on the local GPU. NuRec scenes use a separate rendering service. Pass the selected backend's interface instance to Environment.

- [3.3.1 ST Renderer](#st-renderer)
- [3.3.2 NuRec](nurec.md)
- [Scene asset directories](#scene-files)

<a id="st-renderer"></a>

## 3.3.1 ST Renderer

ST Renderer renders reconstructed nuScenes or Waymo Gaussian scenes on the local GPU. Create a nuScenes interface as follows:

```python
from st_renderer import SimulatorInterface

simulator = SimulatorInterface("nuscenes")
```

Use `SimulatorInterface("waymo")` for Waymo. Files are read from the repository's dataset directories by default. For data elsewhere, set `root` to the directory containing scene NPZ files, for example SimulatorInterface("nuscenes", `root`="/path/to/nuscenes").

See [3.3.2 NuRec](nurec.md) for its scene format, rendering service installation, and startup.

<a id="scene-files"></a>

## Scene asset directories

The default scene paths under the StreetWorld root are:

```text
data/processed/benchmark/
├── nuscenes/
│   ├── 0007.npz
│   ├── <other_scene_name>.npz
│   └── map_cache.npz
├── waymo/
│   ├── <scene_name>.npz
│   └── ground/<scene_name>.obj
└── NuRec/sample_set/25.07_release/
    └── Batch<number>/<scene_directory>/
        ├── <uuid>.usdz
        └── <uuid>/
            ├── rig_trajectories.json
            ├── sequence_tracks.json
            ├── map.xodr
            └── mesh_ground.ply
```

nuScenes and Waymo scene IDs are NPZ filenames without extensions, for example `0007` and 001-segment-1422926405879888210.

NuRec scene IDs are relative paths beginning with Batch followed by digits, such as Batch0001/<scene_directory>, relative to nurec_root. Each scene directory contains a USDZ file and a UUID subdirectory of the same name with unpacked data.

---

[Contents](../../DOCUMENTATION_EN.md) · [Previous: 3.2 3D assets and SimulatorInterface](simulator-interface.md) · [Next: 3.3.2 NuRec](nurec.md)
