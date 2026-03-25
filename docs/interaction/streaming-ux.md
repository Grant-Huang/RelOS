# 流式交互（Streaming UX）详细交互设计稿（Phase 0）

**版本**：v0.1  
**日期**：2026-03-25  
**范围**：以“设备故障分析（告警 → 根因推荐）”为 MVP 核心场景，补齐四阶段知识生命周期下的**流式交互**与**类流式向导**体验。  
**约束**：RelOS 负责关系存储/推理/上下文生成，不直接执行操作（Shadow Mode 默认只记录）。  

---

## 1. 目标与非目标

### 1.1 目标

- **将“不可控的 AI 推理”转为“可消化的增量信息”**：先 L1 结论，再 L2 证据，再 L3 贡献，最后再问一个澄清问题。
- **让运行期反馈成为数据飞轮**：确认/否定动作尽可能一键完成，同时保留“我不确定”。
- **与现有契约对齐**：复用现有 `RootCauseRecommendation` 的自解释字段（`explanation_summary / evidence_relations / phase_contributions / confidence_trace_id`）。
- **为后续 SSE 端点落地提供协议与 UX 规范**：本阶段输出文档，不改代码。

### 1.2 非目标（本稿不实现）

- 不做 AgentNexus 集成、不做真实 Action 执行（Shadow Mode 不变）。
- 不做权限/多租户、不做生产级监控告警。
- 不在本阶段引入 WebSocket 双向编辑（优先 SSE；输入走同步 API）。

---

## 2. 术语与分层解释（L1/L2/L3）

### 2.1 三层信息密度

- **L1（结论 + 下一步）**：推荐根因、置信度、是否需要人工、下一步按钮（确认/否定/不确定）。
- **L2（证据 2–3 条）**：最关键 `evidence_relations`（按置信度与阶段权重排序）。
- **L3（治理与审计）**：`phase_contributions`、`confidence_trace_id`、可回放链路入口（后续可扩展）。

### 2.2 与现有字段的映射（已存在）

- `explanation_summary`：用于 L1 一屏摘要（高层/忙碌场景默认展示）。
- `evidence_relations[]`：用于 L2（工程师需要“为什么”时展开）。
- `phase_contributions[]`：用于 L3（管理者/审计需要“来自哪里”）。
- `confidence_trace_id`：用于追溯与后续问答关联（阶段 4 流式问答依赖）。

---

## 3. 角色分层策略（Frontline / Manager / Executive）

### 3.1 默认展示策略

- **Frontline（老技工）**：默认只展示 L1；L2 需要点击“查看依据”；L3 默认隐藏。
- **Manager（老中层）**：默认展示 L1 + L2（证据折叠展开）；L3 通过“来源与贡献”入口查看。
- **Executive（高层）**：默认展示 `explanation_summary`（一屏摘要）与 `confidence_trace_id`（追溯入口）。

### 3.2 行为目标（每类角色的“最小完成动作”）

- **Frontline**：10 秒内完成“确认/否定/不确定”之一，且不被迫填写表单。
- **Manager**：30 秒内能解释“结论来自哪些证据、主要来自哪个阶段”。
- **Executive**：30 秒内看懂“一屏摘要”，且能把追溯任务交给下级（trace id）。

---

## 4. 四阶段交互总览（与知识生命周期一致）

### 4.1 阶段 1：初始化（资源上传后的“流式澄清”）

**用户目标**：把“上传完成后的一堆候选关系”转为可消化的澄清流程。  
**系统目标**：通过 3 个关键问题把抽取空间收敛，再输出更高质量的候选关系供审核/批量确认。  

建议交互流：

- **Step A（提出 3 个关键澄清问题）**：单选/多选/填空，优先让用户做“选择题”。
- **Step B（基于澄清答案重排候选）**：展示“候选关系数量变化、top 证据变化”。
- **Step C（候选关系逐条到达）**：分页列表或“逐条卡片”，支持批量 approve/skip。

与现有接口对齐方向：

- 文档摄取：`/v1/documents/*`（已存在文档方向；本稿只规定 UX，不新增字段实现）。

空/错/离线态：

