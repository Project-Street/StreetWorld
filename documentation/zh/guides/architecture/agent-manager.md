<a id="section-2-3"></a>

# 2.3 AgentManager 的组成

[English](../../../en/guides/architecture/agent-manager.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.2 SimulatorInterface：场景加载与渲染](simulator.md) · [下一页：2.4 reset：开始一个场景](reset.md)

Environment 通过管理多个 AgentManager 实现场景仿真：主车有自己的 AgentManager，每个周边交通参与者也各有一个。每个仿真步中，Environment 调用这些 Manager 更新对象，让主车和周边对象在同一场景中运动。

每个对象可以分别选择自己的观测、策略和运动方式：

- Observer 生成相机画面、车辆状态等观测。
- Policy 根据外部动作、记录轨迹或交通流模型，计算对象的控制或移动指令。比如，主车可以使用 iLQR 跟踪模型提交的轨迹，周边车辆可以按记录回放，或使用 IDM 模拟交通流。
- Controller 执行这些指令，控制仿真对象的运动。

这里的 Controller 是 `BaseVehicle`、`Pedestrian`、`Cyclist` 等仿真对象。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.2 SimulatorInterface：场景加载与渲染](simulator.md) · [下一页：2.4 reset：开始一个场景](reset.md)
