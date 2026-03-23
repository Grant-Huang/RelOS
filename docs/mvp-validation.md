# RelOS MVP 验证操作文档

**版本**: Sprint 3 Week 12
**日期**: 2026-03-23
**场景**: 设备故障告警 → 根因推荐（工业设备故障分析）

---

## 一、MVP 实现充分性审查

### 1.1 核心流程覆盖

| 编号 | MVP 核心路径 | 实现状态 | 验证方式 |
|------|-------------|---------|---------|
| F-01 | 告警事件接入 → 关系图查询 | ✅ 已实现 | `POST /v1/decisions/analyze-alarm` |
| F-02 | LangGraph 5 节点工作流 | ✅ 已实现 | `relos/decision/workflow.py` |
| F-03 | 规则引擎路径（高置信度）| ✅ 已实现 | 置信度 ≥ 0.7 → `rule_engine` |
| F-04 | LLM 分析路径（中低置信度）| ✅ 已实现 | 置信度 < 0.7 → `llm_analyze` |
| F-05 | Human-in-the-Loop 触发 | ✅ 已实现 | `force_hitl=true` 或 6 条件触发 |
| F-06 | 无数据兜底路径 | ✅ 已实现 | 空图 → `no_data` 路径 |
| F-07 | 关系置信度衰减 | ✅ 已实现 | `RelationEngine.apply_decay()` |
| F-08 | 人工反馈数据飞轮 | ✅ 已实现 | `POST /v1/relations/{id}/feedback` |
| F-09 | Shadow Mode 执行 | ✅ 已实现 | `SHADOW_MODE=true` 默认开启 |
| F-10 | Excel 批量专家知识导入 | ✅ 已实现 | `POST /v1/expert-init/batch` |

### 1.2 数据模型完整性

| 字段 | 设计规格 | 实现状态 |
|------|---------|---------|
| `confidence: float` | 0.0–1.0，LLM 上限 0.85 | ✅ Pydantic validator 强制 |
| `provenance: SourceType` | 5 种来源类型 | ✅ `StrEnum` 5 值 |
| `half_life_days: int` | 按关系类型配置 | ✅ `HALF_LIFE_CONFIG` 字典 |
| `status` | pending_review → active → conflicted → archived | ✅ 完整状态机 |
| LLM 关系强制 `pending_review` | 不自动变 active | ✅ `apply_llm_constraints` validator |

### 1.3 API 端点覆盖（v1）

| 模块 | 端点 | 方法 | 状态 |
|------|-----|------|-----|
| 关系管理 | `/v1/relations/` | POST | ✅ |
| | `/v1/relations/{id}` | GET | ✅ |
| | `/v1/relations/{id}/feedback` | POST | ✅ |
| | `/v1/relations/pending-review` | GET | ✅ |
| | `/v1/relations/subgraph/{node_id}` | GET | ✅ |
| 决策引擎 | `/v1/decisions/analyze-alarm` | POST | ✅ |
| | `/v1/decisions/execute-action` | POST | ✅ |
| | `/v1/decisions/action/{id}` | GET | ✅ |
| 专家初始化 | `/v1/expert-init/batch` | POST | ✅ |
| 本体管理 | `/v1/ontology/templates` | GET | ✅ |
| | `/v1/ontology/templates/{industry}` | GET | ✅ |
| | `/v1/ontology/templates/{industry}/import` | POST | ✅ |
| 系统 | `/v1/health` | GET | ✅ |
| | `/v1/metrics` | GET | ✅ |

### 1.4 测试覆盖统计

| 测试层 | 数量 | 覆盖率目标 | 状态 |
|--------|------|-----------|-----|
| 单元测试 | **105** 项 | ≥75% | ✅ 全部通过 |
| 集成测试 | **40** 项 (IT-001~IT-020) | 核心路径 | ✅ 已实现 |
| E2E 测试 | **12** 项 (5 个场景) | MVP 全流程 | ✅ 已实现 |
| 性能测试 | Locust 脚本 | P95 < 500ms | ✅ 已实现 |

