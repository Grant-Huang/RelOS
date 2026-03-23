"""
relos/api/v1/decisions.py
-------------------------
决策引擎端点（Sprint 2：LangGraph 工作流真实接入）。

端点：
  POST /v1/decisions/analyze-alarm   → 根因分析（主流程）
  POST /v1/decisions/execute-action  → 触发 Action Engine（Shadow Mode）
  GET  /v1/decisions/action/{id}     → 查询操作记录状态
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from relos.action.engine import ActionEngine, ActionRecord
from relos.action.repository import ActionRepository
from relos.config import settings
from relos.core.models import RelationObject
from relos.core.repository import RelationRepository
from relos.decision.workflow import DecisionState, get_decision_workflow

router = APIRouter()
logger = structlog.get_logger(__name__)

_action_engine = ActionEngine()
# 内存缓存：加速同请求内查询；持久化层为 Neo4j（解决重启丢失问题）
_action_cache: dict[str, ActionRecord] = {}


class AlarmEvent(BaseModel):
    alarm_id: str
    device_id: str
    alarm_code: str
    alarm_description: str
    severity: str = "medium"
    timestamp: str = ""
    force_hitl: bool = False


class RootCauseRecommendation(BaseModel):
    alarm_id: str
    device_id: str
    recommended_cause: str
    confidence: float
    reasoning: str
    supporting_relation_ids: list[str]
    engine_used: str
    requires_human_review: bool
    shadow_mode: bool
    context_relations_count: int = 0
    processing_time_ms: float = 0.0


class ExecuteActionRequest(BaseModel):
    alarm_id: str
    device_id: str
    recommended_cause: str
    action_description: str
    operator_id: str


class ActionStatusResponse(BaseModel):
    action_id: str
    status: str
    shadow_mode: bool
    logs: list[dict[str, Any]]
    pre_flight_results: dict[str, Any]


@router.post("/analyze-alarm", response_model=RootCauseRecommendation)
async def analyze_alarm(event: AlarmEvent, request: Request) -> RootCauseRecommendation:
    """核心端点：告警 → LangGraph 工作流 → 根因推荐。"""
    t_start = datetime.now(UTC)

    repo = RelationRepository(request.app.state.neo4j_driver)
    relations: list[RelationObject] = await repo.get_subgraph(
        center_node_id=event.device_id,
        max_hops=2,
        min_confidence=0.3,
    )

    initial_state: DecisionState = {
        "alarm_id": event.alarm_id,
        "device_id": event.device_id,
        "alarm_code": event.alarm_code,
        "alarm_description": event.alarm_description,
        "severity": event.severity,
        "relations": relations,
        "context_block": None,
        "avg_confidence": 0.0,
        "engine_path": "hitl" if event.force_hitl else "none",
        "_rule_engine_no_match": False,
        "recommended_cause": "",
        "confidence": 0.0,
        "reasoning": "",
        "supporting_relation_ids": [],
        "requires_human_review": False,
        "error": None,
    }

    workflow = get_decision_workflow()
    final_state: DecisionState = await workflow.ainvoke(initial_state)

    elapsed_ms = (datetime.utcnow() - t_start).total_seconds() * 1000

    logger.info(
        "alarm_analyzed",
        alarm_id=event.alarm_id,
        engine_path=final_state.get("engine_path", "unknown"),
        confidence=final_state.get("confidence", 0.0),
        processing_time_ms=round(elapsed_ms, 1),
    )

    return RootCauseRecommendation(
        alarm_id=event.alarm_id,
        device_id=event.device_id,
        recommended_cause=final_state.get("recommended_cause", "未能分析"),
        confidence=final_state.get("confidence", 0.0),
        reasoning=final_state.get("reasoning", ""),
        supporting_relation_ids=final_state.get("supporting_relation_ids", []),
        engine_used=final_state.get("engine_path", "none"),
        requires_human_review=final_state.get("requires_human_review", True),
        shadow_mode=settings.SHADOW_MODE,
        context_relations_count=len(relations),
        processing_time_ms=round(elapsed_ms, 1),
    )


@router.post("/execute-action", response_model=ActionStatusResponse)
async def execute_action(body: ExecuteActionRequest, request: Request) -> ActionStatusResponse:
    """触发 Action Engine（Shadow Mode：只记录，不实际执行）。"""
    action = _action_engine.create(
        alarm_id=body.alarm_id,
        device_id=body.device_id,
        recommended_cause=body.recommended_cause,
        action_description=body.action_description,
        shadow_mode=settings.SHADOW_MODE,
    )
    action, _ = _action_engine.start_pre_flight(action, body.operator_id)
    if action.status.value == "approved":
        action = _action_engine.execute(action, body.operator_id)

    # 持久化到 Neo4j，同时写入内存缓存
    action_repo = ActionRepository(request.app.state.neo4j_driver)
    await action_repo.save(action)
    _action_cache[action.id] = action

    return _build_action_response(action)


@router.get("/action/{action_id}", response_model=ActionStatusResponse)
async def get_action_status(action_id: str, request: Request) -> ActionStatusResponse:
    """查询操作记录状态（先查内存缓存，再查 Neo4j）。"""
    action = _action_cache.get(action_id)
    if not action:
        # 内存缓存未命中（服务重启后），从 Neo4j 恢复
        action_repo = ActionRepository(request.app.state.neo4j_driver)
        action = await action_repo.get_by_id(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    return _build_action_response(action)


def _build_action_response(action: ActionRecord) -> ActionStatusResponse:
    return ActionStatusResponse(
        action_id=action.id,
        status=action.status.value,
        shadow_mode=action.shadow_mode,
        logs=[
            {
                "timestamp": log.timestamp.isoformat(),
                "from": log.from_status.value,
                "to": log.to_status.value,
                "operator": log.operator_id,
                "reason": log.reason,
            }
            for log in action.logs
        ],
        pre_flight_results=action.pre_flight_results,
    )
