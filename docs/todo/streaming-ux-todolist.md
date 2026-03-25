# 流式交互（Streaming UX）开发 TodoList（需逐步确认）

> 说明：按你当前习惯，本 TodoList 用于“逐步确认后再进入下一阶段”。  
> 当前处于 **Phase 0（只做文档与原型）**：允许新增/修改文档；不进入代码实现。

---

## 0. 需求与约束复核（本阶段完成后请你确认）

- **载体优先级**：Web（桌面）优先；移动/PDA 仅作为约束（按钮/字体/离线），不做独立交互稿。
- **真流式协议**：阶段 4 优先 SSE；问答输入走同步 API（避免双向流复杂度）。✅ 已确认
- **契约复用**：复用现有 `RootCauseRecommendation` 的解释字段与 `confidence_trace_id`。

---

## Phase 0：只做文档与原型（1–2 天）

### P0-1 产出详细交互稿（文档）

- **目标**：输出“可直接进入实现”的详细交互设计稿。
- **交付物**：`docs/interaction/streaming-ux.md`
- **验收点**：
  - 四阶段策略齐全（初始化/调研/预训练/运行）
  - 阶段 4 SSE 事件顺序与 payload shape 明确
  - 阶段 2 微卡片状态机、空/错/离线态齐全
  - 角色分层（Frontline/Manager/Executive）默认展示策略明确

状态：✅ 已完成

### P0-2 产出低保真线框（入库）

- **目标**：快速对齐“同屏布局（决策卡 + 问答流）”与微卡片向导的关键控件位置。
- **交付物**：`docs/interaction/streaming-wireframes.md`（mermaid 线框）
- **验收点**：一线工程师 3 秒内看懂 L1 主信息；按钮可达性满足手套触控。

状态：✅ 已完成（你已确认需要入库）

---

## Phase 1：阶段 4 真流式最小闭环（后端先行，3–5 天）

> 进入本阶段前，需要你明确“允许开始实现代码”。

### P1-1 新增 SSE 端点（仅改变返回形式）

- **目标**：在不改推理逻辑的前提下，把 `analyze-alarm` 结果分段推送。
- **交付物**：
  - `POST /v1/decisions/analyze-alarm/stream`（`text/event-stream`）
  - 事件：`summary → evidence → contributions → question → done`
- **实现原则**：复用现有字段生成逻辑（`explanation_summary/evidence_relations/phase_contributions/confidence_trace_id`）。

状态：🕒 待开始

### P1-2 trace 短期缓存（TTL）

- **目标**：用 `confidence_trace_id` 关联问答与回放。
- **实现优先级**：先内存缓存（开发态），后续再换 Redis（同接口）。

状态：🕒 待开始

### P1-3 集成测试（最小覆盖）

- **目标**：覆盖 `summary→done` 顺序、断线重连（若支持）、以及 content-type。
- **TDD 约束**：进入测试冻结后，不改断言目标与预期。

状态：🕒 待开始

---

## Phase 2：阶段 2 微卡片后端支持（3–6 天）

### P2-1 引入访谈会话资源（InterviewSession）

- **目标**：支持“访谈会议模式”逐卡推进、可中断续作。
- **接口**：
  - `POST /v1/interview/sessions`
  - `GET /v1/interview/sessions/{id}/next-card`
  - `POST /v1/interview/sessions/{id}/submit-card`

状态：🕒 待开始

---

## Phase 3：阶段 1/3 上传后澄清流（5–10 天）

### P3-1 文档澄清问题结构与提交接口

- **目标**：上传后先澄清再抽取/重排候选。
- **接口**：
  - `POST /v1/documents/{doc_id}/clarify`

状态：🕒 待开始

---

## 你下一步需要确认的事项（确认后我再进入 Phase 1）

- ✅ 已确认：阶段 4 流式输出按 **SSE 优先**推进
- ✅ 已确认：低保真线框入库（`docs/interaction/`）
- 待你确认：是否现在进入 **Phase 1（开始实现代码）**

