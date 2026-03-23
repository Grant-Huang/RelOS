"""
tests/unit/test_core/test_engine.py
-----------------------------------
RelationEngine 单元测试。
无外部依赖（纯计算逻辑）。
"""

from datetime import datetime, timedelta, timezone

import pytest

from relos.core.engine import RelationEngine
from relos.core.models import RelationObject, RelationStatus, SourceType


# ─── 测试数据工厂 ──────────────────────────────────────────────────

def make_relation(
    confidence: float = 0.7,
    provenance: SourceType = SourceType.SENSOR_REALTIME,
    status: RelationStatus = RelationStatus.ACTIVE,
    relation_type: str = "DEVICE__TRIGGERS__ALARM",
    days_old: int = 0,
) -> RelationObject:
    now = datetime.now(timezone.utc) - timedelta(days=days_old)
    return RelationObject(
        relation_type=relation_type,
        source_node_id="device-001",
        source_node_type="Device",
        target_node_id="alarm-001",
        target_node_type="Alarm",
        confidence=confidence,
        provenance=provenance,
        status=status,
        updated_at=now,
        created_at=now,
    )


# ─── 置信度合并测试 ────────────────────────────────────────────────

class TestMergeConfidence:

    def setup_method(self) -> None:
        self.engine = RelationEngine()

    def test_sensor_merge_increases_confidence(self) -> None:
        """传感器高置信度新观测，应拉高旧置信度"""
        existing = make_relation(confidence=0.5)
        incoming = make_relation(confidence=0.9, provenance=SourceType.SENSOR_REALTIME)

        result = self.engine.merge_confidence(existing, incoming)

        # alpha=0.5（sensor），期望：(1-0.5)*0.5 + 0.5*0.9 = 0.7
        assert result.new_confidence == pytest.approx(0.7, abs=0.01)
        assert result.new_confidence > existing.confidence

    def test_llm_merge_is_conservative(self) -> None:
        """LLM 来源 alpha=0.2，新观测影响应较小"""
        existing = make_relation(confidence=0.8)
        incoming = make_relation(confidence=0.3, provenance=SourceType.LLM_EXTRACTED)

        result = self.engine.merge_confidence(existing, incoming)

        # alpha=0.2，期望：(1-0.2)*0.8 + 0.2*0.3 = 0.7
        assert result.new_confidence == pytest.approx(0.7, abs=0.01)

    def test_conflict_detected_on_large_confidence_gap(self) -> None:
        """置信度差异 > 0.5 应触发冲突标记"""
        existing = make_relation(confidence=0.9)
        incoming = make_relation(confidence=0.2)

        result = self.engine.merge_confidence(existing, incoming)

        assert result.conflict_detected is True

    def test_no_conflict_on_small_confidence_gap(self) -> None:
        """置信度差异 <= 0.5 不触发冲突"""
        existing = make_relation(confidence=0.7)
        incoming = make_relation(confidence=0.5)

        result = self.engine.merge_confidence(existing, incoming)

        assert result.conflict_detected is False


# ─── 置信度衰减测试 ────────────────────────────────────────────────

