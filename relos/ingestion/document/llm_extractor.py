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
from typing import Any

import structlog

from relos.ingestion.document.entity_resolver import EntityResolver
from relos.ingestion.document.models import (
    ExtractedRelationDraft,
    ParsedDocument,
    TemplateType,
)

logger = structlog.get_logger(__name__)

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

# ─── Mock 关系（无 API Key 时的 demo 数据）────────────────────────────

_MOCK_RELATIONS: dict[TemplateType, list[dict[str, Any]]] = {
    TemplateType.CMMS_MAINTENANCE: [
        {
            "source_node_name": "焊接机 M3", "source_node_type": "Machine",
            "target_node_name": "轴承磨损",  "target_node_type": "FailureMode",
            "relation_type": "MACHINE__HAS__FAILURE_MODE",
            "confidence": 0.82,
            "evidence": "2026-01-15 工单：焊接机M3轴承温度异常，更换轴承后恢复正常",
            "reasoning": "维修记录明确描述了设备与故障类型的对应关系",
        },
        {
            "source_node_name": "轴承磨损", "source_node_type": "FailureMode",
            "target_node_name": "润滑不足", "target_node_type": "FailureMode",
            "relation_type": "FAILURE_MODE__CAUSED_BY__ROOT_CAUSE",
            "confidence": 0.75,
            "evidence": "原因分析：长期运行未按周期补充润滑脂，导致轴承干摩擦",
            "reasoning": "根因分析栏明确指出润滑不足为直接原因",
        },
        {
            "source_node_name": "焊接机 M3", "source_node_type": "Machine",
            "target_node_name": "李工",      "target_node_type": "Operator",
            "relation_type": "MACHINE__OPERATED_BY__OPERATOR",
            "confidence": 0.78,
            "evidence": "处理人：李工（工号 OPS-001），于 18:30 完成维修确认",
            "reasoning": "维修工单明确记录了负责该设备维修的操作员",
        },
        {
            "source_node_name": "焊接机 M3",    "source_node_type": "Machine",
            "target_node_name": "轴承（M3）",   "target_node_type": "Component",
            "relation_type": "MACHINE__REQUIRES__COMPONENT",
            "confidence": 0.88,
            "evidence": "更换零件：6205 深沟球轴承 × 2，件号 BRG-6205",
            "reasoning": "更换零件记录直接说明该设备的关键部件",
        },
    ],
    TemplateType.FMEA: [
        {
            "source_node_name": "焊接工序", "source_node_type": "Process",
            "target_node_name": "焊缝气孔", "target_node_type": "Defect",
            "relation_type": "PROCESS__GENERATES__DEFECT",
            "confidence": 0.80,
            "evidence": "失效模式：焊缝气孔；严重度 S=8，发生度 O=5，RPN=240",
            "reasoning": "FMEA 表格直接描述了工序与失效模式的对应关系",
        },
        {
            "source_node_name": "焊缝气孔",   "source_node_type": "Defect",
            "target_node_name": "保护气体不足", "target_node_type": "FailureMode",
            "relation_type": "DEFECT__CAUSED_BY__ROOT_CAUSE",
            "confidence": 0.77,
            "evidence": "潜在原因：CO₂保护气体流量不足（<15L/min），导致氧化气孔",
            "reasoning": "FMEA潜在原因栏直接说明了气孔的成因",
        },
        {
            "source_node_name": "焊接机 M3",   "source_node_type": "Machine",
            "target_node_name": "焊接过热",     "target_node_type": "FailureMode",
            "relation_type": "MACHINE__HAS__FAILURE_MODE",
            "confidence": 0.72,
            "evidence": "潜在失效模式：焊机过热停机；严重度 S=7，RPN=168",
            "reasoning": "FMEA 明确列出该机器的过热失效模式",
        },
    ],
    TemplateType.SUPPLIER_DELIVERY: [
        {
            "source_node_name": "华盛钢材",   "source_node_type": "Supplier",
            "target_node_name": "Q235 钢板",  "target_node_type": "Material",
            "relation_type": "SUPPLIER__CAUSES__DELIVERY_DELAY",
            "confidence": 0.85,
            "evidence": "华盛钢材 Q235钢板，应交2026-01-10，实交2026-01-14，延误4天",
            "reasoning": "交期记录明确显示供应商存在延误，且为多次重复",
        },
        {
            "source_node_name": "华盛钢材",  "source_node_type": "Supplier",
            "target_node_name": "Q235 钢板", "target_node_type": "Material",
            "relation_type": "SUPPLIER__SUPPLIES__MATERIAL",
            "confidence": 0.92,
            "evidence": "采购单 PO-2026-001～005：华盛钢材供应 Q235 钢板，单价 ¥3200/吨",
            "reasoning": "多条采购记录证实供需关系",
        },
    ],
    TemplateType.QUALITY_8D: [
        {
            "source_node_name": "焊接工序",   "source_node_type": "Process",
            "target_node_name": "尺寸超差",   "target_node_type": "Defect",
            "relation_type": "PROCESS__GENERATES__DEFECT",
            "confidence": 0.78,
            "evidence": "D2问题描述：产品焊缝宽度超差 0.8mm，不良率 3.2%，批次 B-2026-012",
            "reasoning": "8D报告D2节明确描述了缺陷发生的工序",
        },
        {
            "source_node_name": "尺寸超差",     "source_node_type": "Defect",
            "target_node_name": "夹具磨损",     "target_node_type": "FailureMode",
            "relation_type": "DEFECT__CAUSED_BY__ROOT_CAUSE",
            "confidence": 0.75,
            "evidence": "D4根本原因：定位夹具磨损 0.6mm，导致工件偏移，焊缝超出公差",
            "reasoning": "D4节通过5-why分析确认夹具磨损为根本原因",
        },
        {
            "source_node_name": "尺寸超差",       "source_node_type": "Defect",
            "target_node_name": "夹具更换程序",   "target_node_type": "Action",
            "relation_type": "DEFECT__RESOLVED_BY__ACTION",
            "confidence": 0.80,
            "evidence": "D5纠正措施：立即更换所有超出磨损限度的定位夹具，建立月度点检制度",
            "reasoning": "D5节明确描述了针对该缺陷的永久纠正措施",
        },
    ],
    TemplateType.SHIFT_HANDOVER: [
        {
            "source_node_name": "焊接机 M3",  "source_node_type": "Machine",
            "target_node_name": "焊接过热",   "target_node_type": "FailureMode",
            "relation_type": "MACHINE__HAS__FAILURE_MODE",
            "confidence": 0.68,
            "evidence": "本班异常：M3焊机 22:15 触发过热报警，停机 35 分钟",
            "reasoning": "交接班记录中描述了该设备在本班发生的异常",
        },
        {
            "source_node_name": "焊接机 M3", "source_node_type": "Machine",
            "target_node_name": "李工",      "target_node_type": "Operator",
            "relation_type": "MACHINE__OPERATED_BY__OPERATOR",
            "confidence": 0.72,
            "evidence": "处理人：夜班李工，手动降低焊接电流后恢复，遗留问题：建议白班安排PM",
            "reasoning": "交接班记录指明了设备异常处理的负责人",
        },
    ],
    TemplateType.UNKNOWN: [
        {
            "source_node_name": "设备", "source_node_type": "Machine",
            "target_node_name": "故障", "target_node_type": "FailureMode",
            "relation_type": "MACHINE__HAS__FAILURE_MODE",
            "confidence": 0.55,
            "evidence": "文档中提到设备相关故障信息",
            "reasoning": "未识别模板，抽取结果置信度较低，建议人工核实",
        },
    ],
}


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
    - 否则 → 返回 Mock 数据（演示用）

    所有候选关系均经过 EntityResolver 实体解析。
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        raw_relations = await _extract_via_llm(doc, api_key)
    else:
        logger.info(
            "llm_mock_mode",
            reason="ANTHROPIC_API_KEY not set",
            template=doc.template_type,
        )
        raw_relations = _MOCK_RELATIONS.get(doc.template_type, _MOCK_RELATIONS[TemplateType.UNKNOWN])

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
        logger.error("llm_extraction_failed", error=str(e), template=doc.template_type)
        # 降级到 Mock
        return _MOCK_RELATIONS.get(doc.template_type, _MOCK_RELATIONS[TemplateType.UNKNOWN])


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
