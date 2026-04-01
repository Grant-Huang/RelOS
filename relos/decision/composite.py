from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from relos.config import settings
from relos.context.compiler import ContextBlock, ContextCompiler
from relos.core.models import (
    ActionBundle,
    CandidatePlan,
    CompositeDisturbanceEvent,
    DecisionAction,
    DecisionPackage,
    DecisionPackageStatus,
    RelationObject,
    RiskLevel,
)


def build_composite_context(
    incident: CompositeDisturbanceEvent,
    relations: list[RelationObject],
) -> ContextBlock:
    compiler = ContextCompiler(max_relations=24, token_budget=2200, min_confidence=0.25)
    focus_ids = [event.entity_id for event in incident.events]
    focus_text = ", ".join(f"`{node_id}`" for node_id in focus_ids if node_id) or "`unknown`"
    query_context = (
        f"incident={incident.incident_id} | scenario={incident.scenario_type} | "
        f"goal={incident.goal} | focus={focus_text}"
    )
    center_node_id = focus_ids[0] if focus_ids else incident.incident_id
    return compiler.compile(
        relations=relations,
        center_node_id=center_node_id,
        query_context=query_context,
        strategy="composite_disturbance",
    )


def build_decision_package(
    incident: CompositeDisturbanceEvent,
    relations: list[RelationObject],
    context_block: ContextBlock,
) -> DecisionPackage:
    scenario_type = incident.scenario_type.lower()
    evidence = _build_evidence_payload(relations)
    risk_level = _derive_risk_level(incident)
    candidate_plans = _build_candidate_plans(incident, scenario_type, risk_level)
    recommended_plan = candidate_plans[0]
    actions = _build_decision_actions(incident, scenario_type, risk_level)
    requires_human_review = risk_level != RiskLevel.LOW or any(
        event.event_type in {"machine_anomaly", "quality_degradation"} for event in incident.events
    )
    review_reason = (
        "存在设备异常/质量或物料约束，需要主管确认推荐方案与动作边界"
        if requires_human_review
        else "低风险方案，可直接进入 Shadow 计划"
    )
    now = datetime.now(UTC)
    return DecisionPackage(
        decision_id=f"decision-{incident.incident_id}",
        incident_id=incident.incident_id,
        title=_build_title(incident),
        incident_summary=_build_incident_summary(incident),
        risk_level=risk_level,
        recommended_plan_id=recommended_plan.plan_id,
        candidate_plans=candidate_plans,
        recommended_actions=actions,
        evidence_relations=evidence,
        requires_human_review=requires_human_review,
        review_reason=review_reason,
        trace_id=f"trace-{uuid.uuid4().hex}",
        status=(
            DecisionPackageStatus.PENDING_REVIEW
            if requires_human_review
            else DecisionPackageStatus.DRAFT
        ),
        context_block=context_block.content,
        context_query_strategy=context_block.query_strategy,
        context_relations_count=context_block.relation_count,
        created_at=now,
        updated_at=now,
    )


def build_action_bundle(decision_package: DecisionPackage) -> ActionBundle:
    now = datetime.now(UTC)
    notes = (
        "Shadow Mode 已开启：动作包仅用于演示和审计，不直接触发 MES/MRO 写入。"
    )
    return ActionBundle(
        bundle_id=f"bundle-{decision_package.decision_id}",
        decision_id=decision_package.decision_id,
        status=(
            DecisionPackageStatus.PENDING_REVIEW
            if decision_package.requires_human_review
            else DecisionPackageStatus.SHADOW_PLANNED
        ),
        actions=decision_package.recommended_actions,
        shadow_mode=settings.SHADOW_MODE,
        execution_notes=notes,
        created_at=now,
        updated_at=now,
    )


def _build_title(incident: CompositeDisturbanceEvent) -> str:
    if "semiconductor" in incident.scenario_type.lower():
        return "半导体封装复合扰动决策包"
    if "auto" in incident.scenario_type.lower():
        return "汽车零部件复合扰动决策包"
    return "复合扰动决策包"


def _build_incident_summary(incident: CompositeDisturbanceEvent) -> str:
    summaries = "；".join(event.summary for event in incident.events[:4])
    return f"{incident.goal}。关键扰动：{summaries}"