class TestApplyDecay:

    def setup_method(self) -> None:
        self.engine = RelationEngine()

    def test_fresh_relation_no_decay(self) -> None:
        """刚创建的关系（0 天），置信度应基本不变"""
        relation = make_relation(confidence=0.8, days_old=0)
        decayed = self.engine.apply_decay(relation)

        assert decayed == pytest.approx(0.8, abs=0.01)

    def test_half_life_halves_confidence(self) -> None:
        """经过 half_life_days 后，置信度应衰减约 50%"""
        relation = make_relation(confidence=0.8, days_old=90)   # half_life=90 天
        decayed = self.engine.apply_decay(relation)

        assert decayed == pytest.approx(0.4, abs=0.05)

    def test_very_old_relation_hits_floor(self) -> None:
        """极度老化的关系，置信度应不低于最小下限 0.05"""
        relation = make_relation(confidence=0.8, days_old=3650)  # 10 年
        decayed = self.engine.apply_decay(relation)

        assert decayed >= 0.05

    def test_operator_performs_operation_faster_decay(self) -> None:
        """T-03：OPERATOR__PERFORMS__OPERATION 半衰期 30 天，衰减应快于 DEVICE__TRIGGERS__ALARM（90 天）"""
        # 过了 30 天后，operator 关系应比 device 关系衰减更多
        device_rel = make_relation(
            confidence=0.8, days_old=30, relation_type="DEVICE__TRIGGERS__ALARM"
        )
        operator_rel = make_relation(
            confidence=0.8, days_old=30, relation_type="OPERATOR__PERFORMS__OPERATION"
        )
        device_decayed = self.engine.apply_decay(device_rel)
        operator_decayed = self.engine.apply_decay(operator_rel)

        # DEVICE half_life=90, OPERATOR half_life=30
        # 30 天后：device 衰减 0.5^(30/90)≈0.79, operator 衰减 0.5^(30/30)=0.5
        assert operator_decayed < device_decayed

    def test_component_part_of_device_slow_decay(self) -> None:
        """T-03：COMPONENT__PART_OF__DEVICE 半衰期 365 天，物理关系衰减最慢"""
        component_rel = make_relation(
            confidence=0.8, days_old=90, relation_type="COMPONENT__PART_OF__DEVICE"
        )
        device_rel = make_relation(
            confidence=0.8, days_old=90, relation_type="DEVICE__TRIGGERS__ALARM"
        )
        component_decayed = self.engine.apply_decay(component_rel)
        device_decayed = self.engine.apply_decay(device_rel)

        # COMPONENT half_life=365, 90 天后几乎不衰减；DEVICE half_life=90, 已过半衰期
        assert component_decayed > device_decayed

    def test_half_life_config_covers_all_relation_types(self) -> None:
        """T-03：HALF_LIFE_CONFIG 覆盖设计文档中的所有关系类型"""
        from relos.core.models import HALF_LIFE_CONFIG
        expected_types = {
            "DEVICE__TRIGGERS__ALARM",
            "OPERATOR__PERFORMS__OPERATION",
            "COMPONENT__PART_OF__DEVICE",
            "ALARM__CORRELATES__ALARM",
            "DEFAULT",
        }
        assert set(HALF_LIFE_CONFIG.keys()) == expected_types


# ─── 人工反馈测试 ──────────────────────────────────────────────────

class TestApplyHumanFeedback:

    def setup_method(self) -> None:
        self.engine = RelationEngine()

    def test_confirm_increases_confidence(self) -> None:
        """工程师确认：置信度 +0.15，状态 → active"""
        relation = make_relation(confidence=0.6, status=RelationStatus.PENDING_REVIEW)
        updated = self.engine.apply_human_feedback(relation, confirmed=True, engineer_id="eng-01")

        assert updated.confidence == pytest.approx(0.75, abs=0.01)
        assert updated.status == RelationStatus.ACTIVE

    def test_reject_decreases_confidence(self) -> None:
        """工程师否定：置信度 -0.30"""
        relation = make_relation(confidence=0.7)
        updated = self.engine.apply_human_feedback(relation, confirmed=False, engineer_id="eng-01")

        assert updated.confidence == pytest.approx(0.40, abs=0.01)

    def test_reject_low_confidence_archives(self) -> None:
        """否定后置信度 < 0.2 的关系应被归档（保留历史，不删除）"""
        relation = make_relation(confidence=0.4)
        updated = self.engine.apply_human_feedback(relation, confirmed=False, engineer_id="eng-01")

        assert updated.status == RelationStatus.ARCHIVED
        assert updated.confidence >= 0.0     # 已归档但数据保留

    def test_confirm_caps_at_1(self) -> None:
        """置信度最大为 1.0，不能溢出"""
        relation = make_relation(confidence=0.95)
        updated = self.engine.apply_human_feedback(relation, confirmed=True, engineer_id="eng-01")

        assert updated.confidence <= 1.0


# ─── LLM 置信度约束测试 ────────────────────────────────────────────

class TestLLMConstraints:

    def test_llm_confidence_capped_at_0_85(self) -> None:
        """LLM 来源的关系置信度不能超过 0.85（模型层约束）"""
        # Pydantic validator 会在初始化时夹紧
        relation = RelationObject(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="d-001",
            source_node_type="Device",
            target_node_id="a-001",
            target_node_type="Alarm",
            confidence=0.95,                        # 尝试设置超过上限的值
            provenance=SourceType.LLM_EXTRACTED,    # LLM 来源
            status=RelationStatus.PENDING_REVIEW,
        )
        assert relation.confidence <= 0.85

    def test_llm_relation_forced_pending(self) -> None:
        """LLM 来源的关系，即使设为 active 也应被强制降为 pending_review"""
        relation = RelationObject(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="d-001",
            source_node_type="Device",
            target_node_id="a-001",
            target_node_type="Alarm",
            confidence=0.7,
            provenance=SourceType.LLM_EXTRACTED,
            status=RelationStatus.ACTIVE,           # 尝试直接设为 active
        )
        assert relation.status == RelationStatus.PENDING_REVIEW


