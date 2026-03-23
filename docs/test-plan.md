# RelOS 测试计划

**版本**：v1.0  
**日期**：2026 年 3 月

---

## 1. 测试策略总览

### 1.1 测试金字塔

```
           ┌─────────┐
           │  E2E 测试  │  (少量，高价值场景)
           │  (Sprint 3) │
          ┌┴─────────────┴┐
          │  集成测试       │  (重点：API + Neo4j)
          │  (Sprint 3)    │
         ┌┴───────────────┴┐
         │    单元测试        │  (大量，快速，已有 41 个)
         │   (Sprint 1–2)   │
        └─────────────────┘
```

### 1.2 测试目标

| 测试类型 | 目标 | 当前状态 | Sprint 3 目标 |
|---------|------|---------|--------------|
| 单元测试 | 核心算法逻辑正确性 | 41 个，全部通过 | 80 个 |
| 集成测试 | API + 数据库联动 | 0 个 | 20 个 |
| E2E 测试 | 完整用户场景 | 0 个 | 5 个 |
| 性能测试 | 响应时间 + 并发 | 未测量 | 基准建立 |
| 安全测试 | 注入/越权 | 未测试 | Sprint 4 |

### 1.3 覆盖率目标

| 模块 | 目标覆盖率 | 当前状态 |
|------|-----------|---------|
| `core/engine.py` | ≥ 90% | ~85%（估算）|
| `core/models.py` | ≥ 85% | ~80% |
| `context/compiler.py` | ≥ 85% | ~80% |
| `decision/workflow.py` | ≥ 80% | ~75% |
| `action/engine.py` | ≥ 85% | ~80% |
| `api/v1/` | ≥ 70% | ~20%（缺集成测试）|

---

## 2. 现有单元测试（41 个）

### 2.1 `tests/unit/test_core/test_engine.py`（17 个）

| 测试类 | 测试方法 | 测试目标 |
|--------|---------|---------|
| TestMergeConfidence | test_sensor_merge_increases_confidence | 传感器高置信度新观测拉高旧值 |
| | test_llm_merge_is_conservative | LLM alpha=0.2，新观测影响小 |
| | test_conflict_detected_on_large_confidence_gap | 置信度差 > 0.5 触发冲突 |
| | test_no_conflict_on_small_confidence_gap | 差值 ≤ 0.5 不触发冲突 |
| TestApplyDecay | test_fresh_relation_no_decay | 新关系置信度基本不变 |
| | test_half_life_halves_confidence | 90 天后置信度衰减约 50% |
| | test_very_old_relation_hits_floor | 极老关系不低于 0.05 |
| TestApplyHumanFeedback | test_confirm_increases_confidence | 确认 +0.15，状态→active |
| | test_reject_decreases_confidence | 否定 -0.30 |
| | test_reject_low_confidence_archives | 否定后 < 0.2 → archived |
| | test_confirm_caps_at_1 | 置信度不超过 1.0 |
| TestLLMConstraints | test_llm_confidence_capped_at_0_85 | LLM 置信度硬上限 |
| | test_llm_relation_forced_pending | LLM 关系强制 pending_review |

### 2.2 `tests/unit/test_context/test_compiler.py`（6 个）

| 测试类 | 测试方法 | 测试目标 |
|--------|---------|---------|
| TestPruning | test_archived_relations_pruned | 层 1：archived 不进入 Prompt |
| | test_low_confidence_pruned | 层 2：低置信度过滤 |
| | test_max_relations_limit | 层 6：超出 max 截断 |
| | test_dedup_same_node_pair | 层 5：同节点对去重 |
| TestMarkdownOutput | test_output_contains_table | 输出含 Markdown 表格 |
| | test_empty_relations_returns_valid_block | 空输入不报错 |

### 2.3 `tests/unit/test_core/test_action_engine.py`（11 个）

| 测试类 | 测试方法 | 测试目标 |
|--------|---------|---------|
| TestPreFlightChecks | test_valid_action_passes_all_checks | 合法操作通过五步 |
| | test_empty_device_id_fails | 空设备 ID 失败 |
| | test_control_action_blocked | 控制类操作被白名单拦截 |
| | test_too_short_description_fails | 过短描述失败 |
| | test_empty_alarm_id_fails | 无告警来源失败 |
| TestActionEngineStateMachine | test_create_starts_at_pending | 初始状态 PENDING |
| | test_valid_action_reaches_completed_in_shadow_mode | Shadow Mode 完整流转 |
| | test_failed_preflight_reaches_rejected | Pre-flight 失败→REJECTED |
| | test_logs_are_append_only | 日志只追加（4 次转换=4 条日志）|
| | test_execute_requires_approved_status | 只有 APPROVED 可执行 |
| | test_shadow_mode_default_is_true | Shadow Mode 默认 True |

### 2.4 `tests/unit/test_core/test_decision_workflow.py`（11 个，部分）