### 1.5 不在 MVP 范围内（确认排除）

- Action Engine 真实执行（Shadow Mode 只记日志）✅ 已排除
- AgentNexus L3 集成 ✅ 已排除
- 多租户/权限管理（JWT 中间件已预留）✅ 已排除
- 生产级监控告警 ✅ 已排除

---

## 二、环境准备

### 2.1 依赖服务

```bash
# 启动 Neo4j 5.x + Redis 7.4
docker compose up -d

# 验证服务健康
docker compose ps
# 预期：neo4j (healthy), redis (healthy)
```

### 2.2 环境变量配置

创建 `.env` 文件（参考 `.env.example`）：

```env
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Redis
REDIS_URL=redis://localhost:6379

# Anthropic（LLM 分析路径需要）
ANTHROPIC_API_KEY=sk-ant-xxx

# MVP 配置
SHADOW_MODE=true          # 默认：Action Engine 只记日志
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### 2.3 安装依赖

```bash
pip install -e ".[dev]"
# 验证
python -c "import relos; print('✓ relos OK')"
```

### 2.4 注入种子数据

```bash
# 注入设备故障场景测试数据（7 条关系，置信度各异）
python scripts/seed_neo4j.py

# 预期输出：
# 🌱 RelOS 种子数据注入...
# ✓ [0.92] CNC-M1 --DEVICE__TRIGGERS__ALARM--> ALM-001
# ✓ [0.88] CNC-M1 --DEVICE__HAS__COMPONENT--> SPINDLE-1
# ✓ [0.75] OPR-001 --OPERATOR__MAINTAINS__DEVICE--> CNC-M1
# ... (共 7 条)
```

---

## 三、MVP 核心验证步骤

### 步骤 1：启动 API 服务

```bash
uvicorn relos.main:app --reload --port 8000

# 验证启动
curl http://localhost:8000/v1/health
# 预期响应：
# {"status": "ok", "neo4j": "connected", "redis": "connected"}
```

### 步骤 2：验证基础关系 CRUD

```bash
# 创建关系（MES 结构化数据来源）
curl -X POST http://localhost:8000/v1/relations/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "CNC-M2",
    "source_node_type": "Device",
    "target_node_id": "ALM-002",
    "target_node_type": "Alarm",
    "relation_type": "DEVICE__TRIGGERS__ALARM",
    "confidence": 0.82,
    "provenance": "mes_structured",
    "half_life_days": 90
  }'

# 预期：HTTP 201，返回 RelationObject，status="active"

# 查询关系
curl http://localhost:8000/v1/relations/{id}
# 预期：HTTP 200，返回关系详情
```

### 步骤 3：验证 LLM 来源强制 pending_review

```bash
curl -X POST http://localhost:8000/v1/relations/ \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "CNC-M3",
    "source_node_type": "Device",
    "target_node_id": "ALM-003",
    "target_node_type": "Alarm",
    "relation_type": "DEVICE__TRIGGERS__ALARM",
    "confidence": 0.90,
    "provenance": "llm_extracted",
    "half_life_days": 90
  }'

# 预期：
# - status = "pending_review"（强制，不受输入影响）
# - confidence ≤ 0.85（LLM 上限约束）
```

### 步骤 4：核心流程——告警分析（规则引擎路径）

```bash
# 高置信度场景：命中规则引擎
curl -X POST http://localhost:8000/v1/decisions/analyze-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-001",
    "device_id": "CNC-M1",
    "alarm_type": "SPINDLE_OVERHEAT",
    "severity": "high",
    "description": "主轴温度超过阈值 85°C"
  }'

