"""
scripts/seed_demo_scenarios.py
------------------------------
演示场景数据注入脚本（场景 7–12：中层 + 高层）。

覆盖场景：
  场景 7：产线效率瓶颈识别
  场景 8：跨部门协同问题（生产 vs 采购）
  场景 9：异常处理效率分析
  场景10：企业级风险雷达
  场景11：资源配置优化
  场景12：战略决策模拟

使用方式：
    # 先注入 MVP 基础数据
    python scripts/seed_neo4j.py

    # 再注入演示场景数据
    python scripts/seed_demo_scenarios.py

前置条件：
    docker compose up -d neo4j
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from neo4j import AsyncGraphDatabase

from relos.config import settings
from relos.core.models import Node, RelationObject, RelationStatus, SourceType
from relos.core.repository import RelationRepository

# ─────────────────────────────────────────────────────────────────────────────
# 节点定义
# ─────────────────────────────────────────────────────────────────────────────

NODES: list[dict] = [

    # ── 场景7：产线节点 ────────────────────────────────────────────────────
    {"id": "line-L1", "node_type": "Line", "name": "产线 L1（冲压线）",
     "properties": {"workshop": "车间A", "capacity_per_day": 120, "efficiency_pct": 92}},
    {"id": "line-L2", "node_type": "Line", "name": "产线 L2（焊接线）",
     "properties": {"workshop": "车间A", "capacity_per_day": 100, "efficiency_pct": 64}},
    {"id": "line-L3", "node_type": "Line", "name": "产线 L3（装配线）",
     "properties": {"workshop": "车间B", "capacity_per_day": 80, "efficiency_pct": 81}},

    # 产线设备（L2 上的问题设备 M3）
    {"id": "machine-M3", "node_type": "Machine", "name": "焊接机 M3",
     "properties": {"line_id": "line-L2", "model": "松下 YD-500GR2", "install_year": 2018,
                    "alarm_count_7d": 14, "downtime_hours_7d": 18.5}},
    {"id": "machine-M4", "node_type": "Machine", "name": "焊接机 M4",
     "properties": {"line_id": "line-L2", "model": "松下 YD-500GR2", "install_year": 2020,
                    "alarm_count_7d": 2, "downtime_hours_7d": 1.2}},
    {"id": "machine-M5", "node_type": "Machine", "name": "冲压机 M5",
     "properties": {"line_id": "line-L1", "model": "扬力 JH21-160", "install_year": 2021,
                    "alarm_count_7d": 1, "downtime_hours_7d": 0.5}},

    # 告警（焊接机 M3 相关）
    {"id": "alarm-WELD-OVERHEAT", "node_type": "Alarm", "name": "焊接过热告警",
     "properties": {"alarm_code": "WELD-OHT-001", "severity": "high",
                    "frequency_7d": 9, "avg_duration_min": 45}},
    {"id": "alarm-WELD-ARC", "node_type": "Alarm", "name": "电弧不稳定告警",
     "properties": {"alarm_code": "WELD-ARC-002", "severity": "medium",
                    "frequency_7d": 5, "avg_duration_min": 20}},

    # ── 场景8：供应链节点 ──────────────────────────────────────────────────
    {"id": "supplier-A", "node_type": "Supplier", "name": "供应商 A（华盛钢材）",
     "properties": {"category": "原材料", "contract_lead_days": 7,
                    "actual_avg_lead_days": 11.2, "on_time_rate_90d": 0.43}},
    {"id": "supplier-B", "node_type": "Supplier", "name": "供应商 B（佳友塑料）",
     "properties": {"category": "辅材", "contract_lead_days": 5,
                    "actual_avg_lead_days": 5.3, "on_time_rate_90d": 0.94}},

    {"id": "material-steel-01", "node_type": "Material", "name": "优质钢板 Q235",
     "properties": {"unit": "吨", "safety_stock": 20,
                    "current_stock": 4.5, "stockout_risk": "high"}},
    {"id": "material-plastic-01", "node_type": "Material", "name": "ABS 工程塑料",
     "properties": {"unit": "千克", "safety_stock": 500,
                    "current_stock": 680, "stockout_risk": "low"}},

    {"id": "workorder-WO-001", "node_type": "WorkOrder", "name": "工单 WO-001（车身框架）",
     "properties": {"planned_start": "2026-03-20", "actual_start": "2026-03-23",
                    "delay_days": 3, "delay_reason": "material_shortage"}},
    {"id": "workorder-WO-002", "node_type": "WorkOrder", "name": "工单 WO-002（底盘支撑）",
     "properties": {"planned_start": "2026-03-21", "actual_start": "2026-03-24",
                    "delay_days": 3, "delay_reason": "material_shortage"}},
    {"id": "workorder-WO-003", "node_type": "WorkOrder", "name": "工单 WO-003（内饰件）",
     "properties": {"planned_start": "2026-03-22", "actual_start": "2026-03-22",
                    "delay_days": 0, "delay_reason": "none"}},

    # ── 场景9：异常处理节点 ────────────────────────────────────────────────
    {"id": "issue-BEAR-001", "node_type": "Issue", "name": "轴承磨损故障 #001",
     "properties": {"issue_type": "bearing_wear", "severity": "high",
                    "resolution_hours": 3.2, "shift": "night"}},
    {"id": "issue-BEAR-002", "node_type": "Issue", "name": "轴承磨损故障 #002",
     "properties": {"issue_type": "bearing_wear", "severity": "high",
                    "resolution_hours": 2.8, "shift": "night"}},
    {"id": "issue-ELEC-001", "node_type": "Issue", "name": "电气短路故障 #001",
     "properties": {"issue_type": "electrical", "severity": "medium",
                    "resolution_hours": 1.1, "shift": "day"}},
    {"id": "issue-COOL-001", "node_type": "Issue", "name": "冷却系统故障 #001",
     "properties": {"issue_type": "cooling", "severity": "low",
                    "resolution_hours": 0.7, "shift": "day"}},
    {"id": "issue-BEAR-003", "node_type": "Issue", "name": "轴承磨损故障 #003",
     "properties": {"issue_type": "bearing_wear", "severity": "high",
                    "resolution_hours": 2.1, "shift": "day"}},

    {"id": "operator-li", "node_type": "Operator", "name": "李工（夜班）",
     "properties": {"experience_years": 3, "specialty": "电气", "shift": "night"}},
    {"id": "operator-wang", "node_type": "Operator", "name": "王工（白班）",
     "properties": {"experience_years": 15, "specialty": "机械", "shift": "day"}},
    {"id": "shift-night", "node_type": "Shift", "name": "夜班（22:00-06:00）",
     "properties": {"shift_type": "night", "staff_count": 4,
                    "avg_experience_years": 4.2}},
    {"id": "shift-day", "node_type": "Shift", "name": "白班（08:00-20:00）",
     "properties": {"shift_type": "day", "staff_count": 12,
                    "avg_experience_years": 11.8}},

    # ── 场景10：风险雷达节点 ───────────────────────────────────────────────
    {"id": "risk-supply-chain", "node_type": "Risk", "name": "供应链中断风险",
     "properties": {"risk_domain": "supply_chain", "score": 0.68,
                    "trend": "rising", "top_driver": "supplier-A"}},
    {"id": "risk-quality", "node_type": "Risk", "name": "质量波动风险",
     "properties": {"risk_domain": "quality", "score": 0.52,
                    "trend": "stable", "top_driver": "machine-M3"}},
    {"id": "risk-equipment", "node_type": "Risk", "name": "设备稳定性风险",
     "properties": {"risk_domain": "equipment", "score": 0.41,
                    "trend": "rising", "top_driver": "machine-M3"}},

    # ── 场景11：资源优化节点 ───────────────────────────────────────────────
    {"id": "resource-maintenance", "node_type": "Resource", "name": "设备维护团队",
     "properties": {"resource_type": "maintenance_team", "current_headcount": 3,
                    "recommended_headcount": 5, "roi_estimate": 0.35}},
    {"id": "resource-supplier-mgmt", "node_type": "Resource", "name": "供应商管理专员",
     "properties": {"resource_type": "procurement_team", "current_headcount": 1,
                    "recommended_headcount": 2, "roi_estimate": 0.28}},
    {"id": "resource-night-training", "node_type": "Resource", "name": "夜班技能培训",
     "properties": {"resource_type": "training_program", "duration_weeks": 4,
                    "cost_rmb": 50000, "roi_estimate": 0.22}},
]


# ─────────────────────────────────────────────────────────────────────────────
# 关系定义
# ─────────────────────────────────────────────────────────────────────────────

RELATIONS: list[RelationObject] = [

    # ── 场景7：产线效率 ───────────────────────────────────────────────────

    # L2 产线包含 M3（问题设备）
    RelationObject(
        id="demo-rel-s7-001",
        relation_type="LINE__CONTAINS__MACHINE",
        source_node_id="line-L2",
        source_node_type="Line",
        target_node_id="machine-M3",
        target_node_type="Machine",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 设备台账，产线 L2 配置",
        half_life_days=3650,
        status=RelationStatus.ACTIVE,
        properties={"assignment_date": "2018-06-01"},
    ),
    RelationObject(
        id="demo-rel-s7-002",
        relation_type="LINE__CONTAINS__MACHINE",
        source_node_id="line-L2",
        source_node_type="Line",
        target_node_id="machine-M4",
        target_node_type="Machine",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 设备台账",
        half_life_days=3650,
        status=RelationStatus.ACTIVE,
    ),
    RelationObject(
        id="demo-rel-s7-003",
        relation_type="LINE__CONTAINS__MACHINE",
        source_node_id="line-L1",
        source_node_type="Line",
        target_node_id="machine-M5",
        target_node_type="Machine",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 设备台账",
        half_life_days=3650,
        status=RelationStatus.ACTIVE,
    ),

    # M3 触发告警（过热 + 电弧）
    RelationObject(
        id="demo-rel-s7-004",
        relation_type="DEVICE__TRIGGERS__ALARM",
        source_node_id="machine-M3",
        source_node_type="Machine",
        target_node_id="alarm-WELD-OVERHEAT",
        target_node_type="Alarm",
        confidence=0.91,
        provenance=SourceType.SENSOR_REALTIME,
        provenance_detail="传感器数据：过去 7 天过热告警 9 次，环比增加 80%",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"frequency_7d": 9, "frequency_prior_7d": 5, "change_pct": 80},
    ),
    RelationObject(
        id="demo-rel-s7-005",
        relation_type="DEVICE__TRIGGERS__ALARM",
        source_node_id="machine-M3",
        source_node_type="Machine",
        target_node_id="alarm-WELD-ARC",
        target_node_type="Alarm",
        confidence=0.78,
        provenance=SourceType.SENSOR_REALTIME,
        provenance_detail="传感器数据：过去 7 天电弧不稳告警 5 次",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"frequency_7d": 5},
    ),

    # 告警 → 停机（停机时长存在关系属性中）
    RelationObject(
        id="demo-rel-s7-006",
        relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
        source_node_id="alarm-WELD-OVERHEAT",
        source_node_type="Alarm",
        target_node_id="component-bearing-M1",
        target_node_type="Component",
        confidence=0.72,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="LLM 分析维修记录：焊接过热 72% 由接触嘴磨损引起",
        half_life_days=180,
        status=RelationStatus.PENDING_REVIEW,
        properties={"downtime_contribution_pct": 72, "component": "contact_tip"},
    ),

    # M3 导致产线效率下降（专家判断）
    RelationObject(
        id="demo-rel-s7-007",
        relation_type="MACHINE__CAUSES__DOWNTIME",
        source_node_id="machine-M3",
        source_node_type="Machine",
        target_node_id="line-L2",
        target_node_type="Line",
        confidence=0.88,
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail="王工评估：M3 停机导致 L2 产线效率下降 28 个百分点",
        extracted_by="human:operator-wang",
        half_life_days=7,
        status=RelationStatus.ACTIVE,
        properties={
            "downtime_hours_7d": 18.5,
            "efficiency_loss_pct": 28,
            "bottleneck_contribution_pct": 42,
        },
    ),

    # ── 场景8：跨部门协同 ─────────────────────────────────────────────────

    # 供应商 A → 钢材（延迟高）
    RelationObject(
        id="demo-rel-s8-001",
        relation_type="SUPPLIER__PROVIDES__MATERIAL",
        source_node_id="supplier-A",
        source_node_type="Supplier",
        target_node_id="material-steel-01",
        target_node_type="Material",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="采购合同，Q235 钢板独家供应",
        half_life_days=60,
        status=RelationStatus.ACTIVE,
        properties={"contract_lead_days": 7, "sole_supplier": True},
    ),
    RelationObject(
        id="demo-rel-s8-002",
        relation_type="SUPPLIER__DELAYS__MATERIAL",
        source_node_id="supplier-A",
        source_node_type="Supplier",
        target_node_id="material-steel-01",
        target_node_type="Material",
        confidence=0.86,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="90 天交期记录：平均延迟 4.2 天，准时率仅 43%",
        half_life_days=14,
        status=RelationStatus.ACTIVE,
        properties={
            "avg_delay_days": 4.2,
            "on_time_rate_90d": 0.43,
            "delay_count_90d": 17,
        },
    ),

    # 钢材 → 工单（WO-001, WO-002 因缺料延误）
    RelationObject(
        id="demo-rel-s8-003",
        relation_type="MATERIAL__USED_IN__WORKORDER",
        source_node_id="material-steel-01",
        source_node_type="Material",
        target_node_id="workorder-WO-001",
        target_node_type="WorkOrder",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 工单 BOM：WO-001 使用 Q235 钢板 8.2 吨",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
        properties={"required_qty_ton": 8.2},
    ),
    RelationObject(
        id="demo-rel-s8-004",
        relation_type="MATERIAL__USED_IN__WORKORDER",
        source_node_id="material-steel-01",
        source_node_type="Material",
        target_node_id="workorder-WO-002",
        target_node_type="WorkOrder",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 工单 BOM：WO-002 使用 Q235 钢板 6.5 吨",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
        properties={"required_qty_ton": 6.5},
    ),

    # 钢材缺料 → 工单阻塞
    RelationObject(
        id="demo-rel-s8-005",
        relation_type="WORKORDER__BLOCKED_BY__SHORTAGE",
        source_node_id="workorder-WO-001",
        source_node_type="WorkOrder",
        target_node_id="material-steel-01",
        target_node_type="Material",
        confidence=0.95,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 异常记录：WO-001 因 Q235 库存不足延误 3 天",
        half_life_days=7,
        status=RelationStatus.ACTIVE,
        properties={"delay_days": 3, "shortage_qty_ton": 3.7},
    ),
    RelationObject(
        id="demo-rel-s8-006",
        relation_type="WORKORDER__BLOCKED_BY__SHORTAGE",
        source_node_id="workorder-WO-002",
        source_node_type="WorkOrder",
        target_node_id="material-steel-01",
        target_node_type="Material",
        confidence=0.95,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 异常记录：WO-002 因 Q235 库存不足延误 3 天",
        half_life_days=7,
        status=RelationStatus.ACTIVE,
        properties={"delay_days": 3, "shortage_qty_ton": 1.8},
    ),

    # 供应商 B → 塑料（正常）
    RelationObject(
        id="demo-rel-s8-007",
        relation_type="SUPPLIER__PROVIDES__MATERIAL",
        source_node_id="supplier-B",
        source_node_type="Supplier",
        target_node_id="material-plastic-01",
        target_node_type="Material",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="采购合同，ABS 塑料供应",
        half_life_days=60,
        status=RelationStatus.ACTIVE,
        properties={"on_time_rate_90d": 0.94},
    ),

    # ── 场景9：异常处理效率 ───────────────────────────────────────────────

    # 告警 → 故障 Issue
    RelationObject(
        id="demo-rel-s9-001",
        relation_type="ALARM__CAUSES__ISSUE",
        source_node_id="alarm-VIB-001",  # MVP 基础数据中的振动告警
        source_node_type="Alarm",
        target_node_id="issue-BEAR-001",
        target_node_type="Issue",
        confidence=0.82,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修工单关联：振动告警 → 轴承更换",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
        properties={"alarm_to_issue_min": 12},
    ),
    RelationObject(
        id="demo-rel-s9-002",
        relation_type="ALARM__CAUSES__ISSUE",
        source_node_id="alarm-VIB-001",
        source_node_type="Alarm",
        target_node_id="issue-BEAR-002",
        target_node_type="Issue",
        confidence=0.79,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修工单关联",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
    ),
    RelationObject(
        id="demo-rel-s9-003",
        relation_type="ALARM__CAUSES__ISSUE",
        source_node_id="alarm-VIB-001",
        source_node_type="Alarm",
        target_node_id="issue-BEAR-003",
        target_node_type="Issue",
        confidence=0.77,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修工单关联",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
    ),

    # Issue → 操作员（处理关系，含处理时长）
    RelationObject(
        id="demo-rel-s9-004",
        relation_type="ISSUE__RESOLVED_BY__OPERATOR",
        source_node_id="issue-BEAR-001",
        source_node_type="Issue",
        target_node_id="operator-li",
        target_node_type="Operator",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修记录：李工处理，夜班",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"resolution_hours": 3.2, "shift": "night", "issue_type": "bearing_wear"},
    ),
    RelationObject(
        id="demo-rel-s9-005",
        relation_type="ISSUE__RESOLVED_BY__OPERATOR",
        source_node_id="issue-BEAR-002",
        source_node_type="Issue",
        target_node_id="operator-li",
        target_node_type="Operator",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修记录：李工处理，夜班",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"resolution_hours": 2.8, "shift": "night", "issue_type": "bearing_wear"},
    ),
    RelationObject(
        id="demo-rel-s9-006",
        relation_type="ISSUE__RESOLVED_BY__OPERATOR",
        source_node_id="issue-BEAR-003",
        source_node_type="Issue",
        target_node_id="operator-wang",
        target_node_type="Operator",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修记录：王工处理，白班",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"resolution_hours": 2.1, "shift": "day", "issue_type": "bearing_wear"},
    ),
    RelationObject(
        id="demo-rel-s9-007",
        relation_type="ISSUE__RESOLVED_BY__OPERATOR",
        source_node_id="issue-ELEC-001",
        source_node_type="Issue",
        target_node_id="operator-wang",
        target_node_type="Operator",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修记录：王工处理，白班",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"resolution_hours": 1.1, "shift": "day", "issue_type": "electrical"},
    ),
    RelationObject(
        id="demo-rel-s9-008",
        relation_type="ISSUE__RESOLVED_BY__OPERATOR",
        source_node_id="issue-COOL-001",
        source_node_type="Issue",
        target_node_id="operator-wang",
        target_node_type="Operator",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 维修记录：王工处理，白班",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"resolution_hours": 0.7, "shift": "day", "issue_type": "cooling"},
    ),

    # 班次 → 故障处理（夜班效率低）
    RelationObject(
        id="demo-rel-s9-009",
        relation_type="SHIFT__HANDLES__ISSUE",
        source_node_id="shift-night",
        source_node_type="Shift",
        target_node_id="issue-BEAR-001",
        target_node_type="Issue",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 班次记录",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
        properties={"avg_resolution_hours": 3.0, "vs_day_shift_ratio": 1.38},
    ),

    # ── 场景10：企业级风险雷达 ────────────────────────────────────────────

    # 供应链问题 → 供应链风险
    RelationObject(
        id="demo-rel-s10-001",
        relation_type="ISSUE__CONTRIBUTES_TO__RISK",
        source_node_id="workorder-WO-001",
        source_node_type="WorkOrder",
        target_node_id="risk-supply-chain",
        target_node_type="Risk",
        confidence=0.88,
        provenance=SourceType.INFERENCE,
        provenance_detail="系统推断：工单延误 → 供应链风险分数提升",
        half_life_days=14,
        status=RelationStatus.ACTIVE,
        properties={"risk_contribution_score": 0.35},
    ),
    RelationObject(
        id="demo-rel-s10-002",
        relation_type="ISSUE__CONTRIBUTES_TO__RISK",
        source_node_id="workorder-WO-002",
        source_node_type="WorkOrder",
        target_node_id="risk-supply-chain",
        target_node_type="Risk",
        confidence=0.85,
        provenance=SourceType.INFERENCE,
        provenance_detail="系统推断",
        half_life_days=14,
        status=RelationStatus.ACTIVE,
        properties={"risk_contribution_score": 0.33},
    ),

    # 设备告警 → 设备风险 + 质量风险
    RelationObject(
        id="demo-rel-s10-003",
        relation_type="ALARM__ELEVATES__RISK",
        source_node_id="alarm-WELD-OVERHEAT",
        source_node_type="Alarm",
        target_node_id="risk-equipment",
        target_node_type="Risk",
        confidence=0.83,
        provenance=SourceType.INFERENCE,
        provenance_detail="系统推断：频繁过热告警 → 设备稳定性风险",
        half_life_days=7,
        status=RelationStatus.ACTIVE,
        properties={"risk_contribution_score": 0.41},
    ),
    RelationObject(
        id="demo-rel-s10-004",
        relation_type="ALARM__ELEVATES__RISK",
        source_node_id="alarm-WELD-ARC",
        source_node_type="Alarm",
        target_node_id="risk-quality",
        target_node_type="Risk",
        confidence=0.76,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="LLM 分析：电弧不稳 → 焊缝质量波动风险",
        half_life_days=7,
        status=RelationStatus.PENDING_REVIEW,
        properties={"risk_contribution_score": 0.52},
    ),

    # ── 场景11：资源配置优化 ──────────────────────────────────────────────

    # 问题 → 资源需求
    RelationObject(
        id="demo-rel-s11-001",
        relation_type="ISSUE__REQUIRES__RESOURCE",
        source_node_id="risk-equipment",
        source_node_type="Risk",
        target_node_id="resource-maintenance",
        target_node_type="Resource",
        confidence=0.85,
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail="王工评估：解决设备风险需要扩充维保团队至 5 人",
        extracted_by="human:operator-wang",
        half_life_days=60,
        status=RelationStatus.ACTIVE,
        properties={
            "roi_estimate": 0.35,
            "delay_reduction_pct": 41,
            "investment_rmb": 360000,
        },
    ),
    RelationObject(
        id="demo-rel-s11-002",
        relation_type="ISSUE__REQUIRES__RESOURCE",
        source_node_id="risk-supply-chain",
        source_node_type="Risk",
        target_node_id="resource-supplier-mgmt",
        target_node_type="Resource",
        confidence=0.80,
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail="采购部建议：增派供应商管理专员",
        half_life_days=60,
        status=RelationStatus.ACTIVE,
        properties={
            "roi_estimate": 0.28,
            "delay_reduction_pct": 31,
            "investment_rmb": 180000,
        },
    ),
    RelationObject(
        id="demo-rel-s11-003",
        relation_type="ISSUE__REQUIRES__RESOURCE",
        source_node_id="shift-night",
        source_node_type="Shift",
        target_node_id="resource-night-training",
        target_node_type="Resource",
        confidence=0.75,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="LLM 分析：夜班处理时间比白班长 38%，建议针对性培训",
        half_life_days=60,
        status=RelationStatus.PENDING_REVIEW,
        properties={
            "roi_estimate": 0.22,
            "resolution_time_reduction_pct": 28,
            "investment_rmb": 50000,
        },
    ),

    # 资源 → 改善效果
    RelationObject(
        id="demo-rel-s11-004",
        relation_type="RESOURCE__REDUCES__ISSUE",
        source_node_id="resource-maintenance",
        source_node_type="Resource",
        target_node_id="risk-equipment",
        target_node_type="Risk",
        confidence=0.72,
        provenance=SourceType.INFERENCE,
        provenance_detail="历史数据推断：类似企业增配维保后设备故障率下降 35%",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"expected_risk_reduction_pct": 35, "payback_months": 8},
    ),

    # ── 场景12：战略决策模拟 ──────────────────────────────────────────────

    # 产能-故障率历史关联（基于历史数据）
    RelationObject(
        id="demo-rel-s12-001",
        relation_type="CAPACITY__AFFECTS__FAILURE_RATE",
        source_node_id="line-L2",
        source_node_type="Line",
        target_node_id="risk-equipment",
        target_node_type="Risk",
        confidence=0.78,
        provenance=SourceType.INFERENCE,
        provenance_detail="历史规律：产线 L2 满负荷运行时故障率比正常高 1.8 倍",
        half_life_days=180,
        status=RelationStatus.ACTIVE,
        properties={
            "current_load_pct": 71,
            "failure_rate_baseline": 0.08,
            "load_failure_elasticity": 1.8,  # 负载增加 1% → 故障率增加 1.8%
        },
    ),
    RelationObject(
        id="demo-rel-s12-002",
        relation_type="CAPACITY__AFFECTS__FAILURE_RATE",
        source_node_id="line-L1",
        source_node_type="Line",
        target_node_id="risk-quality",
        target_node_type="Risk",
        confidence=0.71,
        provenance=SourceType.INFERENCE,
        provenance_detail="历史规律：L1 高负荷时质量缺陷率上升",
        half_life_days=180,
        status=RelationStatus.ACTIVE,
        properties={
            "current_load_pct": 65,
            "defect_rate_baseline": 0.032,
            "load_quality_elasticity": 0.9,
        },
    ),
    RelationObject(
        id="demo-rel-s12-003",
        relation_type="LOAD__INCREASES__RISK",
        source_node_id="machine-M3",
        source_node_type="Machine",
        target_node_id="risk-equipment",
        target_node_type="Risk",
        confidence=0.84,
        provenance=SourceType.SENSOR_REALTIME,
        provenance_detail="传感器分析：M3 负载与过热告警强正相关（r=0.84）",
        half_life_days=30,
        status=RelationStatus.ACTIVE,
        properties={
            "correlation_r": 0.84,
            "current_load_pct": 78,
            "overheat_threshold_load_pct": 85,
        },
    ),

    # ── 提示标注队列补充（pending_review · 置信度 0.50–0.79）────────────────
    RelationObject(
        id="demo-rel-prompt-004",
        relation_type="ALARM__AFFECTS__WORKORDER",
        source_node_id="alarm-TEMP-002",
        source_node_type="Alarm",
        target_node_id="workorder-WO-003",
        target_node_type="WorkOrder",
        confidence=0.61,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="MES 关联：温度告警与 WO-003 进度异常（待提示标注确认）",
        half_life_days=60,
        status=RelationStatus.PENDING_REVIEW,
        properties={},
    ),
    RelationObject(
        id="demo-rel-prompt-005",
        relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
        source_node_id="alarm-VIB-001",
        source_node_type="Alarm",
        target_node_id="component-coolant-M1",
        target_node_type="Component",
        confidence=0.55,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="维修记录摘要：振动告警可能与冷却系统流量不足并存（低置信度）",
        half_life_days=90,
        status=RelationStatus.PENDING_REVIEW,
        properties={},
    ),
    RelationObject(
        id="demo-rel-prompt-006",
        relation_type="MACHINE__AFFECTS__QUALITY",
        source_node_id="machine-M3",
        source_node_type="Machine",
        target_node_id="issue-BEAR-001",
        target_node_type="Issue",
        confidence=0.58,
        provenance=SourceType.LLM_EXTRACTED,
        provenance_detail="QMS 导出：焊接线缺陷报告与 M3 停机时段重叠（待确认）",
        half_life_days=90,
        status=RelationStatus.PENDING_REVIEW,
        properties={},
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────────────────────────────────────

async def seed_demo() -> None:
    print("🎬 开始注入演示场景数据（场景 7-12）...")
    print(f"   Neo4j: {settings.NEO4J_URI}")

    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    await driver.verify_connectivity()
    print("✓  Neo4j 连接成功")

    repo = RelationRepository(driver)

    # 注入节点
    print(f"\n📌 注入 {len(NODES)} 个演示节点...")
    for node_data in NODES:
        node = Node(
            id=node_data["id"],
            node_type=node_data["node_type"],
            name=node_data["name"],
            properties=node_data.get("properties", {}),
        )
        await repo.upsert_node(node)
        print(f"   ✓ [{node.node_type:12s}] {node.name}")

    # 注入关系
    print(f"\n🔗 注入 {len(RELATIONS)} 条演示关系...")
    for rel in RELATIONS:
        await repo.upsert_relation(rel)
        src = rel.source_node_id
        tgt = rel.target_node_id
        print(f"   ✓ [{rel.confidence:.2f}] {src} --{rel.relation_type}--> {tgt}")

    await driver.close()

    print("\n✅ 演示场景数据注入完成！")
    print("\n📋 可演示的场景：")
    print("   场景7  → GET /v1/scenarios/line-efficiency")
    print("   场景8  → GET /v1/scenarios/cross-dept-analysis")
    print("   场景9  → GET /v1/scenarios/issue-resolution")
    print("   场景10 → GET /v1/scenarios/risk-radar")
    print("   场景11 → GET /v1/scenarios/resource-optimization")
    print("   场景12 → POST /v1/scenarios/strategic-simulation")
    print("   提示标注 → GET /v1/relations/pending-review（含多条 demo-rel-prompt-* · pending_review）")


if __name__ == "__main__":
    asyncio.run(seed_demo())
