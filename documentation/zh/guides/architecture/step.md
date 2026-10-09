<a id="section-2-5"></a>

# 2.5 step：执行动作

[English](../../../en/guides/architecture/step.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.4 reset：开始一个场景](reset.md) · [下一页：2.6 同步与异步](execution-mode.md)

`step(action)` 用于提交驾驶动作，让环境模拟接下来一段时间内车辆如何运动。环境更新主车和周边对象，生成新的观测，计算奖励，并判断这一轮是否结束。驾驶程序拿到结果后，再计算下一条动作。

一个环境步可以包含多个物理小步。`physics_world_step_size` 设置每个物理小步经过的仿真时间，单位是微秒；默认 `20_000`，即 `0.02 s`。减小这个值后，物理状态更新得更频繁，但模拟同样长的一段时间需要执行更多小步。

`decision_repeat` 设置一个环境步包含多少个物理小步。环境完成这些小步后生成一次新观测，因此它也决定了相邻两次观测之间相隔多长仿真时间：

```text
每个环境步的仿真时长（秒）
  = physics_world_step_size × decision_repeat / 1_000_000
```

例如，物理步长为 `0.02 s`、`decision_repeat=5` 时，一个环境步模拟 `0.1 s`。保持物理步长不变，将 `decision_repeat` 改成 `25`，一个环境步就模拟 `0.5 s`，新观测也每隔 `0.5 s` 仿真时间生成一次。

使用 iLQR 跟踪轨迹时，还要相应调整策略的控制周期，配置方法见[时间设置示例](../configuration/policy-controller.md#section-4-5)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：2.4 reset：开始一个场景](reset.md) · [下一页：2.6 同步与异步](execution-mode.md)
