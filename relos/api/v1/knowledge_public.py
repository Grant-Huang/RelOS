"""
relos/api/v1/knowledge_public.py
---------------------------------
公开知识：从纯文本抽取候选关系（不入库），供前端审核后 POST /relations。
"""

from __future__ import annotations

import html
import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from relos.ingestion.document.llm_extractor import extract_relations_plain_text

router = APIRouter()


class ApiResponse(BaseModel):
    status: str
    data: dict[str, Any] = {}
    message: str = ""


class PublicExtractRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    source_label: str = Field(default="公开知识", max_length=120)


def _highlight_preview(text: str) -> str:
    """与前端原 buildHighlightedHtml 等价的轻量实体高亮（服务端生成）。"""
    s = html.escape(text)
    patterns = [
        (r"(过热报警|振动报警|压力下降)", "ent-alarm"),
        (r"(轴承磨损|轴承失效|安装偏差|润滑不足|尺寸超差)", "ent-issue"),
        (r"(生产工单|工单|设备停机)", "ent-wo"),
        (r"(注塑机|设备|机器|轴承)", "ent-machine"),
    ]
    for pat, cls in patterns:
        s = re.sub(pat, rf'<span class="ent-span {cls}">\1</span>', s)
    return s


@router.post("/extract", response_model=ApiResponse)
async def extract_public_knowledge(body: PublicExtractRequest) -> ApiResponse:
    drafts = await extract_relations_plain_text(
        body.text.strip(),
        source_filename=f"{body.source_label}.txt",
    )
    out = []
    for d in drafts:
        mid = d.relation_type.split("__")[1] if "__" in d.relation_type else d.relation_type[:16]
        out.append({
            "clientKey": d.id,
            "relation_type": d.relation_type,
            "source_node_id": d.source_node_id,
            "source_node_type": d.source_node_type,
            "target_node_id": d.target_node_id,
            "target_node_type": d.target_node_type,
            "confidence": d.confidence,
            "evidence": d.evidence,
            "short": [
                d.source_node_name or d.source_node_id,
                mid,
                d.target_node_name or d.target_node_id,
                str(round(d.confidence, 2)),
            ],
        })
    return ApiResponse(
        status="success",
        data={
            "preview_html": _highlight_preview(body.text.strip()),
            "drafts": out,
        },
        message="",
    )
