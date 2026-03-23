"""
tests/unit/test_ingestion/test_pipeline.py
-------------------------------------------
IngestionPipeline 和 AlarmRelationExtractor 单元测试。
无外部依赖（纯计算逻辑）。
"""

from __future__ import annotations

import pytest

from relos.core.models import RelationObject, RelationStatus, SourceType
from relos.ingestion.pipeline import AlarmRelationExtractor, IngestionPipeline

# ─── 辅助工厂函数 ─────────────────────────────────────────────────────

def make_relation(
    confidence: float = 0.80,
    provenance: SourceType = SourceType.MANUAL_ENGINEER,
    status: RelationStatus = RelationStatus.ACTIVE,
) -> RelationObject:
    return RelationObject(
        relation_type="DEVICE__TRIGGERS__ALARM",
        source_node_id="device-M1",
        source_node_type="Device",
        target_node_id="ALM-001",
        target_node_type="Alarm",
        confidence=confidence,
        provenance=provenance,
        status=status,
    )


# ─── IngestionPipeline 测试 ───────────────────────────────────────────

@pytest.mark.unit
class TestIngestionPipeline:

    def setup_method(self) -> None:
        self.pipeline = IngestionPipeline()

    def test_valid_manual_engineer_passes(self) -> None:
        """manual_engineer 置信度 0.92 在 [0.9, 1.0] 内，应通过"""
        relation = make_relation(confidence=0.92, provenance=SourceType.MANUAL_ENGINEER)
        result = self.pipeline.validate_and_normalize(relation)
        assert result.confidence == 0.92

    def test_valid_sensor_realtime_passes(self) -> None:
        """sensor_realtime 置信度 0.85 在 [0.8, 0.95] 内，应通过"""
        relation = make_relation(confidence=0.85, provenance=SourceType.SENSOR_REALTIME)
        result = self.pipeline.validate_and_normalize(relation)
        assert result.confidence == 0.85

    def test_confidence_below_range_clamped_up(self) -> None:
        """置信度低于来源最低值时，应夹紧到该来源的最低值"""
        # manual_engineer 最低 0.90，输入 0.50 应夹紧到 0.90
        relation = make_relation(confidence=0.50, provenance=SourceType.MANUAL_ENGINEER)
        result = self.pipeline.validate_and_normalize(relation)
        assert result.confidence == 0.90

    def test_confidence_above_range_clamped_down(self) -> None:
        """置信度超过来源最高值时，应夹紧到该来源的最高值"""
        # inference 最高 0.75，输入 0.90 应夹紧到 0.75
        relation = make_relation(confidence=0.90, provenance=SourceType.INFERENCE)
        result = self.pipeline.validate_and_normalize(relation)
        assert result.confidence == 0.75

    def test_llm_extracted_forced_pending_review(self) -> None:
        """LLM 来源尝试设为 active，应被强制改为 pending_review"""
        relation = make_relation(
            confidence=0.70,
            provenance=SourceType.LLM_EXTRACTED,
            status=RelationStatus.ACTIVE,
        )
        result = self.pipeline.validate_and_normalize(relation)
        assert result.status == RelationStatus.PENDING_REVIEW

    def test_manual_engineer_active_unchanged(self) -> None:
        """manual_engineer 来源设为 active 应保持不变"""
        relation = make_relation(
            confidence=0.92,
            provenance=SourceType.MANUAL_ENGINEER,
            status=RelationStatus.ACTIVE,
        )
        result = self.pipeline.validate_and_normalize(relation)
        assert result.status == RelationStatus.ACTIVE

    def test_confidence_ranges_per_source_type(self) -> None:
        """验证各来源的置信度范围配置（设计文档 §3.2）"""
        expected_ranges = {
            SourceType.MANUAL_ENGINEER: (0.90, 1.00),
            SourceType.SENSOR_REALTIME: (0.80, 0.95),
            SourceType.MES_STRUCTURED:  (0.75, 0.90),
            SourceType.LLM_EXTRACTED:   (0.50, 0.85),
            SourceType.INFERENCE:       (0.40, 0.75),
        }
        for source_type, (expected_min, expected_max) in expected_ranges.items():
            actual = IngestionPipeline.CONFIDENCE_RANGE[source_type]
            assert actual == (expected_min, expected_max), (
                f"{source_type}: 期望 {(expected_min, expected_max)}，实际 {actual}"
            )

    def test_pydantic_rejects_negative_confidence(self) -> None:
        """置信度 < 0 的关系应被 Pydantic 拒绝"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RelationObject(
                relation_type="DEVICE__TRIGGERS__ALARM",
                source_node_id="d1",
                source_node_type="Device",
                target_node_id="a1",
                target_node_type="Alarm",
                confidence=-0.1,
                provenance=SourceType.SENSOR_REALTIME,
            )

    def test_pydantic_rejects_confidence_above_one(self) -> None:
        """置信度 > 1 的关系应被 Pydantic 拒绝"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RelationObject(
                relation_type="DEVICE__TRIGGERS__ALARM",
                source_node_id="d1",
                source_node_type="Device",
                target_node_id="a1",
                target_node_type="Alarm",
                confidence=1.1,
                provenance=SourceType.SENSOR_REALTIME,
            )


