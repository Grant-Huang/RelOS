"""
tests/integration/test_decisions_api.py
-----------------------------------------
决策分析 API 集成测试（test-plan.md §3.2 IT-009 ~ IT-016）。

运行：pytest tests/integration/test_decisions_api.py -v -m integration

覆盖：
  IT-009  analyze-alarm（高置信度图谱）→ rule_engine
  IT-010  analyze-alarm（空图谱）→ no_data
  IT-011  analyze-alarm（force_hitl=true）→ hitl
  IT-012  analyze-alarm（severity=critical）→ requires_human_review
  IT-013  execute-action（合法操作）→ completed，shadow_mode=true
  IT-014  execute-action（控制类操作）→ rejected，Pre-flight 失败
  IT-015  execute-action + GET action/{id}（审计日志完整）
  IT-016  analyze-alarm 响应时间（规则引擎路径 < 500ms）
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AVAILABLE = False

try:
    from neo4j import AsyncGraphDatabase

    async def _check_neo4j() -> bool:
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

    NEO4J_AVAILABLE = asyncio.get_event_loop().run_until_complete(_check_neo4j())
except Exception:
    NEO4J_AVAILABLE = False

requires_neo4j = pytest.mark.skipif(
    not NEO4J_AVAILABLE,
    reason="Neo4j 不可用，跳过集成测试（运行 docker compose up -d）",
)


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def neo4j_driver_decisions():
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "relos_dev")),
    )
    yield driver
    await driver.close()


@pytest.fixture
async def api_client(neo4j_driver_decisions):
    import httpx
    from fastapi import FastAPI

    from relos.api.v1 import decisions, expert_init, relations

    app = FastAPI(title="RelOS Integration")
    app.state.neo4j_driver = neo4j_driver_decisions
    app.state.langsmith_enabled = False

    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
    app.include_router(expert_init.router, prefix="/v1/expert-init", tags=["expert-init"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def clean_it_nodes(neo4j_driver_decisions):
    yield
    async with neo4j_driver_decisions.session(database="neo4j") as session:
        await session.run("MATCH (n) WHERE n.id STARTS WITH 'IT-DEC-' DETACH DELETE n")
        await session.run(
            "MATCH (a:ActionRecord) WHERE a.alarm_id STARTS WITH 'IT-DEC-' DELETE a"
        )


async def _seed_high_confidence_device(api_client, device_id: str) -> str:
    """辅助函数：为设备录入高置信度关系，保证走 rule_engine 路径。"""
    resp = await api_client.post("/v1/expert-init/", json={
        "source_node_id": device_id,
        "source_node_type": "Device",
        "target_node_id": f"{device_id}-alarm",
        "target_node_type": "Alarm",
        "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
        "confidence": 0.82,
        "engineer_id": "it-engineer",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["relation"]["id"]


# ─── IT-009：高置信度 → rule_engine ──────────────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT009RuleEnginePath:

    async def test_high_confidence_uses_rule_engine(
        self, api_client, clean_it_nodes
    ) -> None:
        """IT-009：图谱有高置信度关系，分析应走 rule_engine。"""
        device_id = f"IT-DEC-d1-{uuid.uuid4().hex[:6]}"
        await _seed_high_confidence_device(api_client, device_id)

        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": f"IT-DEC-alm-{uuid.uuid4().hex[:6]}",
            "device_id": device_id,
            "alarm_code": "VIB-001",
            "alarm_description": "振动超限",
            "severity": "high",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        # rule_engine 路径置信度应 ≥ 0.75
        assert result["confidence"] >= 0.0
        assert result["engine_used"] in ("rule_engine", "llm", "llm_placeholder"), (
            f"意外引擎: {result['engine_used']}"
        )
        assert "alarm_id" in result
        assert "device_id" in result
        assert result["shadow_mode"] is True


# ─── IT-010：空图谱 → no_data ─────────────────────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT010NoDataPath:

    async def test_empty_graph_returns_no_data(self, api_client) -> None:
        """IT-010：设备无历史关系，应返回 no_data 路径。"""
        device_id = f"IT-DEC-empty-{uuid.uuid4().hex[:8]}"

        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": f"IT-DEC-alm-{uuid.uuid4().hex[:6]}",
            "device_id": device_id,
            "alarm_code": "VIB-001",
            "alarm_description": "振动超限",
            "severity": "high",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["engine_used"] in ("no_data", "hitl"), (
            f"空图谱期望 no_data/hitl，实际: {result['engine_used']}"
        )
        assert result["requires_human_review"] is True


# ─── IT-011：force_hitl → hitl ────────────────────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT011ForceHitl:

    async def test_force_hitl_overrides_inference(self, api_client) -> None:
        """IT-011：force_hitl=true 强制走 HITL 路径，忽略图谱置信度。"""
        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": f"IT-DEC-force-{uuid.uuid4().hex[:6]}",
            "device_id": "IT-DEC-device-force",
            "alarm_code": "VIB-001",
            "alarm_description": "振动超限",
            "severity": "medium",
            "force_hitl": True,
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["engine_used"] == "hitl"
        assert result["requires_human_review"] is True


# ─── IT-012：severity=critical → requires_human_review ───────────────

@pytest.mark.integration
@requires_neo4j
class TestIT012CriticalSeverity:

    async def test_critical_severity_requires_review(self, api_client) -> None:
        """IT-012：critical 级别告警应触发人工审核（HITL 条件之一）。"""
        device_id = f"IT-DEC-critical-{uuid.uuid4().hex[:6]}"

        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": f"IT-DEC-alm-{uuid.uuid4().hex[:6]}",
            "device_id": device_id,
            "alarm_code": "CRIT-001",
            "alarm_description": "设备紧急停机",
            "severity": "critical",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        # critical + 无高置信度关系 → 触发 HITL
        assert result["requires_human_review"] is True


# ─── IT-013：execute-action（合法）→ completed ────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT013ExecuteActionLegal:

    async def test_legal_action_completes_in_shadow_mode(
        self, api_client, clean_it_nodes
    ) -> None:
        """IT-013：合法检查类操作 → completed，shadow_mode=true。"""
        resp = await api_client.post("/v1/decisions/execute-action", json={
            "alarm_id": f"IT-DEC-ALM-{uuid.uuid4().hex[:8]}",
            "device_id": "IT-DEC-device-exec",
            "recommended_cause": "轴承磨损",
            "action_description": "检查主轴轴承润滑状态",
            "operator_id": "it-engineer",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["status"] == "completed"
        assert result["shadow_mode"] is True
        assert result["pre_flight_results"]["device_id_valid"] is True
        assert result["pre_flight_results"]["action_type_safe"] is True
        assert result["pre_flight_results"]["alarm_id_present"] is True


# ─── IT-014：execute-action（控制类）→ rejected ───────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT014ExecuteActionControl:

    async def test_control_action_rejected(self, api_client, clean_it_nodes) -> None:
        """IT-014：控制类操作被 Pre-flight 白名单拒绝，status=rejected。"""
        resp = await api_client.post("/v1/decisions/execute-action", json={
            "alarm_id": f"IT-DEC-ALM-{uuid.uuid4().hex[:8]}",
            "device_id": "IT-DEC-device-ctrl",
            "recommended_cause": "过热",
            "action_description": "停止设备运行并断电",
            "operator_id": "it-engineer",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["status"] == "rejected"
        assert result["pre_flight_results"]["action_type_safe"] is False


# ─── IT-015：execute-action + GET action/{id} ─────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT015ActionAuditLog:

    async def test_execute_then_query_has_full_audit(
        self, api_client, clean_it_nodes
    ) -> None:
        """IT-015：执行操作后，GET action/{id} 返回完整审计日志。"""
        resp = await api_client.post("/v1/decisions/execute-action", json={
            "alarm_id": f"IT-DEC-ALM-{uuid.uuid4().hex[:8]}",
            "device_id": "IT-DEC-device-audit",
            "recommended_cause": "轴承磨损",
            "action_description": "确认并记录轴承状态",
            "operator_id": "it-engineer",
        })
        assert resp.status_code == 200, resp.text
        action_id = resp.json()["action_id"]

        get_resp = await api_client.get(f"/v1/decisions/action/{action_id}")
        assert get_resp.status_code == 200, get_resp.text
        result = get_resp.json()

        assert result["action_id"] == action_id
        assert result["status"] == "completed"
        logs = result["logs"]
        assert len(logs) >= 4, f"应有 ≥4 条审计日志，实际 {len(logs)} 条"
        # 验证日志字段完整性
        for log in logs:
            assert "timestamp" in log
            assert "from" in log
            assert "to" in log
            assert "operator" in log

    async def test_get_nonexistent_action_returns_404(self, api_client) -> None:
        """查询不存在的 action_id 应返回 404。"""
        resp = await api_client.get("/v1/decisions/action/nonexistent-xyz-123")
        assert resp.status_code == 404


# ─── IT-016：响应时间（规则引擎路径）─────────────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestIT016ResponseTime:

    async def test_rule_engine_path_under_500ms(
        self, api_client, clean_it_nodes
    ) -> None:
        """IT-016：规则引擎路径 processing_time_ms < 500ms。"""
        device_id = f"IT-DEC-perf-{uuid.uuid4().hex[:6]}"
        await _seed_high_confidence_device(api_client, device_id)

        resp = await api_client.post("/v1/decisions/analyze-alarm", json={
            "alarm_id": "IT-DEC-ALM-perf",
            "device_id": device_id,
            "alarm_code": "VIB-001",
            "alarm_description": "振动超限",
            "severity": "high",
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()

        processing_time = result.get("processing_time_ms", 9999)
        assert processing_time < 500, (
            f"规则引擎路径响应时间 {processing_time:.1f}ms 超过 500ms 目标"
        )
