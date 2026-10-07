<a id="launcher-openemma_qwen"></a>

# 7.2.15 OpenEMMA Qwen

[English](../../en/launchers/openemma_qwen.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.14 OpenEMMA GPT](openemma_gpt.md) · [下一页：7.2.16 OpenEMMA LLaVA](openemma_llava.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

安装 PyTorch、Transformers、Accelerate、qwen_vl_utils 和 Pillow。加载器使用 Qwen2VLForConditionalGeneration，设置 bfloat16、sdpa 和 device_map="auto"。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | Qwen/Qwen2-VL-7B-Instruct | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

下载表中的 Hugging Face 模型或准备本地缓存。模型配置的 model_type 必须是 qwen2_vl，加载器会检查这一项。

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
  --model openemma_qwen --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用历史中的最后一张，运动提示使用十帧历史。--device 没有传给此类，设备由 device_map="auto" 决定。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.14 OpenEMMA GPT](openemma_gpt.md) · [下一页：7.2.16 OpenEMMA LLaVA](openemma_llava.md)