# 预期响应：
# {
#   "alarm_id": "ALM-001",
#   "engine_path": "rule_engine",     ← 高置信度走规则引擎
#   "root_cause": "主轴轴承磨损导致过热",
#   "confidence": 0.88,
#   "recommendations": [...],
#   "requires_human_review": false,
#   "processing_time_ms": < 500        ← 性能目标
# }
```

### 步骤 5：核心流程——告警分析（LLM 分析路径）

```bash
# 新设备，图中无关系（低置信度）
curl -X POST http://localhost:8000/v1/decisions/analyze-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-NEW",
    "device_id": "CNC-NEW",
    "alarm_type": "VIBRATION_ANOMALY",
    "severity": "medium",
    "description": "异常振动，频率 150Hz"
  }'

# 预期响应：
# {
#   "engine_path": "llm_analyze",    ← 低置信度走 LLM
#   "requires_human_review": false,
#   ...
# }
```

### 步骤 6：Human-in-the-Loop 验证

```bash
# 强制触发 HITL
curl -X POST http://localhost:8000/v1/decisions/analyze-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-HITL",
    "device_id": "CNC-M1",
    "alarm_type": "SPINDLE_OVERHEAT",
    "severity": "critical",
    "description": "严重故障",
    "force_hitl": true
  }'

# 预期：engine_path = "hitl"，requires_human_review = true

# 查看待审核队列
curl http://localhost:8000/v1/relations/pending-review
# 预期：返回 LLM 来源的待审核关系列表
```

### 步骤 7：数据飞轮——人工反馈

```bash
# 确认关系（+0.15 置信度，status → active）
curl -X POST http://localhost:8000/v1/relations/{id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedback": "confirm", "operator_id": "ENG-001"}'

# 预期：confidence 增加约 0.15，status = "active"

# 拒绝关系（-0.30 置信度，低于 0.2 → archived）
curl -X POST http://localhost:8000/v1/relations/{id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"feedback": "reject", "operator_id": "ENG-001"}'

# 预期：confidence 降低约 0.30，低于阈值时 status = "archived"
```

### 步骤 8：Action Engine——Shadow Mode 验证

```bash
# 执行建议动作（Shadow Mode 默认开启，只记日志）
curl -X POST http://localhost:8000/v1/decisions/execute-action \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-001",
    "device_id": "CNC-M1",
    "action_type": "NOTIFY_MAINTENANCE",
    "parameters": {"priority": "high"},
    "operator_id": "OPR-001"
  }'

# 预期：
# - status = "completed"
# - shadow_mode = true
# - logs 包含 4+ 条审计记录（PENDING→PRE_FLIGHT→APPROVED→EXECUTING→COMPLETED）

# 查询动作状态
curl http://localhost:8000/v1/decisions/action/{action_id}
# 预期：完整的状态转换审计日志

# 安全控制验证：控制类操作被拒绝
curl -X POST http://localhost:8000/v1/decisions/execute-action \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-001",
    "device_id": "CNC-M1",
    "action_type": "STOP_MACHINE",
    "parameters": {},
    "operator_id": "OPR-001"
  }'
# 预期：status = "rejected"，pre_flight_results.action_type_safe = false
```

### 步骤 9：专家知识批量导入

```bash
# 方式 A：Excel 文件上传
curl -X POST http://localhost:8000/v1/expert-init/batch \
  -F "file=@data/relations_sample.xlsx"

# 方式 B：使用命令行脚本
python scripts/import_excel.py --file data/relations.xlsx

# 预期：导入结果含 success_count, failed_count, errors 列表
```

### 步骤 10：子图查询验证

```bash
# 获取设备周围的关系子图（2 跳）
curl "http://localhost:8000/v1/relations/subgraph/CNC-M1?hops=2"

# 预期：返回 CNC-M1 相关的所有关系（告警、部件、操作员等）
```

---

## 四、自动化测试执行

### 4.1 单元测试（无外部依赖）

```bash
pytest tests/unit -v --tb=short

