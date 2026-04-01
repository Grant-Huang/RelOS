from __future__ import annotations

from relos.core.models import (
    CompositeDisturbanceEvent,
    CompositeSubEvent,
    RelationObject,
    RelationStatus,
    SourceType,
)
from relos.decision.composite import (
    build_action_bundle,
    build_composite_context,
    build_decision_package,
)


def make_relation(
    rel_id: str,
    source_node_id: str,
    target_node_id: str,
    relation_type: str,
    confidence: float,
) -> RelationObject:
    return RelationObject(
        id=rel_id,
        relation_type=relation_type,
        source_node_id=source_node_id,
        source_node_type="Machine",
        target_node_id=target_node_id,
        target_node_type="Alarm",
        confidence=confidence,
        provenance=SourceType.MES_STRUCTURED,
        status=RelationStatus.ACTIVE,
        provenance_detail="unit-test",
    )


def make_incident(scenario_type: str = "semiconductor_packaging") -> CompositeDisturbanceEvent:
    return CompositeDisturbanceEvent(
        incident_id="incident-semicon-001",
        factory_id="fab-01",
        scenario_type=scenario_type,
        priority="high",
        goal="保障插单交付并控制设备与物料风险",
        time_window_start="2026-03-30T13:47:00+08:00",
        time_window_end="2026-03-30T13:51:00+08:00",
        events=[
            CompositeSubEvent(
                event_id="evt-001",
                event_type="rush_order",
                source_system="ERP",
                occurred_at="2026-03-30T13:47:00+08:00",
                entity_id="order-rush-001",
                entity_type="CustomerOrder",
                severity="high",
                summary="紧急插单 500 件 BGA",
            ),
            CompositeSubEvent(
                event_id="evt-002",
                event_type="machine_anomaly",
                source_system="MES",
                occurred_at="2026-03-30T13:48:00+08:00",
                entity_id="SMT-02",
                entity_type="Machine",
                severity="high",
                summary="SMT-02 贴装偏移接近上限 80%",
            ),
            CompositeSubEvent(
                event_id="evt-003",
                event_type="material_shortage",
                source_system="WMS",
                occurred_at="2026-03-30T13:50:00+08:00",
                entity_id="0402-resistor",
                entity_type="MaterialLot",
                severity="medium",
                summary="0402 电阻仅剩 1.5 小时库存",
            ),
        ],
    )


class TestCompositeDecisionBuilders:
    def test_build_decision_package_returns_pending_review_for_high_risk(self) -> None:
        incident = make_incident()
        relations = [
            make_relation("rel-001", "SMT-02", "alarm-offset", "MACHINE__SHOWS__ANOMALY", 0.84),
            make_relation(
                "rel-002",
                "0402-resistor",
                "process-bga",
                "MATERIAL__DEPLETES__PROCESS",
                0.79,
            ),
        ]

        context_block = build_composite_context(incident, relations)
        package = build_decision_package(incident, relations, context_block)

        assert package.incident_id == incident.incident_id
        assert package.status.value == "pending_review"
        assert package.requires_human_review is True
        assert package.context_relations_count == 2
        assert len(package.candidate_plans) >= 2
        assert len(package.recommended_actions) >= 2
        assert package.evidence_relations[0]["id"] == "rel-001"

    def test_build_action_bundle_follows_decision_status(self) -> None:
        incident = make_incident("auto_parts_manufacturing")
        relations = [
            make_relation("rel-101", "CNC-07", "alarm-vib", "MACHINE__SHOWS__ANOMALY", 0.87),
            make_relation("rel-102", "CNC-07", "BLine_CPK", "MACHINE__IMPACTS__QUALITY", 0.81),
        ]
        context_block = build_composite_context(incident, relations)
        package = build_decision_package(incident, relations, context_block)

        bundle = build_action_bundle(package)

        assert bundle.decision_id == package.decision_id
        assert bundle.shadow_mode is True
        assert bundle.status.value == "pending_review"
        assert len(bundle.actions) == len(package.recommended_actions)
        assert "Shadow Mode" in bundle.execution_notes
