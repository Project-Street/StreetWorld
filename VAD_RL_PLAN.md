<proposed_plan>
**Title: RL 微调 VAD Planning Transformer（对齐现有 UniAD RL Framework）**

**Summary**
- 在 `rl_framework/vad/` 继承扩展 VAD（不改 `VAD/` 源码），新增 `feature_extractor` 路径输出规划输入特征。
- 新增 VAD RL 入口：`create_vad` 加载 ckpt、`VADWrapper` 产生观测、`CustomVADPolicy` 直接跑 `ego_*_decoder` 输出动作与 value。
- PPO 训练只更新规划模块（LoRA+轨迹头），感知/预测冻结；训练节奏沿用 UniAD 的 phase 0/1/2。
- 观测与 mode 选择严格对齐 UniAD：不使用 `ego_his_trajs/ego_lcf_feat`，必须使用 `ego_fut_cmd` 左/右/直选择轨迹。
- 风格要求：实现简洁，异常输入直接抛错。

**Important API / Interface Changes**
- 新增继承扩展模块（`rl_framework/vad`），提供 `feature_extractor` 输出；不改 `VAD/` 源码。
- `rl_framework/train_ppo.py` 新增 VAD 配置字段、backend 切换、以及 VAD 对应的 phase preset。
- 新增 VAD RL 模块与策略网络文件。
- 新增/复用 LoRA 工具（从 `rl_framework/uniad/policy_network.py` 抽出或直接复用）。

**Implementation Plan**
1. **为 VAD 增加 Feature Extractor 路径（继承重写，不改原 VAD）**
   - 新增 `rl_framework/vad/vad_ext.py`：
     - `class VADFeature(VAD)`：继承 `projects.mmdet3d_plugin.VAD.VAD.VAD`。
     - `class VADHeadFeature(VADHead)`：继承 `projects.mmdet3d_plugin.VAD.VAD_head.VADHead`。
   - 重写逻辑：
     - `VADFeature.forward_test()` / `simple_test()` / `simple_test_pts()`：
       - 当 `feature_extractor=True` 时直接返回特征字典，跳过 GT 相关与 metric 计算逻辑。
       - 允许 `gt_bboxes_3d`、`gt_labels_3d` 等为空。
     - `VADHeadFeature.forward(..., feature_extractor=False)`：
       - 在规划部分进入 `ego_agent_decoder` 之前提取并返回：
         - `ego_query`（B,1,D）
         - `ego_pos_emb`（B,1,D）
         - `agent_query`（B,Q,D）
         - `agent_pos_emb`（B,Q,D）
         - `agent_mask`（B,Q）
         - `map_query`（B,M,D）
         - `map_pos_emb`（B,M,D）
         - `map_mask`（B,M）
     - 这些特征来自 VAD 内部已融合的 query / pos embedding，确保感知/预测全冻结。

2. **新增 VAD 模型加载器（运行期替换类型）**
   - 新增 `rl_framework/vad/loader.py`（或扩展 `rl_framework/uniad/loader.py`）：
     - `create_vad(vad_config_path, vad_checkpoint_path, device)`：
       - 导入 `rl_framework.vad.vad_ext` 以注册扩展类。
       - 加载 cfg 后将 `cfg.model.type` 改为 `VADFeature`，`cfg.model.pts_bbox_head.type` 改为 `VADHeadFeature`。
       - 使用 mmcv Config 构建模型并加载 ckpt。
       - `model.eval()` + 全部 `requires_grad=False`。
    - `extract_vad_planning_weights(model)`：
      - 返回 `ego_agent_decoder`、`ego_map_decoder`、`ego_fut_decoder` 的 `state_dict`。
      - 用于 RL policy 初始化。
   - `vad_checkpoint_path` 默认指向 `VAD/ckpts/VAD_base_stage_2.pth`（可由配置覆盖）。

3. **新增 VAD 环境 Wrapper**
   - 新增 `rl_framework/vad/env_wrapper.py`：
     - 类似 `UniADWrapper`，但调用 `VAD`：
       - `raw_data = parse_vad_obs(...)` 保留（VAD 输入格式一致）。
       - **不使用** `ego_his_trajs`、`ego_lcf_feat`。
       - **必须提供 `ego_fut_cmd`**：由 simulator `info['command']` 生成 one‑hot（`0=right, 1=left, 2=straight` → `[1,0,0]/[0,1,0]/[0,0,1]`）。
       - 调用 `vad_model(return_loss=False, feature_extractor=True, **raw_data)`。
       - 生成观测 dict：`ego_query` / `agent_query` / `agent_pos_emb` / `agent_mask` / `map_query` / `map_pos_emb` / `map_mask` / `ego_fut_cmd`。
    - `action_space` 与现有一致：`planning_steps * 2`，保持 delta 轨迹接口不变。
     - 需要在 `TrainingConfig` 中将 `planning_steps` 与 VAD `fut_ts` 对齐（默认 6）。

