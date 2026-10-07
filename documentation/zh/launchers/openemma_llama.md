<a id="launcher-openemma_llama"></a>

# 7.2.17 OpenEMMA Llama

[English](../../en/launchers/openemma_llama.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.16 OpenEMMA LLaVA](openemma_llava.md) · [下一页：总目录](../../DOCUMENTATION_ZH.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

安装 PyTorch、支持 MllamaForConditionalGeneration 的 Transformers、Accelerate 和 Pillow。加载器使用 bfloat16、device_map="auto"。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | meta-llama/Llama-3.2-11B-Vision-Instruct | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

准备完整的 Llama 3.2 Vision 模型，并确认账户具有访问权限。加载器通过 AutoProcessor 和 MllamaForConditionalGeneration.from_pretrained 读取表中的模型名。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_llama --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用最后一张，文本包含十帧运动历史。--device 没有传给此类，设备由模型加载器决定。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.16 OpenEMMA LLaVA](openemma_llava.md) · [下一页：总目录](../../DOCUMENTATION_ZH.md)