- **空**：未抽取到候选 → 提示“缺少关键字段”，引导补充 1–2 个信息再重试。
- **错**：解析失败 → 展示错误原因 + 可重试 + 下载错误报告（后续实现）。
- **离线**：允许保存澄清答案草稿；恢复网络后再提交（前端离线队列）。

### 4.2 阶段 2：调研（微卡片向导：类流式）

**入口**：专家初始化向导 / 访谈会议模式（多人共创）。  
**核心设计**：每次只让用户完成一个 15 秒内的微任务，避免“填表”。  

卡片类型（最小集合）：

- **关系确认卡**：对候选关系给出 `confirm / reject / unsure`。
- **关系新建卡**：模板句填空（默认值自动带出：关系类型/阶段/权重/半衰期）。
- **关系补充卡**：用户否定后给“替代建议”（一键采纳或编辑）。

状态机（与设计计划对齐）：

`INIT → DRAFTING → VALIDATING → SAVED_DRAFT → SUBMITTING → SUBMITTED / SUBMIT_FAILED`

关键 UX 约束：

- **离线草稿**：任何输入立即保存本地草稿；断网不丢。
- **默认值**：默认 `knowledge_phase=interview`、`phase_weight=0.90`、`status=active`（仅当来源为人工确认）。
- **不确定**：允许 `unsure`，写入 `pending_review`（保留贡献，不逼迫结论）。

### 4.3 阶段 3：预训练（资源上传后的“流式澄清” + 候选逐条到达）

阶段 3 与阶段 1 的 UX 框架一致，但来源更偏企业内部文档（SOP/维修记录/日报），因此必须强调：

- `provenance=llm_extracted` 的关系默认 `pending_review`（对齐 `RelationObject` 约束）
- 展示证据片段（后续实现：原文定位/高亮），降低“黑盒恐惧”

### 4.4 阶段 4：运行（决策界面 + 真流式问答）

**同屏布局建议**：

- 上半：决策卡（L1→L2→L3 渐进展开）
- 下半：问答流（仅用于“澄清上下文/选择下一步动作”，不变成闲聊）

核心交互目标：

- **先结论**：在 300–800ms 内给出 `summary`（可先用缓存或规则路径）。
- **再证据**：逐条推送 `evidence`，每条都是可点击的“关系证据卡”。
- **再贡献**：推送 `contributions`，让管理者知道“来自 interview/runtime/pretrain 的占比”。
- **再提问**：只问 1 个“下一步最关键”的澄清问题（提升后续推理质量）。

---

## 5. 阶段 4 真流式协议草案（SSE 优先）

> 本节定义“前后端/调用方契约”，用于后续 Phase 1 实现端点。当前仓库已具备 `confidence_trace_id` 等字段，本协议仅规定事件顺序与 payload shape。

### 5.1 SSE 端点（建议）

- `POST /v1/decisions/analyze-alarm/stream`
- Response：`text/event-stream`

### 5.2 事件序列（建议顺序）

1. `summary`：先给 L1 核心字段  
2. `evidence`：增量推送证据关系列表（逐条或批量）  
3. `contributions`：推送阶段贡献（L3）  
4. `question`：推送 1 个澄清问题（单选/多选/填空）  
5. `done`：结束（或 `error`）

### 5.3 事件 payload 形状（草案）

#### 5.3.1 summary

```json
{
  "confidence_trace_id": "conf-trace-...",
  "recommended_cause": "...",
  "confidence": 0.85,
  "engine_used": "rule_engine|llm|hitl",
  "requires_human_review": false,
  "shadow_mode": true,
  "explanation_summary": "..."
}
```

#### 5.3.2 evidence

```json
{
  "confidence_trace_id": "conf-trace-...",
  "evidence_relations": [
    {
      "id": "rel-...",
      "relation_type": "...",
      "confidence": 0.70,
      "provenance": "manual_engineer|llm_extracted|...",
      "knowledge_phase": "interview|pretrain|runtime|bootstrap",
      "phase_weight": 0.90,
      "status": "active|pending_review|conflicted|archived",
      "provenance_detail": "..."
    }
  ],
  "is_final": false
}
```

