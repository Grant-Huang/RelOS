"""
relos/ingestion/document/word_parser.py
-----------------------------------------
docx 文件解析器（python-docx）。

职责：
  1. 识别文档模板类型（通过标题关键词）
  2. 提取章节结构（标题 → 正文段落）
  3. 提取表格内容
  4. 输出 ParsedDocument 供 LLM 抽取器使用

支持的模板：
  QUALITY_8D     - 8D 质量异常报告（含 D1–D8 章节）
  SHIFT_HANDOVER - 交接班日志（含班次信息、异常记录）

对非结构化段落，将所有内容压缩进 sections["全文"]，
让 LLM 自行决定如何抽取关系。
"""

from __future__ import annotations

import io

import structlog

try:
    from docx import Document as DocxDocument  # python-docx
    from docx.table import Table
except ImportError:
    DocxDocument = None  # type: ignore[assignment]
    Table = None         # type: ignore[assignment]

from relos.ingestion.document.models import ParsedDocument, TemplateType

logger = structlog.get_logger(__name__)

# ─── 模板签名：标题关键词集合 ─────────────────────────────────────────

_TEMPLATE_SIGNATURES: dict[TemplateType, list[str]] = {
    TemplateType.QUALITY_8D: [
        "8d", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8",
        "质量异常", "纠正措施", "根本原因", "遏制措施",
    ],
    TemplateType.SHIFT_HANDOVER: [
        "交接班", "班次", "遗留问题", "本班异常", "接班人", "交班人",
    ],
}

# 8D 标准章节标题映射
_8D_SECTION_KEYS: dict[str, str] = {
    "d1": "D1_小组成员",
    "d2": "D2_问题描述",
    "d3": "D3_临时遏制措施",
    "d4": "D4_根本原因",
    "d5": "D5_永久纠正措施",
    "d6": "D6_实施纠正措施",
    "d7": "D7_预防措施",
    "d8": "D8_小组祝贺",
}

# 交接班标准章节
_SHIFT_SECTION_KEYS: dict[str, str] = {
    "班次信息":   "班次信息",
    "本班异常":   "本班异常事件",
    "异常事件":   "本班异常事件",
    "处理情况":   "处理情况",
    "遗留问题":   "遗留问题",
    "下班注意":   "下班注意事项",
}


def _detect_template(text_content: str) -> TemplateType:
    """通过文档全文中的关键词频率识别模板类型。"""
    lower = text_content.lower()
    scores: dict[TemplateType, int] = {t: 0 for t in _TEMPLATE_SIGNATURES}
    for template, keywords in _TEMPLATE_SIGNATURES.items():
        for kw in keywords:
            if kw in lower:
                scores[template] += 1

    best = max(scores, key=lambda t: scores[t])
    if scores[best] == 0:
        return TemplateType.UNKNOWN
    return best


def _table_to_text(table: "Table") -> str:
    """将 Word 表格转为 key: value 的文本形式。"""
    lines: list[str] = []
    for row in table.rows:
        cells = [c.text.strip() for c in row.cells]
        non_empty = [c for c in cells if c]
        if non_empty:
            lines.append(" | ".join(non_empty))
    return "\n".join(lines)


def parse_word(file_bytes: bytes, filename: str) -> ParsedDocument:
    """
    解析 docx 文件为 ParsedDocument。

    解析逻辑：
    1. 遍历段落，遇到"标题"样式时开启新章节
    2. 普通段落追加到当前章节
    3. 遇到表格，序列化后追加到当前章节
    4. 模板类型通过全文关键词检测

    Args:
        file_bytes: docx 文件二进制内容
        filename:   原始文件名

    Returns:
        ParsedDocument，template_type 已自动识别
    """
    if DocxDocument is None:
        raise RuntimeError("python-docx 未安装，无法解析 Word 文件")

    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"无法读取 Word 文件 {filename}：{e}") from e

    # ── 提取所有段落和表格 ──────────────────────────────────────────
    sections: dict[str, str] = {}
    current_section = "正文"
    buffer: list[str] = []

    # 合并段落和表格（按 docx XML 顺序）
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":  # 段落
            # 找到对应的段落对象
            para_text = "".join(
                run.text for run in element.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
            )
            if not para_text.strip():
                continue

            # 检测是否为标题
            pPr = element.find(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr"
            )
            style_id = ""
            if pPr is not None:
                pStyle = pPr.find(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle"
                )
                if pStyle is not None:
                    style_id = (pStyle.get(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val"
                    ) or "").lower()

            is_heading = ("heading" in style_id or "1" in style_id or
                          any(para_text.strip().lower().startswith(k)
                              for k in ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8",
                                        "一、", "二、", "三、", "四、", "五、"]))

            if is_heading:
                # 保存前一章节
                if buffer:
                    sections[current_section] = "\n".join(buffer)
                    buffer = []
                current_section = para_text.strip()
            else:
                buffer.append(para_text.strip())

        elif tag == "tbl":  # 表格
            # 手动提取表格文本
            rows_text: list[str] = []
            ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            for tr in element.iter(f"{{{ns}}}tr"):
                cells_text = []
                for tc in tr.iter(f"{{{ns}}}tc"):
                    cell_content = "".join(
                        t.text or "" for t in tc.iter(f"{{{ns}}}t")
                    ).strip()
                    if cell_content:
                        cells_text.append(cell_content)
                if cells_text:
                    rows_text.append(" | ".join(cells_text))
            if rows_text:
                buffer.append("[表格]\n" + "\n".join(rows_text))

    # 保存最后一个章节
    if buffer:
        sections[current_section] = "\n".join(buffer)

    # 全文拼接，用于模板检测
    all_text = "\n".join(
        f"{title}\n{content}" for title, content in sections.items()
    )
    template_type = _detect_template(all_text)

    # ── 规范化章节键名 ──────────────────────────────────────────────
    section_map = _8D_SECTION_KEYS if template_type == TemplateType.QUALITY_8D else (
        _SHIFT_SECTION_KEYS if template_type == TemplateType.SHIFT_HANDOVER else {}
    )

    normalized: dict[str, str] = {}
    for raw_title, content in sections.items():
        mapped = False
        lower_title = raw_title.lower().strip()
        for key, canonical in section_map.items():
            if key in lower_title:
                normalized[canonical] = (normalized.get(canonical, "") + "\n" + content).strip()
                mapped = True
                break
        if not mapped:
            normalized[raw_title] = content

    if not normalized:
        normalized["全文"] = all_text

    logger.info(
        "word_parsed",
        filename=filename,
        template=template_type,
        section_count=len(normalized),
    )

    return ParsedDocument(
        template_type=template_type,
        source_filename=filename,
        sections=normalized,
    )
