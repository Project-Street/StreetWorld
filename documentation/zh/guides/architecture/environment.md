<a id="section-2-1"></a>

# 2.1 Environment 的作用与类型

[English](../../../en/guides/architecture/environment.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2. 整体结构](../architecture.md) · [下一页：2.2 SimulatorInterface：场景加载与渲染](simulator.md)

StreetWorld 沿用 OpenAI Gymnasium 的环境接口。Environment 继承 `gym.Env`，是驾驶程序与仿真之间的接口。驾驶程序通过它开始场景、提交动作，再取得车辆运动后的观测、奖励和结束状态。场景加载、车辆运动和观测生成由环境处理。

不同环境在这套接口上提供不同功能：

- [BaseEnv](../../reference/environment.md#api-1-1) 提供场景加载、物理仿真和 `reset()`、`step()` 的基础流程，供具体任务扩展。
- [ScenarioEnv](../../reference/environment.md#api-1-2) 在 BaseEnv 上实现自动驾驶场景任务，增加奖励计算和驾驶表现的评测指标。
- [InteractiveScenarioEnv](../../reference/environment.md#api-1-3) 为 ScenarioEnv 加上浏览器画面、终端状态显示和视频录制。第一章的示例使用它，方便观察车辆的运动和策略的运行结果。
- [GrpcClientEnv](../../reference/environment.md#api-2-1) 是 AD policy 进程使用的远程环境封装，提供与本地环境相同的 Gymnasium 调用形式。它把 `reset()`、`step()` 转成 gRPC 请求，发给 Environment Server，再将服务端返回的观测、奖励和结束状态交给 AD policy。

Environment 通过 SimulatorInterface 读取场景并获取相机图像，场景中的仿真对象则交给各自的 AgentManager 管理。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2. 整体结构](../architecture.md) · [下一页：2.2 SimulatorInterface：场景加载与渲染](simulator.md)
