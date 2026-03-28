"""
tests/integration/test_interview_microcards_api.py
--------------------------------------------------
阶段2：微卡片会话 API 集成测试。
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
async def neo4j_driver_interview():
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "relos_dev")),
    )
    yield driver
    await driver.close()


@pytest_asyncio.fixture
async def api_client(neo4j_driver_interview):
    import httpx
    from fastapi import FastAPI

    from relos.api.v1 import interview, relations

    app = FastAPI(title="RelOS Interview Integration")
    app.state.neo4j_driver = neo4j_driver_interview
    app.state.langsmith_enabled = False

    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(interview.router, prefix="/v1/interview", tags=["interview"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def _create_pending_relation(api_client, device_id: str) -> str:
    rel_id = f"rel-it-{uuid.uuid4().hex}"
    resp = await api_client.post(
        "/v1/relations/",
        json={
            "id": rel_id,
            "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
            "source_node_id": device_id,
            "source_node_type": "Device",
            "target_node_id": f"{device_id}-bearing",
            "target_node_type": "Component",
            "confidence": 0.6,
            "provenance": "llm_extracted",
            "provenance_detail": "从维修记录抽取",
            "extracted_by": "llm:mock",
            "half_life_days": 365,
            "status": "pending_review",
            "properties": {"context": "测试"},
        },
    )
    assert resp.status_code == 201, resp.text
    return rel_id


@pytest.mark.integration
@requires_neo4j
class TestInterviewMicrocards:
    async def test_create_next_submit_confirm(self, api_client) -> None:
        device_id = f"DEV-INT-{uuid.uuid4().hex[:6]}"
        rel_id = await _create_pending_relation(api_client, device_id)

        resp = await api_client.post("/v1/interview/sessions", json={"engineer_id": "eng-1", "limit": 5})
        assert resp.status_code == 201, resp.text
        session_id = resp.json()["session_id"]

        resp = await api_client.get(f"/v1/interview/sessions/{session_id}/next-card")
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["card"]["type"] == "relation_confirm"
        assert payload["card"]["relation"]["id"] == rel_id

        resp = await api_client.post(
            f"/v1/interview/sessions/{session_id}/submit-card",
            json={"card_id": payload["card"]["card_id"], "action": "confirm", "relation_id": rel_id},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["saved_relation_id"] == rel_id

