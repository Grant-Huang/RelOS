"""
tests/integration/test_decisions_stream_api.py
----------------------------------------------
阶段4真流式（SSE）端点集成测试。

覆盖：
  - analyze-alarm/stream 返回 text/event-stream
  - 至少包含 summary 与 done 事件
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


@pytest_asyncio.fixture(scope="function")
async def neo4j_driver_stream():
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "relos_dev")),
    )
    yield driver
    await driver.close()


@pytest_asyncio.fixture
async def api_client(neo4j_driver_stream):
    import httpx
    from fastapi import FastAPI

    from relos.api.v1 import decisions, expert_init, relations

    app = FastAPI(title="RelOS Stream Integration")
    app.state.neo4j_driver = neo4j_driver_stream
    app.state.langsmith_enabled = False

    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
    app.include_router(expert_init.router, prefix="/v1/expert-init", tags=["expert-init"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def _seed_high_confidence_device(api_client, device_id: str) -> None:
    resp = await api_client.post(
        "/v1/expert-init/",
        json={
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": f"{device_id}-alarm",
            "target_node_type": "Alarm",
            "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
            "confidence": 0.82,
            "engineer_id": "it-engineer",
        },
    )
    assert resp.status_code == 201, resp.text


@pytest.mark.integration
@requires_neo4j
class TestAnalyzeAlarmStream:
    async def test_stream_contains_summary_and_done(self, api_client) -> None:
        device_id = f"IT-STREAM-d1-{uuid.uuid4().hex[:6]}"
        await _seed_high_confidence_device(api_client, device_id)

        async with api_client.stream(
            "POST",
            "/v1/decisions/analyze-alarm/stream",
            json={
                "alarm_id": f"IT-STREAM-alm-{uuid.uuid4().hex[:6]}",
                "device_id": device_id,
                "alarm_code": "VIB-001",
                "alarm_description": "振动超限",
                "severity": "high",
            },
        ) as resp:
            assert resp.status_code == 200
            ctype = resp.headers.get("content-type", "")
            assert "text/event-stream" in ctype

            text = await resp.aread()
            body = text.decode("utf-8", errors="ignore")
            assert "event: summary" in body
            assert "event: done" in body

