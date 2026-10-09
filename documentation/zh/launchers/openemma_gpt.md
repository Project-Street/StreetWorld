<a id="launcher-openemma_gpt"></a>

# 7.15 OpenEMMA GPT

[English](../../en/launchers/openemma_gpt.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.14 Epona](epona.md) · [下一页：7.16 OpenEMMA Qwen](openemma_qwen.md)

<a id="launcher-openemma_gpt-environment-and-resources"></a>

## 运行环境与资源

安装 openai 和 Pillow，在 OPENAI_API_KEY 中设置 API 密钥。Launcher 通过 OpenAI SDK 请求模型，默认模型名见表。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | gpt-4o-2024-11-20 | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

在运行 Launcher 的终端设置 OPENAI_API_KEY。修改模型名时，设置 OpenEMMANativeAgent 的构造参数 model_id；统一 CLI 未提供这个参数。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_gpt-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_gpt-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_gpt --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_gpt-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | GPT 请求包含图像与文本；每轮规划分别生成场景描述、关注对象、驾驶意图和未来速度/曲率。--device 对此后端不生效。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.14 Epona](epona.md) · [下一页：7.16 OpenEMMA Qwen](openemma_qwen.md)
