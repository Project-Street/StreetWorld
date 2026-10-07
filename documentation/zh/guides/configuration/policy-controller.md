<a id="section-4-5"></a>

# 4.5 Policy 与 Controller 配置

[English](../../../en/guides/configuration/policy-controller.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.4 Observer 配置](observation.md) · [下一页：5. 组件参考](../../reference/index.md)

驾驶程序向 `step()` 传入动作，Policy 将动作变成控制或移动指令，Controller 执行这些指令。基础配置中，主车使用 EnvInputPolicy，接收转向和油门/制动；周边对象使用 ReplayPolicy，按记录轨迹回放。

## EnvInputILQRPolicy：跟踪模型轨迹

模型输出未来的 `(x, y)` 轨迹时，用 EnvInputILQRPolicy 计算转向和油门/制动。`actor_config.policy` 选择策略类，`actor_config.policy_config` 设置策略参数。输入点位于主车坐标系，格式见 [action](../environment-interface.md#action-format)。

从仓库的默认轨迹配置开始：

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.configs.default_policy_config import DEFAULT_POLICY_CONFIG_0_5S

cfg = ScenarioEnv.default_config()
cfg.merge_from(DEFAULT_POLICY_CONFIG_0_5S)
```

这份配置将主车 Policy 设为 EnvInputILQRPolicy，并提供它需要的参数。接入模型时，需要先核对两个时间间隔：

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.policy_config.trajectory_dt` | float，秒 | 该轨迹配置为 `0.5` | 模型预测点的采样间隔；第一点对应当前时间之后一个间隔的位置 |
| `actor_config.policy_config.control_dt` | float，秒 | 该轨迹配置为 `0.5` | iLQR 更新车辆控制的周期；必须为物理步长的整数倍，当前实现还要求与环境步时长相等 |

一个环境步的时长是 `physics_world_step_size × decision_repeat / 1_000_000` 秒。默认物理步长为 `0.02 s`，这份轨迹配置使用 `decision_repeat=25`，所以每步模拟 `0.5 s`，对应 `control_dt=0.5`。

`trajectory_dt` 由模型输出决定，可以与控制周期不同。例如，模型仍按 `0.5 s` 间隔输出轨迹点，但希望每次 `step()` 只推进 `0.1 s`，就保留 `trajectory_dt=0.5`，一起修改环境步和控制周期：

```python
cfg.merge_from({
    "decision_repeat": 5,
    "actor_config.policy_config.control_dt": 0.1,
})
```

仓库的 `DEFAULT_POLICY_CONFIG_0_1S` 使用的就是这组时间设置。EnvInputILQRPolicy 的完整配置和 API 见 [Policy 参考](../../reference/policy.md#api-6-4)。

## Controller：执行车辆控制

Controller 是场景中实际运动的对象，例如车辆、行人或骑行者。`actor_config.controller` 指定主车对象的类，`actor_config.controller_config` 设置尺寸、动力和碰撞检查等参数。周边对象的类型和尺寸由场景元数据补充。

主车默认使用 DefaultVehicle。下面关闭倒车，并将车辆水平速度变化的加速度上限设为 `3 m/s²`：

```python
cfg.merge_from({
    "actor_config.controller_config.enable_reverse": False,
    "actor_config.controller_config.max_acceleration": 3.0,
})
```

| 字段 | 类型与单位 | 默认值 | 用途与生效条件 |
| --- | --- | --- | --- |
| `actor_config.controller` | 类对象 | `DefaultVehicle` | 主车的仿真对象类；具体车型决定底盘、质量、轮胎等参数 |
| `actor_config.controller_config.size` | `[长, 宽, 高]` 或 None，米 | `None` | 设置主车尺寸；`None` 使用车型默认尺寸 |
| `actor_config.controller_config.enable_reverse` | bool | `True` | 是否允许负油门向后驱动；`False` 时负输入用于制动 |
| `actor_config.controller_config.spawn_velocity` | bool | `True` | 是否按记录的初始速度和角速度创建车辆 |
| `actor_config.controller_config.max_acceleration` | float，m/s² | 主车 `15.0` | 限制车辆水平速度变化；周边对象默认不提供此项 |
| `actor_config.controller_config.max_steering` | 数值，度 | 由车型采样 | 转向控制量为 `1` 或 `-1` 时对应的最大车轮转角 |
| `actor_config.controller_config.check_crash_world` | bool | `False` | 是否检查车辆与背景、地形的碰撞；还需开启 Agent 的 `check_crash` |

Policy 中的 `max_acceleration` 限制轨迹求解，Controller 中的同名字段限制车辆运动时的速度变化，两者需要分别设置。各对象的完整配置和车型参数见 [Object / Controller 参考](../../reference/object.md)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.4 Observer 配置](observation.md) · [下一页：5. 组件参考](../../reference/index.md)
