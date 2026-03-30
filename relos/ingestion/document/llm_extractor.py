"""
relos/ingestion/document/llm_extractor.py
-------------------------------------------
AI 关系抽取器。

流程：
  ParsedDocument → [LLM / 规则] → list[ExtractedRelationDraft]

两种模式：
  1. LLM 模式（ANTHROPIC_API_KEY 已配置）
     使用 Claude 的 Messages API，传入模板特定的 system prompt
     和文档内容，要求输出规范 JSON

  2. Mock 模式（无 API Key 时）
     根据模板类型返回预定义的演示候选关系
     用于不依赖外部服务的 demo 和测试

关系置信度规则：
  - 结构化模板（CMMS / FMEA / SUPPLIER）：0.65–0.82
  - 非结构化模板（8D / SHIFT）：0.55–0.78
  - 模糊抽取降惩 0.05

所有抽取结果强制进入 pending_review，等待人工标注。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import structlog

from relos.config import settings
from relos.ingestion.document.entity_resolver import EntityResolver
from relos.ingestion.document.models import (
    ExtractedRelationDraft,
    ParsedDocument,
    TemplateType,
)

logger = structlog.get_logger(__name__)


class LlmExtractionUnavailableError(RuntimeError):
    """
    上线模式（ALLOW_LLM_MOCK=false）下无法完成抽取时抛出。
    reason 会写入日志与 API 错误信息，勿包含密钥或隐私。
    """

    def __init__(self, reason: str, **log_fields: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.log_fields = log_fields

_resolver = EntityResolver()

# ─── LLM 提示词模板 ──────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
你是一个工业知识图谱专家。
从给定的制造业文档中提取**实体关系**，输出规范 JSON。

输出格式（JSON 数组，不要有其他文字）：
[
  {
    "source_node_name": "实体名称",
    "source_node_type": "Machine|Line|Supplier|Material|Component|FailureMode|Operator|Process|Defect|Action",
    "target_node_name": "实体名称",
    "target_node_type": "Machine|Line|Supplier|Material|Component|FailureMode|Operator|Process|Defect|Action",
    "relation_type": "关系类型（大写下划线格式，如 MACHINE__HAS__FAILURE_MODE）",
    "confidence": 0.75,
    "evidence": "原文中支持该关系的关键句子（最多80字）",
    "reasoning": "为什么认为存在这个关系（最多60字）"
  }
]

关系类型命名规则：SOURCE_TYPE__VERB__TARGET_TYPE（全大写，双下划线分隔）
常见关系类型：
- MACHINE__HAS__FAILURE_MODE     设备发生了某类故障
- MACHINE__REQUIRES__COMPONENT   设备需要某个零件
- FAILURE_MODE__CAUSED_BY__ROOT_CAUSE  故障原因分析
- DEFECT__RESOLVED_BY__ACTION    缺陷被某措施解决
- SUPPLIER__CAUSES__DELIVERY_DELAY  供应商造成延误
- PROCESS__GENERATES__DEFECT     工序导致缺陷
- MACHINE__OPERATED_BY__OPERATOR 设备由某操作员负责

置信度参考：
  0.85: 文档明确陈述，无歧义
  0.75: 有合理依据，逻辑清晰
  0.65: 推断成分较多，需专家确认
  0.55: 不确定，建议人工核实

注意：只提取文档中有证据支撑的关系，不要推断文档中没有的信息。
"""

_USER_PROMPT_TMPL = """\
文档类型：{template_type}
文档内容：

{content}

请提取其中的实体关系，输出 JSON 数组。
"""

# ─── Mock 关系：无 API Key / LLM 失败时从 relos/demo_data 加载 ─────────

_LLM_MOCK_JSON = "llm_extract_mock_relations.json"

# 文件缺失或条目为空时的最后降级（保证流水线不因缺文件而崩溃）
_FALLBACK_UNKNOWN_RAW: list[dict[str, Any]] = [
    {
        "source_node_name": "设备",
        "source_node_type": "Machine",
        "target_node_name": "故障",
        "target_node_type": "FailureMode",
        "relation_type": "MACHINE__HAS__FAILURE_MODE",
        "confidence": 0.55,
        "evidence": "文档中提到设备相关故障信息",
        "reasoning": "未识别模板或 mock 数据未加载，建议人工核实",
    },
]


def _demo_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "demo_data"


@lru_cache(maxsize=1)
def _load_mock_relations_json() -> dict[str, list[dict[str, Any]]]:
    path = _demo_data_dir() / _LLM_MOCK_JSON
    if not path.is_file():
        logger.warning("llm_mock_json_missing", path=str(path))
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("llm_mock_json_read_error", path=str(path), error=str(e))
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            out[str(k)] = [x for x in v if isinstance(x, dict)]
    return out


def clear_llm_mock_relations_cache() -> None:
    """测试或热重载 demo 文件时可调用，清空 JSON 缓存。"""
    _load_mock_relations_json.cache_clear()


def _mock_raw_for_template(template_type: TemplateType) -> list[dict[str, Any]]:
    data = _load_mock_relations_json()
    key = template_type.value
    rows = data.get(key) or []
    if rows:
        return rows
    unk = data.get(TemplateType.UNKNOWN.value) or []
    if unk:
        return unk
    return list(_FALLBACK_UNKNOWN_RAW)


