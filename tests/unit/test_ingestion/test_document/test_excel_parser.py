"""
tests/unit/test_ingestion/test_document/test_excel_parser.py
--------------------------------------------------------------
Excel 解析器单元测试（纯内存，无 Neo4j 依赖）。
"""
from __future__ import annotations

import io

import openpyxl
import pytest

from relos.ingestion.document.excel_parser import parse_excel, _detect_template
from relos.ingestion.document.models import TemplateType


def _make_xlsx(headers: list[str], rows: list[list[str]]) -> bytes:
    """在内存中构造 xlsx 文件字节。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── 模板检测 ──────────────────────────────────────────────────────

class TestDetectTemplate:

    def test_detects_cmms(self) -> None:
        headers = ["工单号", "设备编号", "设备名称", "故障现象", "故障原因", "处理措施", "耗时"]
        assert _detect_template(headers) == TemplateType.CMMS_MAINTENANCE

    def test_detects_fmea(self) -> None:
        headers = ["工序/功能", "潜在失效模式", "严重度S", "发生度O", "探测度D", "RPN"]
        assert _detect_template(headers) == TemplateType.FMEA

    def test_detects_supplier(self) -> None:
        headers = ["采购单号", "供应商名称", "物料名称", "应交日期", "实交日期", "延误天数"]
        assert _detect_template(headers) == TemplateType.SUPPLIER_DELIVERY

    def test_unknown_template(self) -> None:
        headers = ["列A", "列B", "列C"]
        assert _detect_template(headers) == TemplateType.UNKNOWN

    def test_partial_match_still_detects(self) -> None:
        # 即使只有部分关键词也能检测
        headers = ["设备", "故障", "其他列"]
        result = _detect_template(headers)
        assert result == TemplateType.CMMS_MAINTENANCE


# ─── CMMS 维修工单解析 ─────────────────────────────────────────────

class TestParseCMMS:

    def setup_method(self) -> None:
        self.headers = ["工单号", "设备编号", "设备名称", "故障日期", "故障现象",
                        "故障原因", "处理措施", "更换零件", "处理人", "耗时(小时)", "结论"]
        self.rows = [
            ["WO-001", "M3", "焊接机M3", "2026-01-15", "轴承异响", "轴承磨损", "更换轴承", "6205轴承", "李工", "2.5", "已修复"],
            ["WO-002", "M4", "冲压机M4", "2026-01-18", "电气故障", "保险丝熔断", "更换保险丝", "FU-10A", "王工", "0.5", "已修复"],
        ]
        self.xlsx_bytes = _make_xlsx(self.headers, self.rows)

    def test_template_type(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "test.xlsx")
        assert doc.template_type == TemplateType.CMMS_MAINTENANCE

    def test_row_count(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "test.xlsx")
        assert len(doc.rows) == 2

    def test_field_mapping(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "test.xlsx")
        row0 = doc.rows[0]
        assert row0.fields.get("order_id") == "WO-001"
        assert row0.fields.get("machine_name") == "焊接机M3"
        assert row0.fields.get("symptom") == "轴承异响"
        assert row0.fields.get("root_cause") == "轴承磨损"
        assert row0.fields.get("operator") == "李工"

    def test_hours_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "test.xlsx")
        assert doc.rows[0].fields.get("hours") == "2.5"

    def test_source_filename(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "cmms_test.xlsx")
        assert doc.source_filename == "cmms_test.xlsx"


# ─── FMEA 解析 ────────────────────────────────────────────────────

class TestParseFMEA:

    def setup_method(self) -> None:
        self.headers = ["工序/功能", "潜在失效模式", "潜在失效影响",
                        "严重度S", "潜在原因/机制", "发生度O",
                        "现行控制措施", "探测度D", "RPN", "建议措施"]
        self.rows = [
            ["焊接", "焊缝气孔", "强度下降", "8", "保护气体不足", "5", "目视检查", "6", "240", "增加气体流量检查"],
            ["冲压", "尺寸超差", "装配困难", "7", "模具磨损", "4", "首件检验", "5", "140", "定期更换模具"],
        ]
        self.xlsx_bytes = _make_xlsx(self.headers, self.rows)

    def test_template_type(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "fmea.xlsx")
        assert doc.template_type == TemplateType.FMEA

    def test_failure_mode_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "fmea.xlsx")
        assert doc.rows[0].fields.get("failure_mode") == "焊缝气孔"

    def test_rpn_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "fmea.xlsx")
        assert doc.rows[0].fields.get("rpn") == "240"

    def test_severity_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "fmea.xlsx")
        assert doc.rows[0].fields.get("severity") == "8"


# ─── 供应商交期解析 ───────────────────────────────────────────────

class TestParseSupplier:

    def setup_method(self) -> None:
        self.headers = ["采购单号", "供应商名称", "物料编码", "物料名称",
                        "应交日期", "实交日期", "延误天数", "延误原因"]
        self.rows = [
            ["PO-001", "华盛钢材", "MAT-Q235", "Q235钢板", "2026-01-10", "2026-01-14", "4", "原材料短缺"],
            ["PO-002", "东方塑料", "MAT-ABS", "ABS塑料", "2026-01-12", "2026-01-12", "0", ""],
        ]
        self.xlsx_bytes = _make_xlsx(self.headers, self.rows)

    def test_template_type(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "supplier.xlsx")
        assert doc.template_type == TemplateType.SUPPLIER_DELIVERY

    def test_supplier_name_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "supplier.xlsx")
        assert doc.rows[0].fields.get("supplier_name") == "华盛钢材"

    def test_delay_days_field(self) -> None:
        doc = parse_excel(self.xlsx_bytes, "supplier.xlsx")
        assert doc.rows[0].fields.get("delay_days") == "4"
        assert doc.rows[1].fields.get("delay_days") == "0"


# ─── 边界情况 ─────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_rows_skipped(self) -> None:
        headers = ["工单号", "设备编号", "故障现象", "故障原因", "处理措施"]
        rows = [
            ["WO-001", "M3", "振动", "轴承", "更换"],
            ["", "", "", "", ""],   # 全空行，应跳过
            ["WO-002", "M4", "过热", "散热", "清洁"],
        ]
        xlsx = _make_xlsx(headers, rows)
        doc = parse_excel(xlsx, "test.xlsx")
        assert len(doc.rows) == 2

    def test_invalid_file_raises(self) -> None:
        with pytest.raises(ValueError, match="无法读取"):
            parse_excel(b"not an xlsx file", "bad.xlsx")

    def test_empty_file_raises(self) -> None:
        wb = openpyxl.Workbook()
        buf = io.BytesIO()
        wb.save(buf)
        # 空工作簿（只有表头行都没有）—— 实际 openpyxl 会有空 active sheet
        # 这里测试只有表头、没有数据行
        xlsx = _make_xlsx(["工单号", "设备编号", "故障现象"], [])
        doc = parse_excel(xlsx, "empty.xlsx")
        assert len(doc.rows) == 0
