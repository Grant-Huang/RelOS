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

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel

from relos.core.repository import RelationRepository

router = APIRouter()


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
        collected_at=datetime.now(timezone.utc),
    )
