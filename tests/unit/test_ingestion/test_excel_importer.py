"""
tests/unit/test_ingestion/test_excel_importer.py
-------------------------------------------------
Excel 导入器单元测试。

使用 openpyxl 生成内存中的 Excel 文件进行测试，
无需磁盘文件或外部服务。
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from relos.ingestion.excel_importer import (
    REQUIRED_FIELDS,
    ExcelImporter,
    ImportResult,
    RowError,
)

# ─── 辅助：在内存中构建 Excel 字节流 ─────────────────────────────────

def make_excel_bytes(rows: list[list[Any]]) -> bytes:
    """
    根据行数据（含表头）生成 xlsx 字节流。
    rows[0] 必须是表头行。
    """
    pytest.importorskip("openpyxl", reason="openpyxl 未安装，跳过 Excel 测试")
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── 列映射测试 ───────────────────────────────────────────────────────

class TestColumnMapping:

    def test_english_headers_recognized(self) -> None:
        """标准英文列名应被识别"""
        importer = ExcelImporter()
        header = (
            "source_node_id", "source_node_type",
            "target_node_id", "target_node_type",
            "relation_type",
        )
        col_map = importer._build_col_map(header)
        assert col_map == {
            0: "source_node_id",
            1: "source_node_type",
            2: "target_node_id",
            3: "target_node_type",
            4: "relation_type",
        }

    def test_chinese_headers_recognized(self) -> None:
        """中文列名应被映射到内部字段名"""
        importer = ExcelImporter()
        header = ("起始节点ID", "起始节点类型", "目标节点ID", "目标节点类型", "关系类型")
        col_map = importer._build_col_map(header)
        for _, field_name in col_map.items():
            assert field_name in REQUIRED_FIELDS

    def test_unknown_headers_ignored(self) -> None:
        """未知列名应被忽略，不影响已知列的映射"""
        importer = ExcelImporter()
        header = ("source_node_id", "unknown_column_xyz", "target_node_id")
        col_map = importer._build_col_map(header)
        assert 1 not in col_map  # unknown_column_xyz 被忽略
        assert 0 in col_map
        assert 2 in col_map


# ─── 行解析测试 ───────────────────────────────────────────────────────

class TestRowParsing:

    def setup_method(self) -> None:
        self.importer = ExcelImporter()
        self.col_map = {
            0: "source_node_id",
            1: "source_node_type",
            2: "target_node_id",
            3: "target_node_type",
            4: "relation_type",
            5: "confidence",
        }

    def test_valid_row_parses_to_relation_object(self) -> None:
        """合法行应解析为有效的 RelationObject"""
        row = ("CNC-M1", "Device", "ALM-BEARING", "Alarm", "DEVICE__TRIGGERS__ALARM", 0.85)
        relation = self.importer._parse_row(row, self.col_map, 2)

        assert relation.source_node_id == "CNC-M1"
        assert relation.target_node_id == "ALM-BEARING"
        assert relation.relation_type == "DEVICE__TRIGGERS__ALARM"
        assert relation.confidence == 0.85

    def test_relation_type_uppercased(self) -> None:
        """relation_type 应自动转为大写"""
        row = ("CNC-M1", "Device", "ALM", "Alarm", "device__triggers__alarm", 0.8)
        relation = self.importer._parse_row(row, self.col_map, 2)
        assert relation.relation_type == "DEVICE__TRIGGERS__ALARM"

    def test_default_confidence_applied(self) -> None:
        """无 confidence 列时应使用默认值"""
        col_map = {k: v for k, v in self.col_map.items() if v != "confidence"}
        row = ("CNC-M1", "Device", "ALM", "Alarm", "DEVICE__TRIGGERS__ALARM")
        importer = ExcelImporter(default_confidence=0.75)
        relation = importer._parse_row(row, col_map, 2)
        assert relation.confidence == 0.75

    def test_confidence_out_of_range_raises(self) -> None:
        """置信度超出 [0,1] 范围应抛出 ValidationError"""
        from pydantic import ValidationError

        row = ("CNC-M1", "Device", "ALM", "Alarm", "DEVICE__TRIGGERS__ALARM", 1.5)
        with pytest.raises(ValidationError):
            self.importer._parse_row(row, self.col_map, 2)


# ─── 端到端解析测试（需要 openpyxl）─────────────────────────────────

class TestEndToEndParsing:

    @pytest.mark.unit
    def test_parse_valid_excel(self) -> None:
        """完整的有效 Excel 文件应全部解析成功"""
        pytest.importorskip("openpyxl")

        rows: list[list[Any]] = [
            ["source_node_id", "source_node_type", "target_node_id", "target_node_type",
             "relation_type", "confidence"],
            ["CNC-M1", "Device", "ALM-001", "Alarm", "DEVICE__TRIGGERS__ALARM", 0.85],
            ["CNC-M1", "Device", "BEARING-01", "Component", "DEVICE__HAS__COMPONENT", 0.92],
        ]
        content = make_excel_bytes(rows)
        importer = ExcelImporter()
        result = importer.parse_bytes(content)

        assert result.total_rows == 2
        assert result.success_count == 2
        assert result.failed_count == 0
        assert result.accuracy == 1.0
        assert len(result.relations) == 2

    @pytest.mark.unit
    def test_parse_with_invalid_rows(self) -> None:
        """包含无效行的文件：有效行正常导入，无效行记录错误"""
        pytest.importorskip("openpyxl")

        rows: list[list[Any]] = [
            ["source_node_id", "source_node_type", "target_node_id", "target_node_type",
             "relation_type", "confidence"],
            ["CNC-M1", "Device", "ALM-001", "Alarm", "DEVICE__TRIGGERS__ALARM", 0.85],  # 有效
            ["CNC-M1", "Device", "ALM-002", "Alarm", "DEVICE__TRIGGERS__ALARM", 2.0],   # 置信度超范围  # noqa: E501
        ]
        content = make_excel_bytes(rows)
        importer = ExcelImporter()
        result = importer.parse_bytes(content)

        assert result.total_rows == 2
        assert result.success_count == 1
        assert result.failed_count == 1
        assert len(result.errors) == 1

    @pytest.mark.unit
    def test_parse_empty_rows_skipped(self) -> None:
        """完全空行应被跳过，不计入 total_rows"""
        pytest.importorskip("openpyxl")

        rows: list[list[Any]] = [
            ["source_node_id", "source_node_type", "target_node_id", "target_node_type", "relation_type"],  # noqa: E501
            ["CNC-M1", "Device", "ALM-001", "Alarm", "DEVICE__TRIGGERS__ALARM"],
            [None, None, None, None, None],  # 空行
        ]
        content = make_excel_bytes(rows)
        importer = ExcelImporter()
        result = importer.parse_bytes(content)

        assert result.total_rows == 1
        assert result.success_count == 1

    @pytest.mark.unit
    def test_missing_required_columns_raises(self) -> None:
        """缺少必填列时应抛出 ValueError"""
        pytest.importorskip("openpyxl")

        rows: list[list[Any]] = [
            ["source_node_id", "confidence"],  # 缺少 target_node_id 等必填列
            ["CNC-M1", 0.85],
        ]
        content = make_excel_bytes(rows)
        importer = ExcelImporter()

        with pytest.raises(ValueError, match="缺少必填列"):
            importer.parse_bytes(content)

    @pytest.mark.unit
    def test_chinese_headers_work(self) -> None:
        """使用中文列名的 Excel 应正常解析"""
        pytest.importorskip("openpyxl")

        rows: list[list[Any]] = [
            ["起始节点ID", "起始节点类型", "目标节点ID", "目标节点类型", "关系类型", "置信度"],
            ["CNC-M1", "Device", "ALM-001", "Alarm", "DEVICE__TRIGGERS__ALARM", 0.85],
        ]
        content = make_excel_bytes(rows)
        importer = ExcelImporter()
        result = importer.parse_bytes(content)

        assert result.success_count == 1
        assert result.relations[0].source_node_id == "CNC-M1"


# ─── ImportResult 统计测试 ────────────────────────────────────────────

class TestImportResult:

    def test_accuracy_zero_when_no_rows(self) -> None:
        result = ImportResult(total_rows=0)
        assert result.accuracy == 0.0

    def test_accuracy_calculated_correctly(self) -> None:
        result = ImportResult(total_rows=100, success_count=95, failed_count=5)
        assert result.accuracy == 0.95

    def test_summary_includes_required_fields(self) -> None:
        result = ImportResult(total_rows=10, success_count=9, failed_count=1)
        result.errors.append(RowError(row_number=5, raw_data={}, error="test error"))
        summary = result.summary()
        assert "total_rows" in summary
        assert "accuracy" in summary
        assert "errors" in summary
        assert summary["errors"][0]["row"] == 5
