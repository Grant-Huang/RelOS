# RelOS API 接口规范

**版本**：v1.0  
**Base URL**：`http://localhost:8000/v1`  
**格式**：JSON  
**认证**：MVP 阶段无认证；Sprint 4 实现 JWT Bearer Token

---

**Sprint 3 新增端点**：`/v1/expert-init`（专家初始化）、`/v1/metrics`（图谱统计）

## 目录

1. [健康检查](#1-健康检查)
2. [关系管理](#2-关系管理)
3. [决策分析](#3-决策分析)
4. [专家初始化（Sprint 3）](#4-专家初始化-sprint-3)
5. [图谱统计（Sprint 3）](#5-图谱统计-sprint-3)
6. [错误码](#6-错误码)
7. [通用 Schema](#7-通用-schema)

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