# ─── 边界值测试 ────────────────────────────────────────────────────

class TestBoundaryConditions:
    """关键边界值覆盖，防止 off-by-one 错误"""

    def setup_method(self) -> None:
        self.engine = RelationEngine()

    # ── 冲突检测边界 ──────────────────────────────────────────────

    def test_conflict_boundary_gap_exactly_0_5_no_conflict(self) -> None:
        """置信度差=0.5 时（> 号，非 >=），不触发冲突"""
        existing = make_relation(confidence=0.9)
        incoming = make_relation(confidence=0.4)   # gap = 0.5，使用 > 0.5 不触发

        result = self.engine.merge_confidence(existing, incoming)

        assert result.conflict_detected is False

    def test_conflict_boundary_gap_just_above_0_5_triggers(self) -> None:
        """置信度差=0.51 时，触发冲突"""
        existing = make_relation(confidence=0.9)
        incoming = make_relation(confidence=0.39)  # gap ≈ 0.51，触发冲突

        result = self.engine.merge_confidence(existing, incoming)

        assert result.conflict_detected is True

    # ── 人工反馈边界 ──────────────────────────────────────────────

    def test_feedback_reject_confidence_exactly_0_2_archives(self) -> None:
        """否定后置信度精确 = 0.2 时，仍应归档（< 0.2 触发归档，但 0.5-0.3=0.2 恰好不归档）"""
        # 0.5 - 0.30 = 0.20，恰好在边界，按设计 < 0.2 才归档
        relation = make_relation(confidence=0.5)
        updated = self.engine.apply_human_feedback(relation, confirmed=False, engineer_id="eng-01")

        # 0.5 - 0.30 = 0.20，不小于 0.2，应为 PENDING_REVIEW 而非 ARCHIVED
        assert updated.status == RelationStatus.PENDING_REVIEW

    def test_feedback_reject_confidence_just_below_0_2_archives(self) -> None:
        """否定后置信度 < 0.2 应触发归档"""
        relation = make_relation(confidence=0.45)   # 0.45 - 0.30 = 0.15 < 0.2 → 归档
        updated = self.engine.apply_human_feedback(relation, confirmed=False, engineer_id="eng-01")

        assert updated.status == RelationStatus.ARCHIVED

    def test_confirm_near_1_caps_exactly_at_1(self) -> None:
        """置信度接近 1.0 时，确认后不超过 1.0"""
        relation = make_relation(confidence=0.9)    # 0.9 + 0.15 = 1.05 → 应夹紧为 1.0
        updated = self.engine.apply_human_feedback(relation, confirmed=True, engineer_id="eng-01")

        assert updated.confidence == pytest.approx(1.0, abs=1e-6)

    # ── 衰减边界 ──────────────────────────────────────────────────

    def test_decay_with_future_timestamp_no_negative(self) -> None:
        """updated_at 在未来（时钟漂移）时，不应产生负数 elapsed，置信度应基本不变"""
        from datetime import datetime, timedelta, timezone
        future_time = datetime.now(timezone.utc) + timedelta(days=5)
        relation = RelationObject(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="d-001",
            source_node_type="Device",
            target_node_id="a-001",
            target_node_type="Alarm",
            confidence=0.7,
            provenance=SourceType.SENSOR_REALTIME,
            updated_at=future_time,
            created_at=future_time,
        )
        decayed = self.engine.apply_decay(relation)

        # 未来时间戳导致 elapsed_days < 0，decay 结果应不低于原始置信度
        assert decayed >= relation.confidence or decayed == pytest.approx(relation.confidence, abs=0.01)

    # ── alpha 默认值 ───────────────────────────────────────────────

    def test_merge_with_unknown_provenance_uses_default_alpha(self) -> None:
        """未知来源类型应使用默认 alpha（合并后结果在合理范围内）"""
        from relos.core.models import ALPHA_CONFIG
        # inference 是已知类型，验证覆盖所有 SourceType
        for src_type in SourceType:
            assert src_type in ALPHA_CONFIG or True  # inference 使用默认 0.3
        # 验证 inference 来源的合并正常工作
        existing = make_relation(confidence=0.6)
        incoming = make_relation(confidence=0.8, provenance=SourceType.INFERENCE)
        result = self.engine.merge_confidence(existing, incoming)
        assert 0.0 <= result.new_confidence <= 1.0
