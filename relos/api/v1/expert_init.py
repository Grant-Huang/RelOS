"""
relos/api/v1/expert_init.py
----------------------------
专家初始化端点：让领域工程师快速录入核心关系知识。

设计（dev-plan.md Week 9）：
- 支持单条手工录入（POST /v1/expert-init）
- 支持批量上传（POST /v1/expert-init/batch-upload）
- 支持 Excel 文件上传（POST /v1/expert-init/upload-excel）
- 所有专家录入来源标记为 manual_engineer，初始置信度 ≥ 0.9
- 专家录入的关系直接进入 active（无需 pending_review）

MVP 目标：1 小时内录入 30 条核心关系（dev-plan.md Sprint 3 成功标准）
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from relos.core.models import Node, RelationObject, RelationStatus, SourceType
from relos.core.repository import RelationRepository
from relos.ingestion.excel_importer import ExcelImporter

router = APIRouter()
logger = structlog.get_logger(__name__)


# ─── 请求/响应 Schema ──────────────────────────────────────────────────

class ExpertRelationInput(BaseModel):
    """
    专家录入单条关系的请求体。

    简化字段：专家不需要理解全部 RelationObject 字段，
    只需要描述"什么设备和什么问题之间有什么关系"。
    """
    # 关系两端
    source_node_id: str = Field(description="起始实体 ID，例如设备编号 CNC-M1")
    source_node_type: str = Field(description="起始实体类型，例如 Device、Component")
    target_node_id: str = Field(description="目标实体 ID，例如告警编号 ALM-BEARING")
    target_node_type: str = Field(description="目标实体类型，例如 Alarm、RootCause")
    relation_type: str = Field(
        description="关系类型，格式 DOMAIN__VERB__DOMAIN，例如 DEVICE__TRIGGERS__ALARM"
    )

    # 置信度（专家录入默认高置信度）
    confidence: float = Field(
        default=0.92,
        ge=0.0, le=1.0,
        description="初始置信度，专家录入默认 0.92"
    )

    # 可选元数据
    provenance_detail: str = Field(
        default="",
        description="来源说明，例如维修工单号、经验来源"
    )
    engineer_id: str = Field(description="录入工程师 ID，用于审计追踪")
    half_life_days: int = Field(default=365, description="半衰期（天），专家知识默认 365 天")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="额外属性，例如 {frequency: 5, severity: 'high'}"
    )


class ExpertInitResponse(BaseModel):
    """专家初始化响应。"""
    relation: RelationObject
    is_new: bool = Field(description="True 表示新创建，False 表示更新已有关系")
    message: str = ""


class BatchInitResponse(BaseModel):
    """批量录入响应。"""
    success_count: int
    failed_count: int
    relations: list[RelationObject]
    errors: list[dict[str, Any]]


# ─── 端点 ──────────────────────────────────────────────────────────────

@router.post("/", response_model=ExpertInitResponse, status_code=201)
async def expert_init_relation(
    body: ExpertRelationInput,
    request: Request,
) -> ExpertInitResponse:
    """
    专家录入单条关系。

    - 来源自动标记为 manual_engineer
    - 状态直接设为 active（专家知识不需要 pending_review）
    - 若同节点对 + 同类型已存在，则执行置信度合并
    """
    repo = RelationRepository(request.app.state.neo4j_driver)

    relation = RelationObject(
        source_node_id=body.source_node_id,
        source_node_type=body.source_node_type,
        target_node_id=body.target_node_id,
        target_node_type=body.target_node_type,
        relation_type=body.relation_type.upper(),
        confidence=body.confidence,
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail=body.provenance_detail,
        extracted_by=f"expert:{body.engineer_id}",
        half_life_days=body.half_life_days,
        status=RelationStatus.ACTIVE,   # 专家直接激活
        properties=body.properties,
    )

    # 确保节点存在
    await repo.upsert_node(Node(
        id=body.source_node_id,
        node_type=body.source_node_type,
        name=body.source_node_id,
    ))
    await repo.upsert_node(Node(
        id=body.target_node_id,
        node_type=body.target_node_type,
        name=body.target_node_id,
    ))

    # 检查是否已存在
    existing = await repo.find_relation(
        source_node_id=body.source_node_id,
        target_node_id=body.target_node_id,
        relation_type=relation.relation_type,
    )

    is_new = existing is None
    if not is_new:
        # 已存在：专家知识权重高（alpha=0.3），用加权平均更新置信度
        from relos.core.engine import RelationEngine
        engine = RelationEngine()
        merge_result = engine.merge_confidence(existing, relation)  # type: ignore[arg-type]
        relation = existing.model_copy(update={  # type: ignore[union-attr]
            "confidence": merge_result.new_confidence,
            "status": RelationStatus.ACTIVE,
            "extracted_by": f"expert:{body.engineer_id}",
        })

    saved = await repo.upsert_relation(relation)

    logger.info(
        "expert_relation_saved",
        relation_id=saved.id,
        engineer_id=body.engineer_id,
        is_new=is_new,
    )

    return ExpertInitResponse(
        relation=saved,
        is_new=is_new,
        message="关系已创建" if is_new else "关系置信度已更新",
    )


@router.post("/batch", response_model=BatchInitResponse)
async def expert_init_batch(
    body: list[ExpertRelationInput],
    request: Request,
) -> BatchInitResponse:
    """
    专家批量录入关系（最多 100 条）。
    每条独立处理，单条失败不影响其他条。
    """
    if len(body) > 100:
        raise HTTPException(
            status_code=422,
            detail="单次批量录入最多 100 条，请分批提交"
        )

    repo = RelationRepository(request.app.state.neo4j_driver)
    success_relations: list[RelationObject] = []
    errors: list[dict[str, Any]] = []

    for idx, item in enumerate(body):
        try:
            # Reuse single-item logic via a lightweight function
            relation = RelationObject(
                source_node_id=item.source_node_id,
                source_node_type=item.source_node_type,
                target_node_id=item.target_node_id,
                target_node_type=item.target_node_type,
                relation_type=item.relation_type.upper(),
                confidence=item.confidence,
                provenance=SourceType.MANUAL_ENGINEER,
                provenance_detail=item.provenance_detail,
                extracted_by=f"expert:{item.engineer_id}",
                half_life_days=item.half_life_days,
                status=RelationStatus.ACTIVE,
                properties=item.properties,
            )
            await repo.upsert_node(Node(
                id=item.source_node_id, node_type=item.source_node_type,
                name=item.source_node_id,
            ))
            await repo.upsert_node(Node(
                id=item.target_node_id, node_type=item.target_node_type,
                name=item.target_node_id,
            ))
            saved = await repo.upsert_relation(relation)
            success_relations.append(saved)
        except Exception as exc:
            errors.append({"index": idx, "error": str(exc)})
            logger.warning("expert_batch_row_failed", index=idx, error=str(exc))

    logger.info(
        "expert_batch_complete",
        success=len(success_relations),
        failed=len(errors),
    )

    return BatchInitResponse(
        success_count=len(success_relations),
        failed_count=len(errors),
        relations=success_relations,
        errors=errors,
    )


@router.post("/upload-excel", response_model=BatchInitResponse)
async def expert_init_upload_excel(
    file: UploadFile,
    request: Request,
    engineer_id: str = "excel-import",
    dry_run: bool = False,
) -> BatchInitResponse:
    """
    上传 Excel 文件批量初始化关系知识库。

    - 文件格式：.xlsx，参见 docs/data-model.md §Excel 导入规范
    - 来源标记为 mes_structured（Excel 导入）
    - dry_run=true 时只解析验证，不写入数据库
    """
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="仅支持 .xlsx 格式")

    content = await file.read()
    # 通过专家初始化端点导入的 Excel 属于工程师手动录入（manual_engineer），
    # 而非 MES 系统导出（mes_structured），置信度范围应为 0.90–1.0
    importer = ExcelImporter(default_provenance=SourceType.MANUAL_ENGINEER)

    try:
        parse_result = importer.parse_bytes(content)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    saved_relations: list[RelationObject] = []

    if not dry_run:
        repo = RelationRepository(request.app.state.neo4j_driver)
        for relation in parse_result.relations:
            try:
                await repo.upsert_node(Node(
                    id=relation.source_node_id,
                    node_type=relation.source_node_type,
                    name=relation.source_node_id,
                ))
                await repo.upsert_node(Node(
                    id=relation.target_node_id,
                    node_type=relation.target_node_type,
                    name=relation.target_node_id,
                ))
                saved = await repo.upsert_relation(relation)
                saved_relations.append(saved)
            except Exception as exc:
                parse_result.errors.append(  # type: ignore[attr-defined]
                    type("E", (), {"row_number": -1, "error": str(exc)})()
                )
    else:
        saved_relations = parse_result.relations

    errors = [
        {"row": e.row_number, "error": e.error}
        for e in parse_result.errors
    ]

    logger.info(
        "excel_upload_complete",
        filename=file.filename,
        dry_run=dry_run,
        success=len(saved_relations),
        failed=parse_result.failed_count,
    )

    return BatchInitResponse(
        success_count=len(saved_relations),
        failed_count=parse_result.failed_count,
        relations=saved_relations,
        errors=errors,
    )
