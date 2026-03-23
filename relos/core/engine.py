"""
relos/core/engine.py
--------------------
关系核心引擎：合并、置信度衰减、冲突检测。

这是 RelOS 的核心飞轮驱动模块：
- 每次工程师确认/否定都精确更新置信度（学习反馈机制）
- 冲突关系不删除，保留完整历史
- 时间衰减使用指数函数，按关系类型配置 half_life
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import structlog

from relos.core.models import (
    ALPHA_CONFIG,
    HALF_LIFE_CONFIG,
    MergeResult,
    RelationObject,
    RelationStatus,
)

logger = structlog.get_logger(__name__)


class RelationEngine:
    """
    关系合并与衰减逻辑（纯计算，不依赖数据库）。
    具体的图存储操作由 RelationRepository 负责。
    """

    # ─── 置信度合并（加权滑动平均）────────────────────────────────

    def merge_confidence(
        self,
        existing: RelationObject,
        incoming: RelationObject,
    ) -> MergeResult:
        """
        将新观测的关系与已有关系合并，更新置信度。

        算法（设计文档 §4.1）：
            new_confidence = (1 - alpha) * old_confidence + alpha * incoming_confidence
            alpha 由 incoming 的 provenance 类型决定

        Args:
            existing: 图中已存在的关系
            incoming: 新观测到的关系（来自 Ingestion Layer）

        Returns:
            MergeResult 包含更新后的置信度和冲突信息
        """
        alpha = ALPHA_CONFIG.get(incoming.provenance, 0.3)
        old_conf = existing.confidence
        new_conf = (1 - alpha) * old_conf + alpha * incoming.confidence

        # 检测冲突（同类型关系但方向相反，或置信度差异超过阈值）
        conflict_detected = self._detect_conflict(existing, incoming)

        logger.info(
            "relation_merged",
            relation_id=existing.id,
            old_confidence=round(old_conf, 4),
            new_confidence=round(new_conf, 4),
            alpha=alpha,
            source=incoming.provenance,
            conflict=conflict_detected,
        )

        return MergeResult(
            relation_id=existing.id,
            previous_confidence=old_conf,
            new_confidence=round(new_conf, 4),
            alpha_used=alpha,
            merge_count=0,          # 由 Repository 更新实际计数
            conflict_detected=conflict_detected,
        )

    # ─── 置信度衰减（指数函数）────────────────────────────────────

    def apply_decay(
        self,
        relation: RelationObject,
        as_of: datetime | None = None,
    ) -> float:
        """
        计算关系在当前时间点的衰减后置信度。

        公式（设计文档 §4.2）：
            confidence(t) = c0 * 0.5 ^ (elapsed_days / half_life_days)

        Args:
            relation: 待衰减的关系
            as_of: 计算时间点，默认当前时间

        Returns:
            衰减后的置信度（float, 0.0–1.0）
        """
        as_of = as_of or datetime.now(UTC)
        elapsed_days = (as_of - relation.updated_at).total_seconds() / 86400.0

        # 获取该关系类型的半衰期，默认 90 天
        half_life = HALF_LIFE_CONFIG.get(
            relation.relation_type,
            HALF_LIFE_CONFIG["DEFAULT"]
        )

        decayed = relation.confidence * math.pow(0.5, elapsed_days / half_life)

        # 置信度下限 0.05，防止完全归零导致关系消失
        return max(round(decayed, 4), 0.05)

    # ─── 人工反馈更新（飞轮核心）──────────────────────────────────

    def apply_human_feedback(
        self,
        relation: RelationObject,
        confirmed: bool,
        engineer_id: str,
    ) -> RelationObject:
        """
        工程师确认或否定关系时，精确更新置信度。
        这是数据飞轮的核心：每次反馈都提升系统准确性。

        规则（设计文档 §4.3）：
        - 确认：confidence = min(1.0, confidence + 0.15)，状态 → active
        - 否定：confidence = max(0.0, confidence - 0.30)，confidence < 0.2 则 archived

        Args:
            relation: 待更新的关系
            confirmed: True=确认，False=否定
            engineer_id: 操作工程师 ID，用于审计追踪

        Returns:
            更新后的 RelationObject（需调用方持久化）
        """
        old_conf = relation.confidence

        if confirmed:
            new_conf = min(1.0, relation.confidence + 0.15)
            new_status = RelationStatus.ACTIVE
            feedback_type = "confirmed"
        else:
            new_conf = max(0.0, relation.confidence - 0.30)
            # 置信度过低则归档（但不删除，保留历史）
            new_status = (
                RelationStatus.ARCHIVED
                if new_conf < 0.2
                else RelationStatus.PENDING_REVIEW
            )
            feedback_type = "rejected"

        logger.info(
            "human_feedback_applied",
            relation_id=relation.id,
            feedback=feedback_type,
            engineer_id=engineer_id,
            old_confidence=round(old_conf, 4),
            new_confidence=round(new_conf, 4),
            new_status=new_status,
        )

        # 返回更新后的 copy（immutable-first 设计）
        return relation.model_copy(
            update={
                "confidence": round(new_conf, 4),
                "status": new_status,
                "updated_at": datetime.now(UTC),
                "extracted_by": f"human:{engineer_id}",
            }
        )

    # ─── 冲突检测 ─────────────────────────────────────────────────

    def _detect_conflict(
        self,
        existing: RelationObject,
        incoming: RelationObject,
    ) -> bool:
        """
        判断两条关系是否构成冲突。

        冲突定义（设计文档 §4.4）：
        1. 相同节点对，相同关系类型，但属性矛盾（例如状态互斥）
        2. 置信度差异 > 0.5（说明来源信息严重不一致）
        """
        # 规则 1：节点对和关系类型相同，视为同一关系的不同版本
        same_relation = (
            existing.source_node_id == incoming.source_node_id
            and existing.target_node_id == incoming.target_node_id
            and existing.relation_type == incoming.relation_type
        )

        if not same_relation:
            return False

        # 规则 2：置信度差异超过阈值 → 冲突
        confidence_gap = abs(existing.confidence - incoming.confidence)
        return confidence_gap > 0.5
