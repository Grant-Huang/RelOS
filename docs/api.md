# RelOS API 接口规范

**版本**：v1.0  
**Base URL**：`http://localhost:8000/v1`  
**格式**：JSON  
**认证**：MVP 阶段无认证；Sprint 4 实现 JWT Bearer Token

---

**Sprint 3 新增端点**：`/v1/expert-init`（专家初始化）、`/v1/metrics`（图谱统计）、`/v1/scenarios`（演示场景）

## 目录

1. [健康检查](#1-健康检查)
2. [关系管理](#2-关系管理)
3. [决策分析](#3-决策分析)
4. [专家初始化（Sprint 3）](#4-专家初始化-sprint-3)
5. [图谱统计（Sprint 3）](#5-图谱统计-sprint-3)
6. [演示场景（Sprint 3 扩展）](#6-演示场景-sprint-3-扩展)
7. [错误码](#7-错误码)
8. [通用 Schema](#8-通用-schema)

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
  "processing_time_ms": 87.3
}
```

| 字段 | 说明 |
|------|------|
| `engine_used` | `rule_engine` / `llm` / `hitl` / `no_data` / `llm_placeholder` |
| `requires_human_review` | `true` 时前端应显示 HITL 提示 |
| `shadow_mode` | `true` 时操作未实际执行 |
| `processing_time_ms` | 端到端处理时间 |

---

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

---

## 4. 专家初始化（Sprint 3）

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
  "provenance_detail": "维修工单 WO-2026-001",
  "engineer_id": "zhang-engineer",
  "half_life_days": 365,
  "properties": {"frequency": 5, "severity": "high"}
}
```

**响应** `201 Created`：
```json
{
  "relation": { ...RelationObject },
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

## 5. 图谱统计（Sprint 3）

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

## 6. 错误码

| HTTP 状态码 | 错误场景 | 响应示例 |
|------------|---------|---------|
| `400 Bad Request` | 请求体格式错误 | `{"detail": "confidence must be between 0.0 and 1.0"}` |
| `404 Not Found` | 资源不存在 | `{"detail": "Relation rel-xxx not found"}` |
| `422 Unprocessable Entity` | Pydantic 校验失败 | `{"detail": [{"loc": [...], "msg": "..."}]}` |
| `500 Internal Server Error` | 服务器内部错误 | `{"detail": "Internal server error"}` |
| `503 Service Unavailable` | Neo4j/Redis 不可用 | `{"status": "degraded", "neo4j": "error"}` |

---

## 7. 通用 Schema

### SourceType 枚举

| 值 | 说明 |
|----|------|
| `manual_engineer` | 工程师手动录入 |
| `sensor_realtime` | 传感器实时数据 |
| `mes_structured` | MES/ERP 结构化导入 |
| `llm_extracted` | LLM 从文本中抽取 |
| `inference` | 系统推断 |

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

---

## 6. 演示场景（Sprint 3 扩展）

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
