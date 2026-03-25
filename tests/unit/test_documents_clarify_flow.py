"""
tests/unit/test_documents_clarify_flow.py
-----------------------------------------
阶段1/3：上传后澄清流（clarify Q&A）的最小单元测试。
"""

from __future__ import annotations

from datetime import UTC, datetime

from relos.ingestion.document.models import DocumentRecord, DocumentStatus, TemplateType
from relos.ingestion.document.store import DocumentStore


def test_document_store_set_clarify_questions_and_answers() -> None:
    store = DocumentStore()
    rec = DocumentRecord(
        filename="a.xlsx",
        file_size_bytes=10,
        template_type=TemplateType.CMMS_MAINTENANCE,
        status=DocumentStatus.PENDING_REVIEW,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    store.save(rec)

    qs = [{"question_id": "cq-001", "type": "single_choice"}]
    store.set_clarify_questions(rec.id, qs)
    updated = store.get(rec.id)
    assert updated is not None
    assert updated.clarify_questions == qs

    store.set_clarify_answers(rec.id, {"cq-001": "opt-a"})
    updated2 = store.get(rec.id)
    assert updated2 is not None
    assert updated2.clarify_answers["cq-001"] == "opt-a"