# 预期：105 passed，0 failed
# 覆盖测试文件：
# - test_api/test_route_order.py        (路由顺序)
# - test_context/test_compiler.py       (Context Compiler)
# - test_core/test_action_engine.py     (Action 状态机)
# - test_core/test_decision_workflow.py (LangGraph 工作流)
# - test_core/test_engine.py            (关系引擎)
# - test_core/test_redis_dedup.py       (Redis 去重)
# - test_ingestion/test_excel_importer.py (Excel 导入)
# - test_ingestion/test_pipeline.py     (摄取管道)
```

### 4.2 集成测试（需要 Neo4j + Redis）

```bash
# 确保 docker compose up -d 已运行
pytest tests/integration -v -m mvp --tb=short

# 预期测试项（IT-001 ~ IT-020）：
# IT-001: POST /relations → 201, 可查询
# IT-002: 同节点对 → 置信度合并（加权滑动平均）
# IT-003: LLM 来源 → 强制 pending_review, ≤0.85
# IT-004: feedback confirm → 置信度+0.15, active
# IT-005: feedback reject 低置信度 → archived
# IT-006: subgraph 返回连接关系
# IT-007: pending-review 路由不被 /{id} 遮蔽
# IT-008: 不存在 ID → 404
# IT-009: 高置信度 → rule_engine 路径
# IT-010: 空图 → no_data 路径
# IT-011: force_hitl → hitl 路径
# IT-012: severity=critical → requires_human_review=True
# IT-013: 合法动作 → completed, shadow_mode=True
# IT-014: 控制动作 → rejected, action_type_safe=False
# IT-015: execute + GET action/{id} → 完整审计日志
# IT-016: rule_engine 路径 processing_time_ms < 500ms
# IT-017: 多次 confirm → 置信度持续增长
# IT-018: 大置信度差 → 冲突检测（关系保留）
# IT-020: 批量导入 5 条 → subgraph 包含全部
```

### 4.3 E2E 测试（需要 Neo4j + Redis）

```bash
pytest tests/e2e -v --tb=short

# 预期测试场景：
# E2E-001: 数据飞轮流程
#   alarm → confirm 反馈 → 置信度增长 → 再分析效果更好
# E2E-002: 冷启动恢复
#   空图 → no_data → 专家初始化 → 第二次有推荐
# E2E-003: HITL 完整流程
#   低置信度触发 HITL → pending-review 可访问
# E2E-004: Action Engine Shadow Mode
#   执行完成 → 4+ 审计日志 → 控制动作被拒绝
# E2E-005: 强制 HITL + 性能
#   force_hitl 绕过推理 → rule_engine < 1000ms
```

### 4.4 代码质量检查

```bash
# Lint（应全部通过，0 error）
ruff check .
# 预期：All checks passed!

# 格式化检查
ruff format --check .
# 预期：0 files would be reformatted

# 类型检查（mypy 部分告警为遗留问题，不阻断）
mypy relos/ --ignore-missing-imports
```

---

## 五、性能基准测试

### 5.1 Locust 压力测试

```bash
# 需要启动 API 服务
uvicorn relos.main:app --port 8000 &

# 运行 Locust（Web UI 模式）
locust -f tests/performance/locustfile.py --host http://localhost:8000

