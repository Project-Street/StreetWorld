<a id="section-4-2"></a>

# 4.2 配置层级与优先级

[English](../../../en/guides/configuration/hierarchy.md)

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.1 Config 的用途与使用](config.md) · [下一页：4.3 Environment 与 Agent 的常用参数](environment-agent.md)

下面配置主车使用 iLQR 跟踪轨迹，每个环境步模拟 `0.5 s`，并关闭倒车。先取得 ScenarioEnv 的默认配置，再写入本次测试的设置：

```python
from streetworld.envs.scenario_env import ScenarioEnv
from streetworld.policy.env_input_ilqr_policy import EnvInputILQRPolicy

cfg = ScenarioEnv.default_config()
cfg.merge_from({
    "scene_ids": ["0007"],
    "decision_repeat": 25,
    "actor_config": {
        "policy": EnvInputILQRPolicy,
        "policy_config": {
            "smooth": False,
            "max_acceleration": 3.0,
            "trajectory_dt": 0.5,
            "control_dt": 0.5,
        },
        "controller_config": {"enable_reverse": False},
    },
})
```

顶层的 `scene_ids` 和 `decision_repeat` 是环境参数，分别指定运行哪个场景、每步推进多少个物理小步。`actor_config` 是主车 AgentManager 的配置：`policy` 指定策略类，`policy_config` 传给这个策略，`controller_config` 传给车辆对象。`observer` 和 `observer_config` 同样分别指定观测类和它的参数，本例沿用默认值。

周边交通对象使用 `participant_config`，与主车的配置层级相同。例如，主车可以用 EnvInputILQRPolicy 跟踪模型轨迹，周边车辆仍用默认 ReplayPolicy 按记录轨迹回放。不同对象的 Policy、Observer 和 Controller 可以分别选择。

## 默认值和运行配置

基础参数来自 [BASE_DEFAULT_CONFIG](../../../../streetworld/configs/default_config.py)。ScenarioEnv 在此基础上加入 [SCENARIO_ENV_CONFIG](../../../../streetworld/configs/default_scenario_config.py)；交互环境再加入 [INTERACTIVE_ENV_CONFIG](../../../../streetworld/envs/interactive_env.py)。构造环境时，最后合并调用者传入的配置，同名字段以传入值为准。

例如，上例没有修改观测设置，主车就使用默认 AssemblyObservation；`decision_repeat` 则由默认的 `5` 改为 `25`。调用 `default_config()` 得到类的默认值。运行时用 `env.config` 查看当前配置；加载场景后，它返回 ScenarioDataManager 保存的场景配置副本。

## 启动脚本中的合并顺序

Environment Server 的 nuScenes / Waymo 分支依次合并 [DEFAULT_POLICY_CONFIG_0_5S](../../../../streetworld/configs/default_policy_config.py)、`--ad-policy-config` 指定的模型配置和命令行设置，再将结果传入环境。后合并的同名字段覆盖前面的值，例如 `--web-port` 会覆盖配置中的网页端口。

NuRec 分支先根据命令行生成环境配置，再合并 [NUREC_CONFIG](../../../../streetworld/configs/nurec_config.py)，设置 NuRec 的相机布局和导航方式。这个分支不应用 `--ad-policy-config`，默认使用原始控制输入 Policy，运行步骤见[NuRec 示例](../rendering-backends.md#nurec)。

---

[总目录](../../../DOCUMENTATION_ZH.md) · [上一页：4.1 Config 的用途与使用](config.md) · [下一页：4.3 Environment 与 Agent 的常用参数](environment-agent.md)
