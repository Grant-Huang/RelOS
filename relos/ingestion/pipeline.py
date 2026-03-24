"""
relos/ingestion/pipeline.py
---------------------------
统一接入管道：将所有来源的原始数据标准化为 RelationObject。

设计原则（设计文档 §3.1）：
- 语义标准化：不同来源的关系信号必须收敛到同一 Schema
- 置信度初始化：严格按来源类型设置初始置信度区间
- LLM 强制待审：所有 LLM 抽取的关系进入 pending_review
"""

from __future__ import annotations

from datetime import datetime

import structlog

from relos.core.models import RelationObject, RelationStatus, SourceType

logger = structlog.get_logger(__name__)


class IngestionPipeline:
    """
    关系接入管道。
    负责验证、置信度初始化、并路由到 Relation Core Engine。
    """

    # 按来源类型的置信度初始化范围（设计文档 §3.2）
    CONFIDENCE_RANGE: dict[SourceType, tuple[float, float]] = {
        SourceType.MANUAL_ENGINEER: (0.90, 1.00),
        SourceType.SENSOR_REALTIME: (0.80, 0.95),
        SourceType.MES_STRUCTURED:  (0.75, 0.90),
        SourceType.LLM_EXTRACTED:   (0.50, 0.85),   # 硬上限 0.85
        SourceType.INFERENCE:           (0.40, 0.75),
        SourceType.STRUCTURED_DOCUMENT: (0.65, 0.85),
        SourceType.EXPERT_DOCUMENT:     (0.50, 0.85),
    }

    def validate_and_normalize(self, relation: RelationObject) -> RelationObject:
        """
        验证并标准化输入关系：
        1. 置信度必须在该来源允许的范围内
        2. LLM 抽取的关系强制 pending_review（模型层也有 validator，双重保险）
        3. 记录接入日志
        """
        min_c, max_c = self.CONFIDENCE_RANGE[relation.provenance]

        if not (min_c <= relation.confidence <= max_c):
            logger.warning(
                "confidence_out_of_range",
                provenance=relation.provenance,
                confidence=relation.confidence,
                expected_range=(min_c, max_c),
            )
            # 夹紧到合法范围
            clamped = max(min_c, min(max_c, relation.confidence))
            relation = relation.model_copy(update={"confidence": clamped})

        # LLM 抽取强制 pending_review
        if (
            relation.provenance == SourceType.LLM_EXTRACTED
            and relation.status == RelationStatus.ACTIVE
        ):
            relation = relation.model_copy(update={"status": RelationStatus.PENDING_REVIEW})
            logger.info("llm_relation_forced_pending", relation_id=relation.id)

        logger.info(
            "relation_ingested",
            relation_id=relation.id,
            relation_type=relation.relation_type,
            provenance=relation.provenance,
            confidence=relation.confidence,
            status=relation.status,
        )
        return relation


class AlarmRelationExtractor:
    """
    MVP 专用：从告警事件中提取关系。

    输入：原始告警数据（告警码 + 设备 ID）
    输出：RelationObject 列表（设备↔告警的关系）

    这是 MVP 阶段 Ingestion Layer 的主要来源，
    数据已存在于 Andon/SCADA，无需额外采集。
    """

    def extract(
        self,
        device_id: str,
        alarm_id: str,
        alarm_code: str,
        alarm_description: str,
        severity: str = "medium",
    ) -> list[RelationObject]:
        """
        从告警事件中生成关系列表。
        创建两条关系：设备触发告警 + 告警指示严重程度。
        """
        now = datetime.utcnow()

        # 关系 1：设备 --[TRIGGERS]--> 告警
        device_triggers_alarm = RelationObject(
            relation_type="DEVICE__TRIGGERS__ALARM",
            source_node_id=device_id,
            source_node_type="Device",
            target_node_id=alarm_id,
            target_node_type="Alarm",
            confidence=0.95,            # 传感器数据，高置信度
            provenance=SourceType.SENSOR_REALTIME,
            provenance_detail=f"alarm_code={alarm_code}",
            half_life_days=90,
            status=RelationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            properties={
                "alarm_code": alarm_code,
                "severity": severity,
                "description": alarm_description[:200],
            },
        )

        return [device_triggers_alarm]