| 测试类 | 测试方法 | 测试目标 |
|--------|---------|---------|
| TestNodeExtractContext | test_high_confidence_routes_to_rule_engine | ≥ 0.75 → 规则引擎 |
| | test_low_confidence_routes_to_hitl | < 0.5 → HITL |
| | test_mid_confidence_routes_to_llm | 0.5–0.75 → LLM |
| | test_empty_relations_routes_to_none | 无数据 → no_data |
| TestNodeRuleEngine | test_high_confidence_indicates_returns_cause | 高置信度推断根因 |
| | test_no_indicates_relations_fallback_to_llm | 无匹配降级 LLM |
| TestNodeHitl | test_hitl_always_requires_human_review | HITL 必须人工审核 |
| | test_critical_severity_in_reasoning | critical 在推理说明中 |
| TestNodeNoData | test_no_data_suggests_expert_init | 提示专家初始化 |
| TestRouting | test_route_by_engine_path | 四路路由正确分流 |

---

## 3. Sprint 3 集成测试计划

### 3.1 测试基础设施

```bash
# 集成测试需要运行中的 Neo4j + Redis
docker compose up -d neo4j redis

# 运行集成测试
pytest tests/integration -v -m integration
```

**测试夹具（`tests/conftest.py`）**：
```python
@pytest.fixture(scope="session")
async def neo4j_driver():
    """提供测试用 Neo4j 连接，测试后清理数据"""
    driver = AsyncGraphDatabase.driver(TEST_NEO4J_URI, auth=(USER, PASS))
    yield driver
    # 清理测试数据
    async with driver.session() as s:
        await s.run("MATCH (n) WHERE n.id STARTS WITH 'test-' DETACH DELETE n")
    await driver.close()
```

### 3.2 集成测试用例设计（20 个）

#### 关系 API 集成测试（8 个）

| 测试 ID | 测试场景 | 预期结果 |
|---------|---------|---------|
| IT-001 | POST /relations → 新关系写入 Neo4j | 201，可从 Neo4j 查到 |
| IT-002 | POST /relations（相同节点对）→ 置信度合并 | 200，置信度按加权平均更新 |
| IT-003 | POST /relations（LLM 来源）→ 强制 pending | 201，status=pending_review，confidence≤0.85 |
| IT-004 | POST /relations/{id}/feedback（确认）| 200，Neo4j 中置信度 +0.15 |
| IT-005 | POST /relations/{id}/feedback（否定低置信度）| 200，status=archived |
| IT-006 | POST /relations/subgraph | 200，返回 2 跳子图 |
| IT-007 | GET /relations/pending-review | 200，返回所有 pending 关系 |
| IT-008 | GET /relations/{不存在的ID} | 404 |

#### 决策 API 集成测试（8 个）

| 测试 ID | 测试场景 | 预期结果 |
|---------|---------|---------|
| IT-009 | analyze-alarm（图谱有高置信度关系）| 200，engine_used=rule_engine |
| IT-010 | analyze-alarm（图谱为空）| 200，engine_used=no_data，requires_human_review=true |
| IT-011 | analyze-alarm（force_hitl=true）| 200，engine_used=hitl |
| IT-012 | analyze-alarm（severity=critical）| 200，requires_human_review=true |
| IT-013 | execute-action（合法操作）| 200，status=completed，shadow_mode=true |
| IT-014 | execute-action（控制类操作）| 200，status=rejected，Pre-flight 失败 |
| IT-015 | execute-action + GET action/{id} | GET 返回完整审计日志 |
| IT-016 | analyze-alarm 响应时间（规则引擎路径）| processing_time_ms < 500 |

#### 数据飞轮集成测试（4 个）

| 测试 ID | 测试场景 | 预期结果 |
|---------|---------|---------|
| IT-017 | 录入关系 → 确认 5 次 → 再次分析 | 根因置信度提升，engine_path 可能从 llm → rule_engine |
| IT-018 | 录入冲突关系 → 检查状态 | 两条关系均标注 conflicted |
| IT-019 | 关系衰减计算（模拟 90 天后）| 置信度约为初始值 50% |
| IT-020 | 批量导入 50 条关系 → 子图提取 | 子图包含导入关系，置信度正确 |

---

## 4. E2E 测试计划（Sprint 3）

### 4.1 E2E 测试场景（5 个核心场景）

| 场景 ID | 场景名称 | 步骤 | 成功标准 |
|---------|---------|------|---------|
| E2E-001 | **MVP 核心场景：告警→确认** | 注入种子数据 → 发送告警 → 获取推荐 → 提交确认反馈 → 再次发送相同告警 | 第二次推荐置信度高于第一次 |
| E2E-002 | **冷启动场景** | 空图谱 → 发送告警 → 获取 no_data → 专家初始化录入关系 → 再次告警 | 第二次返回实质性推荐 |
| E2E-003 | **HITL 完整流程** | 录入低置信度关系 → 发送告警 → 触发 HITL → 从 pending-review 审批 → 告警再分析 | 审批后置信度提升，推荐改善 |
| E2E-004 | **Action Engine 流程** | 分析告警 → 执行操作（Shadow Mode）→ 查询操作状态 | 状态=completed，审计日志完整 |
| E2E-005 | **冲突场景** | 录入两条冲突关系 → 发送告警 → 触发 HITL | requires_human_review=true，conflict 原因在 reasoning 中 |