def _derive_risk_level(incident: CompositeDisturbanceEvent) -> RiskLevel:
    severities = {event.severity.lower() for event in incident.events}
    if "critical" in severities or len(incident.events) >= 3:
        return RiskLevel.HIGH
    if "high" in severities:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _build_candidate_plans(
    incident: CompositeDisturbanceEvent,
    scenario_type: str,
    risk_level: RiskLevel,
) -> list[CandidatePlan]:
    if "semiconductor" in scenario_type:
        return [
            CandidatePlan(
                plan_id="plan-balance-repair-and-expedite",
                name="先预防维修再并行插单保交付",
                summary="14:15 前处理 SMT-02 送料器风险，随后由 SMT-02 与 SMT-04 共同承接插单。",
                assumptions=["备料能在 15:00 前到位", "SMT-04 可释放部分产能"],
                risk_level=risk_level,
                estimated_delivery_impact="当班内仍有机会完成 18:00 插单目标",
                estimated_quality_impact="降低贴装偏移继续扩大带来的批量风险",
                estimated_capacity_impact="短时牺牲 25 分钟，换取后续稳定产能",
            ),
            CandidatePlan(
                plan_id="plan-expedite-without-stop",
                name="不停机强行保交付",
                summary="保持 SMT-02 连续运行，同时压缩换线窗口抢交付。",
                assumptions=["设备可继续稳定运行", "质量风险可接受"],
                risk_level=RiskLevel.HIGH,
                estimated_delivery_impact="短期交付看似最优",
                estimated_quality_impact="质量逸散与返工风险显著增加",
                estimated_capacity_impact="名义产能最高，但不稳定",
            ),
        ]
    return [
        CandidatePlan(
            plan_id="plan-shift-capacity-and-maintain",
            name="完成在制后切换产能并安排维护",
            summary="CNC-07 完成当前批次后停机，改由 CNC-09 与 CNC-12 承接高优订单。",
            assumptions=["刀具与夹具可在短时内调拨到位", "CNC-09/CNC-12 有可用窗口"],
            risk_level=risk_level,
            estimated_delivery_impact="16:00 交期可控，但需要严格执行调度",
            estimated_quality_impact="及时隔离 CNC-07 对 B 线 CPK 的继续拖累",
            estimated_capacity_impact="主产能转移，整体负载更均衡",
        ),
        CandidatePlan(
            plan_id="plan-keep-cnc07-running",
            name="保持 CNC-07 连续生产",
            summary="继续使用 CNC-07 承接插单，暂不进行维护。",
            assumptions=["振动未继续恶化", "CPK 波动可在线纠偏"],
            risk_level=RiskLevel.HIGH,
            estimated_delivery_impact="短期产出最大",
            estimated_quality_impact="B 线质量扩散风险高",
            estimated_capacity_impact="对单机依赖过强",
        ),
    ]


def _build_decision_actions(
    incident: CompositeDisturbanceEvent,
    scenario_type: str,
    risk_level: RiskLevel,
) -> list[DecisionAction]:
    if "semiconductor" in scenario_type:
        return [
            DecisionAction(
                action_id="act-maint-smt02-feeder",
                action_type="maintenance_work_order",
                target_system="MRO",
                target_entity="SMT-02",
                summary="创建 SMT-02 送料器预防性更换工单",
                risk_level=risk_level,
                requires_human_review=True,
                payload_preview={
                    "machine_id": "SMT-02",
                    "component": "feeder_gear",
                    "window": "14:15-14:40",
                },
            ),
            DecisionAction(
                action_id="act-allocate-0402",
                action_type="material_transfer",
                target_system="WMS",
                target_entity="0402-resistor",
                summary="发起 0402 电阻卷料紧急调拨",
                risk_level=RiskLevel.MEDIUM,
                requires_human_review=False,
                payload_preview={
                    "material_id": "0402-resistor",
                    "required_eta": "15:00",
                    "destination_machine": "SMT-02",
                },
            ),
            DecisionAction(
                action_id="act-reschedule-bga-order",
                action_type="schedule_update",
                target_system="MES",
                target_entity="BGA-order-rush",
                summary="更新 BGA 插单排产到 SMT-02 与 SMT-04 联合产能",
                risk_level=RiskLevel.MEDIUM,
                requires_human_review=True,
                payload_preview={"machines": ["SMT-02", "SMT-04"], "priority": "rush"},
            ),
        ]
    return [
        DecisionAction(
            action_id="act-maint-cnc07-spindle",
            action_type="maintenance_work_order",
            target_system="MRO",
            target_entity="CNC-07",
            summary="创建 CNC-07 主轴轴承更换工单",
            risk_level=risk_level,
            requires_human_review=True,
            payload_preview={
                "machine_id": "CNC-07",
                "component": "spindle_bearing",
                "downtime_hours": 3,
            },
        ),
        DecisionAction(
            action_id="act-shift-order-capacity",
            action_type="schedule_update",
            target_system="MES",
            target_entity="priority-order-A",
            summary="将大客户订单切换到 CNC-09 与 CNC-12 组合产能",
            risk_level=RiskLevel.MEDIUM,
            requires_human_review=True,
            payload_preview={"machines": ["CNC-09", "CNC-12"], "deadline": "16:00"},
        ),
        DecisionAction(
            action_id="act-transfer-tooling",
            action_type="tooling_transfer",
            target_system="MRO",
            target_entity="phi32-mill",
            summary="紧急调拨 CNC-12 所需 φ32 铣刀与夹具",
            risk_level=RiskLevel.LOW,
            requires_human_review=False,
            payload_preview={"tool": "phi32-mill", "destination_machine": "CNC-12"},
        ),
    ]


def _build_evidence_payload(relations: list[RelationObject]) -> list[dict[str, Any]]:
    top_relations = sorted(relations, key=lambda relation: relation.confidence, reverse=True)[:6]
    payload: list[dict[str, Any]] = []
    for relation in top_relations:
        payload.append(
            {
                "id": relation.id,
                "relation_type": relation.relation_type,
                "source_node_id": relation.source_node_id,
                "target_node_id": relation.target_node_id,
                "confidence": relation.confidence,
                "provenance": relation.provenance.value,
                "knowledge_phase": (
                    relation.knowledge_phase.value if relation.knowledge_phase else ""
                ),
                "status": relation.status.value,
                "provenance_detail": relation.provenance_detail,
            }
        )
    return payload
