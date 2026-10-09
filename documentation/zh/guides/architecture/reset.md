<a id="section-2-4"></a>

# 2.4 reset：开始一个场景

[English](../../../en/guides/architecture/reset.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.3 AgentManager 的组成](agent-manager.md) · [下一页：2.5 step：执行动作](step.md)

`reset()` 用于开始一轮新的驾驶测试。它加载选定的场景，把主车和周边交通参与者放到初始状态，清空上一轮的累计记录，并返回第一帧观测和场景信息。

第一次运行时先调用 `reset()`，驾驶程序就能根据初始观测计算第一条动作。一个场景结束后，再调用 `reset()` 开始下一轮。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.3 AgentManager 的组成](agent-manager.md) · [下一页：2.5 step：执行动作](step.md)
