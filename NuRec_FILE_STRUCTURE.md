# NuRec 数据集文件结构说明（基于当前本地扫描）

本文档根据当前目录下软链接 `NuRec -> /nas2/home/fulvchang/NuRec` 的实际文件扫描结果生成。

## 1. 顶层结构

当前可见顶层仅有：

- `NuRec/sample_set/`

继续向下：

- `NuRec/sample_set/25.07_release/`

## 2. 批次（Batch）结构

当前扫描到以下批次目录：

- `NuRec/sample_set/25.07_release/Batch0001`
- `NuRec/sample_set/25.07_release/Batch0002`

按 `.usdz` 场景包计数（当前本地快照）：

- `Batch0001`: `81` 个场景
- `Batch0002`: `1` 个场景（当前看起来是未完整下载状态）

## 3. 场景目录层级

每个场景的典型路径形式如下：

```text
NuRec/sample_set/25.07_release/Batch000X/<scene_uuid>/
├── <scene_uuid>.usdz                  # 场景压缩包
└── <scene_uuid>/                      # 解包后的内容目录
    ├── default.usda
    ├── dome_light.usda
    ├── map.xodr
    ├── mesh.usd
    ├── mesh.ply
    ├── mesh_ground.usd
    ├── mesh_ground.ply
    ├── metadata.yaml
    ├── parsed_config.yaml
    ├── pose_record.json
    ├── rig_trajectories.json
    ├── rig_trajectories.usda
    ├── sequence_tracks.json
    ├── sequence_tracks.usda
    ├── volume.nurec
    ├── volume.usda
    ├── checkpoint.ckpt
    ├── data_info.json
    ├── datasource_summary.json
    ├── camera_front_wide_120fov.mp4   # 部分场景存在
    └── clipgt/                         # 部分场景存在
        ├── lane.parquet
        ├── lane_line.parquet
        ├── traffic_light.parquet
        ├── traffic_sign.parquet
        ├── obstacle.parquet
        └── ...（其他 gt parquet）
```

## 4. 文件类型统计（当前本地扫描）

- `.json`: 411
- `.usda`: 410
- `.yaml`: 164
- `.usd`: 164
- `.ply`: 164
- `.xodr`: 82
- `.usdz`: 82
- `.nurec`: 82
- `.ckpt`: 82
- `.parquet`: 19
- `.mp4`: 1

## 5. 说明

- 本文档描述的是“当前本地可见结构”，会随下载/解压进度变化。
- 从统计上看，`Batch0001` 基本完整，`Batch0002` 当前仅有少量样本。
