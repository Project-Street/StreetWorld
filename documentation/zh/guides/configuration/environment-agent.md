<a id="section-4-3"></a>

# 4.3 Environment 与 Agent 的常用参数

[English](../../../en/guides/configuration/environment-agent.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.2 配置层级与优先级](hierarchy.md) · [下一页：4.4 Observer 配置](observation.md)

环境参数控制整个场景怎样运行；Agent 参数控制单个对象。下表使用基础环境的默认值，启动脚本或模型配置可以覆盖它们。

## Environment

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `scene_ids` | list[str] | 必填 | 要运行的场景 ID；格式取决于数据集，见[场景目录](../rendering-backends.md#scene-files) |
| `random_scenario` | bool | `True` | 非评测模式且没有显式指定场景时，随机选择场景；`False` 按列表顺序循环 |
| `physics_world_step_size` | 数值，微秒 | `20_000` | 每个物理小步推进的仿真时间，即 `0.02 s` |
| `decision_repeat` | int，物理步数 | `5` | 每个环境步包含的物理小步数；默认每步模拟 `0.1 s` |
| `max_step` | int 或 None，环境步数 | `None` | 一轮测试的环境步数上限；`None` 不设置这一层的限制，主车仍受自己的 `max_step` 限制 |
| `async_mode` | bool | `False` | 是否在等待驾驶输入期间继续仿真，见[同步与异步](../architecture/execution-mode.md#section-2-6) |

## Agent

主车使用 `actor_config`，周边对象使用 `participant_config`。两者都由 AgentManager 读取；下面列主车路径：

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.max_step` | int 或 None，环境步数 | `10_000` | 主车运行步数上限；达到上限后结束本轮 |
| `actor_config.check_crash` | bool | `True` | 是否检测该对象的碰撞；主车碰撞时会产生对应的结束原因 |
| `actor_config.warmup_step` | int 或 None，环境步数 | `None` | 设置数值后，前若干步由 ExpertILQRPolicy 跟随记录轨迹，之后切换到配置的 Policy |

完整字段见 [Environment](../../reference/environment.md) 和 [AgentManager](../../reference/manager.md#api-4-3)。结束状态见 [AgentState](../environment-interface.md#agent-states)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.2 配置层级与优先级](hierarchy.md) · [下一页：4.4 Observer 配置](observation.md)
