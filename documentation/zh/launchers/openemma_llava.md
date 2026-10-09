<a id="launcher-openemma_llava"></a>

# 7.17 OpenEMMA LLaVA

[English](../../en/launchers/openemma_llava.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.16 OpenEMMA Qwen](openemma_qwen.md) · [下一页：7.18 OpenEMMA Llama](openemma_llama.md)

<a id="launcher-openemma_llava-environment-and-resources"></a>

## 运行环境与资源

将 OpenEMMA 源码放在 StreetWorld 根目录，其中提供 llava.model.builder。按 OpenEMMA/requirements.txt 安装 PyTorch、Transformers、CUDA 和图像处理依赖。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| Launcher 实现 | policy_launcher/openemma/native_agent.py | 共用 OpenEMMANativeAgent，不同子类选择后端 |
| 后端实现 | policy_launcher/openemma/backbone.py | 模型加载与生成 |
| 默认模型名 | liuhaotian/llava-v1.6-mistral-7b | 代码默认 model_id，不由统一 CLI 修改 |
| 依赖说明 | [OpenEMMA requirements](https://github.com/taco-group/openemma/blob/8403ea636696c5c10e8fdeca566410de0a07e449/requirements.txt) | 后端依赖列表 |

加载器将 OpenEMMA/ 添加到 Python 路径，以 llava-v1.6-mistral-7b 名称创建模型。按表准备模型资源；移动源码目录时，修改 backbone.py 的 source_root。

实现：[openemma/native_agent.py](../../../policy_launcher/openemma/native_agent.py)。

<a id="launcher-openemma_llava-server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config openemma
```

<a id="launcher-openemma_llava-launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model openemma_llava --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="launcher-openemma_llava-input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT 相机、主车运动状态和导航提示；缓存 10 帧，motion_dt=0.5 s。历史不足时返回 warmup_action 的 (1,2) 数组，服务端专家预热控制覆盖这些初始动作。 |
| 输出 | 解析未来速度/曲率并以 prediction_dt=0.5 s 积分为车辆坐标 (N,2) 轨迹，提示要求 10 点，解析器至少要求 2 点。 |
| 注意事项 | 图像输入只使用最后一张，张量通过 .cuda() 移到 GPU；统一 --device 没有传入模型。需要指定可见 GPU 时在启动进程前设置 CUDA_VISIBLE_DEVICES。服务端 openemma preset 设置 warmup_step=10；生成内容未通过回复检查时会重试；解析失败且存在上次轨迹时，返回上次轨迹。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.16 OpenEMMA Qwen](openemma_qwen.md) · [下一页：7.18 OpenEMMA Llama](openemma_llama.md)