def _build_content(doc: ParsedDocument) -> str:
    """将 ParsedDocument 序列化为适合 LLM 输入的文本。"""
    parts: list[str] = []

    if doc.rows:
        parts.append("【表格数据】")
        for row in doc.rows[:30]:  # 最多 30 行，避免 context 过长
            parts.append(f"行{row.row_index}: " + " | ".join(
                f"{k}={v}" for k, v in row.fields.items() if v
            ))

    if doc.sections:
        parts.append("【文档章节】")
        for title, content in doc.sections.items():
            parts.append(f"\n【{title}】\n{content[:500]}")  # 每节最多 500 字

    return "\n".join(parts)


async def extract_relations(doc: ParsedDocument) -> list[ExtractedRelationDraft]:
    """
    从 ParsedDocument 抽取候选关系。

    自动判断模式：
    - ANTHROPIC_API_KEY 存在 → 调用 Claude API
    - 否则 → 若 ALLOW_LLM_MOCK=true，从 demo JSON 返回 Mock；若 false（上线）则报错并打日志

    所有候选关系均经过 EntityResolver 实体解析。
    """
    api_key = (settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "") or "").strip()

    if api_key:
        raw_relations = await _extract_via_llm(doc, api_key)
    else:
        if not settings.ALLOW_LLM_MOCK:
            logger.error(
                "llm_extraction_blocked",
                reason="no_api_key_mock_disabled",
                env=settings.ENV,
                allow_llm_mock=settings.ALLOW_LLM_MOCK,
                template=str(doc.template_type.value),
                hint="配置 ANTHROPIC_API_KEY，或开发环境将 ALLOW_LLM_MOCK=true",
            )
            raise LlmExtractionUnavailableError(
                "未配置 ANTHROPIC_API_KEY，且已关闭演示抽取（ALLOW_LLM_MOCK=false），无法执行关系抽取。",
                template=str(doc.template_type.value),
            )
        logger.info(
            "llm_mock_mode",
            reason="ANTHROPIC_API_KEY not set",
            template=doc.template_type,
            allow_llm_mock=settings.ALLOW_LLM_MOCK,
        )
        raw_relations = _mock_raw_for_template(doc.template_type)

    return _build_drafts(raw_relations)


async def _extract_via_llm(
    doc: ParsedDocument,
    api_key: str,
) -> list[dict[str, Any]]:
    """调用 Claude API 抽取关系，返回原始 dict 列表。"""
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        content = _build_content(doc)
        user_prompt = _USER_PROMPT_TMPL.format(
            template_type=doc.template_type,
            content=content,
        )

        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = message.content[0].text.strip()
        # 尝试提取 JSON 块
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        relations: list[dict[str, Any]] = json.loads(text)
        logger.info(
            "llm_extraction_done",
            template=doc.template_type,
            relation_count=len(relations),
        )
        return relations

    except Exception as e:
        logger.error(
            "llm_extraction_failed",
            error=str(e),
            template=doc.template_type,
            allow_llm_mock=settings.ALLOW_LLM_MOCK,
        )
        if not settings.ALLOW_LLM_MOCK:
            logger.error(
                "llm_no_mock_fallback",
                reason="allow_llm_mock_disabled",
                template=str(doc.template_type.value),
            )
            raise LlmExtractionUnavailableError(
                "LLM 调用失败且未启用 Mock 降级（ALLOW_LLM_MOCK=false），请检查模型服务与密钥配置。",
                template=str(doc.template_type.value),
            ) from e
        return _mock_raw_for_template(doc.template_type)


def _build_drafts(raw: list[dict[str, Any]]) -> list[ExtractedRelationDraft]:
    """将 LLM 输出的原始字典列表转换为 ExtractedRelationDraft 列表。"""
    drafts: list[ExtractedRelationDraft] = []

    for item in raw:
        try:
            src_name = item.get("source_node_name", "")
            src_type = item.get("source_node_type", "Unknown")
            tgt_name = item.get("target_node_name", "")
            tgt_type = item.get("target_node_type", "Unknown")

            src_entity, tgt_entity = _resolver.resolve_pair(
                src_name, src_type, tgt_name, tgt_type,
            )

            # 未匹配到别名的节点，置信度降惩 0.05
            confidence = float(item.get("confidence", 0.70))
            if not src_entity.exact_match or not tgt_entity.exact_match:
                confidence = max(0.45, confidence - 0.05)

            drafts.append(ExtractedRelationDraft(
                source_node_id=src_entity.node_id,
                source_node_name=src_entity.canonical_name,
                source_node_type=src_type,
                target_node_id=tgt_entity.node_id,
                target_node_name=tgt_entity.canonical_name,
                target_node_type=tgt_type,
                relation_type=item.get("relation_type", "UNKNOWN__RELATES_TO__UNKNOWN"),
                confidence=min(0.85, confidence),  # 硬上限 0.85
                evidence=str(item.get("evidence", ""))[:200],
                reasoning=str(item.get("reasoning", ""))[:100],
            ))

        except Exception as e:
            logger.warning("draft_build_error", error=str(e), item=item)
            continue

    return drafts


async def extract_relations_plain_text(text: str, source_filename: str = "public_knowledge.txt") -> list[ExtractedRelationDraft]:
    """
    从纯文本抽取候选关系（公开知识页）。
    与文档上传共用 LLM / Mock 分支逻辑。
    """
    body = (text or "").strip()
    if not body:
        return []
    doc = ParsedDocument(
        template_type=TemplateType.UNKNOWN,
        source_filename=source_filename,
        sections={"正文": body[:12000]},
    )
    return await extract_relations(doc)
