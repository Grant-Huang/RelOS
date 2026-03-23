"""
tests/e2e/test_alarm_flow.py
-----------------------------
E2E 测试：告警→根因分析完整流程（test-plan.md §4）。

标记：@pytest.mark.integration（需要 Neo4j）
运行：pytest tests/e2e/ -v -m integration

覆盖场景：
  E2E-001  MVP 核心场景：告警→确认→学习（数据飞轮验证）
  E2E-002  冷启动场景：空图谱→专家录入→再次告警
  E2E-003  HITL 完整流程：低置信度→触发 HITL→审批→改善
  E2E-004  Action Engine 流程：分析→执行→查询状态（含持久化验证）
  E2E-005  force_hitl 和响应时间验证
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

# ─── Neo4j 可用性检查（同 test_full_pipeline.py 模式）──────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AVAILABLE = False

try:
    from neo4j import AsyncGraphDatabase

    async def _check() -> bool:
        try:
            drv = AsyncGraphDatabase.driver(
                NEO4J_URI,
                auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "relos_dev")),
            )
            await drv.verify_connectivity()
            await drv.close()
            return True
        except Exception:
            return False

    NEO4J_AVAILABLE = asyncio.get_event_loop().run_until_complete(_check())
except Exception:
    NEO4J_AVAILABLE = False

requires_neo4j = pytest.mark.skipif(
    not NEO4J_AVAILABLE,
    reason="Neo4j 不可用，跳过 E2E 测试（运行 docker compose up -d）",
)

pytestmark = pytest.mark.integration


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def neo4j_driver_e2e():
    """模块级 Neo4j driver（E2E 专用）。"""
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "relos_dev")),
    )
    yield driver
    asyncio.get_event_loop().run_until_complete(driver.close())


@pytest.fixture
async def api_client(neo4j_driver_e2e):
    """
    带真实 Neo4j 的 FastAPI AsyncClient。
    不启动完整 lifespan，直接注入 driver。
    """
    import httpx
    from fastapi import FastAPI

    from relos.api.v1 import decisions, expert_init, health, metrics, relations

    app = FastAPI(title="RelOS E2E Test")
    app.state.neo4j_driver = neo4j_driver_e2e
    app.state.langsmith_enabled = False

    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
    app.include_router(expert_init.router, prefix="/v1/expert-init", tags=["expert-init"])
    app.include_router(metrics.router, prefix="/v1/metrics", tags=["metrics"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def clean_e2e_nodes(neo4j_driver_e2e):
    """测试前后清理所有 E2E 测试节点（前缀 E2E-）。"""
    yield
    async with neo4j_driver_e2e.session(database="neo4j") as session:
        await session.run(
            "MATCH (n) WHERE n.id STARTS WITH 'E2E-' DETACH DELETE n"
        )
        await session.run(
            "MATCH (a:ActionRecord) WHERE a.alarm_id STARTS WITH 'E2E-' DELETE a"
        )


def _alarm(device_id: str, alarm_id: str | None = None, severity: str = "high") -> dict:
    return {
        "alarm_id": alarm_id or f"E2E-ALM-{uuid.uuid4().hex[:8]}",
        "device_id": device_id,
        "alarm_code": "VIB-001",
        "alarm_description": "主轴振动超限 18.3mm/s",
        "severity": severity,
    }


# ─── E2E-001：MVP 核心场景（数据飞轮）────────────────────────────────

@requires_neo4j
class TestE2E001DataFlywheel:
    """
    E2E-001：告警→根因推荐→确认→再次告警→置信度提升。
    验证数据飞轮的核心闭环（test-plan.md E2E-001）。
    """

    async def test_alarm_confirm_then_reanalyze(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """确认根因后，第二次分析的置信度不低于第一次。"""
        device_id = "E2E-device-001"
        alarm_node_id = "E2E-alarm-VIB-001"

        # Step 1: 专家录入高置信度关系（rule_engine 路径要求 ≥ 0.75）
        resp = await api_client.post("/v1/expert-init/", json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": alarm_node_id,
            "target_node_type": "Alarm",
            "relation_type": "DEVICE__TRIGGERS__ALARM",
            "confidence": 0.78,
            "engineer_id": "e2e-engineer",
        })
        assert resp.status_code == 201, resp.text
        rel_id = resp.json()["relation"]["id"]

        # Step 2: 首次告警分析
        alarm_payload = _alarm(device_id)
        resp1 = await api_client.post("/v1/decisions/analyze-alarm", json=alarm_payload)
        assert resp1.status_code == 200, resp1.text
        result1 = resp1.json()
        initial_confidence = result1["confidence"]
        assert initial_confidence > 0, "应返回有效置信度"

        # Step 3: 工程师确认推荐
        await api_client.post(f"/v1/relations/{rel_id}/feedback", json={
            "engineer_id": "e2e-engineer",
            "confirmed": True,
        })

        # Step 4: 再次分析同一告警
        resp2 = await api_client.post("/v1/decisions/analyze-alarm", json=alarm_payload)
        assert resp2.status_code == 200, resp2.text
        result2 = resp2.json()

        # 验证：置信度不低于初次（数据飞轮效果）
        assert result2["confidence"] >= initial_confidence, (
            f"数据飞轮失效：确认后置信度 {result2['confidence']} < 初始 {initial_confidence}"
        )

    async def test_reject_decreases_confidence(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """工程师否定后，关系置信度应下降。"""
        device_id = "E2E-device-002"

        resp = await api_client.post("/v1/expert-init/", json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": "E2E-alarm-002",
            "target_node_type": "Alarm",
            "relation_type": "DEVICE__TRIGGERS__ALARM",
            "confidence": 0.80,
            "engineer_id": "e2e-engineer",
        })
        assert resp.status_code == 201
        rel_id = resp.json()["relation"]["id"]
        original_confidence = resp.json()["relation"]["confidence"]

        # 否定
        await api_client.post(f"/v1/relations/{rel_id}/feedback", json={
            "engineer_id": "e2e-engineer",
            "confirmed": False,
        })

        # 验证置信度下降
        get_resp = await api_client.get(f"/v1/relations/{rel_id}")
        assert get_resp.status_code == 200
        updated = get_resp.json()
        assert updated["confidence"] < original_confidence, "否定后置信度应下降"


# ─── E2E-002：冷启动场景────────────────────────────────────────────────

@requires_neo4j
class TestE2E002ColdStart:
    """
    E2E-002：空图谱→发送告警→获取 no_data→专家初始化→再次告警。
    验证专家初始化能解除冷启动困境（test-plan.md E2E-002）。
    """

    async def test_cold_start_then_expert_init(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """首次告警返回 no_data，专家录入后再次告警有实质推荐。"""
        device_id = f"E2E-cold-{uuid.uuid4().hex[:6]}"

        # Step 1: 空图谱中发送告警
        resp1 = await api_client.post("/v1/decisions/analyze-alarm", json=_alarm(device_id))
        assert resp1.status_code == 200, resp1.text
        result1 = resp1.json()
        assert result1["engine_used"] in ("no_data", "hitl"), (
            f"空图谱应返回 no_data 或 hitl，实际: {result1['engine_used']}"
        )
        assert result1["requires_human_review"] is True

        # Step 2: 专家录入关系
        resp_init = await api_client.post("/v1/expert-init/", json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": "E2E-alarm-cold",
            "target_node_type": "Alarm",
            "relation_type": "DEVICE__TRIGGERS__ALARM",
            "confidence": 0.82,
            "engineer_id": "e2e-engineer",
        })
        assert resp_init.status_code == 201

        # Step 3: 再次告警
        resp2 = await api_client.post("/v1/decisions/analyze-alarm", json=_alarm(device_id))
        assert resp2.status_code == 200, resp2.text
        result2 = resp2.json()
        assert result2["engine_used"] != "no_data", (
            "专家录入后不应再返回 no_data"
        )
        assert result2["confidence"] > 0, "应有实质性根因推荐"


# ─── E2E-003：HITL 完整流程────────────────────────────────────────────

@requires_neo4j
class TestE2E003HitlFlow:
    """
    E2E-003：低置信度→触发 HITL→从 pending-review 审批。
    验证 HITL 队列的完整工作流（test-plan.md E2E-003）。
    """

    async def test_low_confidence_triggers_hitl(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """低置信度关系应触发 HITL，requires_human_review=true。"""
        device_id = f"E2E-hitl-{uuid.uuid4().hex[:6]}"

        # 录入低置信度 LLM 关系
        await api_client.post("/v1/relations/", json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": "E2E-alarm-hitl",
            "target_node_type": "Alarm",
            "relation_type": "DEVICE__TRIGGERS__ALARM",
            "confidence": 0.35,
            "provenance": "llm_extracted",
            "status": "pending_review",
        })

        resp = await api_client.post("/v1/decisions/analyze-alarm", json=_alarm(device_id))
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["requires_human_review"] is True

    async def test_pending_review_queue_accessible(self, api_client) -> None:
        """pending-review 端点应可访问并返回正确格式。"""
        resp = await api_client.get("/v1/relations/pending-review?limit=10")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)


# ─── E2E-004：Action Engine 流程──────────────────────────────────────

@requires_neo4j
class TestE2E004ActionEngine:
    """
    E2E-004：分析告警→执行操作（Shadow Mode）→查询状态（含持久化验证）。
    验证 Action Engine 完整状态机（test-plan.md E2E-004）。
    """

    async def test_execute_action_shadow_mode_and_query(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """Shadow Mode 下操作完成，审计日志完整，可通过 ID 查询持久化记录。"""
        alarm_id = f"E2E-ALM-{uuid.uuid4().hex[:8]}"

        resp = await api_client.post("/v1/decisions/execute-action", json={
            "alarm_id": alarm_id,
            "device_id": "E2E-device-action",
            "recommended_cause": "轴承磨损",
            "action_description": "检查主轴轴承磨损情况",
            "operator_id": "e2e-engineer",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()

        assert result["status"] == "completed"
        assert result["shadow_mode"] is True
        assert len(result["logs"]) >= 4, "Shadow Mode 应有 ≥4 次状态转换日志"
        assert result["pre_flight_results"]["device_id_valid"] is True

        action_id = result["action_id"]

        # 查询持久化的 Action 记录
        get_resp = await api_client.get(f"/v1/decisions/action/{action_id}")
        assert get_resp.status_code == 200, get_resp.text
        get_result = get_resp.json()
        assert get_result["status"] == "completed"
        assert get_result["action_id"] == action_id

    async def test_control_action_rejected_by_preflight(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """控制类操作应被 Pre-flight 拦截，状态 rejected。"""
        resp = await api_client.post("/v1/decisions/execute-action", json={
            "alarm_id": f"E2E-ALM-{uuid.uuid4().hex[:8]}",
            "device_id": "E2E-device-ctrl",
            "recommended_cause": "传感器故障",
            "action_description": "重启设备电源",
            "operator_id": "e2e-engineer",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["status"] == "rejected"
        assert result["pre_flight_results"]["action_type_safe"] is False

    async def test_action_not_found_returns_404(self, api_client) -> None:
        """查询不存在的 Action ID 应返回 404。"""
        resp = await api_client.get("/v1/decisions/action/nonexistent-id-xyz")
        assert resp.status_code == 404


# ─── E2E-005：force_hitl 和性能验证────────────────────────────────────

@requires_neo4j
class TestE2E005ForceHitlAndPerf:
    """
    E2E-005：force_hitl 参数验证 + 响应时间基准（test-plan.md E2E-005 & IT-016）。
    """

    async def test_force_hitl_skips_inference(self, api_client) -> None:
        """force_hitl=true 应强制跳过推理，直接返回 HITL。"""
        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            **_alarm("E2E-device-force"),
            "force_hitl": True,
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["requires_human_review"] is True
        assert result["engine_used"] == "hitl"

    async def test_rule_engine_path_response_time(
        self, api_client, clean_e2e_nodes
    ) -> None:
        """IT-016：规则引擎路径响应时间 < 1000ms（E2E 环境宽松标准）。"""
        device_id = f"E2E-perf-{uuid.uuid4().hex[:6]}"

        await api_client.post("/v1/expert-init/", json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": "E2E-alarm-perf",
            "target_node_type": "Alarm",
            "relation_type": "DEVICE__TRIGGERS__ALARM",
            "confidence": 0.85,
            "engineer_id": "e2e-perf",
        })

        resp = await api_client.post("/v1/decisions/analyze-alarm", json=_alarm(device_id))
        assert resp.status_code == 200, resp.text
        result = resp.json()

        processing_time = result.get("processing_time_ms", 0)
        assert processing_time < 1000, (
            f"响应时间 {processing_time:.1f}ms 超过 1000ms 阈值"
        )
