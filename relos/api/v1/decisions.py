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

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from relos.action.engine import ActionEngine, ActionRecord
from relos.action.repository import ActionRepository
from relos.config import settings
from relos.core.models import (
    ActionBundle,
    DecisionPackage,
    DecisionPackageStatus,
    DecisionReviewRecord,
    RelationObject,
)
from relos.core.repository import RelationRepository
from relos.decision.repository import DecisionRepository
from relos.decision.workflow import DecisionState, get_decision_workflow

router = APIRouter()
logger = structlog.get_logger(__name__)

_action_engine = ActionEngine()
# 内存缓存：加速同请求内查询；持久化层为 Neo4j（解决重启丢失问题）
_action_cache: dict[str, ActionRecord] = {}

# 阶段4真流式：短期会话缓存（MVP 先内存，后续可迁移到 Redis）
_stream_session_cache: dict[str, dict[str, Any]] = {}
_STREAM_SESSION_TTL_SECONDS = 15 * 60  # 15分钟


def _sse_event(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {payload}\n\n"


def _prune_stream_sessions(now: datetime) -> None:
    expired: list[str] = []
    for trace_id, item in _stream_session_cache.items():
        created_at = item.get("created_at")
        if not isinstance(created_at, datetime):
            expired.append(trace_id)
            continue
        if (now - created_at).total_seconds() > _STREAM_SESSION_TTL_SECONDS:
            expired.append(trace_id)
    for trace_id in expired:
        _stream_session_cache.pop(trace_id, None)


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

    # ── 自解释协议（分层解释）────────────────────────────────────
    # 兼容旧前端：新增字段为必填（有默认）也不会影响旧字段读取。
    explanation_summary: str = ""
    evidence_relations: list[dict[str, Any]] = []
    phase_contributions: list[dict[str, Any]] = []
    confidence_trace_id: str = ""


class StreamAnswerRequest(BaseModel):
    confidence_trace_id: str
    question_id: str
    answer: str


class ApiResponse(BaseModel):
    status: str
    data: dict[str, Any] = {}
    message: str = ""


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


class DecisionReviewRequest(BaseModel):
    reviewed_by: str
    selected_plan_id: str
    approved_actions: list[str] = []
    rejected_actions: list[str] = []
    review_comment: str = ""
    approve: bool = True


class PendingDecisionSummary(BaseModel):
    decision_id: str
    incident_id: str
    title: str
    risk_level: str
    recommended_plan_id: str
    requires_human_review: bool
    review_reason: str
    status: str


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

    # 注意：t_start 使用的是带时区的 UTC 时间，elapsed 计算必须保持同一时区语义
    elapsed_ms = (datetime.now(UTC) - t_start).total_seconds() * 1000

    logger.info(
        "alarm_analyzed",
        alarm_id=event.alarm_id,
        engine_path=final_state.get("engine_path", "unknown"),
        confidence=final_state.get("confidence", 0.0),
        processing_time_ms=round(elapsed_ms, 1),
    )

    # ─── 分层解释协议生成（证据/阶段贡献）────────────────────────────
    trace_id = f"conf-trace-{uuid.uuid4().hex}"

    supporting_ids: list[str] = final_state.get("supporting_relation_ids", []) or []
    relations_by_id = {r.id: r for r in relations}

    # 如果规则引擎给出了 supporting_relation_ids，就优先使用；否则退化为选取子图中最高置信度证据
    evidence: list[RelationObject] = [
        relations_by_id[rid]
        for rid in supporting_ids
        if rid in relations_by_id
    ]
    if not evidence:
        evidence = sorted(relations, key=lambda r: r.confidence, reverse=True)[:3]

    evidence_payload: list[dict[str, Any]] = []
    phase_score: dict[str, float] = {}
    for r in evidence:
        phase = str(getattr(r, "knowledge_phase", None) or "")
        weight = float(getattr(r, "phase_weight", 0.0) or 0.0)
        score = float(r.confidence) * weight
        phase_score[phase] = phase_score.get(phase, 0.0) + score

        evidence_payload.append(
            {
                "id": r.id,
                "relation_type": r.relation_type,
                "confidence": r.confidence,
                "provenance": r.provenance.value,
                "knowledge_phase": str(r.knowledge_phase),
                "phase_weight": r.phase_weight,
                "status": r.status.value,
                "provenance_detail": r.provenance_detail,
            }
        )

    total_score = sum(phase_score.values()) or 1.0
    phase_contrib_payload: list[dict[str, Any]] = [
        {
            "knowledge_phase": phase,
            "score": round(score, 6),
            "share": round(score / total_score, 4),
        }
        for phase, score in sorted(phase_score.items(), key=lambda x: x[1], reverse=True)
    ]

    top_phase = phase_contrib_payload[0]["knowledge_phase"] if phase_contrib_payload else "unknown"
    share_pct = int(round(phase_contrib_payload[0]["share"] * 100)) if phase_contrib_payload else 0

    explanation_summary = (
        f"推荐：{final_state.get('recommended_cause','')}；"
        f"置信度 {final_state.get('confidence',0.0):.2f}；"
        f"主要证据阶段：{top_phase}（约 {share_pct}%）"
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

        # 自解释协议字段
        explanation_summary=explanation_summary,
        evidence_relations=evidence_payload,
        phase_contributions=phase_contrib_payload,
        confidence_trace_id=trace_id,
    )


@router.post("/analyze-alarm/stream")
async def analyze_alarm_stream(event: AlarmEvent, request: Request) -> StreamingResponse:
    """
    阶段4真流式：SSE 端点。

    事件序列：summary → evidence → contributions → question → done
    """
    _prune_stream_sessions(datetime.now(UTC))

    async def gen() -> Any:
        result = await analyze_alarm(event, request)

        _stream_session_cache[result.confidence_trace_id] = {
            "created_at": datetime.now(UTC),
            "alarm_id": result.alarm_id,
            "device_id": result.device_id,
            "last_question_id": "q-001",
        }

        yield _sse_event(
            "summary",
            {
                "confidence_trace_id": result.confidence_trace_id,
                "recommended_cause": result.recommended_cause,
                "confidence": result.confidence,
                "engine_used": result.engine_used,
                "requires_human_review": result.requires_human_review,
                "shadow_mode": result.shadow_mode,
                "explanation_summary": result.explanation_summary,
            },
        )

        yield _sse_event(
            "evidence",
            {
                "confidence_trace_id": result.confidence_trace_id,
                "evidence_relations": result.evidence_relations,
                "is_final": True,
            },
        )

        yield _sse_event(
            "contributions",
            {
                "confidence_trace_id": result.confidence_trace_id,
                "phase_contributions": result.phase_contributions,
            },
        )

        yield _sse_event(
            "question",
            {
                "confidence_trace_id": result.confidence_trace_id,
                "question": {
                    "question_id": "q-001",
                    "type": "single_choice",
                    "prompt": "为提高准确率，需要确认一个信息：当前是否处于高温环境（>35°C）？",
                    "options": [
                        {"id": "opt-yes", "label": "是（>35°C）"},
                        {"id": "opt-no", "label": "否（≤35°C）"},
                        {"id": "opt-unknown", "label": "不确定"},
                    ],
                    "required": False,
                },
            },
        )

        yield _sse_event("done", {"confidence_trace_id": result.confidence_trace_id, "ok": True})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/stream-answer", response_model=ApiResponse)
async def stream_answer(body: StreamAnswerRequest) -> ApiResponse:
    """
    阶段4真流式问答：接收用户对 SSE question 的回答。
    MVP：只做短期缓存记录（为后续“根据回答重算/补充证据”预留接口）。
    """
    now = datetime.now(UTC)
    _prune_stream_sessions(now)

    session = _stream_session_cache.get(body.confidence_trace_id)
    if not session:
        return ApiResponse(
            status="error",
            data={"accepted": False},
            message="confidence_trace_id 已过期或不存在，请重新发起分析",
        )

    if body.question_id != session.get("last_question_id"):
        return ApiResponse(
            status="error",
            data={"accepted": False},
            message="question_id 不匹配或已过期",
        )

    session["last_answer"] = {"question_id": body.question_id, "answer": body.answer}
    session["answered_at"] = datetime.now(UTC)

    return ApiResponse(status="success", data={"accepted": True}, message="")


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


@router.get("/pending-review", response_model=list[PendingDecisionSummary])
async def get_pending_review_decisions(request: Request) -> list[PendingDecisionSummary]:
    """获取决策级 HITL 队列，与关系审核队列分离。"""
    repo = DecisionRepository(request.app.state.neo4j_driver)
    packages = await repo.list_pending_review(limit=20)
    return [
        PendingDecisionSummary(
            decision_id=package.decision_id,
            incident_id=package.incident_id,
            title=package.title,
            risk_level=package.risk_level.value,
            recommended_plan_id=package.recommended_plan_id,
            requires_human_review=package.requires_human_review,
            review_reason=package.review_reason,
            status=package.status.value,
        )
        for package in packages
    ]


@router.post("/{decision_id}/review", response_model=DecisionPackage)
async def review_decision_package(
    decision_id: str,
    body: DecisionReviewRequest,
    request: Request,
) -> DecisionPackage:
    repo = DecisionRepository(request.app.state.neo4j_driver)
    package = await repo.get_decision_package_by_id(decision_id)
    if not package:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id} not found")

    new_status = (
        DecisionPackageStatus.APPROVED if body.approve else DecisionPackageStatus.REJECTED
    )
    review_record = DecisionReviewRecord(
        decision_id=decision_id,
        status=new_status,
        reviewed_by=body.reviewed_by,
        review_comment=body.review_comment,
        selected_plan_id=body.selected_plan_id,
        approved_actions=body.approved_actions,
        rejected_actions=body.rejected_actions,
    )
    await repo.save_review(review_record)

    package.recommended_plan_id = body.selected_plan_id
    package.status = new_status
    package.updated_at = datetime.now(UTC)
    if body.approve:
        package.review_reason = body.review_comment or "已完成人工确认，进入 Shadow 动作规划"
    else:
        package.review_reason = body.review_comment or "方案被人工驳回，等待重新分析"
    await repo.save_decision_package(package)

    bundle = await repo.get_action_bundle(decision_id)
    if bundle:
        bundle.status = (
            DecisionPackageStatus.SHADOW_PLANNED if body.approve else DecisionPackageStatus.REJECTED
        )
        bundle.updated_at = datetime.now(UTC)
        await repo.save_action_bundle(bundle)

    return package


@router.get("/{decision_id}/actions", response_model=ActionBundle)
async def get_decision_actions(decision_id: str, request: Request) -> ActionBundle:
    repo = DecisionRepository(request.app.state.neo4j_driver)
    bundle = await repo.get_action_bundle(decision_id)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Action bundle for {decision_id} not found")
    return bundle


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
