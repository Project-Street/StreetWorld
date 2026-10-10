<a id="section-3-2"></a>

# 3.2 3D 资产与 SimulatorInterface

[English](../../en/guides/simulator-interface.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.1 Environment：本地与远程调用](environment-interface.md) · [下一页：3.3 SimulatorInterface 示例](rendering-backends.md)

SimulatorInterface 是 StreetWorld 对场景加载和图像渲染的接口约定。不同数据集的场景资产按这套约定提供轨迹、相机参数、地图和地形，就能以相同的数据格式交给 Environment。不同渲染器实现这套接口后，也可以根据仿真中的对象位置和相机位置生成画面。

Environment 按约定调用这些方法，具体实现自行读取数据文件、加载资产和渲染图像。接入新的数据集或渲染器时，实现下面四个方法，再把实例传给 Environment。仓库已有后端的创建与启动方法见 [SimulatorInterface 示例](rendering-backends.md#section-3-3)。

## SimulatorInterface 的四个调用

接口将加载与渲染分开：开始一个场景时读取元数据和模型，运行期间更新对象位置并反复获取图像。四个方法的调用顺序是 `load_metadata()`、`load_model()`，随后重复 `update_scene()`、`render()`。Environment 按方法名调用，不要求接口继承公共基类。

下面用 `scene_id` 表示场景标识。Environment 将它作为位置参数传入；ST Renderer 的两个加载方法中，这个参数名为 `scene_name`。

<a id="load-metadata"></a>

### load_metadata(scene_id)

Environment 需要知道场景持续多久、主车从哪里出发、周边有哪些对象，以及相机安装在哪里，才能创建仿真。这些信息由 `load_metadata()` 读取；渲染模型在下一步加载。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `scene_id` | 场景标识；ST Renderer 使用字符串，NuRec 也接受相对 Path | 指定要读取的场景；两种后端的 ID 写法见[场景目录](rendering-backends.md#scene-files) |

返回六元组，顺序固定：

```python
(timestamp_range, camera_params, ego_poses, participants,
 scene_mesh_path, scene_mesh_transform)
```

| 返回项 | 类型与单位 | 用途 |
| --- | --- | --- |
| `timestamp_range` | `[开始时间, 结束时间]`，整数微秒 | 场景的记录时间范围；环境按物理步长采样，不包含结束时刻 |
| `camera_params` | `{相机名: 参数字典}` | 每台相机需要 `K`：3×3 内参矩阵，焦距与主点以像素表示；`H`、`W`：图像高、宽，整数像素；`ego2camera`：4×4 车辆到相机的变换；`extra` 可存后端专用相机参数 |
| `ego_poses` | `{整数微秒时间戳: 4×4 位姿}` | 主车记录轨迹；矩阵将车辆坐标变换到仿真世界坐标，平移以米表示 |
| `participants` | `{对象ID: {'poses': 位姿字典, 'size': [长, 宽, 高], 'type': 类型}}` | 周边交通对象；`poses` 与主车轨迹使用相同的时间和矩阵约定，尺寸以米表示，类型用于选择车辆、行人或骑行者等仿真对象 |
| `scene_mesh_path` | OBJ（`.obj`）或 PLY（`.ply`）三角网格文件路径，或 `None` | 为物理仿真提供地形网格；没有网格时环境会创建平面地形。当前 Waymo 使用 OBJ，NuRec 使用 PLY。 |
| `scene_mesh_transform` | 4×4 网格到仿真世界的变换，或 `None` | 将地形网格放到对应位置；`None` 表示不附加变换 |

位姿矩阵的左上 3×3 部分表示旋转，最后一列的前三个数表示位置。主车位姿、周边对象位姿和道路地图要使用同一套仿真世界坐标。车辆自身的坐标为 X 向前、Y 向左、Z 向上，相机坐标为 X 向右、Y 向下、Z 向前。

Environment 读取后会按车辆高度修正主车记录原点，并一起调整相机外参。查询道路地图时使用车辆底面中心。扩展接口或设置相机位置时，要保持位姿和外参的原点一致。

<a id="load-model"></a>

### load_model(scene_id)

这一步加载场景3D资产与高精地图，并返回道路地图。元数据描述场景中的对象，渲染模型用于生成图像；将两者分开，环境就能先读取轨迹和相机参数，再准备模型。目前StreetWorld支持的地图为 `trajdata.VectorMap`。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `scene_id` | 与 `load_metadata()` 相同的场景 ID | 指定要加载模型的场景；必须先读取该场景的元数据 |

返回值为 `trajdata.VectorMap` 或 `None`。地图供车道查询、导航和道路检查使用，渲染模型由接口自身保存。ST Renderer 加载场景中的高斯模型；NuRec 准备远程渲染所需的场景信息，并从 XODR 构建 VectorMap。

<a id="update-scene"></a>

### update_scene(timestamp, object_poses)

仿真中的车辆可能偏离记录轨迹。每次获取画面前，Environment 用这个方法告诉渲染器当前的仿真时间和周边对象位置，让画面反映它们在仿真中的运动。

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `timestamp` | 当前场景时间戳，微秒 | 与记录数据使用同一条时间轴；这里传入 `current_timestamp`，不是从零开始的 `relative_timestamp` |
| `object_poses` | `{对象 ID: torch.Tensor}`；每个张量是 4×4 的位姿矩阵 | 字典的键与 `participants` 中的对象 ID 一致；矩阵表示该对象在仿真世界中的位置和朝向，平移单位为米 |

Environment 将仍在运行的周边对象放入 `object_poses`。主车的位置通过相机外参传给渲染器，不放进这个字典。

返回 `None`。接口保存时间和对象位姿，供后续 `render()` 使用。

<a id="render"></a>

### render(K, H, W, extrinsics)

相机观测需要从主车当前的位置拍摄。`render()` 根据前一步保存的场景状态，以及本次传入的相机参数生成图像。它按批次处理相机，输入中的第 i 组参数对应返回的第 i 张图像。

设本次渲染 B 台相机：

| 参数 | 类型与单位 | 用途 |
| --- | --- | --- |
| `K` | `(B, 3, 3)` 内参矩阵；Environment 传入 `torch.float32` 张量 | 每台相机的焦距与主点，单位为像素；ST Renderer 要求 Torch 张量，NuRec 也接受 NumPy 数组 |
| `H` | 长度为 B 的整数列表，像素 | 每张图像的高度 |
| `W` | 长度为 B 的整数列表，像素 | 每张图像的宽度 |
| `extrinsics` | `(B, 4, 4)` 仿真世界到相机的变换；Environment 传入 `torch.float32` 张量 | 决定每台相机在当前场景中的位置和朝向；ST Renderer 要求 Torch 张量，NuRec 也接受 NumPy 数组 |

相机外参由 `ego2camera @ inverse(主车的车辆到世界位姿)` 得到。主车移动后重新计算它，就能从新的车辆位置获取画面。

返回 B 张 `uint8` RGB 图像，像素值为 0–255，每张形状为 `(H[i], W[i], 3)`。当前 ST Renderer 返回 `(B, H, W, 3)` 的 NumPy 数组，同批相机必须使用相同的 H、W；NuRec 返回图像列表。GaussianObservation 按相机顺序读取这些图像，再为本地观测加上首个帧维。

NuRec 的部分相机使用 `ftheta` 鱼眼模型。它们的成像需要额外的标定数据，不能只用内参矩阵 `K` 描述。因此，NuRec 的 `render()` 还接受 `extra` 参数，用来传递相机名称、模型类型和标定参数。

`extra` 是长度为 B 的列表，与 `K` 使用相同的相机顺序。每台相机的参数字典包含：

| 字段 | 含义 |
| --- | --- |
| `logical_id` | NuRec 场景中的相机名，例如 `camera_front_wide_120fov` |
| `type` | 相机模型；`pinhole` 表示针孔模型，`ftheta` 表示鱼眼模型 |
| `parameters` | `ftheta` 相机的原始标定参数，包括主点、多项式系数等；针孔相机使用 `K`，不需要这个字段 |

正常通过 Environment 获取观测时，无需手工填写 `extra`。NuRec 的 `load_metadata()` 从 `rig_trajectories.json` 读取这些数据，放进每台相机的 `camera_params`，GaussianObservation 再将它们传给 `render()`。直接调用 NuRec 的 `render()` 时，应按相机顺序传入这些 `extra` 字典。不传 `extra` 或某项为 `None` 时，该项使用针孔模型和相机名 `camera_front_tele_30fov`。参数读取代码见 [parse_camera_params()](../../../submodules/nurec_interface/nurec_parser.py)。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：3.1 Environment：本地与远程调用](environment-interface.md) · [下一页：3.3 SimulatorInterface 示例](rendering-backends.md)
