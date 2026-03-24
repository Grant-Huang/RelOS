"""
tests/unit/test_ingestion/test_document/test_llm_extractor.py
---------------------------------------------------------------
LLM 抽取器单元测试（Mock 模式，不需要 ANTHROPIC_API_KEY）。
"""
from __future__ import annotations

import pytest

from relos.ingestion.document.llm_extractor import extract_relations
from relos.ingestion.document.models import (
    AnnotationStatus,
    ParsedDocument,
    ParsedRow,
    TemplateType,
)


def _make_doc(template: TemplateType, rows: list[dict] | None = None) -> ParsedDocument:
    parsed_rows = []
    if rows:
        for i, row in enumerate(rows):
            parsed_rows.append(ParsedRow(row_index=i + 1, fields=row))
    return ParsedDocument(
        template_type=template,
        source_filename="test.xlsx",
        rows=parsed_rows,
    )


class TestExtractRelationsMock:
    """无 API Key 时使用 Mock 数据，验证输出格式正确。"""

    @pytest.mark.asyncio
    async def test_cmms_returns_drafts(self) -> None:
        doc = _make_doc(TemplateType.CMMS_MAINTENANCE)
        drafts = await extract_relations(doc)
        assert len(drafts) > 0

    @pytest.mark.asyncio
    async def test_fmea_returns_drafts(self) -> None:
        doc = _make_doc(TemplateType.FMEA)
        drafts = await extract_relations(doc)
        assert len(drafts) > 0

    @pytest.mark.asyncio
    async def test_supplier_returns_drafts(self) -> None:
        doc = _make_doc(TemplateType.SUPPLIER_DELIVERY)
        drafts = await extract_relations(doc)
        assert len(drafts) > 0

    @pytest.mark.asyncio
    async def test_quality_8d_returns_drafts(self) -> None:
        doc = _make_doc(TemplateType.QUALITY_8D)
        drafts = await extract_relations(doc)
        assert len(drafts) > 0

    @pytest.mark.asyncio
    async def test_shift_handover_returns_drafts(self) -> None:
        doc = _make_doc(TemplateType.SHIFT_HANDOVER)
        drafts = await extract_relations(doc)
        assert len(drafts) > 0

    @pytest.mark.asyncio
    async def test_all_drafts_have_required_fields(self) -> None:
        doc = _make_doc(TemplateType.CMMS_MAINTENANCE)
        drafts = await extract_relations(doc)
        for draft in drafts:
            assert draft.source_node_id
            assert draft.source_node_type
            assert draft.target_node_id
            assert draft.target_node_type
            assert draft.relation_type
            assert 0.0 <= draft.confidence <= 0.85
            assert draft.evidence
            assert draft.reasoning

    @pytest.mark.asyncio
    async def test_confidence_hard_cap(self) -> None:
        """所有候选关系置信度不超过 0.85（硬上限）。"""
        for template in TemplateType:
            doc = _make_doc(template)
            drafts = await extract_relations(doc)
            for d in drafts:
                assert d.confidence <= 0.85, (
                    f"{template}: {d.relation_type} confidence={d.confidence} > 0.85"
                )

    @pytest.mark.asyncio
    async def test_default_annotation_status_pending(self) -> None:
        doc = _make_doc(TemplateType.CMMS_MAINTENANCE)
        drafts = await extract_relations(doc)
        for draft in drafts:
            assert draft.annotation_status == AnnotationStatus.PENDING

    @pytest.mark.asyncio
    async def test_resolved_entity_ids(self) -> None:
        """CMMS mock 数据中的 M3 应被解析为 machine-M3。"""
        doc = _make_doc(TemplateType.CMMS_MAINTENANCE)
        drafts = await extract_relations(doc)
        machine_ids = [d.source_node_id for d in drafts if d.source_node_type == "Machine"]
        # 至少有一个候选关系的来源节点被解析到图谱已知节点
        assert any(mid.startswith("machine-") for mid in machine_ids)
