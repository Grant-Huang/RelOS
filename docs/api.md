# RelOS API 接口规范

**版本**：v1.1  
**Base URL**：`http://localhost:8000/v1`  
**格式**：JSON  
**认证**：MVP 阶段无认证；Sprint 4 实现 JWT Bearer Token

---

**近期新增端点**：`/v1/expert-init`（专家初始化）、`/v1/metrics`（图谱统计）、`/v1/scenarios`（演示场景 + 复合扰动分析）、`/v1/documents`（文档摄取 + AI 标注）、`/v1/decisions/pending-review`（决策级 HITL）

## 目录

1. [健康检查](#1-健康检查)
2. [关系管理](#2-关系管理)
3. [决策分析](#3-决策分析)
4. [访谈微卡片（阶段 2）](#4-访谈微卡片阶段-2)
5. [专家初始化（Sprint 3）](#5-专家初始化-sprint-3)
6. [图谱统计（Sprint 3）](#6-图谱统计-sprint-3)
7. [演示场景（Sprint 3 扩展）](#7-演示场景-sprint-3-扩展)
8. [文档摄取与 AI 标注（Sprint 3 扩展）](#8-文档摄取与-ai-标注-sprint-3-扩展)
9. [错误码](#9-错误码)
10. [通用 Schema](#10-通用-schema)
11. [Telemetry（MVP）](#11-telemetrymvp)

---

## 1. 健康检查

### GET /health

检查服务和依赖是否正常。

**响应**：
```json
{
  "status": "ok",
  "neo4j": "ok",
  "version": "0.1.0"
}
```

| 字段 | 说明 |
|------|------|
| `status` | `"ok"` 或 `"degraded"` |
| `neo4j` | `"ok"` 或 `"error"` |

---

## 2. 关系管理

### POST /relations

创建或合并一条关系。

若图中已存在相同节点对 + 相同 relation_type 的关系，执行置信度合并（加权滑动平均）。

**请求体**（RelationObject）：
```json
{
  "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
  "source_node_id": "alarm-VIB-001",
  "source_node_type": "Alarm",
  "target_node_id": "component-bearing-M1",
  "target_node_type": "Component",
  "confidence": 0.70,
  "knowledge_phase": "interview",
  "phase_weight": 0.90,
  "provenance": "manual_engineer",
  "provenance_detail": "张工 20 年经验总结",
  "extracted_by": "human:operator-zhang",
  "half_life_days": 365,
  "status": "active",
  "properties": {
    "context": "高温天气（>35°C）"
  }
}
```

**注意**：
- `provenance = "llm_extracted"` 时，`confidence` 自动夹紧到 0.85，`status` 强制为 `pending_review`
- 未传 `knowledge_phase` / `phase_weight` 时，系统按来源自动填充默认值（见通用 Schema）
- `id` 字段可省略，系统自动生成 UUID

**响应** `201 Created`：返回完整的 RelationObject。

---

### GET /relations/{relation_id}

按 ID 查询单条关系。

**响应** `200 OK`：
```json
{
  "id": "rel-001",
  "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
  "source_node_id": "alarm-VIB-001",
  "source_node_type": "Alarm",
  "target_node_id": "component-bearing-M1",
  "target_node_type": "Component",
  "confidence": 0.70,
  "provenance": "manual_engineer",
  "provenance_detail": "张工 20 年经验总结",
  "extracted_by": "human:operator-zhang",
  "created_at": "2026-03-22T10:00:00Z",
  "updated_at": "2026-03-22T10:00:00Z",
  "half_life_days": 365,
  "status": "active",
  "conflict_with": [],
  "properties": {}
}
```

**错误** `404 Not Found`：关系不存在。

---

### POST /relations/{relation_id}/feedback

提交人工反馈（确认/否定）。这是**数据飞轮的核心触发点**。

**请求体**：
```json
{
  "engineer_id": "operator-zhang",
  "confirmed": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `engineer_id` | string | 操作工程师 ID（用于审计追踪）|
| `confirmed` | boolean | `true`=确认，`false`=否定 |

**置信度更新规则**：
- 确认：`confidence = min(1.0, confidence + 0.15)`，`status → active`
- 否定：`confidence = max(0.0, confidence - 0.30)`；若 `confidence < 0.2`，`status → archived`

**响应** `200 OK`：返回更新后的 RelationObject。

**阶段强化说明（阶段 4 -> 强化闭环）**：
- 反馈事件默认记为 `knowledge_phase = "runtime"`
- 若反馈来自运行期真实操作，系统可将该关系的 `phase_weight` 提升到运行期权重（建议 1.00）
- 建议在 `properties.feedback_context` 中记录操作上下文（班次、环境、工单）

---

### POST /relations/subgraph

提取以指定节点为中心的子图。

**请求体**：
```json
{
  "center_node_id": "device-M1",
  "max_hops": 2,
  "min_confidence": 0.3
}
```

**响应** `200 OK`：RelationObject 数组，按 confidence 降序。

---

### GET /relations/pending-review?limit=50

获取待人工审核的关系列表（Human-in-the-Loop 工作队列）。

**Query 参数**：
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `limit` | int | 50 | 返回数量上限 |

**响应** `200 OK`：RelationObject 数组，按 confidence 降序。

---

## 3. 决策分析

### POST /decisions/analyze-alarm

**核心端点**：接收设备告警，经 LangGraph 工作流返回根因推荐。

**请求体**：
```json
{
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "alarm_code": "VIB-001",
  "alarm_description": "主轴振动超限 18.3mm/s，环境温度 38°C",
  "severity": "high",
  "timestamp": "2026-03-22T10:30:00Z",
  "force_hitl": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `alarm_id` | string | ✅ | 告警唯一 ID |
| `device_id` | string | ✅ | 设备节点 ID |
| `alarm_code` | string | ✅ | 标准告警码 |
| `alarm_description` | string | ✅ | 告警描述（用于 LLM 分析）|
| `severity` | string | 否 | `low/medium/high/critical`，默认 `medium` |
| `force_hitl` | boolean | 否 | `true` 强制跳过推理，直接触发人工审核 |

**响应** `200 OK`：
```json
{
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "recommended_cause": "component-bearing-M1 异常（近 6 个月触发 8 次）",
  "confidence": 0.85,
  "reasoning": "规则引擎基于 2 条高置信度关系推断，最高置信度关系：ALARM__INDICATES__COMPONENT_FAILURE，置信度 0.70。来源：张工 20 年经验总结",
  "supporting_relation_ids": ["rel-001", "rel-002"],
  "engine_used": "rule_engine",
  "requires_human_review": false,
  "shadow_mode": true,
  "context_relations_count": 4,
  "processing_time_ms": 87.3,

  "explanation_summary": "推荐：component-bearing-M1 异常；置信度 0.85；主要证据阶段：interview（约 65%）",
  "evidence_relations": [
    {
      "id": "rel-001",
      "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
      "confidence": 0.70,
      "provenance": "manual_engineer",
      "knowledge_phase": "interview",
      "phase_weight": 0.90,
      "status": "active",
      "provenance_detail": "张工 20 年经验总结"
    }
  ],
  "phase_contributions": [
    {"knowledge_phase": "interview", "score": 0.63, "share": 0.65},
    {"knowledge_phase": "runtime", "score": 0.34, "share": 0.35}
  ],
  "confidence_trace_id": "conf-trace-3fa2c9e8d1b64c6ab2a5c4c1"
}
```

| 字段 | 说明 |
|------|------|
| `engine_used` | `rule_engine` / `llm` / `hitl` / `no_data` / `llm_placeholder` |
| `requires_human_review` | `true` 时前端应显示 HITL 提示 |
| `shadow_mode` | `true` 时操作未实际执行 |
| `processing_time_ms` | 端到端处理时间 |
| `explanation_summary` | 供管理层/高层的“一屏简短解释”（由证据阶段贡献自动生成） |
| `evidence_relations` | 解释证据关系的最小集合（用于追溯） |
| `phase_contributions` | 按 `knowledge_phase` 汇总的阶段贡献（用于分层可解释性） |
| `confidence_trace_id` | 本次决策的可审计追踪 ID（便于日志/埋点关联） |

---

### POST /decisions/analyze-alarm/stream

告警根因分析（**SSE 真流式**）。复用 `POST /decisions/analyze-alarm` 的计算逻辑与解释字段，只改变返回形式为分段事件：

- `summary`：先给 L1（结论/置信度/摘要）
- `evidence`：推送证据关系（L2）
- `contributions`：推送阶段贡献（L3）
- `question`：推送 1 个澄清问题（可跳过）
- `done`：结束

**请求体**：同 `POST /decisions/analyze-alarm`（`AlarmEvent`）。

**响应**：`200 OK`，`Content-Type: text/event-stream`

事件示例（节选）：

```
event: summary
data: {"confidence_trace_id":"conf-trace-...","recommended_cause":"...","confidence":0.85,"engine_used":"rule_engine","requires_human_review":false,"shadow_mode":true,"explanation_summary":"..."}

event: evidence
data: {"confidence_trace_id":"conf-trace-...","evidence_relations":[{"id":"rel-001","relation_type":"...","confidence":0.7,"provenance":"manual_engineer","knowledge_phase":"interview","phase_weight":0.9,"status":"active","provenance_detail":"..."}],"is_final":true}

event: done
data: {"confidence_trace_id":"conf-trace-...","ok":true}
```

---

### POST /decisions/stream-answer

阶段 4 流式问答的输入接口：用于提交 `analyze-alarm/stream` 返回的 `question` 回答。

**请求体**：

```json
{
  "confidence_trace_id": "conf-trace-...",
  "question_id": "q-001",
  "answer": "opt-yes"
}
```

**响应**（统一返回结构）：

```json
{
  "status": "success",
  "data": { "accepted": true },
  "message": ""
}
```

### POST /decisions/execute-action

将决策推荐转化为可审计的操作记录（Shadow Mode 下只记录日志）。

**请求体**：
```json
{
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "recommended_cause": "轴承磨损",
  "action_description": "检查主轴轴承磨损情况",
  "operator_id": "operator-zhang"
}
```

**Pre-flight Check 规则**：操作描述必须包含检查/查看/确认/记录/测量类关键词（MVP 安全白名单）。

**响应** `200 OK`：
```json
{
  "action_id": "act-uuid-...",
  "status": "completed",
  "shadow_mode": true,
  "logs": [
    {"timestamp": "...", "from": "pending", "to": "pre_flight_check", "operator": "operator-zhang", "reason": ""},
    {"timestamp": "...", "from": "pre_flight_check", "to": "approved", "operator": "operator-zhang", "reason": "Pre-flight 五步检查全部通过"},
    {"timestamp": "...", "from": "approved", "to": "executing", "operator": "operator-zhang", "reason": ""},
    {"timestamp": "...", "from": "executing", "to": "completed", "operator": "operator-zhang", "reason": "[Shadow Mode] 操作已记录，未实际执行"}
  ],
  "pre_flight_results": {
    "device_id_valid": true,
    "action_description_valid": true,
    "alarm_id_present": true,
    "action_type_safe": true,
    "no_duplicate": true
  }
}
```

---

### GET /decisions/action/{action_id}

查询操作记录状态（前端轮询用）。

**响应** `200 OK`：ActionStatusResponse（同上格式）。

**错误** `404 Not Found`：Action 不存在。

---

### GET /decisions/pending-review

获取**决策级** HITL 队列，与 `GET /relations/pending-review` 的“关系审核队列”分离。

**响应** `200 OK`：

```json
[
  {
    "decision_id": "decision-incident-semicon-001",
    "incident_id": "incident-semicon-001",
    "title": "半导体封装复合扰动决策包",
    "risk_level": "high",
    "recommended_plan_id": "plan-balance-repair-and-expedite",
    "requires_human_review": true,
    "review_reason": "存在设备异常/质量或物料约束，需要主管确认推荐方案与动作边界",
    "status": "pending_review"
  }
]
```

---

### POST /decisions/{decision_id}/review

提交决策级审核结果。

**请求体**：

```json
{
  "reviewed_by": "supervisor-li",
  "selected_plan_id": "plan-balance-repair-and-expedite",
  "approved_actions": ["act-maint-smt02-feeder", "act-allocate-0402"],
  "rejected_actions": [],
  "review_comment": "允许先维修再并行排产",
  "approve": true
}
```

**响应**：返回更新后的 `DecisionPackage`。

---

### GET /decisions/{decision_id}/actions

查询某个决策包对应的 `ActionBundle`。

**响应** `200 OK`：

```json
{
  "bundle_id": "bundle-decision-incident-semicon-001",
  "decision_id": "decision-incident-semicon-001",
  "status": "shadow_planned",
  "actions": [
    {
      "action_id": "act-maint-smt02-feeder",
      "action_type": "maintenance_work_order",
      "target_system": "MRO",
      "target_entity": "SMT-02",
      "summary": "创建 SMT-02 送料器预防性更换工单",
      "risk_level": "high",
      "requires_human_review": true,
      "payload_preview": {"machine_id": "SMT-02"}
    }
  ],
  "shadow_mode": true,
  "execution_notes": "Shadow Mode 已开启：动作包仅用于演示和审计，不直接触发 MES/MRO 写入。"
}
```

---

## 4. 访谈微卡片（阶段 2）

> 微卡片是“类流式向导”：一次只做一个 15 秒内的微任务（确认/否定/不确定，或新建关系）。

### POST /interview/sessions

创建访谈会话（MVP：从 `pending_review` 队列生成一组“关系确认卡”）。

**请求体**：

```json
{
  "engineer_id": "eng-1",
  "device_id": "device-M1",
  "limit": 20
}
```

**响应** `201 Created`：

```json
{
  "session_id": "ivs-...",
  "total_cards": 12
}
```

---

### GET /interview/sessions/{session_id}/next-card

拉取下一张卡片。

**响应** `200 OK`（示例：关系确认卡）：

```json
{
  "session_id": "ivs-...",
  "card": {
    "card_id": "card-ivs-...-0",
    "type": "relation_confirm",
    "hint": "请确认这条关系是否正确（可选择不确定）",
    "relation": { "id": "rel-001", "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE", "source_node_id": "device-M1", "source_node_type": "Device", "target_node_id": "component-bearing-M1", "target_node_type": "Component", "confidence": 0.6, "provenance": "llm_extracted", "provenance_detail": "从维修记录抽取", "extracted_by": "llm:mock", "half_life_days": 365, "status": "pending_review", "conflict_with": [], "properties": {} }
  }
}
```

卡片结束时会返回：

```json
{
  "session_id": "ivs-...",
  "card": { "card_id": "done", "type": "done", "message": "本次访谈卡片已完成" }
}
```

---

### POST /interview/sessions/{session_id}/submit-card

提交卡片结果。

- `confirm/reject`：等价于人工反馈（会触发运行期强化字段写入）
- `unsure`：保留 `pending_review`，但记录弱反馈（审计/回访用）
- `create_relation`：创建一条人工录入关系（访谈阶段），直接 `active`

**请求体**（示例：确认）：

```json
{
  "card_id": "card-ivs-...-0",
  "action": "confirm",
  "relation_id": "rel-001"
}
```

**响应** `200 OK`：

```json
{
  "session_id": "ivs-...",
  "accepted": true,
  "saved_relation_id": "rel-001",
  "message": "ok"
}
```

---

---

## 5. 专家初始化（Sprint 3）

### POST /expert-init

专家录入单条关系知识。来源自动标记为 `manual_engineer`，状态直接设为 `active`（无需 pending_review）。

**请求体**：
```json
{
  "source_node_id": "CNC-M1",
  "source_node_type": "Device",
  "target_node_id": "ALM-BEARING",
  "target_node_type": "Alarm",
  "relation_type": "DEVICE__TRIGGERS__ALARM",
  "confidence": 0.92,
  "knowledge_phase": "interview",
  "phase_weight": 0.90,
  "provenance_detail": "维修工单 WO-2026-001",
  "engineer_id": "zhang-engineer",
  "half_life_days": 365,
  "properties": {"frequency": 5, "severity": "high"}
}
```

**响应** `201 Created`：
```json
{
  "relation": {
    "id": "rel-8c2f",
    "relation_type": "DEVICE__TRIGGERS__ALARM",
    "confidence": 0.92,
    "knowledge_phase": "interview",
    "phase_weight": 0.90,
    "status": "active"
  },
  "is_new": true,
  "message": "关系已创建"
}
```

---

### POST /expert-init/batch

批量录入关系（最多 100 条）。每条独立处理，单条失败不影响其他条。

**请求体**：ExpertRelationInput 数组

**响应** `200 OK`：
```json
{
  "success_count": 28,
  "failed_count": 2,
  "relations": [...],
  "errors": [{"index": 5, "error": "..."}]
}
```

---

### POST /expert-init/upload-excel

上传 Excel 文件批量导入关系。

**Query 参数**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `engineer_id` | string | 录入工程师 ID |
| `dry_run` | boolean | 只验证不写库，默认 false |

**Excel 格式**（支持中英文列名）：

| source_node_id | source_node_type | target_node_id | target_node_type | relation_type | confidence |
|---|---|---|---|---|---|
| CNC-M1 | Device | ALM-001 | Alarm | DEVICE__TRIGGERS__ALARM | 0.85 |

**响应**：同 `/expert-init/batch`

---

## 6. 图谱统计（Sprint 3）

### GET /metrics

获取关系图谱健康度和规模统计。

**响应** `200 OK`：
```json
{
  "total_nodes": 128,
  "total_relations": 347,
  "avg_confidence": 0.7831,
  "active_count": 289,
  "pending_review_count": 42,
  "conflicted_count": 8,
  "archived_count": 8,
  "active_ratio": 0.833,
  "review_backlog": 42,
  "collected_at": "2026-03-23T10:00:00Z"
}
```

| 字段 | 说明 |
|------|------|
| `active_ratio` | 激活关系比例（active / total），越高代表数据质量越好 |
| `review_backlog` | 待审核积压量，建议保持 < 50 |

---

## 7. 演示场景（Sprint 3 扩展）

> 面向中层（运营）和高层（战略）用户的聚合分析端点。
> 所有数据均来自 Neo4j 中的 RelationObject，无独立数据库。
> 演示前需执行：`python scripts/seed_demo_scenarios.py`

### GET /scenarios/line-efficiency

**场景7**：产线效率瓶颈识别。分析各产线效率，定位瓶颈产线及其根因设备。

**响应示例**：

```json
{
  "lines": [
    {"line_id": "line-L2", "name": "产线 L2（焊接线）", "efficiency_pct": 64, "status": "bottleneck"},
    {"line_id": "line-L3", "name": "产线 L3（装配线）", "efficiency_pct": 81, "status": "normal"},
    {"line_id": "line-L1", "name": "产线 L1（冲压线）", "efficiency_pct": 92, "status": "normal"}
  ],
  "bottleneck_line_id": "line-L2",
  "bottleneck_reason": "设备 M3 过热告警频繁，停机时间 18.5 小时/7天",
  "bottleneck_machine_id": "machine-M3",
  "bottleneck_contribution_pct": 42.0,
  "root_cause_path": [
    "设备 machine-M3 停机频繁",
    "告警：焊接过热告警（7天内 9 次，环比 +80%）",
    "产线 line-L2 效率损失 28%",
    "占总延误贡献 42%"
  ],
  "confidence": 0.88
}
```

---

### GET /scenarios/cross-dept-analysis

**场景8**：跨部门协同问题定位。分析供应链延误的因果路径，计算各部门责任占比。

**响应示例**：

```json
{
  "delayed_workorders": [
    {"workorder_id": "workorder-WO-001", "name": "工单 WO-001", "delay_days": 3, "blocked_by": "优质钢板 Q235"},
    {"workorder_id": "workorder-WO-002", "name": "工单 WO-002", "delay_days": 3, "blocked_by": "优质钢板 Q235"}
  ],
  "delay_attribution": {
    "采购部门（供应商管理）": 47.8,
    "生产部门（排产调整）": 21.7,
    "计划部门（安全库存设置）": 30.5
  },
  "causal_chain": [
    "供应商 A 准时率仅 43%",
    "Q235 钢板库存降至安全库存 22%",
    "2 个工单因缺料被迫推迟",
    "平均每工单延误 3 天"
  ],
  "total_delay_days": 6,
  "confidence": 0.88
}
```

---

### GET /scenarios/issue-resolution

**场景9**：异常处理效率分析。对比不同故障类型和班次的处理时间差异。

**响应示例**：

```json
{
  "issue_type_summary": [
    {"display_name": "轴承磨损", "avg_resolution_hours": 2.7, "sample_count": 3, "status": "slow"},
    {"display_name": "电气故障", "avg_resolution_hours": 1.1, "sample_count": 1, "status": "normal"},
    {"display_name": "冷却系统", "avg_resolution_hours": 0.7, "sample_count": 1, "status": "normal"}
  ],
  "shift_comparison": {
    "night_avg_hours": 3.0,
    "day_avg_hours": 1.3,
    "night_vs_day_ratio": 2.31
  },
  "slowest_issue_type": "轴承磨损",
  "night_vs_day_ratio": 2.31,
  "insight": "夜班处理时间比白班平均长 131%，轴承类问题最为突出（平均 2.7 小时）",
  "confidence": 0.85
}
```

---

### GET /scenarios/risk-radar

**场景10**：企业级风险雷达。聚合全企业风险信号，输出实时风险评分和因果链。

**响应示例**：

```json
{
  "risk_domains": [
    {"name": "供应链中断风险", "domain": "supply_chain", "score": 0.68, "score_pct": 68, "trend": "rising", "level": "high"},
    {"name": "质量波动风险",   "domain": "quality",       "score": 0.52, "score_pct": 52, "trend": "stable", "level": "medium"},
    {"name": "设备稳定性风险", "domain": "equipment",     "score": 0.41, "score_pct": 41, "trend": "rising", "level": "medium"}
  ],
  "top_risk": {"name": "供应链中断风险", "score_pct": 68, "top_driver": "supplier-A"},
  "top_risk_causal_chain": [
    "供应商 A（华盛钢材）交期不稳定，准时率 43%",
    "Q235 钢板库存仅剩 22%",
    "2 个在制工单面临延误，交付承诺风险 ↑"
  ],
  "overall_risk_level": "high",
  "trend": "deteriorating",
  "confidence": 0.82
}
```

---

### GET /scenarios/resource-optimization

**场景11**：资源配置优化。基于问题-资源关系给出 ROI 排序的投入建议。

**响应示例**：

```json
{
  "recommendations": [
    {
      "rank": 1,
      "resource_name": "设备维护团队",
      "roi_pct": 35,
      "investment_rmb": 360000,
      "impact_description": "可减少交付延误 41%"
    },
    {
      "rank": 2,
      "resource_name": "供应商管理专员",
      "roi_pct": 28,
      "investment_rmb": 180000,
      "impact_description": "可减少交付延误 31%"
    },
    {
      "rank": 3,
      "resource_name": "夜班技能培训",
      "roi_pct": 22,
      "investment_rmb": 50000,
      "impact_description": "可缩短故障处理时间 28%"
    }
  ],
  "total_investment_rmb": 590000,
  "expected_efficiency_gain_pct": 18.9,
  "priority_action": "优先投入：设备维护团队（ROI 最高，预计 8 个月回本）",
  "confidence": 0.80
}
```

---

### POST /scenarios/strategic-simulation

**场景12**：战略决策模拟。输入扩产比例，推算对交付风险、故障率、质量的影响。

**请求体**：

```json
{
  "expansion_pct": 30,
  "simulation_horizon_days": 90
}
```

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `expansion_pct` | float | 30.0 | 产能扩张比例（%），如 30 表示扩产 30% |
| `simulation_horizon_days` | int | 90 | 模拟时间窗口（天）|

**响应示例**（`expansion_pct=30`）：

```json
{
  "expansion_pct": 30,
  "delivery_risk_change_pct": 27.0,
  "failure_rate_change_pct": 18.0,
  "quality_risk_change_pct": 12.0,
  "risk_level": "high",
  "causal_chain": [
    "订单量 +30%",
    "产线负载：70% → 91%（+21%）",
    "设备故障率预计上升 18%（弹性系数 1.8）",
    "质量缺陷率预计上升 12%",
    "交付风险综合上升 27%"
  ],
  "recommendations": [
    "建议扩产前完成 M3 维修保养（消除当前 18.5h/周停机隐患）",
    "将供应商 A 准时率提升至 80% 以上，否则扩产后缺料风险 ×2",
    "夜班增配有经验维修工（当前夜班经验均值仅 4.2 年）"
  ],
  "confidence": 0.78
}
```

**注**：模拟基于图中 `CAPACITY__AFFECTS__FAILURE_RATE` 和 `LOAD__INCREASES__RISK` 关系的历史弹性系数，置信度随历史数据积累而提升。

---

### POST /scenarios/composite-disturbance/analyze

**复合场景一期核心端点**：输入 `CompositeDisturbanceEvent`，返回 `DecisionPackage`。

**请求体**：

```json
{
  "incident_id": "incident-semicon-001",
  "factory_id": "fab-01",
  "scenario_type": "semiconductor_packaging",
  "priority": "high",
  "goal": "保障插单交付并控制设备与物料风险",
  "time_window_start": "2026-03-30T13:47:00+08:00",
  "time_window_end": "2026-03-30T13:51:00+08:00",
  "events": [
    {
      "event_id": "evt-001",
      "event_type": "rush_order",
      "source_system": "ERP",
      "occurred_at": "2026-03-30T13:47:00+08:00",
      "entity_id": "order-BGA-rush-500",
      "entity_type": "CustomerOrder",
      "severity": "high",
      "summary": "紧急插单 500 件 BGA",
      "payload": {}
    }
  ]
}
```

**响应** `200 OK`：

```json
{
  "decision_id": "decision-incident-semicon-001",
  "incident_id": "incident-semicon-001",
  "title": "半导体封装复合扰动决策包",
  "incident_summary": "保障插单交付并控制设备与物料风险。关键扰动：紧急插单 500 件 BGA",
  "risk_level": "high",
  "recommended_plan_id": "plan-balance-repair-and-expedite",
  "candidate_plans": [
    {
      "plan_id": "plan-balance-repair-and-expedite",
      "name": "先预防维修再并行插单保交付",
      "summary": "14:15 前处理 SMT-02 送料器风险，随后由 SMT-02 与 SMT-04 共同承接插单。",
      "assumptions": ["备料能在 15:00 前到位"],
      "risk_level": "high",
      "estimated_delivery_impact": "当班内仍有机会完成 18:00 插单目标",
      "estimated_quality_impact": "降低贴装偏移继续扩大的质量风险",
      "estimated_capacity_impact": "短时停机换取稳定产能"
    }
  ],
  "recommended_actions": [],
  "evidence_relations": [],
  "requires_human_review": true,
  "review_reason": "存在设备异常/质量或物料约束，需要主管确认推荐方案与动作边界",
  "trace_id": "trace-...",
  "status": "pending_review",
  "context_block": "## 工厂关系上下文（RelOS）...",
  "context_query_strategy": "composite_disturbance",
  "context_relations_count": 6
}
```

---

### GET /scenarios/composite-disturbance/{incident_id}

按 `incident_id` 查询单个复合场景分析结果。

---

### GET /scenarios/composite-disturbance

列出当前处于待审状态的复合场景摘要。

---

## 8. 文档摄取与 AI 标注（Sprint 3 扩展）

> **工作流**：上传文档 → AI 分析（Claude）→ 人工标注（approve/reject/modify）→ 提交图谱
>
> 演示前运行：`python scripts/generate_sample_docs.py` 生成样本文档
>
> 无 `ANTHROPIC_API_KEY` 时自动切换 Mock 模式，返回预定义演示候选关系。

### 支持的文档类型

| 模板类型 | 格式 | 说明 |
|---------|------|------|
| `cmms_maintenance` | xlsx | 设备维修工单（CMMS 系统导出）|
| `fmea` | xlsx | FMEA 失效模式分析表 |
| `supplier_delivery` | xlsx | 供应商交期记录 |
| `quality_8d` | docx | 8D 质量异常报告 |
| `shift_handover` | docx | 交接班日志 |
| `unknown` | xlsx/docx | 未识别模板，全量 LLM 处理 |

---

### POST /documents/upload

上传文档并启动 AI 关系抽取（异步后台执行）。

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | File | ✅ | xlsx 或 docx 文件，最大 10MB |
| `template_hint` | string | ❌ | 模板类型提示（若已知，跳过自动检测）|

**响应**：`202 Accepted`

```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "cmms_maintenance_orders.xlsx",
  "template_type": "cmms_maintenance",
  "status": "uploaded",
  "pending_count": 0,
  "approved_count": 0,
  "committed_count": 0,
  "created_at": "2026-03-24T10:00:00"
}
```

客户端通过 `GET /documents/{doc_id}` 轮询，直到 `status = "pending_review"`。

---

### GET /documents/

列出所有文档记录，按上传时间倒序。

**响应**：`DocumentSummary[]`

---

### GET /documents/{doc_id}

查询文档详情，包含所有 AI 候选关系。

**响应**（`status = "pending_review"` 时）：

```json
{
  "id": "a1b2c3d4e5f6",
  "filename": "cmms_maintenance_orders.xlsx",
  "template_type": "cmms_maintenance",
  "status": "pending_review",
  "clarify_questions": [
    {
      "question_id": "cq-001",
      "type": "single_choice",
      "prompt": "文档数据主要对应哪类设备？",
      "options": [{"id": "dev-cnc", "label": "CNC/机加工"}],
      "required": false
    }
  ],
  "clarify_answers": { "cq-001": "dev-cnc" },
  "extracted_relations": [
    {
      "id": "3f7a9c1b",
      "source_node_id": "machine-M3",
      "source_node_name": "焊接机 M3",
      "source_node_type": "Machine",
      "target_node_id": "fm-bearing-wear",
      "target_node_name": "轴承磨损",
      "target_node_type": "FailureMode",
      "relation_type": "MACHINE__HAS__FAILURE_MODE",
      "confidence": 0.82,
      "evidence": "2026-01-15 工单：焊接机M3轴承温度异常，更换轴承后恢复正常",
      "reasoning": "维修记录明确描述了设备与故障类型的对应关系",
      "annotation_status": "pending",
      "modified_confidence": null,
      "annotated_at": null
    }
  ],
  "committed_count": 0,
  "created_at": "2026-03-24T10:00:00"
}
```

**`status` 状态说明**：

| 值 | 说明 |
|----|------|
| `uploaded` | 刚上传，等待处理 |
| `parsing` | 正在读取文件结构 |
| `extracting` | AI 正在分析文档 |
| `pending_review` | 候选关系已生成，等待人工标注 |
| `committed` | 已全部提交到图谱 |
| `failed` | 处理出错（见 `error_message`）|

---

### POST /documents/{doc_id}/clarify

阶段 1/3：上传后的“流式澄清”接口，用于提交澄清问题的答案（用于收敛抽取空间、提升候选关系质量）。

MVP 当前行为：**仅记录并回显**答案，后续可在此基础上实现“重抽取/重排序/候选逐条到达”的完整澄清流。

**请求体**：

```json
{
  "answers": {
    "cq-001": "dev-cnc",
    "cq-003": "高温 >35°C"
  },
  "answered_by": "engineer"
}
```

**响应**：返回更新后的完整 `DocumentRecord`（含 `clarify_answers`）。

---

### POST /documents/{doc_id}/annotate/{rel_id}

标注单条候选关系。

**请求体**：

```json
{
  "action": "approve",
  "modified_confidence": null,
  "modified_relation_type": null,
  "annotated_by": "engineer"
}
```

| `action` | 说明 |
|----------|------|
| `approve` | 确认关系，以原置信度提交 |
| `reject` | 拒绝关系，不写入图谱 |
| `modify` | 修改置信度/关系类型后确认（需提供 `modified_confidence` 或 `modified_relation_type`）|

**响应**：返回更新后的完整 `DocumentRecord`。

**批量标注示例（shell 脚本）**：

```bash
DOC_ID="a1b2c3d4e5f6"
# 查出所有 pending 关系 ID
REL_IDS=$(curl -s http://localhost:8000/v1/documents/$DOC_ID \
  | python3 -c "import sys,json; [print(r['id']) for r in json.load(sys.stdin)['extracted_relations']]")

# 全部批准
for REL_ID in $REL_IDS; do
  curl -s -X POST http://localhost:8000/v1/documents/$DOC_ID/annotate/$REL_ID \
    -H "Content-Type: application/json" \
    -d '{"action":"approve"}'
done
```

---

### POST /documents/{doc_id}/commit

将所有 `approved` / `modified` 的候选关系提交到 Neo4j 图谱。

- 跳过 `pending` 和 `rejected` 关系
- 提交后文档状态变为 `committed`，不可重复提交
- 关系 `provenance` 自动设置：
  - 结构化模板（CMMS/FMEA/SUPPLIER）→ `structured_document`（初始置信度 0.65–0.85）
  - 非结构化模板（8D/SHIFT/UNKNOWN）→ `expert_document`（初始置信度 0.50–0.85）
- 关系阶段字段自动设置：`knowledge_phase = "pretrain"`，`phase_weight = 0.70`
- 所有提交关系状态为 `pending_review`（图谱层的第二道审核）

**响应**：

```json
{
  "doc_id": "a1b2c3d4e5f6",
  "committed_count": 3,
  "skipped_count": 1,
  "relation_ids": ["3f7a9c1b", "8e2b4d6f", "1a9c3e5b"],
  "knowledge_phase": "pretrain",
  "phase_weight": 0.70
}
```

---

### 完整 Demo 流程（curl 命令）

```bash
# 1. 生成样本文档
python scripts/generate_sample_docs.py

# 2. 上传维修工单
DOC_ID=$(curl -s -X POST http://localhost:8000/v1/documents/upload \
  -F "file=@sample_docs/cmms_maintenance_orders.xlsx" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Document ID: $DOC_ID"

# 3. 轮询等待 AI 分析完成（状态变为 pending_review）
until [ "$(curl -s http://localhost:8000/v1/documents/$DOC_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")" = "pending_review" ]; do
  echo "Waiting..."; sleep 1
done

# 4. 查看候选关系
curl -s http://localhost:8000/v1/documents/$DOC_ID | python3 -m json.tool

# 5. 批准第一条关系（替换 REL_ID）
curl -X POST http://localhost:8000/v1/documents/$DOC_ID/annotate/REL_ID \
  -H "Content-Type: application/json" \
  -d '{"action": "approve"}'

# 6. 修改置信度后批准
curl -X POST http://localhost:8000/v1/documents/$DOC_ID/annotate/REL_ID \
  -H "Content-Type: application/json" \
  -d '{"action": "modify", "modified_confidence": 0.90}'

# 7. 提交到图谱
curl -X POST http://localhost:8000/v1/documents/$DOC_ID/commit
```

---

## 9. 错误码

| HTTP 状态码 | 错误场景 | 响应示例 |
|------------|---------|---------|
| `400 Bad Request` | 请求体格式错误 | `{"detail": "confidence must be between 0.0 and 1.0"}` |
| `404 Not Found` | 资源不存在 | `{"detail": "Relation rel-xxx not found"}` |
| `422 Unprocessable Entity` | Pydantic 校验失败 | `{"detail": [{"loc": [...], "msg": "..."}]}` |
| `500 Internal Server Error` | 服务器内部错误 | `{"detail": "Internal server error"}` |
| `503 Service Unavailable` | Neo4j/Redis 不可用 | `{"status": "degraded", "neo4j": "error"}` |

---

## 10. 通用 Schema

### KnowledgePhase 枚举（新增）

| 值 | 阶段 | 说明 |
|----|------|------|
| `bootstrap` | 阶段 1 | 公共知识初始化（公开报告/文献/网络） |
| `interview` | 阶段 2 | 专家访谈与关系补录 |
| `pretrain` | 阶段 3 | 企业文档导入与预训练 |
| `runtime` | 阶段 4 | 运行期在线反馈与强化 |

### phase_weight 字段（新增）

| knowledge_phase | 默认值（建议） |
|----------------|---------------|
| `bootstrap` | 0.35 |
| `interview` | 0.90 |
| `pretrain` | 0.70 |
| `runtime` | 1.00 |

约定：
- 该字段范围为 `0.0–1.0`
- 若请求未显式传入，服务端按 `knowledge_phase` 自动回填
- 该字段用于置信度计算排序与可解释性展示，不替代 `confidence` 本身

### SourceType 枚举

| 值 | 说明 |
|----|------|
| `manual_engineer` | 工程师手动录入 |
| `sensor_realtime` | 传感器实时数据 |
| `mes_structured` | MES/ERP 结构化导入 |
| `llm_extracted` | LLM 从文本中抽取 |
| `inference` | 系统推断 |
| `structured_document` | 结构化文档解析（FMEA/CMMS 工单，Sprint 3）|
| `expert_document` | 专家文档 LLM 抽取 + 人工标注（8D 报告/交接班日志，Sprint 3）|

### RelationStatus 枚举

| 值 | 说明 |
|----|------|
| `pending_review` | 待审核（LLM 抽取的关系默认）|
| `active` | 已激活，参与推理 |
| `conflicted` | 存在冲突，暂停推理 |
| `archived` | 已归档，保留历史 |

### ActionStatus 枚举

| 值 | 说明 |
|----|------|
| `pending` | 待处理 |
| `pre_flight_check` | 验证中 |
| `approved` | 验证通过 |
| `rejected` | 已拒绝 |
| `executing` | 执行中 |
| `completed` | 已完成 |
| `failed` | 已失败 |
| `rolled_back` | 已回滚 |

### DecisionPackageStatus 枚举

| 值 | 说明 |
|----|------|
| `draft` | 已生成但尚未进入审核 |
| `pending_review` | 等待主管/工程师确认 |
| `approved` | 方案已通过 |
| `rejected` | 方案被驳回 |
| `shadow_planned` | 动作包已生成，等待上层执行编排 |
| `executed` | 外部系统已执行并回写 |
| `rolled_back` | 已撤销或回退 |

---

## 11. Telemetry（MVP）

最小埋点接收接口，用于验证阶段 2/4 易用性改进的效果（见 `docs/test-plan.md §1.4`）。

### POST /telemetry/events

提交一条埋点事件。

**请求体**：

```json
{
  "event_name": "recommendation_shown",
  "actor_role": "frontline_engineer",
  "actor_id": "operator-zhang",
  "session_id": "sess-001",
  "confidence_trace_id": "conf-trace-...",
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "props": { "engine_used": "rule_engine", "confidence": 0.85 }
}
```

**响应**：

```json
{ "status": "success", "data": { "accepted": true }, "message": "" }
```

### GET /telemetry/events?limit=50

调试用：返回最近 N 条事件（MVP 仅用于开发验证）。
