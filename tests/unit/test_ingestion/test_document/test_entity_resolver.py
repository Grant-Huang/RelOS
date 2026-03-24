"""
tests/unit/test_ingestion/test_document/test_entity_resolver.py
-----------------------------------------------------------------
实体别名解析器单元测试。
"""
from __future__ import annotations

import pytest

from relos.ingestion.document.entity_resolver import EntityResolver


class TestEntityResolver:

    def setup_method(self) -> None:
        self.resolver = EntityResolver()

    # ─── 精确匹配 ──────────────────────────────────────────────────

    def test_resolve_machine_by_alias(self) -> None:
        result = self.resolver.resolve("1号焊接机", "Machine")
        assert result.node_id == "machine-M3"
        assert result.exact_match is True

    def test_resolve_machine_case_insensitive(self) -> None:
        result = self.resolver.resolve("M3", "Machine")
        assert result.node_id == "machine-M3"

    def test_resolve_supplier_alias(self) -> None:
        result = self.resolver.resolve("华盛钢材", "Supplier")
        assert result.node_id == "supplier-A"

    def test_resolve_material_alias(self) -> None:
        result = self.resolver.resolve("Q235钢板", "Material")
        assert result.node_id == "material-steel-q235"

    def test_resolve_operator_alias(self) -> None:
        result = self.resolver.resolve("李工", "Operator")
        assert result.node_id == "operator-LiGong"

    def test_resolve_component_alias(self) -> None:
        result = self.resolver.resolve("轴承", "Component")
        assert result.node_id == "component-bearing-M3"

    def test_resolve_failure_mode_alias(self) -> None:
        result = self.resolver.resolve("轴承磨损", "FailureMode")
        assert result.node_id == "fm-bearing-wear"

    # ─── 全局扁平查找（不指定 type）──────────────────────────────────

    def test_resolve_without_type(self) -> None:
        result = self.resolver.resolve("华盛钢材")
        assert result.node_id == "supplier-A"
        assert result.node_type == "Supplier"

    def test_resolve_line_without_type(self) -> None:
        result = self.resolver.resolve("焊接线")
        assert result.node_id == "line-L2"

    # ─── 未知实体 → 生成占位 ID ────────────────────────────────────

    def test_resolve_unknown_generates_id(self) -> None:
        result = self.resolver.resolve("未知设备XYZ", "Machine")
        assert result.node_id.startswith("machine-")
        assert result.exact_match is False

    def test_resolve_unknown_no_type(self) -> None:
        result = self.resolver.resolve("完全不知道的东西")
        assert result.exact_match is False
        assert result.node_type == "Unknown"

    # ─── 动态添加别名 ──────────────────────────────────────────────

    def test_add_alias_and_resolve(self) -> None:
        self.resolver.add_alias("特殊设备99", "machine-X99", "Machine", "特殊设备 X99")
        result = self.resolver.resolve("特殊设备99", "Machine")
        assert result.node_id == "machine-X99"
        assert result.exact_match is True

    def test_dynamic_alias_overrides_builtin(self) -> None:
        # 动态别名优先级高于内置
        self.resolver.add_alias("李工", "operator-custom", "Operator", "自定义李工")
        result = self.resolver.resolve("李工", "Operator")
        assert result.node_id == "operator-custom"

    # ─── resolve_pair ──────────────────────────────────────────────

    def test_resolve_pair(self) -> None:
        src, tgt = self.resolver.resolve_pair(
            "1号焊接机", "Machine",   # 使用已知别名
            "轴承磨损", "FailureMode",
        )
        assert src.node_id == "machine-M3"
        assert tgt.node_id == "fm-bearing-wear"

    # ─── 带空格/连字符的别名 ───────────────────────────────────────

    def test_resolve_with_spaces(self) -> None:
        result = self.resolver.resolve("Q235 钢板", "Material")
        assert result.node_id == "material-steel-q235"

    def test_resolve_id_key(self) -> None:
        # "machine-m3" normalize → "machinem3"，在表中存在
        result = self.resolver.resolve("machine-m3", "Machine")
        assert result.node_id == "machine-M3"
