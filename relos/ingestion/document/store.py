"""
relos/ingestion/document/store.py
------------------------------------
文档记录的内存存储（MVP 阶段）。

生产阶段应替换为 Redis Hash 或 PostgreSQL，
但 MVP Demo 直接存内存即可，单进程部署无并发问题。

用法：
  # 在 app startup 时注册到 app.state
  app.state.document_store = DocumentStore()

  # 在 API handler 中
  store: DocumentStore = request.app.state.document_store
  doc = store.get("doc-id")
"""

from __future__ import annotations

from typing import Optional

import structlog

from relos.ingestion.document.models import AnnotationStatus, DocumentRecord, DocumentStatus

logger = structlog.get_logger(__name__)


class DocumentStore:
    """线程不安全的内存文档存储（MVP 演示用）。"""

    def __init__(self) -> None:
        self._records: dict[str, DocumentRecord] = {}

    # ─── CRUD ──────────────────────────────────────────────────────

    def save(self, record: DocumentRecord) -> None:
        self._records[record.id] = record
        logger.debug("document_saved", doc_id=record.id, status=record.status)

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        return self._records.get(doc_id)

    def list_all(self) -> list[DocumentRecord]:
        return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)

    def update_status(self, doc_id: str, status: DocumentStatus, error: str = "") -> None:
        if rec := self._records.get(doc_id):
            self._records[doc_id] = rec.model_copy(update={
                "status": status,
                **({"error_message": error} if error else {}),
            })

    # ─── 标注操作 ───────────────────────────────────────────────────

    def annotate_relation(
        self,
        doc_id: str,
        rel_id: str,
        action: str,                   # "approve" | "reject" | "modify"
        modified_confidence: Optional[float] = None,
        modified_relation_type: Optional[str] = None,
        annotated_by: str = "engineer",
    ) -> Optional[DocumentRecord]:
        """
        更新单条候选关系的标注状态。

        Returns:
            更新后的 DocumentRecord，未找到则返回 None
        """
        from datetime import datetime

        rec = self._records.get(doc_id)
        if not rec:
            return None

        new_relations = []
        for rel in rec.extracted_relations:
            if rel.id == rel_id:
                status_map = {
                    "approve": AnnotationStatus.APPROVED,
                    "reject":  AnnotationStatus.REJECTED,
                    "modify":  AnnotationStatus.MODIFIED,
                }
                new_status = status_map.get(action, AnnotationStatus.PENDING)
                rel = rel.model_copy(update={
                    "annotation_status": new_status,
                    "annotated_at": datetime.utcnow(),
                    "annotated_by": annotated_by,
                    **({"modified_confidence": modified_confidence}
                       if modified_confidence is not None else {}),
                    **({"modified_relation_type": modified_relation_type}
                       if modified_relation_type else {}),
                })
            new_relations.append(rel)

        updated = rec.model_copy(update={"extracted_relations": new_relations})
        self._records[doc_id] = updated
        logger.info("relation_annotated", doc_id=doc_id, rel_id=rel_id, action=action)
        return updated

    def set_relations(self, doc_id: str, relations: list) -> None:  # type: ignore[type-arg]
        """替换文档的候选关系列表（AI 抽取完成后调用）。"""
        if rec := self._records.get(doc_id):
            self._records[doc_id] = rec.model_copy(update={
                "extracted_relations": relations,
                "status": DocumentStatus.PENDING_REVIEW,
            })

    def set_clarify_questions(self, doc_id: str, questions: list[dict]) -> None:
        """设置澄清问题（阶段1/3：上传后引导）。"""
        if rec := self._records.get(doc_id):
            self._records[doc_id] = rec.model_copy(update={"clarify_questions": questions})

    def set_clarify_answers(self, doc_id: str, answers: dict[str, str]) -> None:
        """提交澄清答案（MVP：仅记录，后续可触发重抽取/重排）。"""
        if rec := self._records.get(doc_id):
            merged = {**(rec.clarify_answers or {}), **answers}
            self._records[doc_id] = rec.model_copy(update={"clarify_answers": merged})
