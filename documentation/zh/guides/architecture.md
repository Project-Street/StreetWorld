<a id="chapter-2"></a>

# 2. 整体结构

[English](../../en/guides/architecture.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.4 运行 Expert iLQR](../getting-started/expert-ilqr.md) · [下一页：3.1 Environment：本地与远程调用](environment-interface.md)

- [2.1 Environment 的作用与类型](#section-2-1)
- [2.2 SimulatorInterface：场景加载与渲染](#section-2-2)
- [2.3 AgentManager 的组成](#section-2-3)
- [2.4 reset：开始一个场景](#section-2-4)
- [2.5 step：执行动作](#section-2-5)
- [2.6 同步与异步](#section-2-6)

<a id="section-2-1"></a>

## 2.1 Environment 的作用与类型

StreetWorld 沿用 OpenAI Gymnasium 的环境接口。Environment 继承 `gym.Env`，是驾驶程序与仿真之间的接口。驾驶程序通过它开始场景、提交动作，再取得车辆运动后的观测、奖励和结束状态。场景加载、车辆运动和观测生成由环境处理。

不同环境在这套接口上提供不同功能：

- [BaseEnv](../reference/environment.md#api-1-1) 提供场景加载、物理仿真和 `reset()`、`step()` 的基础流程，供具体任务扩展。
- [ScenarioEnv](../reference/environment.md#api-1-2) 在 BaseEnv 上实现自动驾驶场景任务，增加奖励计算和驾驶表现的评测指标。
- [InteractiveScenarioEnv](../reference/environment.md#api-1-3) 为 ScenarioEnv 加上浏览器画面、终端状态显示和视频录制。第一章的示例使用它，方便观察车辆的运动和策略的运行结果。
- [GrpcClientEnv](../reference/environment.md#api-2-1) 是 AD policy 进程使用的远程环境封装，提供与本地环境相同的 Gymnasium 调用形式。它把 `reset()`、`step()` 转成 gRPC 请求，发给 Environment Server，再将服务端返回的观测、奖励和结束状态交给 AD policy。

Environment 通过 SimulatorInterface 读取场景并获取相机图像，场景中的仿真对象则交给各自的 AgentManager 管理。

<a id="section-2-2"></a>

## 2.2 SimulatorInterface：场景加载与渲染

SimulatorInterface 约定场景数据怎样交给 Environment，以及渲染器怎样根据仿真状态生成相机图像。不同数据集可以有各自的文件格式，不同渲染器也可以有各自的运行方式；各实现按这套约定返回数据，Environment 就能使用它们。

创建 Environment 时，需要传入一个 SimulatorInterface 实例。`reset()` 通过它读取轨迹、相机参数和地形，加载 3D 资产与道路地图。运行场景时，Environment 把当前时间和周边对象的位姿交给它，主车的相机观测再调用它获取图像。

仓库中的 ST Renderer 实现读取 nuScenes 或 Waymo 资产，在本机 GPU 上渲染；NuRec 实现读取 NuRec 资产，向独立运行的渲染服务请求图像。接口的数据格式和两种实现的配置见[第三章](simulator-interface.md#section-3-2)。

<a id="section-2-3"></a>

## 2.3 AgentManager 的组成

Environment 通过管理多个 AgentManager 实现场景仿真：主车有自己的 AgentManager，每个周边交通参与者也各有一个。每个仿真步中，Environment 调用这些 Manager 更新对象，让主车和周边对象在同一场景中运动。

每个对象可以分别选择自己的观测、策略和运动方式：

- Observer 生成相机画面、车辆状态等观测。
- Policy 根据外部动作、记录轨迹或交通流模型，计算对象的控制或移动指令。比如，主车可以使用 iLQR 跟踪模型提交的轨迹，周边车辆可以按记录回放，或使用 IDM 模拟交通流。
- Controller 执行这些指令，控制仿真对象的运动。

这里的 Controller 是 `BaseVehicle`、`Pedestrian`、`Cyclist` 等仿真对象。

<a id="section-2-4"></a>

## 2.4 reset：开始一个场景

`reset()` 用于开始一轮新的驾驶测试。它加载选定的场景，把主车和周边交通参与者放到初始状态，清空上一轮的累计记录，并返回第一帧观测和场景信息。

第一次运行时先调用 `reset()`，驾驶程序就能根据初始观测计算第一条动作。一个场景结束后，再调用 `reset()` 开始下一轮。

<a id="section-2-5"></a>

## 2.5 step：执行动作

`step(action)` 用于提交驾驶动作，让环境模拟接下来一段时间内车辆如何运动。环境更新主车和周边对象，生成新的观测，计算奖励，并判断这一轮是否结束。驾驶程序拿到结果后，再计算下一条动作。

一个环境步可以包含多个物理小步。`physics_world_step_size` 设置每个物理小步经过的仿真时间，单位是微秒；默认 `20_000`，即 `0.02 s`。减小这个值后，物理状态更新得更频繁，但模拟同样长的一段时间需要执行更多小步。

`decision_repeat` 设置一个环境步包含多少个物理小步。环境完成这些小步后生成一次新观测，因此它也决定了相邻两次观测之间相隔多长仿真时间：

```text
每个环境步的仿真时长（秒）
  = physics_world_step_size × decision_repeat / 1_000_000
```

例如，物理步长为 `0.02 s`、`decision_repeat=5` 时，一个环境步模拟 `0.1 s`。保持物理步长不变，将 `decision_repeat` 改成 `25`，一个环境步就模拟 `0.5 s`，新观测也每隔 `0.5 s` 仿真时间生成一次。

使用 iLQR 跟踪轨迹时，还要相应调整策略的控制周期，配置方法见[时间设置示例](configuration/policy-controller.md#section-4-5)。

<a id="section-2-6"></a>

## 2.6 同步与异步

两种模式的区别是：仿真器等待驾驶策略推理时，仿真是否并行地运行。通过 `async_mode` 选择，默认值为 `False`。

同步模式下，环境等待驾驶程序调用 `step(action)`，再模拟一个环境步并返回结果。假设每步模拟 `0.1 s`，模型花了 `0.3 s` 实际时间计算动作，这期间仿真时间不会改变；下一次 `step()` 仍然只模拟 `0.1 s`。这种方式适合按步测试策略，仿真中的车辆运动了多久，不受模型推理耗时影响。

设置 `async_mode=True` 后，`reset()` 完成时仿真就开始持续运行，不再等待下一次 `step()` 请求。驾驶程序计算新动作期间，环境沿用最近提交的动作继续模拟车辆运动。这种方式用于浏览器驾驶等持续交互，也能观察模型推理耗时对驾驶结果的影响。

仍以上述时间为例，每步模拟 `0.1 s`，如果每一步的物理计算和渲染耗时小于 `0.1 s`，环境会约每隔 `0.1 s` 实际时间更新一轮状态。模型推理花费的 `0.3 s` 中，仿真也会经过约 `0.3 s`。

异步模式下，`step(action)` 更新动作并返回最近完成的一步结果。返回的观测不一定已经反映刚提交的动作，多次调用也可能拿到同一帧。场景结束后，环境停下来等待下一次 `reset()`。

如果物理计算和渲染耗时超过设定的每步时长，异步仿真也会跟不上实际时间。每一步经过的仿真时间仍由步长和 `decision_repeat` 决定。

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：1.4 运行 Expert iLQR](../getting-started/expert-ilqr.md) · [下一页：3.1 Environment：本地与远程调用](environment-interface.md)
