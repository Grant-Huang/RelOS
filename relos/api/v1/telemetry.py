"""
relos/api/v1/telemetry.py
-------------------------
最小埋点接收端点（MVP）。

目的：
- 让阶段2/4的易用性改进可测量（见 docs/test-plan.md §1.4）
- 为后续灰度/A/B/回滚提供数据基础

约束：
- MVP 阶段内存存储（重启丢失）；生产应迁移到 Redis/Kafka/ClickHouse 等。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import uuid

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()
logger = structlog.get_logger(__name__)

_events: list[dict[str, Any]] = []
_MAX_EVENTS = 5000


class ApiResponse(BaseModel):
    status: str
    data: dict[str, Any] = {}
    message: str = ""


class TelemetryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    actor_role: str = "frontline_engineer"
    actor_id: str = "anonymous"
    factory_id: str = ""
    session_id: str = ""

    event_name: str
    confidence_trace_id: str | None = None
    alarm_id: str | None = None
    device_id: str | None = None

    props: dict[str, Any] = Field(default_factory=dict)


@router.post("/events", response_model=ApiResponse)
async def ingest_event(evt: TelemetryEvent) -> ApiResponse:
    _events.append(evt.model_dump())
    if len(_events) > _MAX_EVENTS:
        del _events[: len(_events) - _MAX_EVENTS]

    logger.info(
        "telemetry_event",
        event_name=evt.event_name,
        actor_role=evt.actor_role,
        session_id=evt.session_id,
        confidence_trace_id=evt.confidence_trace_id,
    )

    return ApiResponse(status="success", data={"accepted": True}, message="")


@router.get("/events", response_model=list[dict[str, Any]])
async def list_events(limit: int = 50) -> list[dict[str, Any]]:
    """调试用：返回最近 N 条事件（MVP 仅用于开发验证）。"""
    limit = max(1, min(200, limit))
    return list(reversed(_events[-limit:]))

