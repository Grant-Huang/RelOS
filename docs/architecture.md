# RelOS 系统架构设计文档

**版本**：v1.0  
**日期**：2026 年 3 月

---

## 目录

1. [架构总览](#1-架构总览)
2. [三层系统边界](#2-三层系统边界)
3. [五大模块详细设计](#3-五大模块详细设计)
4. [核心流程：告警→根因分析](#4-核心流程告警根因分析)
5. [数据流架构](#5-数据流架构)
6. [技术选型决策](#6-技术选型决策)
7. [部署架构](#7-部署架构)
8. [安全与合规设计](#8-安全与合规设计)
9. [演进路径](#9-演进路径)

---

## 1. 架构总览

RelOS 采用**分层 + 模块化**架构，遵循单一职责原则。每个模块有明确的输入/输出边界，通过异步 API 通信。

```
┌──────────────────────────────────────────────────────────────────┐
│                     Nexus AI Platform                            │
│                                                                  │
│   L3  ┌─────────────────────────────────────────────────────┐   │
│       │  AgentNexus  自然语言界面 / 多 Agent 协同             │   │
│       └──────────────────┬──────────────────────────────────┘   │
│                          │  Context Block (Markdown)             │
│   L2  ┌──────────────────▼──────────────────────────────────┐   │
│       │  RelOS  ★  关系操作系统                               │   │
│       │                                                      │   │
│       │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │   │
│       │  │Ingestion │→ │  Core    │→ │    Context       │   │   │
│       │  │ Layer    │  │ Engine   │  │    Compiler      │   │   │
│       │  └──────────┘  └────┬─────┘  └────────┬─────────┘   │   │
│       │                     │                  │              │   │
│       │               ┌─────▼─────────────────▼──────────┐  │   │
│       │               │      Decision Workflow            │  │   │
│       │               │  rule → llm → hitl → no_data     │  │   │
│       │               └─────────────────┬────────────────┘  │   │
│       │                                 │                    │   │
│       │               ┌─────────────────▼────────────────┐  │   │
│       │               │      Action Engine               │  │   │
│       │               │  Shadow Mode State Machine       │  │   │
│       │               └──────────────────────────────────┘  │   │
│       │                                                      │   │
│       │         ┌────────────┐  ┌───────────────┐           │   │
│       │         │  Neo4j 5.x │  │  Redis Cache  │           │   │
│       │         │  图数据库  │  │  任务队列     │           │   │
│       │         └────────────┘  └───────────────┘           │   │
│       └──────────────────────────────────────────────────────┘   │
│                          │  REST API / Events                    │
│   L1  ┌──────────────────▼──────────────────────────────────┐   │
│       │  Nexus Ops  设备 / IoT / 工单 / MES 执行层           │   │
│       └─────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 三层系统边界

### 2.1 层间边界规则（不可违反）

| 规则 | 说明 | 违反后果 |
|------|------|---------|
| **RelOS 不执行操作** | 所有生产操作通过 Action Engine Shadow Mode 记录，不直接操控设备 | 安全事故风险 |
| **RelOS 不直接对话** | 自然语言接口属于 AgentNexus，RelOS 只输出结构化 ContextBlock | 职责混乱 |
| **关系不删除** | 过期关系标注为 archived，冲突关系标注为 conflicted，完整历史保留 | 数据飞轮失效 |
| **LLM 结果待审** | LLM 抽取的关系 confidence 上限 0.85，强制 pending_review | 系统过度信任 AI |

### 2.2 L2 ↔ L3 接口（RelOS → AgentNexus）

**输出**：`ContextBlock` — 结构化 Markdown 文本块

```markdown
## 工厂关系上下文（RelOS）
**分析对象节点**: `device-M1`
**当前查询**: 告警码: VIB-001 | 主轴振动超限

### 关系列表
| 关系类型 | 起始节点 | 目标节点 | 置信度 | 来源 |
|---------|---------|---------|--------|------|
| `ALARM__INDICATES__COMPONENT_FAILURE` | `alarm-VIB-001` | `component-bearing-M1` | 0.70 ████░ | manual_engineer |
```

### 2.3 L2 ↔ L1 接口（Nexus Ops → RelOS）

**输入**：`AlarmEvent` — 告警事件 JSON

```json
{
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "alarm_code": "VIB-001",
  "alarm_description": "主轴振动超限 18.3mm/s",
  "severity": "high",
  "timestamp": "2026-03-22T10:30:00Z"
}
```

---

## 3. 五大模块详细设计

### 3.1 Ingestion Layer（关系接入层）

**职责**：将所有来源的原始数据标准化为 `RelationObject`。

**输入来源**：

| 来源 | 数据格式 | 触发方式 | 置信度区间 |
|------|---------|---------|-----------|
| 工程师手动输入 | API JSON | 用户操作 | 0.90–1.00 |
| 传感器实时数据 | IoT 事件流 | 告警触发 | 0.80–0.95 |
| MES 结构化导入 | Excel / API | 批处理 | 0.75–0.90 |
| LLM 文本抽取 | 非结构化文本 | NLP Pipeline | 0.50–0.85（硬上限）|
| 系统推断 | 内部计算 | 图推理 | 0.40–0.75 |

**核心组件**：

```
IngestionPipeline
  ├── validate_and_normalize()  → 置信度区间检查 + LLM 强制 pending
  └── AlarmRelationExtractor    → 从告警事件提取关系三元组
```

### 3.2 Relation Core Engine（关系核心引擎）

**职责**：关系合并、置信度衰减、冲突检测、人工反馈处理。

**合并算法（加权滑动平均）**：
```
new_confidence = (1 - α) × old_confidence + α × incoming_confidence

α 值（按来源类型）：
  manual_engineer: 0.30  （稳定，新观测权重低）
  sensor_realtime: 0.50  （实时，新观测权重高）
  mes_structured:  0.40
  llm_extracted:   0.20  （不确定，保守更新）
  inference:       0.15
```

**衰减算法（指数衰减）**：
```
confidence(t) = c0 × 0.5^(elapsed_days / half_life_days)

半衰期配置（天）：
  DEVICE__TRIGGERS__ALARM:       90
  OPERATOR__PERFORMS__OPERATION: 30
  COMPONENT__PART_OF__DEVICE:    365
  ALARM__CORRELATES__ALARM:      60
  DEFAULT:                        90
```

**人工反馈**：
```
确认：confidence = min(1.0, confidence + 0.15)，状态 → active
否定：confidence = max(0.0, confidence - 0.30)
      confidence < 0.2 → 状态 = archived（保留历史）
```

### 3.3 Context Engine（上下文引擎）

**职责**：子图提取 → Token 预算管理 → Prompt 编译。

**六层剪枝流程**：

```
输入：N 条关系
  ↓
层 1：过滤 archived 状态
  ↓
层 2：过滤 confidence < min_confidence (0.3)
  ↓
层 3：优先保留与中心节点直接关联的关系（权重 × 2）
  ↓
层 4：按 confidence 降序排列
  ↓
层 5：相同节点对只保留最高 confidence 关系（去重）
  ↓
层 6：截断超出 max_relations (20) 的部分
  ↓
输出：ContextBlock（Markdown 表格 + Token 估算）
```

### 3.4 Decision Engine（决策引擎）

**职责**：基于图上下文，选择最优决策路径，输出根因推荐。

**LangGraph 工作流**：

```
[extract_context]
    ↓ route by avg_confidence
    ├── ≥ 0.75 → [rule_engine] → 直接推断 → END
    │                ↓ (no match)
    │           → [llm_analyze]
    ├── 0.5–0.75 → [llm_analyze] → Claude API → END
    ├── < 0.5   → [hitl] → 触发人工队列 → END
    └── 无数据  → [no_data] → 提示专家初始化 → END
```

**路由决策逻辑**：

| 子图平均置信度 | 决策引擎 | LLM Token 消耗 | 响应时间 |
|-------------|---------|--------------|---------|
| ≥ 0.75 | 规则引擎 | 0 | < 100ms |
| 0.5–0.75 | LLM 融合 | ~500–1000 | 3–8s |
| < 0.5 | HITL | 0 | < 50ms |
| 无关系 | no_data | 0 | < 50ms |

### 3.5 Action Engine（执行引擎）

**职责**：将决策推荐转化为可审计的操作记录，管理执行生命周期。

**八状态机**：

```
PENDING
  ↓ start_pre_flight()
PRE_FLIGHT_CHECK
  ↓ (passed)              ↓ (failed)
APPROVED               REJECTED
  ↓ execute()
EXECUTING
  ↓ (success)           ↓ (failure)
COMPLETED              FAILED
                         ↓ rollback()
                      ROLLED_BACK
```

**Pre-flight Check 五步**：

| 步骤 | 检查内容 | 失败处理 |
|------|---------|---------|
| 1 | 设备 ID 格式合法性 | REJECTED |
| 2 | 操作描述长度（5–500 字符）| REJECTED |
| 3 | 告警 ID 存在性 | REJECTED |
| 4 | 操作类型白名单（MVP：仅检查类）| REJECTED |
| 5 | 重复操作检查（24 小时内）| REJECTED |

---

## 4. 核心流程：告警→根因分析

```
工程师/系统
    │
    │  POST /v1/decisions/analyze-alarm
    │  {alarm_id, device_id, alarm_code, ...}
    ▼
┌────────────────────────────────────────────────────┐
│  decisions.py (API Layer)                          │
│  1. 调用 RelationRepository.get_subgraph()         │
│  2. 构建 DecisionState                             │
│  3. 调用 LangGraph workflow.ainvoke()              │
└────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────┐
│  node_extract_context                              │
│  1. 调用 ContextCompiler.compile() 编译子图        │
│  2. 计算加权平均置信度                             │
│  3. 决定 engine_path                              │
└────────────────────────────────────────────────────┘
    │
    ▼ (route)
    │
    ├──[≥0.75]──→ node_rule_engine
    │               筛选 INDICATES 关系
    │               返回最高置信度根因
    │
    ├──[0.5~0.75]─→ node_llm_analyze
    │               调用 Claude API
    │               system: 角色 + 关系上下文 Markdown
    │               user: 告警码 + 描述
    │               解析 JSON 响应
    │
    ├──[<0.5]───→ node_hitl
    │               生成 HITL 触发原因
    │               加入 pending-review 队列
    │
    └──[空]─────→ node_no_data
                    提示专家初始化

    │
    ▼
RootCauseRecommendation
{
  recommended_cause: "轴承磨损（component-bearing-M1）",
  confidence: 0.70,
  reasoning: "规则引擎基于 2 条高置信度关系推断...",
  engine_used: "rule_engine",
  requires_human_review: false,
  shadow_mode: true
}
```

---

## 5. 数据流架构

```
外部数据源
    │
    ├── Sensor/SCADA → AlarmRelationExtractor → RelationObject
    ├── MES 历史数据 → Excel Import Pipeline  → RelationObject
    ├── 工程师录入   → API POST /v1/relations → RelationObject
    └── LLM 抽取    → Ingestion Pipeline     → RelationObject (pending)
                                                    │
                                                    ▼
                                          Relation Core Engine
                                          ┌─────────────────────┐
                                          │  Neo4j Graph Store  │
                                          │  节点：Device,Alarm, │
                                          │        Operator...  │
                                          │  边：RelationObject  │
                                          │      + confidence   │
                                          │      + provenance   │
                                          │      + half_life    │
                                          └─────────────────────┘
                                                    │
                                    ┌───────────────┤
                                    │               │
                                    ▼               ▼
                             Decision API     Context API
                             （根因分析）   （子图提取）
                                    │               │
                                    ▼               ▼
                            Action Engine    AgentNexus
                            （Shadow Mode）  （LLM 对话）
```

---

## 6. 技术选型决策

### 6.1 为什么用 Neo4j 而不是向量数据库？

工厂知识的核心价值是**关系**，不是语义相似度：

- 图遍历可以精确回答："设备 M1 通过哪些路径导致告警 A？"
- 向量数据库做不到多跳路径推理
- Neo4j APOC 库的 `subgraphAll` 支持高效子图提取

### 6.2 为什么用 LangGraph 而不是 LangChain？

- LangGraph 支持有状态的**循环图**，可表达"推理→人工确认→继续推理"
- HITL 中间状态持久化需要 LangGraph 的 state management
- LangChain LCEL 是线性管道，不支持条件路由和状态回溯

### 6.3 为什么用 Temporal.io 而不是 Airflow / Celery？

| | Airflow | Celery | Temporal |
|--|---------|--------|---------|
| 工业合规（审计日志）| 弱 | 无 | ✅ 完整 |
| 长时工作流 | 批处理 DAG | 不支持 | ✅ 原生 |
| 故障重试 | 手动配置 | 基础 | ✅ 内置 |
| 状态可见性 | 弱 | 无 | ✅ 完整 |

### 6.4 为什么用 FastAPI 而不是 Django / Flask？

- 原生异步（`async/await`），适合高并发的告警分析场景
- Pydantic v2 集成，Schema 校验零额外代码
- 自动生成 OpenAPI 文档（`/docs`）

---

## 7. 部署架构

### 7.1 开发环境（docker-compose）

```yaml
services:
  neo4j:   Neo4j 5.26 Community + APOC 插件
  redis:   Redis 7.4 Alpine（缓存 + 队列）
  api:     RelOS API（热重载，源码挂载）
```

### 7.2 生产环境（Sprint 4 目标）

```
┌─────────────────────────────────────────────┐
│                Load Balancer                 │
└─────────────────┬───────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
 RelOS API    RelOS API    RelOS API
 (Pod 1)      (Pod 2)      (Pod 3)
    │             │             │
    └─────────────┼─────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼                           ▼
Neo4j Cluster               Redis Cluster
(Causal Cluster 3节点)      (Sentinel 模式)
```

### 7.3 私有化部署（制造客户主流场景）

```bash
# 单机部署（适合中小工厂）
docker compose -f docker-compose.prod.yml up -d

# 注意：制造客户大多不使用公有云，优先支持私有化
```

---

## 8. 安全与合规设计

### 8.1 操作日志不可变

Action Engine 的每次状态转换追加 `ActionLog`，不允许修改或删除：
```python
action.logs.append(log_entry)  # 只追加
# 没有 action.logs[i] = ... 的操作
```

### 8.2 LLM 约束

- LLM 抽取关系的置信度硬上限 0.85（`model_validator` 双重保证）
- LLM 关系强制进入 `pending_review`，不自动生效
- LLM 每次调用记录 token 消耗（LangSmith 追踪，Sprint 3 实现）

### 8.3 API 安全（Sprint 4 实现）

- JWT 认证（工厂员工身份验证）
- 操作级别权限控制（工程师 vs 只读）
- API Key 通过环境变量注入，不在代码中出现

### 8.4 数据隔离（Sprint 4 实现）

- 多租户：工厂级数据隔离（Neo4j 数据库级别隔离）
- PII 处理：操作员 ID 哈希化存储

---

## 9. 演进路径

### Sprint 3 架构扩展

```
新增：
  ├── Excel Import Pipeline（批量关系导入）
  ├── /v1/expert-init 端点（专家初始化 API）
  ├── Temporal.io 客户端（Action Engine 生产执行）
  └── LangSmith 追踪中间件
```

### Sprint 4 架构扩展

```
新增：
  ├── 多租户中间件（JWT + 工厂 ID 路由）
  ├── 行业本体模板服务（汽车/3C/化工）
  └── 私有化部署包（K8s Helm Chart）
```

### Sprint 5 架构扩展

```
新增：
  ├── 图谱可视化前端（React + D3.js）
  ├── AgentNexus 集成接口（WebSocket）
  └── 第三方 MES 适配器库
```
