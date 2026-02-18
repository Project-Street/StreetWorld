# 世界坐标系到 XODR 坐标系转换（独立可迁移版）

本文档不依赖任何现有代码库路径，可直接放到另一个工程使用。

## 1. 输入与输出

输入数据:
- `map.xodr`: OpenDRIVE 地图 XML 文本
- `rig_trajectories.json`: 其中包含 `T_world_base` (4x4)

输出矩阵:
- `T_sim_world_to_xodr_map` (4x4): 仿真世界坐标系 -> XODR 地图坐标系
- `T_xodr_map_to_sim_world` (4x4): `inv(T_sim_world_to_xodr_map)`

## 2. 数据约定

- `T_world_base` 必须是 4x4 齐次变换矩阵
- 点使用齐次坐标列向量: `[x, y, z, 1]^T`
- 矩阵左乘: `p_out = T @ p_in`

## 3. 计算流程

1. 读取 `map.xodr` 得到字符串 `xodr_xml`
2. 读取 `rig_trajectories.json`，取出 `T_world_base`
3. 调用:
   `T_sim_world_to_xodr_map = get_t_rig_enu_from_ecef(T_world_base, xodr_xml)`
4. 计算逆矩阵:
   `T_xodr_map_to_sim_world = np.linalg.inv(T_sim_world_to_xodr_map)`

## 4. 最小可用代码

```python
import json
import numpy as np

# 你自己的实现或第三方实现，接口保持一致:
# get_t_rig_enu_from_ecef(T_world_base: np.ndarray, xodr_xml: str) -> np.ndarray(4,4)
from trajdata.dataset_specific.xodr.geo_transform import get_t_rig_enu_from_ecef


def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def compute_sim_world_to_xodr_map(
    rig_trajectories_json_path: str,
    xodr_path: str,
):
    xodr_xml = load_text(xodr_path)
    rig_data = json.loads(load_text(rig_trajectories_json_path))

    T_world_base = np.asarray(rig_data["T_world_base"], dtype=float)
    if T_world_base.shape != (4, 4):
        raise ValueError(f"T_world_base shape must be (4, 4), got {T_world_base.shape}")

    T_sim_world_to_xodr_map = get_t_rig_enu_from_ecef(T_world_base, xodr_xml)
    T_sim_world_to_xodr_map = np.asarray(T_sim_world_to_xodr_map, dtype=float)
    if T_sim_world_to_xodr_map.shape != (4, 4):
        raise ValueError(
            f"Returned transform shape must be (4, 4), got {T_sim_world_to_xodr_map.shape}"
        )

    T_xodr_map_to_sim_world = np.linalg.inv(T_sim_world_to_xodr_map)
    return T_sim_world_to_xodr_map, T_xodr_map_to_sim_world
```

## 5. 如何使用

点转换:
- 世界到 XODR:
  `p_xodr = T_sim_world_to_xodr_map @ p_sim_world`
- XODR 到世界:
  `p_sim_world = T_xodr_map_to_sim_world @ p_xodr`

位姿转换:
- 已知 `T_sim_world_to_ego`
- 则 `T_xodr_map_to_ego = T_sim_world_to_xodr_map @ T_sim_world_to_ego`

## 6. 快速自检

- 检查 `T_world_base.shape == (4, 4)`
- 检查函数返回矩阵是 `(4, 4)`
- 检查 `T @ inv(T)` 近似单位阵:
  `np.allclose(T @ np.linalg.inv(T), np.eye(4), atol=1e-6)`

## 7. 一句话版本

从 `rig_trajectories.json` 读取 `T_world_base`，从 `map.xodr` 读取 `xodr_xml`，
调用 `get_t_rig_enu_from_ecef(T_world_base, xodr_xml)`，返回值就是
`T_sim_world_to_xodr_map`。
