"""
relos/api/v1/documents.py
---------------------------
文档摄取 API：上传 → AI 抽取 → 人工标注 → 提交图谱。

端点概览：
  POST /v1/documents/upload             上传并启动 AI 分析
  GET  /v1/documents/                   列出所有文档记录
  GET  /v1/documents/{doc_id}           查询文档状态和候选关系
  POST /v1/documents/{doc_id}/annotate/{rel_id}  标注单条候选关系
  POST /v1/documents/{doc_id}/commit    提交已审核关系到图谱

设计要点：
  - 上传后立即返回 doc_id，AI 抽取通过 BackgroundTask 异步执行
  - 客户端通过轮询 GET /{doc_id} 查看进度（status 字段）
  - commit 只处理 approved / modified 的关系，跳过 pending / rejected
  - 提交的关系写入 Neo4j，provenance = EXPERT_DOCUMENT 或 STRUCTURED_DOCUMENT
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Annotated, Literal, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from neo4j import AsyncDriver
from pydantic import BaseModel

from relos.core.models import RelationObject, RelationStatus, SourceType
from relos.core.repository import RelationRepository
from relos.ingestion.document.excel_parser import parse_excel
from relos.ingestion.document.llm_extractor import extract_relations
from relos.ingestion.document.models import (
    AnnotationStatus,
    DocumentRecord,
    DocumentStatus,
    TemplateType,
)
from relos.ingestion.document.store import DocumentStore
from relos.ingestion.document.word_parser import parse_word

router = APIRouter()
logger = structlog.get_logger(__name__)

# 允许的 MIME 类型
_ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # xlsx
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/octet-stream",  # 某些客户端对 xlsx/docx 发送的通用类型
}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ─── 请求 / 响应模型 ──────────────────────────────────────────────────

class AnnotateRequest(BaseModel):
    action: Literal["approve", "reject", "modify"]
    modified_confidence: Optional[float] = None
    modified_relation_type: Optional[str] = None
    annotated_by: str = "engineer"


class CommitResponse(BaseModel):
    doc_id: str
    committed_count: int
    skipped_count: int
    relation_ids: list[str]


class DocumentSummary(BaseModel):
    """列表视图的精简字段。"""
    id: str
    filename: str
    template_type: str
    status: str
    pending_count: int
    approved_count: int
    committed_count: int
    created_at: datetime


# ─── 辅助函数 ──────────────────────────────────────────────────────────

def _get_store(request: Request) -> DocumentStore:
    return request.app.state.document_store  # type: ignore[no-any-return]


def _get_driver(request: Request) -> AsyncDriver:
    return request.app.state.neo4j_driver  # type: ignore[no-any-return]


def _detect_file_type(filename: str, content_type: str) -> str:
    """根据文件名后缀判断类型（content_type 不可靠）。"""
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return "xlsx"
    if lower.endswith(".docx"):
        return "docx"
    # fallback：从 content_type 推断
    if "spreadsheet" in content_type or "excel" in content_type:
        return "xlsx"
    if "wordprocessing" in content_type or "word" in content_type:
        return "docx"
    return "unknown"


async def _process_document(
    doc_id: str,
    file_bytes: bytes,
    filename: str,
    file_type: str,
    store: DocumentStore,
) -> None:
    """
    后台任务：解析文件 → AI 抽取关系 → 更新存储。
    发生任何错误均写入 DocumentRecord.error_message。
    """
    try:
        store.update_status(doc_id, DocumentStatus.PARSING)
        logger.info("document_parsing", doc_id=doc_id, filename=filename)

        if file_type == "xlsx":
            parsed = parse_excel(file_bytes, filename)
        elif file_type == "docx":
            parsed = parse_word(file_bytes, filename)
        else:
            store.update_status(doc_id, DocumentStatus.FAILED, f"不支持的文件类型：{file_type}")
            return

        store.update_status(doc_id, DocumentStatus.EXTRACTING)
        logger.info("document_extracting", doc_id=doc_id, template=parsed.template_type)

        relations = await extract_relations(parsed)
        store.set_relations(doc_id, relations)

        logger.info(
            "document_ready_for_review",
            doc_id=doc_id,
            relation_count=len(relations),
        )

    except Exception as e:
        logger.error("document_processing_failed", doc_id=doc_id, error=str(e))
        store.update_status(doc_id, DocumentStatus.FAILED, str(e))


# ─── 端点 ──────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentSummary, status_code=202)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    template_hint: Optional[str] = Form(default=None),  # 可选：指定模板类型
) -> DocumentSummary:
    """
    上传文档并启动 AI 分析。

    立即返回 202 Accepted + doc_id。
    客户端轮询 GET /v1/documents/{doc_id} 查看进度。

    支持格式：xlsx（Excel）、docx（Word）
    最大文件大小：10 MB
    """
    filename = file.filename or "unknown"
    content_type = file.content_type or ""

    file_type = _detect_file_type(filename, content_type)
    if file_type == "unknown":
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式：{filename}。仅支持 .xlsx 和 .docx",
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(file_bytes) // 1024} KB），最大限制 10 MB",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 确定模板类型（如果用户指定了 hint）
    template_type = TemplateType.UNKNOWN
    if template_hint:
        try:
            template_type = TemplateType(template_hint)
        except ValueError:
            pass  # 忽略无效 hint，由解析器自动检测

    store = _get_store(request)
    record = DocumentRecord(
        filename=filename,
        file_size_bytes=len(file_bytes),
        template_type=template_type,
        status=DocumentStatus.UPLOADED,
    )
    store.save(record)

    # 启动后台处理
    background_tasks.add_task(
        _process_document,
        doc_id=record.id,
        file_bytes=file_bytes,
        filename=filename,
        file_type=file_type,
        store=store,
    )

    logger.info(
        "document_uploaded",
        doc_id=record.id,
        filename=filename,
        file_type=file_type,
        size_bytes=len(file_bytes),
    )

    return DocumentSummary(
        id=record.id,
        filename=record.filename,
        template_type=record.template_type,
        status=record.status,
        pending_count=record.pending_count(),
        approved_count=record.approved_count(),
        committed_count=record.committed_count,
        created_at=record.created_at,
    )


@router.get("/", response_model=list[DocumentSummary])
async def list_documents(request: Request) -> list[DocumentSummary]:
    """列出所有文档记录（按上传时间倒序）。"""
    store = _get_store(request)
    return [
        DocumentSummary(
            id=r.id,
            filename=r.filename,
            template_type=r.template_type,
            status=r.status,
            pending_count=r.pending_count(),
            approved_count=r.approved_count(),
            committed_count=r.committed_count,
            created_at=r.created_at,
        )
        for r in store.list_all()
    ]


@router.get("/{doc_id}", response_model=DocumentRecord)
async def get_document(doc_id: str, request: Request) -> DocumentRecord:
    """
    查询文档状态和 AI 抽取的候选关系列表。

    status 字段说明：
      uploaded       → 刚上传，处理中
      parsing        → 正在读取文件结构
      extracting     → AI 正在分析
      pending_review → 可以开始标注
      committed      → 已全部提交到图谱
      failed         → 处理出错（error_message 有详情）
    """
    store = _get_store(request)
    record = store.get(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    return record


@router.post("/{doc_id}/annotate/{rel_id}", response_model=DocumentRecord)
async def annotate_relation(
    doc_id: str,
    rel_id: str,
    body: AnnotateRequest,
    request: Request,
) -> DocumentRecord:
    """
    标注单条候选关系。

    action 说明：
      approve  → 确认该关系，将以原置信度写入图谱
      reject   → 拒绝该关系，不写入图谱
      modify   → 修改置信度或关系类型后确认

    示例（批准）：
      {"action": "approve"}

    示例（修改后批准）：
      {"action": "modify", "modified_confidence": 0.90, "modified_relation_type": "MACHINE__HAS__FAILURE_MODE"}
    """
    if body.action == "modify" and body.modified_confidence is None and body.modified_relation_type is None:
        raise HTTPException(
            status_code=400,
            detail="modify 操作必须提供 modified_confidence 或 modified_relation_type",
        )
    if body.modified_confidence is not None and not (0.0 <= body.modified_confidence <= 1.0):
        raise HTTPException(status_code=400, detail="confidence 必须在 0.0–1.0 之间")

    store = _get_store(request)
    updated = store.annotate_relation(
        doc_id=doc_id,
        rel_id=rel_id,
        action=body.action,
        modified_confidence=body.modified_confidence,
        modified_relation_type=body.modified_relation_type,
        annotated_by=body.annotated_by,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 或关系 {rel_id} 不存在")
    return updated


@router.post("/{doc_id}/commit", response_model=CommitResponse)
async def commit_document(doc_id: str, request: Request) -> CommitResponse:
    """
    将所有已审核（approved / modified）的候选关系提交到 Neo4j 图谱。

    - 跳过 pending 和 rejected 的关系
    - 提交后文档状态变为 committed
    - 关系 provenance 根据文档模板类型自动设置：
        结构化（CMMS/FMEA/SUPPLIER） → structured_document
        非结构化（8D/SHIFT/UNKNOWN）  → expert_document
    - 所有提交关系强制 pending_review（人工标注后仍需图谱层确认）
    """
    store = _get_store(request)
    record = store.get(doc_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
    if record.status == DocumentStatus.COMMITTED:
        raise HTTPException(status_code=409, detail="该文档已提交过，不可重复提交")
    if record.status not in (DocumentStatus.PENDING_REVIEW, DocumentStatus.COMMITTED):
        raise HTTPException(
            status_code=400,
            detail=f"文档当前状态为 {record.status}，无法提交（需为 pending_review）",
        )

    # 确定 provenance
    structured_templates = {
        TemplateType.CMMS_MAINTENANCE,
        TemplateType.FMEA,
        TemplateType.SUPPLIER_DELIVERY,
    }
    provenance = (
        SourceType.STRUCTURED_DOCUMENT
        if record.template_type in structured_templates
        else SourceType.EXPERT_DOCUMENT
    )

    driver = _get_driver(request)
    repo = RelationRepository(driver)

    committed_ids: list[str] = []
    skipped = 0
    now = datetime.utcnow()

    for draft in record.extracted_relations:
        if draft.annotation_status not in (AnnotationStatus.APPROVED, AnnotationStatus.MODIFIED):
            skipped += 1
            continue

        try:
            relation = RelationObject(
                relation_type=draft.effective_relation_type,
                source_node_id=draft.source_node_id,
                source_node_type=draft.source_node_type,
                target_node_id=draft.target_node_id,
                target_node_type=draft.target_node_type,
                confidence=min(0.85, draft.effective_confidence),
                provenance=provenance,
                provenance_detail=f"doc:{doc_id} rel:{draft.id}",
                half_life_days=180,   # 文档关系半衰期 180 天（比传感器长，比永久短）
                status=RelationStatus.PENDING_REVIEW,
                created_at=now,
                updated_at=now,
                properties={
                    "evidence": draft.evidence,
                    "source_document": record.filename,
                    "annotated_by": draft.annotated_by or "engineer",
                },
            )
            await repo.upsert_relation(relation)
            committed_ids.append(draft.id)

        except Exception as e:
            logger.error(
                "relation_commit_failed",
                doc_id=doc_id,
                rel_id=draft.id,
                error=str(e),
            )
            skipped += 1

    # 更新文档状态
    if committed_ids:
        rec = store.get(doc_id)
        if rec:
            store.save(rec.model_copy(update={
                "status": DocumentStatus.COMMITTED,
                "committed_count": len(committed_ids),
                "completed_at": now,
            }))

    logger.info(
        "document_committed",
        doc_id=doc_id,
        committed=len(committed_ids),
        skipped=skipped,
    )

    return CommitResponse(
        doc_id=doc_id,
        committed_count=len(committed_ids),
        skipped_count=skipped,
        relation_ids=committed_ids,
    )