### 4.2 E2E 自动化工具

```bash
# 使用 httpx + pytest 实现
# tests/e2e/test_mvp_flow.py

@pytest.mark.e2e
async def test_alarm_to_feedback_cycle(api_client, seed_data):
    """E2E-001：告警→确认→学习完整闭环"""
    # Step 1: 发送告警
    resp = await api_client.post("/v1/decisions/analyze-alarm", json=ALARM_EVENT)
    assert resp.status_code == 200
    result = resp.json()
    initial_confidence = result["confidence"]

    # Step 2: 确认推荐
    rel_id = result["supporting_relation_ids"][0]
    await api_client.post(f"/v1/relations/{rel_id}/feedback",
                          json={"engineer_id": "test-eng", "confirmed": True})

    # Step 3: 再次发送相同告警
    resp2 = await api_client.post("/v1/decisions/analyze-alarm", json=ALARM_EVENT)
    result2 = resp2.json()

    # 验证：置信度提升
    assert result2["confidence"] >= initial_confidence
```

---

## 5. 性能测试计划（Sprint 3）

### 5.1 性能基准目标

| 指标 | 目标 | 测试方法 |
|------|------|---------|
| 规则引擎路径响应时间 | P95 < 500ms | locust 并发测试 |
| LLM 路径响应时间 | P95 < 8s | locust 串行测试 |
| HITL 路径响应时间 | P95 < 100ms | locust 并发测试 |
| 子图提取（1000 条关系）| < 200ms | pytest 基准测试 |
| 并发支持 | 10 个并发告警分析 | locust 并发测试 |

### 5.2 性能测试脚本（`tests/performance/locustfile.py`）

```python
from locust import HttpUser, task, between

class AlarmAnalysisUser(HttpUser):
    wait_time = between(1, 3)

    @task(10)
    def analyze_alarm_rule_engine(self):
        """高置信度场景（走规则引擎）"""
        self.client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": f"PERF-{uuid4()}",
            "device_id": "device-M1",   # 已有丰富关系数据
            "alarm_code": "VIB-001",
            "alarm_description": "振动超限",
            "severity": "high"
        })

    @task(2)
    def get_pending_review(self):
        """HITL 队列查询"""
        self.client.get("/v1/relations/pending-review?limit=20")
```

---

## 6. 测试运行规范

### 6.1 日常开发

```bash
# 只运行单元测试（无外部依赖，秒级完成）
pytest tests/unit -v

# 运行特定模块测试
pytest tests/unit/test_core -v

# 运行并生成覆盖率报告
pytest tests/unit --cov=relos --cov-report=html
```

### 6.2 提交前（Pre-commit Hook）

```bash
# .git/hooks/pre-commit
ruff check relos/           # 代码规范检查
mypy relos/core/            # 类型检查
pytest tests/unit -x -q     # 单元测试（第一个失败即停止）
```

### 6.3 CI/CD（Sprint 4 实现，GitHub Actions）

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5.26-community
        env:
          NEO4J_AUTH: neo4j/test_password
      redis:
        image: redis:7.4-alpine

    steps:
      - name: 单元测试
        run: pytest tests/unit -v --cov=relos

      - name: 集成测试
        run: pytest tests/integration -v -m integration
        env:
          NEO4J_URI: bolt://localhost:7687

      - name: 代码规范
        run: ruff check relos/

      - name: 类型检查
        run: mypy relos/
```

### 6.4 测试命名规范

```
tests/
├── unit/                    # 无外部依赖，纯逻辑测试
│   ├── test_core/
│   │   ├── test_engine.py
│   │   ├── test_action_engine.py
│   │   └── test_decision_workflow.py
│   ├── test_context/
│   │   └── test_compiler.py
│   └── test_ingestion/
│       └── test_pipeline.py  (Sprint 3 新增)
│
├── integration/             # 需要 Neo4j + Redis
│   ├── test_relations_api.py
│   └── test_decisions_api.py
│
├── e2e/                     # 需要完整服务
│   └── test_mvp_flow.py
│
└── performance/
    └── locustfile.py
```

**命名约定**：
- 测试方法：`test_<被测方法>_<场景>_<预期结果>`
- 例：`test_merge_confidence_sensor_source_increases_value`
- 夹具：`make_<对象类型>` 函数用于创建测试数据

---

## 7. 缺陷管理

| 严重程度 | 定义 | 修复时限 |
|---------|------|---------|
| P0（阻断）| 核心功能不可用（告警无法分析）| 24 小时内 |
| P1（严重）| 功能异常（置信度计算错误）| 3 天内 |
| P2（一般）| 功能缺陷（边界情况处理不当）| 下个 Sprint |
| P3（轻微）| 体验问题（错误信息不友好）| 积压处理 |

**缺陷报告模板**：
```
标题：[模块] 简短描述
严重程度：P0/P1/P2/P3
复现步骤：
  1. ...
  2. ...
预期结果：...
实际结果：...
相关测试：tests/unit/test_xxx.py::test_xxx
```