4. **新增 VAD Planning Policy（PPO） + LoRA**
   - 新增 `rl_framework/vad/policy_network.py`：
     - 只实现 **一个类**：`CustomVADPolicy(ActorCriticPolicy)`，**不再单独定义网络类**。工程实现要求如下：
       - **初始化与参数**：
         - `__init__(...)` 接收 `planning_steps`, `embed_dims`, `ego_fut_mode`，以及 `planning_weights`（包含 `ego_agent_decoder / ego_map_decoder / ego_fut_decoder` 的 `state_dict`）。
         - `features_extractor_class` 使用 pass-through（同 UniAD 的 `UniADFeaturesExtractor` 逻辑）。
       - **模块构建（_build 内完成）**：
         - 构建 `ego_agent_decoder` / `ego_map_decoder` / `ego_fut_decoder` 并加载 `planning_weights`。
         - `action_net = nn.Identity()`（动作均值直接来自 `ego_fut_preds`，不再额外投影）。
         - `value_adapter = LayerNorm(embed_dims) -> Linear(embed_dims, 2*embed_dims) -> ReLU -> Linear(2*embed_dims, embed_dims)`.
         - `value_net = Linear(embed_dims, embed_dims) -> ReLU -> Linear(embed_dims, 1)`.
         - `log_std` 与 UniAD 一致（每 2 维一组低/高噪声初始化）。
       - **actor 前向（用于动作分布均值）**：
         - `ego_agent_decoder` → `ego_map_decoder` → `ego_fut_decoder` 得到 `ego_fut_preds`，形状 `[B, M, T, 2]`。
         - 用 `ego_fut_cmd` 选择 mode（左/右/直），得到 `[B, T, 2]`。
         - 按 delta 形式 flatten 成 `[B, T*2]`，作为 `action_mean`。
       - **critic 前向（只在分叉处 detach）**：
         - `ego_map_out = ego_map_query.permute(1, 0, 2)`，形状 `[B, 1, D]`。
         - `value_in = ego_map_out.squeeze(1).detach()`，形状 `[B, D]`。
         - `latent_vf = value_adapter(value_in)` → `value_net(latent_vf) = V(s)`。
       - **输出**：
         - `action_mean` + `log_std` 组成动作分布；`value_net` 输出 `V(s)`。
    - **LoRA 注入点**：
      - 遍历 `ego_agent_decoder.layers[*].attentions` 与 `ego_map_decoder.layers[*].attentions`，对 `MultiheadAttention` 的 `in_proj_weight` 注入 LoRA（仅 q/v）。
      - **mmcv 的 `MultiheadAttention` 是 wrapper，真实的 `nn.MultiheadAttention` 在 `attn.attn`：**
        - 若对象有 `in_proj_weight` → 直接用；
        - 否则若有 `attn.attn.in_proj_weight` → 用 `attn.attn`；
        - 其他情况直接 `raise`。
      - 复用 `rl_framework/uniad/policy_network.py` 的 `LoRAParametrization` 与 `_register_lora_on_attention` 逻辑，必要时抽成 util。
      - 冻结原 attention 权重，仅 LoRA 参数可训练。
     - 加载权重：
       - 从 `extract_vad_planning_weights()` 获得 state_dict 初始化。
       - 仅这些模块参与优化，其它模块保持冻结。
     - 输入合法性：`ego_fut_cmd` 非 one‑hot / shape 错误 → 直接 `raise`。

5. **Phase 训练策略（与 UniAD 对齐）**
   - 在 `TrainingConfig.phase_presets` 中复用现有 0/1/2 相同配方，映射到 VAD：
     - `train_action` → 训练 `ego_fut_decoder`
     - `train_lora` → 启用 LoRA 并仅训练 LoRA 参数
     - `train_log_std` → 是否训练动作分布噪声
   - 默认 schedule：`[(0,0.05),(1,0.55),(2,0.4)]`（可由配置覆盖）
   - Phase 0：仅训练 critic（稳定 V 值）
   - Phase 1：训练 LoRA + 小学习率微调 ego_fut_decoder
   - Phase 2：训练 LoRA + 进一步微调 ego_fut_decoder（可选更小 lr）

6. **在训练入口加入 VAD Backend 分支**
   - 修改 `rl_framework/train_ppo.py`：
     - `TrainingConfig` 新增：
       - `vad_config_path`
       - `vad_checkpoint_path`
       - `backend = "vad" | "uniad"`
     - `create_env()` 根据 backend 选择 `UniADWrapper` 或 `VADWrapper`。
     - `create_ppo_model()` 根据 backend 选择 `CustomUniADPolicy` 或 `CustomVADPolicy`。
     - 如果 backend=vad，加载 planning weights 初始化 policy。

7. **文档与配置同步**
   - 更新 `rl_framework/README.md`：
     - 新增 VAD 路径、ckpt 要求与运行说明。
     - 写清楚 LoRA 与 phase 训练策略、`ego_fut_cmd` 与 cmd‑mode 选择规则。

8. **代码风格要求（强制）**
   - 新增代码保持简洁：
     - 不写复杂 if‑else 链；
     - 不用 try/except 去吞异常；
     - 非正常输入直接 `raise ValueError` / `AssertionError`。

**Test Cases and Scenarios**
- 运行一次 VAD feature_extractor 前向，确认输出 dict 键与形状正确。
- 运行 VAD 推理（单场景），确认 `ego_fut_cmd`→mode 选择逻辑生效。
- 少场景 PPO 训练，确认 loss 能下降且无 shape/设备错误。
</proposed_plan>