#### 5.3.3 contributions

```json
{
  "confidence_trace_id": "conf-trace-...",
  "phase_contributions": [
    { "knowledge_phase": "interview", "score": 0.123456, "share": 0.65 }
  ]
}
```

#### 5.3.4 question

```json
{
  "confidence_trace_id": "conf-trace-...",
  "question": {
    "question_id": "q-001",
    "type": "single_choice|multi_choice|free_text",
    "prompt": "需要确认一个关键信息以提高准确率：当前环境温度是否 > 35°C？",
    "options": [
      { "id": "opt-yes", "label": "是（>35°C）" },
      { "id": "opt-no", "label": "否（≤35°C）" },
      { "id": "opt-unknown", "label": "不确定" }
    ],
    "required": false
  }
}
```

#### 5.3.5 done / error

```json
{ "confidence_trace_id": "conf-trace-...", "ok": true }
```

```json
{
  "confidence_trace_id": "conf-trace-...",
  "ok": false,
  "error_code": "STREAM_INTERNAL_ERROR",
  "message": "..."
}
```

### 5.4 流式问答输入（建议走同步 API）

为降低双向流复杂度，建议把用户回答单独走同步请求：

- `POST /v1/decisions/stream-answer`

请求体建议：

```json
{
  "confidence_trace_id": "conf-trace-...",
  "question_id": "q-001",
  "answer": "opt-yes"
}
```

响应体建议（统一结构可复用现有接口风格，后续实现再定）：

```json
{
  "status": "success",
  "data": { "accepted": true },
  "message": ""
}
```

---

## 6. 关键界面与交互细节（阶段 4 为主）

### 6.1 决策卡（上半屏）

默认折叠策略：

- 首屏展示：`recommended_cause`、`confidence`、`explanation_summary`、`requires_human_review`、Shadow Mode 提示条、三按钮（确认/否定/不确定）
- “查看依据”展开后才展示 `evidence_relations`（最多 3 条，更多则“查看全部证据”）
- “来源与贡献”展开后展示 `phase_contributions` 与 `confidence_trace_id`

按钮语义（与数据飞轮一致）：

- **确认**：我认可本次推荐（后续落地会调用反馈接口或记录事件）
- **否定**：我不认可（后续应引导“替代建议”，但默认允许直接完成）
- **不确定**：我无法判断（记录为弱反馈，避免强迫）

### 6.2 问答流（下半屏）

原则：问答只做“澄清上下文/下一步动作”，避免“聊天”。

- 系统每轮最多问 1 个关键问题（可跳过）
- 每个问题都要说明“为什么问这个”（一句话）
- 用户回答后，系统只做两件事：
  - 更新决策卡中的证据/贡献（如果有变化）
  - 给出下一步建议（例如“建议先检查轴承温升”）

---

## 7. 运行期指标与验收（与现有 test-plan/设计计划一致口径）

建议埋点（后续实现）：

- 决策卡首屏渲染耗时、summary 首包时间（SSE）、evidence 完整时间
- 反馈点击率（确认/否定/不确定）、否定后的替代采纳率
- `requires_human_review=true` 的触发率与最终解决耗时

验收门槛（建议）：

- Frontline：10 秒内完成一次反馈动作（含离线队列写入）
- Manager：30 秒内能解释“主要证据阶段占比”
- Executive：30 秒内看懂 `explanation_summary` 并能复制 `confidence_trace_id`

---

## 8. 与现有实现的对齐清单（本稿输出的“落地要点”）

- 现有 `POST /v1/decisions/analyze-alarm` 已生成：
  - `explanation_summary`
  - `evidence_relations`
  - `phase_contributions`
  - `confidence_trace_id`
- 现有 `RelationObject` 已约束：
  - `llm_extracted` 置信度上限 0.85
  - `llm_extracted` 默认 `pending_review`（除非明确人工确认/运行期强化）
- Phase 1 实现 SSE 时应遵循：
  - **只改变返回形式**：复用现有推理逻辑与字段生成逻辑
  - `confidence_trace_id` 需要短期缓存（TTL）以便问答/回放（先内存，后 Redis）

