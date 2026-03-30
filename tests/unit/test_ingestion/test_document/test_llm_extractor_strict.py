"""
ALLOW_LLM_MOCK=false 时抽取器须明确失败（上线模式）。
"""
from __future__ import annotations

import pytest

from relos.config import Settings
from relos.ingestion.document.llm_extractor import (
    LlmExtractionUnavailableError,
    extract_relations,
)
from relos.ingestion.document.models import ParsedDocument, TemplateType


def _doc() -> ParsedDocument:
    return ParsedDocument(
        template_type=TemplateType.CMMS_MAINTENANCE,
        source_filename="t.xlsx",
        rows=[],
    )


@pytest.mark.asyncio
async def test_no_api_key_raises_when_mock_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from relos.ingestion.document import llm_extractor

    fake = Settings(
        ANTHROPIC_API_KEY="",
        ALLOW_LLM_MOCK=False,
        ENV="production",
    )
    monkeypatch.setattr(llm_extractor, "settings", fake)

    with pytest.raises(LlmExtractionUnavailableError) as exc_info:
        await extract_relations(_doc())
    assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    assert "ALLOW_LLM_MOCK" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mock_allowed_without_key_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    from relos.ingestion.document import llm_extractor

    fake = Settings(
        ANTHROPIC_API_KEY="",
        ALLOW_LLM_MOCK=True,
        ENV="development",
    )
    monkeypatch.setattr(llm_extractor, "settings", fake)

    drafts = await extract_relations(_doc())
    assert len(drafts) > 0
