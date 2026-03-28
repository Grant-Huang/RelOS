"""
relos/api/v1/metrics.py
------------------------
关系图谱统计指标端点。

提供关系图谱的健康度和规模统计，用于：
- 监控系统运行状态
- 评估数据飞轮积累速度
- 向客户展示知识库规模

Sprint 3 Week 11：可观测性 — /v1/metrics 端点。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from relos.core.repository import RelationRepository

router = APIRouter()


class RelationTypeBucket(BaseModel):
    relation_type: str
    count: int
    avg_confidence: float


class ProvenanceBucket(BaseModel):
    provenance: str
    count: int


class PhaseBucket(BaseModel):
    phase: str
    count: int
    avg_confidence: float


class GraphMetrics(BaseModel):
    """关系图谱统计指标。"""
    # 图谱规模
    total_nodes: int
    total_relations: int

    # 关系质量
    avg_confidence: float
    active_count: int
    pending_review_count: int
    conflicted_count: int
    archived_count: int

    # 衍生指标
    active_ratio: float  # active_count / total_relations
    review_backlog: int  # 待审核积压量（= pending_review_count）

    # 分布（Neo4j 聚合，供知识库状态等页）
    relation_type_breakdown: list[RelationTypeBucket] = Field(default_factory=list)
    provenance_breakdown: list[ProvenanceBucket] = Field(default_factory=list)
    knowledge_phase_breakdown: list[PhaseBucket] = Field(default_factory=list)

    # 元信息
    collected_at: datetime


@router.get("/", response_model=GraphMetrics)
async def get_metrics(request: Request) -> GraphMetrics:
    """
    获取关系图谱统计指标。

    返回关系图谱的规模、质量和状态分布，
    用于监控和评估知识库积累进度。
    """
    repo = RelationRepository(request.app.state.neo4j_driver)
    raw = await repo.get_graph_metrics()
    rt_dist, prov_dist, phase_dist = await asyncio.gather(
        repo.get_relation_type_distribution(8),
        repo.get_provenance_distribution(),
        repo.get_knowledge_phase_distribution(),
    )

    total = raw["total_relations"]
    active = raw["active_count"]
    active_ratio = round(active / total, 4) if total > 0 else 0.0

    return GraphMetrics(
        total_nodes=raw["total_nodes"],
        total_relations=total,
        avg_confidence=raw["avg_confidence"],
        active_count=active,
        pending_review_count=raw["pending_review_count"],
        conflicted_count=raw["conflicted_count"],
        archived_count=raw["archived_count"],
        active_ratio=active_ratio,
        review_backlog=raw["pending_review_count"],
        relation_type_breakdown=[RelationTypeBucket(**x) for x in rt_dist],
        provenance_breakdown=[ProvenanceBucket(**x) for x in prov_dist],
        knowledge_phase_breakdown=[PhaseBucket(**x) for x in phase_dist],
        collected_at=datetime.now(UTC),
    )
