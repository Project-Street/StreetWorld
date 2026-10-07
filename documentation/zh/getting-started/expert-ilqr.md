# 1.4 运行 Expert iLQR

[English](../../en/getting-started/expert-ilqr.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.3 启动 Environment Server](environment-server.md) · [下一页：2. 整体结构](../guides/architecture.md)

[drive_expert_ilqr.py](../../../streetworld/examples/drive_expert_ilqr.py) 用于查看车辆沿专家轨迹行驶时的仿真效果。它把场景中记录的主车轨迹作为专家轨迹，用 iLQR 计算转向和油门/制动，驱动车辆跟踪这条轨迹。

## 启动

创建 `scenes.txt`，每行写一个场景 ID，例如：

```text
0007
0008
```

从 StreetWorld 根目录运行：

```bash
python -m streetworld.examples.drive_expert_ilqr \
  --scene-config scenes.txt \
  --dataset nuscenes \
  --max-steps 1000
```

脚本按文本中的顺序运行场景。`scenes.txt` 使用 UTF-8 编码，只写场景 ID，不加空行或注释；场景 ID 和数据文件的对应关系见[场景目录](../guides/rendering-backends.md#scene-files)。

## 运行后

车辆开始自动驾驶。打开 `http://127.0.0.1:8080` 查看相机画面和车辆状态，视频保存到 `videos/`。终端会打印场景名；每个场景结束后打印累计奖励 `reward_sum`，正常终止或截断时还会打印时间戳和结束原因。

脚本运行完一个场景后继续运行下一个，全部结束后关闭环境。单场景最多执行 `--max-steps` 次 `step()`；到达终点、碰撞或环境步数耗尽，也可能提前结束。按 `Ctrl-C` 可以提前退出。

专家策略每次取最多 30 个未来轨迹点，轨迹采样间隔和控制周期均为 `0.1 s`。脚本调用 `env.step(None)` 时，由 ExpertILQRPolicy 从记录中生成目标轨迹，再交给 iLQR 跟踪。

## 参数

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `--scene-config` / `-c` | 必填 | 场景列表文本文件，每行一个场景 ID，按文件中的顺序运行 |
| `--dataset` | 必填 | `nuscenes` 或 `waymo` |
| `--max-steps` | `1000` | 脚本对单场景的 `step()` 次数上限；环境自身的步数限制仍然生效 |
| `--warmup-step` | `None` | 初始阶段由 ExpertILQRPolicy 控制的环境步数 |
| `--gui` / `--no-gui` | 开启 | 未生效；该参数不能关闭网页、终端界面或视频录制 |
| `--gui-image-key` | `FRONT` | 未生效；该参数不改变网页中显示的相机 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.3 启动 Environment Server](environment-server.md) · [下一页：2. 整体结构](../guides/architecture.md)