# ─── AlarmRelationExtractor 测试 ──────────────────────────────────────

@pytest.mark.unit
class TestAlarmRelationExtractor:

    def setup_method(self) -> None:
        self.extractor = AlarmRelationExtractor()

    def test_extract_returns_relation_list(self) -> None:
        """extract 应返回非空的关系列表"""
        relations = self.extractor.extract(
            device_id="CNC-M1",
            alarm_id="ALM-VIB-001",
            alarm_code="VIB-001",
            alarm_description="振动超限 18.3mm/s",
        )
        assert isinstance(relations, list)
        assert len(relations) >= 1

    def test_extract_creates_device_triggers_alarm(self) -> None:
        """应生成 DEVICE__TRIGGERS__ALARM 关系，方向正确"""
        relations = self.extractor.extract(
            device_id="CNC-M1",
            alarm_id="ALM-VIB-001",
            alarm_code="VIB-001",
            alarm_description="振动超限",
        )
        rel = relations[0]
        assert rel.relation_type == "DEVICE__TRIGGERS__ALARM"
        assert rel.source_node_id == "CNC-M1"
        assert rel.target_node_id == "ALM-VIB-001"

    def test_extracted_relation_source_is_sensor_realtime(self) -> None:
        """告警关系来源应为 sensor_realtime（告警来自传感器）"""
        relations = self.extractor.extract(
            device_id="M1", alarm_id="A1", alarm_code="VIB", alarm_description="测试"
        )
        assert all(r.provenance == SourceType.SENSOR_REALTIME for r in relations)

    def test_extracted_relation_has_alarm_code_in_properties(self) -> None:
        """告警码应存储在 properties 中（供后续推理使用）"""
        relations = self.extractor.extract(
            device_id="M1", alarm_id="A1", alarm_code="VIB-007", alarm_description="测试"
        )
        assert relations[0].properties.get("alarm_code") == "VIB-007"

    def test_high_confidence_for_sensor_data(self) -> None:
        """传感器实时数据置信度应 ≥ 0.80（高可信来源）"""
        relations = self.extractor.extract(
            device_id="M1", alarm_id="A1", alarm_code="VIB", alarm_description="测试"
        )
        assert all(r.confidence >= 0.80 for r in relations)

    def test_severity_stored_in_properties(self) -> None:
        """严重程度应存储在 properties 中"""
        relations = self.extractor.extract(
            device_id="M1", alarm_id="A1", alarm_code="VIB",
            alarm_description="测试", severity="critical",
        )
        assert relations[0].properties.get("severity") == "critical"

    def test_long_description_truncated(self) -> None:
        """超长描述应被截断（防止属性过大）"""
        long_desc = "x" * 500
        relations = self.extractor.extract(
            device_id="M1", alarm_id="A1", alarm_code="VIB", alarm_description=long_desc
        )
        desc_in_props = relations[0].properties.get("description", "")
        assert len(desc_in_props) <= 200