# 访问 http://localhost:8089 配置：
# - 并发用户数：50
# - 用户增加速率：5/秒
# - 运行时长：60 秒
```

### 5.2 性能目标

| 端点 | P95 目标 | 验证方式 |
|------|---------|---------|
| `POST /analyze-alarm`（rule_engine 路径）| < 500ms | IT-016, E2E-005 |
| `POST /analyze-alarm`（llm_analyze 路径）| < 3000ms | Locust |
| `GET /relations/{id}` | < 100ms | Locust |
| `GET /relations/pending-review` | < 200ms | Locust |

---

## 六、验证数据参考

### 6.1 种子数据（`scripts/seed_neo4j.py`）

| 来源节点 | 关系类型 | 目标节点 | 置信度 | 来源 |
|---------|---------|---------|--------|------|
| CNC-M1 | DEVICE__TRIGGERS__ALARM | ALM-001 | 0.92 | mes_structured |
| CNC-M1 | DEVICE__HAS__COMPONENT | SPINDLE-1 | 0.88 | manual_engineer |
| OPR-001 | OPERATOR__MAINTAINS__DEVICE | CNC-M1 | 0.75 | mes_structured |
| SPINDLE-1 | COMPONENT__PART_OF__DEVICE | CNC-M1 | 0.95 | sensor_realtime |
| CNC-M1 | DEVICE__LOCATED_IN__AREA | WORKSHOP-A | 0.80 | mes_structured |
| ALM-001 | ALARM__INDICATES__FAULT | FAULT-001 | 0.70 | llm_extracted |
| FAULT-001 | FAULT__REQUIRES__ACTION | ACT-001 | 0.65 | inference |

**注意**：`llm_extracted` 和 `inference` 来源的关系初始状态为 `pending_review`。

### 6.2 预期置信度衰减参数

| 关系类型 | 半衰期（天）| 30 天后置信度（原始 0.9）|
|---------|------------|----------------------|
| DEVICE__TRIGGERS__ALARM | 90 | ~0.81 |
| OPERATOR__PERFORMS__OPERATION | 30 | ~0.64 |
| DEVICE__HAS__COMPONENT | 365 | ~0.88 |

### 6.3 Alpha 合并系数参考

| 来源类型 | Alpha 权重 | 说明 |
|---------|-----------|------|
| manual_engineer | 0.7 | 工程师输入权重最高 |
| sensor_realtime | 0.6 | 传感器数据次之 |
| mes_structured | 0.5 | MES 结构化中等权重 |
| llm_extracted | 0.3 | LLM 提取权重较低 |
| inference | 0.2 | 推理结果最低权重 |

---

## 七、已知限制（MVP 阶段）

| 限制 | 影响 | 计划解决版本 |
|------|------|------------|
| `SHADOW_MODE=true` 默认，Action Engine 不真实执行 | 无实际设备操作 | Sprint 4 |
| LLM 分析需要 `ANTHROPIC_API_KEY`，无 key 时降级处理 | LLM 路径不可用 | - |
| `pending_review` 关系需人工逐一确认，无批量审核 UI | 效率低 | Sprint 4 |
| 无多租户隔离，所有数据共用 Neo4j 默认数据库 | 单租户 | Sprint 5 |
| Temporal.io 工作流为可选依赖，MVP 不强依赖 | 无持久化工作流 | Sprint 4 |

---

## 八、快速排障

### Q1: `NEO4J_URI` 连接失败

```bash
# 检查 Neo4j 服务
docker compose ps neo4j
docker compose logs neo4j --tail=20

# 验证连接
python -c "
import asyncio
from neo4j import AsyncGraphDatabase
async def test():
    driver = AsyncGraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','password'))
    await driver.verify_connectivity()
    print('✓ Neo4j OK')
    await driver.close()
asyncio.run(test())
"
```

### Q2: `ANTHROPIC_API_KEY` 未设置时 LLM 路径行为

系统会降级处理：分析结果 `engine_path` 仍为 `llm_analyze`，但 `root_cause` 为 "LLM 服务不可用" 错误信息。不会崩溃。

### Q3: `pending_review` 关系未出现在队列

检查关系创建时 `provenance` 是否为 `llm_extracted` 或 `inference`；其他来源默认创建为 `active`。

### Q4: Action Engine 返回 `rejected`

检查 `action_type` 是否在安全白名单内。MVP 允许的操作类型：
- `NOTIFY_MAINTENANCE`（通知维保）
- `CREATE_WORK_ORDER`（创建工单）
- `LOG_ALARM`（记录告警）

被拒绝的操作类型（需工程师手动确认）：
- `STOP_MACHINE`（停机）
- `RESET_SYSTEM`（系统重置）
- 所有 `CONTROL_*` 前缀操作

---

*文档版本：Sprint 3 Week 12 | RelOS MVP v0.1.0*
