<a id="launcher-autovla"></a>

# 7.2.12 AutoVLA

[English](../../en/launchers/autovla.md)

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.11 Alpamayo 1.5](alpamayo1.5.md) · [下一页：7.2.13 Epona](epona.md)

相关页面：[Launcher 目录](index.md) · [通用启动流程](common.md)

本页目录

- [运行环境与资源](#environment-and-resources)
- [服务端配置](#server-configuration)
- [启动命令](#launch-command)
- [输入输出与限制](#input-output-and-limits)

<a id="environment-and-resources"></a>

## 运行环境与资源

安装 PyTorch、支持 Qwen2.5-VL 的 Transformers、qwen_vl_utils、PyTorch Lightning 和 AutoVLA 项目依赖。除主 checkpoint 外，还需准备基础模型和动作 codebook。

| 项目 | 值或路径 | 用途 |
| --- | --- | --- |
| 上游源码 | AutoVLA/ | AutoVLA 和 navsim 路径 |
| 模型配置 | AutoVLA/config/eval/qwen2.5-vl-3B-nusc-sft-eval.yaml | 视频、动作词表与采样设置 |
| 主权重 | AutoVLA/checkpoints/AutoVLA/AutoVLA_PDMS_89.ckpt | AutoVLA checkpoint |
| 基础模型 | AutoVLA/Qwen2.5-VL-3B-Instruct/ | 配置 model.pretrained_model_path |
| 动作词表 | AutoVLA/codebook_cache/agent_vocab.pkl | 配置 model.codebook_cache_path |
| 依赖说明 | [AutoVLA README](https://github.com/ucla-mobility/AutoVLA/blob/ba34eed74ce6729e7986592d0e66cbaca397b4fa/README.md) | 模型环境和项目依赖 |

配置中的 pretrained_model_path、codebook_cache_path 相对于 AutoVLA 根目录解析。模型配置和主 checkpoint 使用 native_agent.py 指定的路径。

实现：[autovla/native_agent.py](../../../policy_launcher/autovla/native_agent.py)。

<a id="server-configuration"></a>

## 服务端配置

在仿真终端运行以下命令，随后选择场景：

```bash
python -m streetworld.examples.env_server_easydrive \
  --host 127.0.0.1 --port 50052 --web-port 18080 \
  --ad-policy-config autovla
```

<a id="launch-command"></a>

## 启动命令

另开终端，激活模型环境，在 StreetWorld 根目录运行：

```bash
python -m policy_launcher.launch \
  --model autovla --host 127.0.0.1 --port 50052 \
  --device cuda --timeout 360 --max-steps 1000
```

<a id="input-output-and-limits"></a>

## 输入输出与限制

| 项目 | 要求 |
| --- | --- |
| 输入 | FRONT、FRONT_LEFT、FRONT_RIGHT 三相机；各相机维护 4 帧、间隔 0.5 s 的视频历史。还读取主车速度、转向、加速度和导航命令。 |
| 输出 | 生成动作 token 后解码为车辆坐标 float32 (10,2) 轨迹；模型配置为 0.5 s 间隔、5 s 范围。 |
| 注意事项 | autovla 服务端 preset 设置 warmup_step=4，轨迹与控制间隔均为 0.5 s。初始化历史不足的帧由客户端缓存逻辑处理。 |

---

[总目录](../../DOCUMENTATION_ZH.md) · [上一页：7.2.11 Alpamayo 1.5](alpamayo1.5.md) · [下一页：7.2.13 Epona](epona.md)
