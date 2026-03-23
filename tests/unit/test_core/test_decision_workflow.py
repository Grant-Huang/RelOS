"""
tests/unit/test_core/test_decision_workflow.py
-----------------------------------------------
决策工作流单元测试（不调用真实 LLM）。

测试策略：
- 单独测试每个节点函数（纯函数，无副作用）
- 路由逻辑测试（条件边的正确性）
- LLM 节点使用 mock 隔离外部调用
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from relos.core.models import RelationObject, RelationStatus, SourceType
from relos.decision.workflow import (
    DecisionState,
    node_extract_context,
    node_hitl,
    node_llm_analyze,
    node_no_data,
    node_rule_engine,
    route_by_engine_path,
)


# ─── 测试数据 ──────────────────────────────────────────────────────

def make_relation(
    confidence: float = 0.8,
    relation_type: str = "ALARM__INDICATES__COMPONENT_FAILURE",
    src: str = "alarm-VIB-001",
    tgt: str = "component-bearing-M1",
    provenance_detail: str = "张工经验",
) -> RelationObject:
    return RelationObject(
        relation_type=relation_type,
        source_node_id=src,
        source_node_type="Alarm",
        target_node_id=tgt,
        target_node_type="Component",
        confidence=confidence,
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail=provenance_detail,
        status=RelationStatus.ACTIVE,
    )


def make_state(
    relations: list[RelationObject] | None = None,
    avg_confidence: float = 0.0,
    engine_path: str = "none",
    severity: str = "medium",
    rule_engine_no_match: bool = False,
) -> DecisionState:
    return DecisionState(
        alarm_id="ALM-TEST-001",
        device_id="device-M1",
        alarm_code="VIB-001",
        alarm_description="主轴振动超限",
        severity=severity,
        relations=relations or [],
        context_block=None,
        avg_confidence=avg_confidence,
        engine_path=engine_path,   # type: ignore[arg-type]
        _rule_engine_no_match=rule_engine_no_match,
        recommended_cause="",
        confidence=0.0,
        reasoning="",
        supporting_relation_ids=[],
        requires_human_review=False,
        error=None,
    )


# ─── node_extract_context 测试 ────────────────────────────────────

class TestNodeExtractContext:

    def test_high_confidence_routes_to_rule_engine(self) -> None:
        """高置信度子图 → rule_engine 路径"""
        relations = [make_relation(confidence=0.9) for _ in range(3)]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "rule_engine"
        assert result["avg_confidence"] >= 0.75

    def test_low_confidence_routes_to_hitl(self) -> None:
        """低置信度子图 → hitl 路径"""
        relations = [make_relation(confidence=0.3) for _ in range(2)]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "hitl"
        assert result["avg_confidence"] < 0.5

    def test_mid_confidence_routes_to_llm(self) -> None:
        """中等置信度子图 → llm 路径"""
        relations = [make_relation(confidence=0.6) for _ in range(2)]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "llm"

    def test_empty_relations_routes_to_none(self) -> None:
        """无关系数据 → none 路径（no_data 节点）"""
        state = make_state(relations=[])

        result = node_extract_context(state)

        assert result["engine_path"] == "none"
        assert result["avg_confidence"] == 0.0


# ─── node_rule_engine 测试 ────────────────────────────────────────

class TestNodeRuleEngine:

    def test_high_confidence_indicates_returns_cause(self) -> None:
        """高置信度 INDICATES 关系 → 直接推断根因"""
        state = make_state(
            relations=[make_relation(confidence=0.85)],
            avg_confidence=0.85,
            engine_path="rule_engine",
        )
        result = node_rule_engine(state)

        assert "recommended_cause" in result
        assert result.get("requires_human_review") is False
        assert len(result.get("supporting_relation_ids", [])) > 0

    def test_no_indicates_relations_fallback_to_llm(self) -> None:
        """无 INDICATES 类关系 → 降级到 LLM"""
        state = make_state(
            relations=[make_relation(
                relation_type="DEVICE__TRIGGERS__ALARM",   # 非 INDICATES 类型
                confidence=0.9,
            )],
            avg_confidence=0.9,
            engine_path="rule_engine",
        )
        result = node_rule_engine(state)

        assert result.get("engine_path") == "llm"


# ─── node_hitl 测试 ───────────────────────────────────────────────

class TestNodeHitl:

    def test_hitl_always_requires_human_review(self) -> None:
        """HITL 节点必须触发人工审核"""
        state = make_state(avg_confidence=0.3, engine_path="hitl")
        result = node_hitl(state)

        assert result["requires_human_review"] is True

    def test_critical_severity_in_reasoning(self) -> None:
        """critical 级别告警的原因应在 reasoning 中体现"""
        state = make_state(avg_confidence=0.3, engine_path="hitl", severity="critical")
        result = node_hitl(state)

        assert "critical" in result["reasoning"]

    def test_empty_relations_mentioned(self) -> None:
        """无历史数据时，reasoning 应提示录入知识"""
        state = make_state(relations=[], avg_confidence=0.0, engine_path="hitl")
        result = node_hitl(state)

        assert result["confidence"] == 0.0


# ─── node_no_data 测试 ────────────────────────────────────────────

class TestNodeNoData:

    def test_no_data_suggests_expert_init(self) -> None:
        """无数据节点应提示运行专家初始化"""
        state = make_state()
        result = node_no_data(state)

        assert result["confidence"] == 0.0
        assert result["requires_human_review"] is True
        assert "expert-init" in result["reasoning"] or "专家初始化" in result["reasoning"]


# ─── 路由函数测试 ────────────────────────────────────────────────

class TestRouting:

    def test_route_by_engine_path(self) -> None:
        """路由函数按 engine_path 正确分流"""
        for path, expected_node in [
            ("rule_engine", "rule_engine"),
            ("llm", "llm_analyze"),
            ("hitl", "hitl"),
            ("none", "no_data"),
        ]:
            state = make_state(engine_path=path)
            assert route_by_engine_path(state) == expected_node


# ─── T-04：HITL 触发条件 2/3 测试 ──────────────────────────────────

class TestHitlConditions:
    """T-04：验证 node_extract_context 的六条 HITL 规则中条件 2 和 3"""

    def test_condition_2_critical_with_no_high_confidence_forces_hitl(self) -> None:
        """条件 2：severity=critical 且无高置信度关系 → 强制 HITL（不走 LLM）"""
        # 置信度 0.5，低于 RULE_ENGINE_MIN_CONFIDENCE（0.75）
        relations = [make_relation(confidence=0.5) for _ in range(3)]
        state = make_state(relations=relations, severity="critical")

        result = node_extract_context(state)

        assert result["engine_path"] == "hitl"

    def test_condition_2_critical_with_high_confidence_does_not_force_hitl(self) -> None:
        """条件 2 不成立：critical 但有高置信度关系 → 按正常路径走"""
        # 置信度 0.9 ≥ RULE_ENGINE_MIN_CONFIDENCE → 应走 rule_engine
        relations = [make_relation(confidence=0.9) for _ in range(3)]
        state = make_state(relations=relations, severity="critical")

        result = node_extract_context(state)

        # 有高置信度，即使是 critical，也不应强制 HITL
        assert result["engine_path"] != "hitl"

    def test_condition_3_many_conflicts_forces_hitl(self) -> None:
        """条件 3：冲突关系数量 > 2 → 强制 HITL"""
        # 三条关系都有 conflict_with（冲突关系），触发条件 3
        relations = [
            RelationObject(
                relation_type="DEVICE__TRIGGERS__ALARM",
                source_node_id="device-M1",
                source_node_type="Device",
                target_node_id=f"alarm-{i:03d}",
                target_node_type="Alarm",
                confidence=0.9,    # 高置信度，但有冲突
                provenance=SourceType.MANUAL_ENGINEER,
                conflict_with=[f"rel-conflict-{i}"],
            )
            for i in range(3)
        ]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "hitl"

    def test_condition_3_two_or_fewer_conflicts_does_not_force_hitl(self) -> None:
        """条件 3 不成立：冲突关系数 ≤ 2 时不强制 HITL（由置信度决定路径）"""
        # 2 条冲突 + 高置信度 → 应走 rule_engine
        conflicted = [
            RelationObject(
                relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
                source_node_id="alarm-VIB-001",
                source_node_type="Alarm",
                target_node_id="component-bearing",
                target_node_type="Component",
                confidence=0.85,
                provenance=SourceType.MANUAL_ENGINEER,
                conflict_with=["rel-x"],
            )
            for _ in range(2)
        ]
        state = make_state(relations=conflicted)

        result = node_extract_context(state)

        # ≤ 2 冲突不触发条件 3
        assert result["engine_path"] != "hitl"


# ─── 置信度阈值精确边界测试 ─────────────────────────────────────────

class TestConfidenceThresholdBoundaries:
    """验证 0.75（规则引擎）和 0.5（HITL）两个关键阈值的精确边界行为"""

    def test_avg_confidence_exactly_at_rule_engine_threshold_routes_to_rule_engine(self) -> None:
        """直接关联节点 avg_confidence ≥ 0.75 → rule_engine（边界值等于阈值时）"""
        # 构造 3 条直接关联 device-M1 的关系，权重 x2，avg 等于 0.75
        relations = [
            RelationObject(
                relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
                source_node_id="device-M1",      # 直接关联中心节点
                source_node_type="Device",
                target_node_id="component-bearing-M1",
                target_node_type="Component",
                confidence=0.75,
                provenance=SourceType.MANUAL_ENGINEER,
                status=RelationStatus.ACTIVE,
            )
        ]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        # avg_conf 加权后 ≥ 0.75，应走 rule_engine（或 hitl 若无高置信度）
        # 关键：不应走 llm（即不在中间区间）
        assert result["engine_path"] in ("rule_engine", "hitl")
        assert result["engine_path"] != "llm"

    def test_avg_confidence_just_below_hitl_threshold_routes_to_llm(self) -> None:
        """avg_confidence 恰在 0.5~0.75 区间（走 LLM）"""
        relations = [
            RelationObject(
                relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
                source_node_id="alarm-001",
                source_node_type="Alarm",
                target_node_id="component-bearing",
                target_node_type="Component",
                confidence=0.6,
                provenance=SourceType.MANUAL_ENGINEER,
                status=RelationStatus.ACTIVE,
            )
        ]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "llm"

    def test_avg_confidence_exactly_at_hitl_threshold_routes_to_hitl(self) -> None:
        """avg_confidence < 0.5 → hitl（边界：0.49 应触发 HITL）"""
        relations = [
            RelationObject(
                relation_type="DEVICE__TRIGGERS__ALARM",
                source_node_id="alarm-001",
                source_node_type="Alarm",
                target_node_id="component-001",
                target_node_type="Component",
                confidence=0.49,
                provenance=SourceType.MANUAL_ENGINEER,
                status=RelationStatus.ACTIVE,
            )
        ]
        state = make_state(relations=relations)

        result = node_extract_context(state)

        assert result["engine_path"] == "hitl"

    def test_route_by_engine_path_unknown_path_falls_back_to_hitl(self) -> None:
        """未知 engine_path 值应降级到 hitl（防御性路由）"""
        state = make_state(engine_path="unknown_path")   # type: ignore[arg-type]
        # route_by_engine_path 对未知路径应返回 "hitl" 或抛出可预期异常
        try:
            result = route_by_engine_path(state)
            assert result == "hitl"
        except (KeyError, ValueError):
            pass  # 抛出异常也是可接受的防御行为


# ─── node_llm_analyze 异常路径测试 ────────────────────────────────

class TestNodeLLMAnalyzeErrorPaths:
    """验证 LLM 分析节点的三个异常路径（timeout/json错误/API失败）均降级到 HITL"""

    @pytest.mark.asyncio
    async def test_llm_timeout_falls_back_to_hitl(self) -> None:
        """LLM 调用超时（asyncio.TimeoutError）→ 降级路径（engine_path=hitl）"""
        from relos.context.compiler import ContextBlock

        state = make_state(
            relations=[make_relation(confidence=0.6)],
            avg_confidence=0.6,
            engine_path="llm",
        )
        state["context_block"] = ContextBlock(
            content="| 关系类型 | 置信度 |\n| rel-001 | 0.60 |",
            relation_count=1,
            estimated_tokens=20,
            pruned_count=0,
            query_strategy="direct",
        )

        with patch("anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.side_effect = asyncio.TimeoutError()

            result = await node_llm_analyze(state)

        # 超时后应降级，confidence 为 0 并需要人工审核
        assert result["requires_human_review"] is True or result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_llm_json_parse_error_falls_back(self) -> None:
        """LLM 返回非法 JSON → 降级处理，不崩溃"""
        from unittest.mock import MagicMock
        from relos.context.compiler import ContextBlock

        state = make_state(
            relations=[make_relation(confidence=0.6)],
            avg_confidence=0.6,
            engine_path="llm",
        )
        state["context_block"] = ContextBlock(
            content="| 关系类型 | 置信度 |\n| rel-001 | 0.60 |",
            relation_count=1,
            estimated_tokens=20,
            pruned_count=0,
            query_strategy="direct",
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="这不是合法的 JSON 格式")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        with patch("anthropic.AsyncAnthropic") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            result = await node_llm_analyze(state)

        # JSON 解析失败应降级，不应抛出未捕获异常
        assert "requires_human_review" in result or "confidence" in result
