"""
relos/ingestion/document/excel_parser.py
------------------------------------------
xlsx 文件解析器。

职责：
  1. 检测模板类型（通过列名特征识别）
  2. 提取数据行，统一转为 ParsedDocument（中间表示）
  3. 不做关系抽取，只做结构化

支持的模板：
  CMMS_MAINTENANCE  - 设备维修工单
  FMEA              - FMEA 失效模式分析
  SUPPLIER_DELIVERY - 供应商交期记录

检测策略：各模板有独特列名关键词集合，
匹配度最高的模板胜出（Hamming 相似度）。
"""

from __future__ import annotations

import io
from typing import Any

import openpyxl
import structlog

from relos.ingestion.document.models import ParsedDocument, ParsedRow, TemplateType

logger = structlog.get_logger(__name__)

# ─── 模板签名：列名关键词（中文为主，兼容英文）────────────────────────

_TEMPLATE_SIGNATURES: dict[TemplateType, list[str]] = {
    TemplateType.CMMS_MAINTENANCE: [
        "故障", "维修", "设备", "工单", "处理", "原因", "零件", "耗时",
    ],
    TemplateType.FMEA: [
        "失效", "严重度", "发生度", "探测度", "rpn", "失效模式", "潜在",
    ],
    TemplateType.SUPPLIER_DELIVERY: [
        "供应商", "交期", "延误", "采购", "物料", "应交", "实交",
    ],
}

# ─── 标准列名映射：各模板的关键列 → 内部字段名 ─────────────────────────

# CMMS 维修工单
_CMMS_COL_MAP: dict[str, str] = {
    "工单号":   "order_id",
    "设备编号": "machine_id",
    "设备名称": "machine_name",
    "故障日期": "fault_date",
    "故障现象": "symptom",
    "故障原因": "root_cause",
    "处理措施": "action",
    "更换零件": "replaced_part",
    "处理人":   "operator",
    "耗时":     "hours",
    "耗时(小时)": "hours",
    "结论":     "conclusion",
}

# FMEA
_FMEA_COL_MAP: dict[str, str] = {
    "工序":         "process",
    "功能":         "function",
    "工序/功能":    "process",
    "潜在失效模式": "failure_mode",
    "失效模式":     "failure_mode",
    "潜在失效影响": "failure_effect",
    "失效影响":     "failure_effect",
    "严重度":       "severity",
    "严重度s":      "severity",
    "潜在原因":     "root_cause",
    "潜在原因/机制": "root_cause",
    "发生度":       "occurrence",
    "发生度o":      "occurrence",
    "现行控制措施": "control",
    "探测度":       "detection",
    "探测度d":      "detection",
    "rpn":          "rpn",
    "建议措施":     "recommendation",
}

# 供应商交期
_SUPPLIER_COL_MAP: dict[str, str] = {
    "采购单号":   "po_id",
    "供应商名称": "supplier_name",
    "供应商":     "supplier_name",
    "物料编码":   "material_code",
    "物料名称":   "material_name",
    "物料":       "material_name",
    "应交日期":   "due_date",
    "实交日期":   "actual_date",
    "延误天数":   "delay_days",
    "延误原因":   "delay_reason",
    "准时":       "on_time",
}

_COL_MAPS: dict[TemplateType, dict[str, str]] = {
    TemplateType.CMMS_MAINTENANCE:  _CMMS_COL_MAP,
    TemplateType.FMEA:              _FMEA_COL_MAP,
    TemplateType.SUPPLIER_DELIVERY: _SUPPLIER_COL_MAP,
}


def _detect_template(headers: list[str]) -> TemplateType:
    """
    根据列名关键词打分，返回最可能的模板类型。
    未识别时返回 UNKNOWN。
    """
    normalized = [h.lower().strip() for h in headers]
    scores: dict[TemplateType, int] = {t: 0 for t in _TEMPLATE_SIGNATURES}

    for template, keywords in _TEMPLATE_SIGNATURES.items():
        for kw in keywords:
            for header in normalized:
                if kw in header:
                    scores[template] += 1

    best_type = max(scores, key=lambda t: scores[t])
    best_score = scores[best_type]

    if best_score == 0:
        logger.warning("template_detection_failed", headers=headers)
        return TemplateType.UNKNOWN

    logger.info(
        "template_detected",
        template=best_type,
        score=best_score,
        scores=dict(scores),
    )
    return best_type


def _map_headers(
    raw_headers: list[str],
    col_map: dict[str, str],
) -> dict[int, str]:
    """
    将 Excel 列索引映射到内部字段名。
    支持模糊匹配（包含关系，不要求完全一致）。
    返回：{col_index → field_name}
    """
    result: dict[int, str] = {}
    for i, raw in enumerate(raw_headers):
        normalized = raw.strip().lower()
        # 精确匹配优先
        if normalized in col_map:
            result[i] = col_map[normalized]
            continue
        # 模糊包含匹配
        for key, field in col_map.items():
            if key in normalized or normalized in key:
                result[i] = field
                break
    return result


def _cell_to_str(value: Any) -> str:
    """将 openpyxl 单元格值转为字符串，None 返回空字符串。"""
    if value is None:
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def parse_excel(file_bytes: bytes, filename: str) -> ParsedDocument:
    """
    解析 xlsx 文件为 ParsedDocument。

    Args:
        file_bytes: xlsx 文件的二进制内容
        filename:   原始文件名（用于日志）

    Returns:
        ParsedDocument，template_type 已自动识别

    Raises:
        ValueError: 文件格式不合法或无法读取
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as e:
        raise ValueError(f"无法读取 Excel 文件 {filename}：{e}") from e

    ws = wb.active
    if ws is None:
        raise ValueError(f"Excel 文件 {filename} 没有活动工作表")

    rows_iter = list(ws.iter_rows(values_only=True))
    if not rows_iter:
        raise ValueError(f"Excel 文件 {filename} 没有数据")

    # 第一行为表头
    raw_headers = [_cell_to_str(h) for h in rows_iter[0]]
    template_type = _detect_template(raw_headers)

    col_map = _COL_MAPS.get(template_type, {})
    col_index_map = _map_headers(raw_headers, col_map)

    parsed_rows: list[ParsedRow] = []
    for row_idx, row in enumerate(rows_iter[1:], start=1):
        # 跳过全空行
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        fields: dict[str, str] = {}
        # 映射的字段
        for col_i, field_name in col_index_map.items():
            if col_i < len(row):
                fields[field_name] = _cell_to_str(row[col_i])
        # 未映射列用原始列名保存（前缀 raw_）
        for col_i, raw_header in enumerate(raw_headers):
            if col_i not in col_index_map and col_i < len(row):
                val = _cell_to_str(row[col_i])
                if val:
                    fields[f"raw_{raw_header}"] = val

        if fields:
            parsed_rows.append(ParsedRow(row_index=row_idx, fields=fields))

    wb.close()

    logger.info(
        "excel_parsed",
        filename=filename,
        template=template_type,
        row_count=len(parsed_rows),
    )

    return ParsedDocument(
        template_type=template_type,
        source_filename=filename,
        rows=parsed_rows,
    )
