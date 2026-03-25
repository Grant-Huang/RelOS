"""
tests/unit/test_telemetry_api.py
--------------------------------
最小埋点 API 的单元测试（不依赖外部服务）。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from relos.api.v1 import telemetry


def test_post_telemetry_event_success() -> None:
    app = FastAPI()
    app.include_router(telemetry.router, prefix="/v1/telemetry")
    client = TestClient(app)

    resp = client.post(
        "/v1/telemetry/events",
        json={
            "event_name": "recommendation_shown",
            "actor_role": "frontline_engineer",
            "actor_id": "op-1",
            "session_id": "sess-1",
            "confidence_trace_id": "conf-trace-x",
            "props": {"confidence": 0.8},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["accepted"] is True

