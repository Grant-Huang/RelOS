"""
tests/integration/test_documents_clarify_api.py
------------------------------------------------
阶段1/3：上传后澄清流（clarify Q&A）API 集成测试（不依赖 Neo4j）。
"""

from __future__ import annotations

import io

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def api_client():
    import httpx
    from fastapi import FastAPI

    from relos.api.v1 import documents
    from relos.ingestion.document.store import DocumentStore

    app = FastAPI(title="RelOS Documents Clarify Integration")
    app.state.document_store = DocumentStore()

    # documents.py 还需要 neo4j_driver，但本测试只走 upload/get/clarify，不触发 commit
    class _Dummy:
        pass

    app.state.neo4j_driver = _Dummy()
    app.state.langsmith_enabled = False

    app.include_router(documents.router, prefix="/v1/documents", tags=["documents"])

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.mark.integration
class TestDocumentsClarify:
    async def test_upload_get_has_questions_and_can_clarify(self, api_client) -> None:
        # 用一个最小 xlsx 文件头触发类型识别（解析失败也会写 error，但不影响本测试的 get/clarify 形状）
        # 注意：这里不追求抽取成功，只验证 clarify 字段与端点存在
        fake_xlsx = b"PK\x03\x04" + b"\x00" * 10

        resp = await api_client.post(
            "/v1/documents/upload",
            files={"file": ("a.xlsx", io.BytesIO(fake_xlsx), "application/octet-stream")},
        )
        assert resp.status_code == 202, resp.text
        doc_id = resp.json()["id"]

        # 轮询一次详情（后台任务未必完成；此处只验证字段存在不报错）
        resp = await api_client.get(f"/v1/documents/{doc_id}")
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert "clarify_questions" in payload
        assert "clarify_answers" in payload

        # 若尚未进入 pending_review，clarify 会返回 400；这符合实现约束（必须 pending_review）
        resp = await api_client.post(
            f"/v1/documents/{doc_id}/clarify",
            json={"answers": {"cq-001": "dev-cnc"}, "answered_by": "engineer"},
        )
        assert resp.status_code in (200, 400), resp.text

