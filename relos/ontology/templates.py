"""
relos/ontology/templates.py
----------------------------
行业本体模板（Sprint 4 Week 17-18）。

提供两种行业的预置关系模板，降低新客户冷启动门槛。

支持的行业：
- automotive: 汽车零部件（焊接、冲压、总装）
- electronics_3c: 3C 电子（SMT、AOI、测试）

使用方式：
  templates = get_templates_for_industry("automotive")
  # 返回 List[RelationObject]，可直接批量导入

设计文档 §8.1：本体模板遵循 RelationObject Schema，
所有模板关系使用 provenance=MANUAL_ENGINEER，confidence=0.85，
客户使用后通过反馈循环校正到真实场景。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from relos.core.models import RelationObject, RelationStatus, SourceType

Industry = Literal["automotive", "electronics_3c"]


@dataclass
class OntologyTemplate:
    """行业本体模板元数据。"""
    industry: Industry
    name: str
    description: str
    version: str
    relations: list[RelationObject] = field(default_factory=list)


def _make_template_relation(
    relation_type: str,
    source_node_id: str,
    source_node_type: str,
    target_node_id: str,
    target_node_type: str,
    confidence: float = 0.85,
    properties: dict | None = None,
) -> RelationObject:
    """创建模板关系（工程师经验来源，pending_review 等待客户确认）。"""
    return RelationObject(
        relation_type=relation_type,
        source_node_id=source_node_id,
        source_node_type=source_node_type,
        target_node_id=target_node_id,
        target_node_type=target_node_type,
        confidence=confidence,
        provenance=SourceType.MANUAL_ENGINEER,
        status=RelationStatus.PENDING_REVIEW,  # 需客户确认后才变 active
        provenance_detail="行业本体模板（需客户根据实际场景确认）",
        properties=properties or {},
    )


# ─── 汽车零部件行业模板 ────────────────────────────────────────────────

AUTOMOTIVE_TEMPLATE = OntologyTemplate(
    industry="automotive",
    name="汽车零部件行业本体模板",
    description="覆盖焊接、冲压、总装工艺的设备-告警-组件关系模板",
    version="1.0.0",
    relations=[
        # 焊接工站故障链
        _make_template_relation(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="welding-robot-template",
            source_node_type="Device",
            target_node_id="alarm-weld-spatter-template",
            target_node_type="Alarm",
            confidence=0.90,
            properties={"process": "welding", "alarm_category": "quality"},
        ),
        _make_template_relation(
            relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
            source_node_id="alarm-weld-spatter-template",
            source_node_type="Alarm",
            target_node_id="weld-gun-electrode-template",
            target_node_type="Component",
            confidence=0.85,
            properties={"failure_mode": "electrode_wear", "mttr_hours": "2"},
        ),
        _make_template_relation(
            relation_type="COMPONENT__PART_OF__DEVICE",
            source_node_id="weld-gun-electrode-template",
            source_node_type="Component",
            target_node_id="welding-robot-template",
            target_node_type="Device",
            confidence=0.95,
        ),
        # 冲压工站故障链
        _make_template_relation(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="stamping-press-template",
            source_node_type="Device",
            target_node_id="alarm-die-misalign-template",
            target_node_type="Alarm",
            confidence=0.88,
            properties={"process": "stamping", "alarm_category": "equipment"},
        ),
        _make_template_relation(
            relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
            source_node_id="alarm-die-misalign-template",
            source_node_type="Alarm",
            target_node_id="upper-die-guide-template",
            target_node_type="Component",
            confidence=0.82,
            properties={"failure_mode": "guide_wear", "replacement_cycle_km": "500000"},
        ),
        # 振动告警通用关系（设备通用）
        _make_template_relation(
            relation_type="ALARM__CORRELATES__ALARM",
            source_node_id="alarm-vibration-x-template",
            source_node_type="Alarm",
            target_node_id="alarm-vibration-z-template",
            target_node_type="Alarm",
            confidence=0.75,
            properties={"correlation_type": "co-occurrence", "axis": "multiple"},
        ),
        # 操作员-操作关联
        _make_template_relation(
            relation_type="OPERATOR__PERFORMS__OPERATION",
            source_node_id="operator-welding-template",
            source_node_type="Operator",
            target_node_id="weld-gun-replace-template",
            target_node_type="Operation",
            confidence=0.80,
            properties={"operation_type": "maintenance", "skill_level": "level-3"},
        ),
    ],
)


# ─── 3C 电子行业模板 ──────────────────────────────────────────────────

ELECTRONICS_3C_TEMPLATE = OntologyTemplate(
    industry="electronics_3c",
    name="3C 电子行业本体模板",
    description="覆盖 SMT 贴片、AOI 检测、ICT 测试工序的关系模板",
    version="1.0.0",
    relations=[
        # SMT 贴片故障链
        _make_template_relation(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="smt-machine-template",
            source_node_type="Device",
            target_node_id="alarm-placement-offset-template",
            target_node_type="Alarm",
            confidence=0.88,
            properties={"process": "smt", "alarm_category": "quality", "spec_mm": "0.1"},
        ),
        _make_template_relation(
            relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
            source_node_id="alarm-placement-offset-template",
            source_node_type="Alarm",
            target_node_id="smt-nozzle-template",
            target_node_type="Component",
            confidence=0.83,
            properties={"failure_mode": "nozzle_clog", "replacement_cycle_pcs": "200000"},
        ),
        # AOI 检测关联
        _make_template_relation(
            relation_type="ALARM__CORRELATES__ALARM",
            source_node_id="alarm-placement-offset-template",
            source_node_type="Alarm",
            target_node_id="alarm-aoi-false-positive-template",
            target_node_type="Alarm",
            confidence=0.70,
            properties={"correlation_type": "causal", "delay_seconds": "120"},
        ),
        _make_template_relation(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="aoi-machine-template",
            source_node_type="Device",
            target_node_id="alarm-aoi-false-positive-template",
            target_node_type="Alarm",
            confidence=0.85,
            properties={"process": "aoi", "defect_type": "solder_bridge"},
        ),
        # 锡膏印刷工序
        _make_template_relation(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id="spi-machine-template",
            source_node_type="Device",
            target_node_id="alarm-solder-volume-template",
            target_node_type="Alarm",
            confidence=0.87,
            properties={"process": "screen_printing", "alarm_category": "quality"},
        ),
        _make_template_relation(
            relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
            source_node_id="alarm-solder-volume-template",
            source_node_type="Alarm",
            target_node_id="stencil-template",
            target_node_type="Component",
            confidence=0.80,
            properties={"failure_mode": "stencil_clog", "cleaning_cycle_pcs": "5000"},
        ),
    ],
)


# ─── 注册表 ─────────────────────────────────────────────────────────

_REGISTRY: dict[Industry, OntologyTemplate] = {
    "automotive": AUTOMOTIVE_TEMPLATE,
    "electronics_3c": ELECTRONICS_3C_TEMPLATE,
}


def get_templates_for_industry(industry: Industry) -> OntologyTemplate:
    """获取指定行业的本体模板。"""
    if industry not in _REGISTRY:
        raise ValueError(f"未知行业: {industry}。支持: {list(_REGISTRY.keys())}")
    return _REGISTRY[industry]


def list_available_industries() -> list[dict]:
    """列出所有可用的行业模板摘要。"""
    return [
        {
            "industry": key,
            "name": tmpl.name,
            "description": tmpl.description,
            "version": tmpl.version,
            "relation_count": len(tmpl.relations),
        }
        for key, tmpl in _REGISTRY.items()
    ]
