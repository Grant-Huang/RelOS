"""
relos/api/v1/relations.py
-------------------------
关系 CRUD 和人工反馈端点。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from relos.core.engine import RelationEngine
from relos.core.models import RelationObject
from relos.core.repository import RelationRepository

router = APIRouter()
_engine = RelationEngine()


# ─── 请求/响应 Schema ─────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    engineer_id: str
    confirmed: bool


class SubgraphRequest(BaseModel):
    center_node_id: str
    max_hops: int = 2
    min_confidence: float = 0.3


# ─── 端点 ─────────────────────────────────────────────────────────

@router.post("/", response_model=RelationObject, status_code=201)
async def create_relation(
    relation: RelationObject,
    request: Request,
) -> RelationObject:
    """
    插入新关系。
    LLM 抽取的关系自动降级为 pending_review（由模型 validator 保证）。
    """
    repo = RelationRepository(request.app.state.neo4j_driver)

    # 检查是否已存在相同关系
    existing = await _find_existing(repo, relation)
    if existing:
        # 执行置信度合并
        merge_result = _engine.merge_confidence(existing, relation)
        updated = existing.model_copy(
            update={
                "confidence": merge_result.new_confidence,
                "conflict_with": (
                    existing.conflict_with + [relation.id]
                    if merge_result.conflict_detected
                    else existing.conflict_with
                ),
            }
        )
        return await repo.upsert_relation(updated)

    return await repo.upsert_relation(relation)


@router.get("/{relation_id}", response_model=RelationObject)
async def get_relation(relation_id: str, request: Request) -> RelationObject:
    """按 ID 获取关系。"""
    repo = RelationRepository(request.app.state.neo4j_driver)
    relation = await repo.get_relation_by_id(relation_id)
    if not relation:
        raise HTTPException(status_code=404, detail=f"Relation {relation_id} not found")
    return relation


@router.post("/{relation_id}/feedback", response_model=RelationObject)
async def submit_feedback(
    relation_id: str,
    feedback: FeedbackRequest,
    request: Request,
) -> RelationObject:
    """
    提交人工反馈（确认/否定关系）。
    这是数据飞轮的核心触发点——每次反馈都精确更新置信度。
    """
    repo = RelationRepository(request.app.state.neo4j_driver)
    relation = await repo.get_relation_by_id(relation_id)
    if not relation:
        raise HTTPException(status_code=404, detail=f"Relation {relation_id} not found")

    updated = _engine.apply_human_feedback(
        relation=relation,
        confirmed=feedback.confirmed,
        engineer_id=feedback.engineer_id,
    )
    return await repo.upsert_relation(updated)


@router.post("/subgraph", response_model=list[RelationObject])
async def get_subgraph(body: SubgraphRequest, request: Request) -> list[RelationObject]:
    """
    提取以指定节点为中心的子图（供 Context Engine 使用）。
    """
    repo = RelationRepository(request.app.state.neo4j_driver)
    return await repo.get_subgraph(
        center_node_id=body.center_node_id,
        max_hops=body.max_hops,
        min_confidence=body.min_confidence,
    )


@router.get("/pending-review", response_model=list[RelationObject])
async def get_pending_relations(request: Request, limit: int = 50) -> list[RelationObject]:
    """
    获取待人工审核的关系列表（HITL 工作队列）。
    """
    repo = RelationRepository(request.app.state.neo4j_driver)
    return await repo.get_pending_review_relations(limit=limit)


# ─── 内部辅助 ─────────────────────────────────────────────────────

async def _find_existing(
    repo: RelationRepository,
    incoming: RelationObject,
) -> RelationObject | None:
    """查找图中是否已存在相同的关系（同节点对 + 同类型）。"""
    # TODO: 实现按 source_node_id + target_node_id + relation_type 查询
    # MVP 阶段暂时依赖 upsert 的 MERGE 语义
    return None
