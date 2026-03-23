"""
relos/api/v1/ontology.py
------------------------
行业本体模板端点（Sprint 4 Week 17-18）。

端点：
  GET  /v1/ontology/templates          → 列出所有行业模板
  GET  /v1/ontology/templates/{industry} → 获取指定行业模板详情
  POST /v1/ontology/templates/{industry}/import → 导入模板到 Neo4j
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from relos.core.repository import RelationRepository
from relos.ontology.templates import Industry, get_templates_for_industry, list_available_industries

router = APIRouter()


class TemplateSummary(BaseModel):
    industry: str
    name: str
    description: str
    version: str
    relation_count: int


class ImportResult(BaseModel):
    industry: str
    imported_count: int
    skipped_count: int
    dry_run: bool
    relations: list[dict[str, Any]]


@router.get("/templates", response_model=list[TemplateSummary])
async def list_templates() -> list[TemplateSummary]:
    """列出所有可用的行业本体模板。"""
    return [TemplateSummary(**item) for item in list_available_industries()]


@router.get("/templates/{industry}", response_model=dict[str, Any])
async def get_template(industry: str) -> dict[str, Any]:
    """获取指定行业的本体模板详情（含所有关系）。"""
    try:
        template = get_templates_for_industry(industry)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "industry": template.industry,
        "name": template.name,
        "description": template.description,
        "version": template.version,
        "relations": [r.model_dump() for r in template.relations],
    }


@router.post("/templates/{industry}/import", response_model=ImportResult)
async def import_template(
    industry: str,
    request: Request,
    dry_run: bool = False,
) -> ImportResult:
    """
    将行业本体模板导入 Neo4j。

    - dry_run=True：只返回将要导入的关系，不写库（用于预览）
    - 所有模板关系以 pending_review 状态导入，需工程师逐一确认
    - 已存在的关系（同节点对+类型）会跳过导入（不覆盖）
    """
    try:
        template = get_templates_for_industry(industry)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    imported = []
    skipped = []

    if not dry_run:
        repo = RelationRepository(request.app.state.neo4j_driver)
        for rel in template.relations:
            existing = await repo.find_relation(
                source_node_id=rel.source_node_id,
                target_node_id=rel.target_node_id,
                relation_type=rel.relation_type,
            )
            if existing:
                skipped.append(rel)
            else:
                await repo.upsert_relation(rel)
                imported.append(rel)
    else:
        # Dry run：全部当作将导入（不检查已存在）
        imported = list(template.relations)

    return ImportResult(
        industry=industry,
        imported_count=len(imported),
        skipped_count=len(skipped),
        dry_run=dry_run,
        relations=[r.model_dump() for r in imported],
    )
