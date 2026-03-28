"""
relos/api/v1/interview.py
-------------------------
阶段2（调研/专家访谈）微卡片向导接口。

目标：用“类流式”的微任务卡片降低专家录入负担，支持 confirm/reject/unsure 与新关系创建。

MVP 约束：
- 会话状态先用内存保存（重启会丢失）；后续可迁移 Redis。
- 卡片内容优先复用 Neo4j 中的 pending_review 关系，避免重复实现抽取逻辑。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from relos.core.engine import RelationEngine
from relos.core.models import Node, RelationObject, RelationStatus, SourceType
from relos.core.repository import RelationRepository

router = APIRouter()
logger = structlog.get_logger(__name__)

_engine = RelationEngine()

_interview_sessions: dict[str, dict[str, Any]] = {}
_INTERVIEW_TTL_SECONDS = 60 * 60  # 1小时


def _prune_sessions(now: datetime) -> None:
    expired: list[str] = []
    for sid, item in _interview_sessions.items():
        created_at = item.get("created_at")
        if not isinstance(created_at, datetime):
            expired.append(sid)
            continue
        if (now - created_at).total_seconds() > _INTERVIEW_TTL_SECONDS:
            expired.append(sid)
    for sid in expired:
        _interview_sessions.pop(sid, None)


class ApiResponse(BaseModel):
    status: str
    data: dict[str, Any] = {}
    message: str = ""


class CreateSessionRequest(BaseModel):
    engineer_id: str = Field(description="访谈工程师/专家 ID（用于审计）")
    device_id: str | None = Field(default=None, description="可选：聚焦某台设备的子图/待审队列")
    limit: int = Field(default=20, ge=1, le=100, description="本会话最多推送多少张确认卡")


class CreateSessionResponse(BaseModel):
    session_id: str
    total_cards: int


CardType = Literal["relation_confirm", "relation_create", "done"]


class RelationConfirmCard(BaseModel):
    card_id: str
    type: Literal["relation_confirm"] = "relation_confirm"
    relation: RelationObject
    hint: str = "请确认这条关系是否正确（可选择不确定）"


class RelationCreateCard(BaseModel):
    card_id: str
    type: Literal["relation_create"] = "relation_create"
    template: str = "当 ___ 告警时，通常先检查 ___"
    defaults: dict[str, Any] = {
        "knowledge_phase": "interview",
        "phase_weight": 0.90,
        "provenance": "manual_engineer",
        "status": "active",
    }


class DoneCard(BaseModel):
    card_id: str
    type: Literal["done"] = "done"
    message: str = "本次访谈卡片已完成"


class NextCardResponse(BaseModel):
    session_id: str
    card: RelationConfirmCard | RelationCreateCard | DoneCard


SubmitAction = Literal["confirm", "reject", "unsure", "create_relation", "skip"]


class SubmitCardRequest(BaseModel):
    card_id: str
    action: SubmitAction
    relation_id: str | None = None
    create_relation: RelationObject | None = None


class SubmitCardResponse(BaseModel):
    session_id: str
    accepted: bool
    saved_relation_id: str | None = None
    message: str = ""


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    """
    创建一个访谈会话。

    MVP：默认从 pending_review 队列拉取候选关系，生成“关系确认卡”队列。
    """
    _prune_sessions(datetime.now(UTC))

    repo = RelationRepository(request.app.state.neo4j_driver)
    pending = await repo.get_pending_review_relations(limit=body.limit)

    session_id = f"ivs-{uuid.uuid4().hex}"
    _interview_sessions[session_id] = {
        "created_at": datetime.now(UTC),
        "engineer_id": body.engineer_id,
        "queue_relation_ids": [r.id for r in pending],
        "cursor": 0,
        "device_id": body.device_id,
    }

    logger.info(
        "interview_session_created",
        session_id=session_id,
        engineer_id=body.engineer_id,
        total=len(pending),
    )

    return CreateSessionResponse(session_id=session_id, total_cards=len(pending))


@router.get("/sessions/{session_id}/next-card", response_model=NextCardResponse)
async def next_card(session_id: str, request: Request) -> NextCardResponse:
    """获取下一张微卡片。"""
    _prune_sessions(datetime.now(UTC))

    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found or expired")

    queue: list[str] = session.get("queue_relation_ids", [])
    cursor: int = int(session.get("cursor", 0))

    if cursor >= len(queue):
        return NextCardResponse(session_id=session_id, card=DoneCard(card_id="done"))

    relation_id = queue[cursor]
    repo = RelationRepository(request.app.state.neo4j_driver)
    relation = await repo.get_relation_by_id(relation_id)
    if not relation:
        # 关系可能被其他人处理掉：跳过
        session["cursor"] = cursor + 1
        return await next_card(session_id, request)

    card = RelationConfirmCard(
        card_id=f"card-{session_id}-{cursor}",
        relation=relation,
    )
    return NextCardResponse(session_id=session_id, card=card)


@router.post("/sessions/{session_id}/submit-card", response_model=SubmitCardResponse)
async def submit_card(session_id: str, body: SubmitCardRequest, request: Request) -> SubmitCardResponse:
    """
    提交当前卡片的结果。

    - confirm/reject：等价于对 RelationObject 做人工反馈（运行期强化字段会在 engine 中写入）
    - unsure：保留 pending_review，但记录为弱反馈（运行期）以便审计/后续复查
    - create_relation：创建一条人工录入关系（interview 阶段），直接 active
    """
    _prune_sessions(datetime.now(UTC))

    session = _interview_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found or expired")

    engineer_id: str = session.get("engineer_id", "")
    if not engineer_id:
        raise HTTPException(status_code=500, detail="session missing engineer_id")

    repo = RelationRepository(request.app.state.neo4j_driver)

    saved_relation_id: str | None = None

    if body.action in ("confirm", "reject", "unsure"):
        if not body.relation_id:
            raise HTTPException(status_code=422, detail="relation_id is required for this action")
        relation = await repo.get_relation_by_id(body.relation_id)
        if not relation:
            raise HTTPException(status_code=404, detail="relation not found")

        if body.action == "unsure":
            updated = relation.model_copy(
                update={
                    "status": RelationStatus.PENDING_REVIEW,
                    "updated_at": datetime.now(UTC),
                    "extracted_by": f"human:{engineer_id}",
                    "properties": {
                        **relation.properties,
                        "last_feedback_type": "unsure",
                        "last_feedback_engineer_id": engineer_id,
                    },
                }
            )
        else:
            updated = _engine.apply_human_feedback(
                relation=relation,
                confirmed=(body.action == "confirm"),
                engineer_id=engineer_id,
            )

        saved = await repo.upsert_relation(updated)
        saved_relation_id = saved.id

    elif body.action == "create_relation":
        if body.create_relation is None:
            raise HTTPException(status_code=422, detail="create_relation payload is required")

        incoming = body.create_relation
        # 强制“访谈阶段”语义：人工来源、active、extracted_by=human:*
        relation = incoming.model_copy(
            update={
                "provenance": SourceType.MANUAL_ENGINEER,
                "status": RelationStatus.ACTIVE,
                "extracted_by": f"human:{engineer_id}",
                "provenance_detail": incoming.provenance_detail or "访谈录入",
            }
        )

        # 确保节点存在（关系写入前置条件）
        await repo.upsert_node(
            Node(id=relation.source_node_id, node_type=relation.source_node_type, name=relation.source_node_id)
        )
        await repo.upsert_node(
            Node(id=relation.target_node_id, node_type=relation.target_node_type, name=relation.target_node_id)
        )

        saved = await repo.upsert_relation(relation)
        saved_relation_id = saved.id

    elif body.action == "skip":
        pass
    else:
        raise HTTPException(status_code=422, detail="unknown action")

    # 游标前进（无论本次是否真正保存）
    session["cursor"] = int(session.get("cursor", 0)) + 1

    return SubmitCardResponse(
        session_id=session_id,
        accepted=True,
        saved_relation_id=saved_relation_id,
        message="ok",
    )

