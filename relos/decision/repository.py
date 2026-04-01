from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import structlog
from neo4j import AsyncDriver

from relos.core.models import (
    ActionBundle,
    DecisionPackage,
    DecisionPackageStatus,
    DecisionReviewRecord,
)

logger = structlog.get_logger(__name__)


class DecisionRepository:
    """复合场景决策包与动作包的轻量持久化层。"""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    async def save_decision_package(self, package: DecisionPackage) -> DecisionPackage:
        query = """
        MERGE (d:DecisionPackage {decision_id: $decision_id})
        SET d += {
            incident_id: $incident_id,
            title: $title,
            incident_summary: $incident_summary,
            risk_level: $risk_level,
            recommended_plan_id: $recommended_plan_id,
            candidate_plans_json: $candidate_plans_json,
            recommended_actions_json: $recommended_actions_json,
            evidence_relations_json: $evidence_relations_json,
            requires_human_review: $requires_human_review,
            review_reason: $review_reason,
            trace_id: $trace_id,
            status: $status,
            context_block: $context_block,
            context_query_strategy: $context_query_strategy,
            context_relations_count: $context_relations_count,
            created_at: $created_at,
            updated_at: $updated_at
        }
        RETURN d
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                decision_id=package.decision_id,
                incident_id=package.incident_id,
                title=package.title,
                incident_summary=package.incident_summary,
                risk_level=package.risk_level.value,
                recommended_plan_id=package.recommended_plan_id,
                candidate_plans_json=json.dumps(
                    [item.model_dump(mode="json") for item in package.candidate_plans],
                    ensure_ascii=True,
                ),
                recommended_actions_json=json.dumps(
                    [item.model_dump(mode="json") for item in package.recommended_actions],
                    ensure_ascii=True,
                ),
                evidence_relations_json=json.dumps(package.evidence_relations, ensure_ascii=True),
                requires_human_review=package.requires_human_review,
                review_reason=package.review_reason,
                trace_id=package.trace_id,
                status=package.status.value,
                context_block=package.context_block,
                context_query_strategy=package.context_query_strategy,
                context_relations_count=package.context_relations_count,
                created_at=package.created_at.isoformat(),
                updated_at=package.updated_at.isoformat(),
            )
        logger.debug("decision_package_saved", decision_id=package.decision_id)
        return package

    async def get_decision_package(self, incident_id: str) -> DecisionPackage | None:
        query = "MATCH (d:DecisionPackage {incident_id: $incident_id}) RETURN d LIMIT 1"
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, incident_id=incident_id)
            record = await result.single()
        if not record:
            return None
        return _node_to_decision_package(record["d"])

    async def get_decision_package_by_id(self, decision_id: str) -> DecisionPackage | None:
        query = "MATCH (d:DecisionPackage {decision_id: $decision_id}) RETURN d LIMIT 1"
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, decision_id=decision_id)
            record = await result.single()
        if not record:
            return None
        return _node_to_decision_package(record["d"])

    async def list_pending_review(self, limit: int = 20) -> list[DecisionPackage]:
        query = """
        MATCH (d:DecisionPackage)
        WHERE d.status = $status
        RETURN d
        ORDER BY d.updated_at DESC
        LIMIT $limit
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(
                query,
                status=DecisionPackageStatus.PENDING_REVIEW.value,
                limit=limit,
            )
            rows = await result.data()
        return [_node_to_decision_package(row["d"]) for row in rows]

    async def save_review(self, review: DecisionReviewRecord) -> DecisionReviewRecord:
        query = """
        MERGE (r:DecisionReviewRecord {decision_id: $decision_id})
        SET r += {
            status: $status,
            reviewed_by: $reviewed_by,
            review_comment: $review_comment,
            selected_plan_id: $selected_plan_id,
            approved_actions_json: $approved_actions_json,
            rejected_actions_json: $rejected_actions_json,
            reviewed_at: $reviewed_at
        }
        RETURN r
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                decision_id=review.decision_id,
                status=review.status.value,
                reviewed_by=review.reviewed_by,
                review_comment=review.review_comment,
                selected_plan_id=review.selected_plan_id,
                approved_actions_json=json.dumps(review.approved_actions, ensure_ascii=True),
                rejected_actions_json=json.dumps(review.rejected_actions, ensure_ascii=True),
                reviewed_at=review.reviewed_at.isoformat(),
            )
        logger.debug(
            "decision_review_saved",
            decision_id=review.decision_id,
            status=review.status.value,
        )
        return review

    async def save_action_bundle(self, bundle: ActionBundle) -> ActionBundle:
        query = """
        MERGE (b:ActionBundle {bundle_id: $bundle_id})
        SET b += {
            decision_id: $decision_id,
            status: $status,
            actions_json: $actions_json,
            shadow_mode: $shadow_mode,
            execution_notes: $execution_notes,
            created_at: $created_at,
            updated_at: $updated_at
        }
        RETURN b
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                bundle_id=bundle.bundle_id,
                decision_id=bundle.decision_id,
                status=bundle.status.value,
                actions_json=json.dumps(
                    [item.model_dump(mode="json") for item in bundle.actions],
                    ensure_ascii=True,
                ),
                shadow_mode=bundle.shadow_mode,
                execution_notes=bundle.execution_notes,
                created_at=bundle.created_at.isoformat(),
                updated_at=bundle.updated_at.isoformat(),
            )
        logger.debug("action_bundle_saved", bundle_id=bundle.bundle_id)
        return bundle

    async def get_action_bundle(self, decision_id: str) -> ActionBundle | None:
        query = "MATCH (b:ActionBundle {decision_id: $decision_id}) RETURN b LIMIT 1"
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, decision_id=decision_id)
            record = await result.single()
        if not record:
            return None
        return _node_to_action_bundle(record["b"])


def _node_to_decision_package(node: Any) -> DecisionPackage:
    return DecisionPackage(
        decision_id=node["decision_id"],
        incident_id=node["incident_id"],
        title=node["title"],
        incident_summary=node["incident_summary"],
        risk_level=node.get("risk_level", "medium"),
        recommended_plan_id=node["recommended_plan_id"],
        candidate_plans=_load_json(node.get("candidate_plans_json", "[]")),
        recommended_actions=_load_json(node.get("recommended_actions_json", "[]")),
        evidence_relations=_load_json(node.get("evidence_relations_json", "[]")),
        requires_human_review=bool(node.get("requires_human_review", True)),
        review_reason=node.get("review_reason", ""),
        trace_id=node.get("trace_id", ""),
        status=node.get("status", DecisionPackageStatus.DRAFT.value),
        context_block=node.get("context_block", ""),
        context_query_strategy=node.get("context_query_strategy", ""),
        context_relations_count=int(node.get("context_relations_count", 0) or 0),
        created_at=_parse_dt(node.get("created_at")),
        updated_at=_parse_dt(node.get("updated_at")),
    )


def _node_to_action_bundle(node: Any) -> ActionBundle:
    return ActionBundle(
        bundle_id=node["bundle_id"],
        decision_id=node["decision_id"],
        status=node.get("status", DecisionPackageStatus.DRAFT.value),
        actions=_load_json(node.get("actions_json", "[]")),
        shadow_mode=bool(node.get("shadow_mode", True)),
        execution_notes=node.get("execution_notes", ""),
        created_at=_parse_dt(node.get("created_at")),
        updated_at=_parse_dt(node.get("updated_at")),
    )


def _load_json(raw: str) -> Any:
    try:
        return json.loads(raw or "[]")
    except Exception:
        return []


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if isinstance(raw, str) and raw:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    return datetime.now(UTC)
