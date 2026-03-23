"""
relos/core/repository.py
------------------------
Neo4j 图数据库操作层。

所有与 Neo4j 的交互集中于此模块，其他模块不直接执行 Cypher。
使用异步 neo4j-driver，配合 FastAPI 的异步生命周期。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from neo4j import AsyncDriver

from relos.core.models import Node, RelationObject, RelationStatus

logger = structlog.get_logger(__name__)


class RelationRepository:
    """
    关系图的持久化操作。

    Neo4j 数据模型：
    - Node  → 图节点，label = node_type（例如 :Device, :Alarm）
    - RelationObject → 图边，type = relation_type，属性存储置信度等元数据
    """

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    # ─── 节点操作 ──────────────────────────────────────────────────

    async def upsert_node(self, node: Node) -> Node:
        """
        插入或更新节点（MERGE on id）。
        """
        query = """
        MERGE (n {id: $id})
        SET n += $props, n.node_type = $node_type, n.name = $name
        RETURN n
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                id=node.id,
                node_type=node.node_type,
                name=node.name,
                props=node.properties,
            )
        logger.debug("node_upserted", node_id=node.id, node_type=node.node_type)
        return node

    # ─── 关系操作 ──────────────────────────────────────────────────

    async def upsert_relation(self, relation: RelationObject) -> RelationObject:
        """
        插入或更新关系。

        注意：合并逻辑（置信度计算）在 RelationEngine 中完成，
        此方法只负责将计算结果写入图。
        """
        query = f"""
        MATCH (src {{id: $src_id}})
        MATCH (tgt {{id: $tgt_id}})
        MERGE (src)-[r:{relation.relation_type} {{id: $rel_id}}]->(tgt)
        SET r += {{
            confidence:       $confidence,
            provenance:       $provenance,
            provenance_detail: $provenance_detail,
            status:           $status,
            half_life_days:   $half_life_days,
            updated_at:       $updated_at,
            conflict_with:    $conflict_with
        }}
        RETURN r
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                src_id=relation.source_node_id,
                tgt_id=relation.target_node_id,
                rel_id=relation.id,
                confidence=relation.confidence,
                provenance=relation.provenance.value,
                provenance_detail=relation.provenance_detail,
                status=relation.status.value,
                half_life_days=relation.half_life_days,
                updated_at=relation.updated_at.isoformat(),
                conflict_with=relation.conflict_with,
            )
        logger.debug("relation_upserted", relation_id=relation.id)
        return relation

    async def get_relation_by_id(self, relation_id: str) -> RelationObject | None:
        """
        按 ID 查询单条关系。
        """
        query = """
        MATCH ()-[r {id: $rel_id}]->()
        RETURN r, type(r) AS rel_type,
               startNode(r).id AS src_id, startNode(r).node_type AS src_type,
               endNode(r).id AS tgt_id, endNode(r).node_type AS tgt_type
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, rel_id=relation_id)
            record = await result.single()
            if not record:
                return None
            return self._record_to_relation(record)

    async def get_subgraph(
        self,
        center_node_id: str,
        max_hops: int = 2,
        min_confidence: float = 0.3,
        statuses: list[RelationStatus] | None = None,
    ) -> list[RelationObject]:
        """
        以指定节点为中心，提取 N 跳子图（供 Context Engine 使用）。

        Args:
            center_node_id: 中心节点 ID（例如告警关联的设备）
            max_hops: 最大跳数，默认 2
            min_confidence: 最低置信度过滤，低于此值的关系不返回
            statuses: 允许的状态列表，默认 [active]
        """
        allowed_statuses = [s.value for s in (statuses or [RelationStatus.ACTIVE])]

        query = """
        MATCH (center {id: $center_id})
        CALL apoc.path.subgraphAll(center, {
            maxLevel: $max_hops,
            relationshipFilter: '>'
        })
        YIELD relationships
        UNWIND relationships AS r
        WITH r
        WHERE r.confidence >= $min_confidence
          AND r.status IN $statuses
        RETURN r, type(r) AS rel_type,
               startNode(r).id AS src_id, startNode(r).node_type AS src_type,
               endNode(r).id AS tgt_id, endNode(r).node_type AS tgt_type
        ORDER BY r.confidence DESC
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(
                query,
                center_id=center_node_id,
                max_hops=max_hops,
                min_confidence=min_confidence,
                statuses=allowed_statuses,
            )
            records = await result.data()

        relations = [self._record_to_relation(r) for r in records]
        logger.info(
            "subgraph_extracted",
            center_node=center_node_id,
            relation_count=len(relations),
        )
        return relations

    async def find_relation(
        self,
        source_node_id: str,
        target_node_id: str,
        relation_type: str,
    ) -> RelationObject | None:
        """
        按节点对 + 关系类型查找已存在的关系（用于合并逻辑）。
        """
        query = f"""
        MATCH (src {{id: $src_id}})-[r:{relation_type} {{}}]->(tgt {{id: $tgt_id}})
        RETURN r, type(r) AS rel_type,
               startNode(r).id AS src_id, startNode(r).node_type AS src_type,
               endNode(r).id AS tgt_id, endNode(r).node_type AS tgt_type
        LIMIT 1
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(
                query,
                src_id=source_node_id,
                tgt_id=target_node_id,
            )
            record = await result.single()
            if not record:
                return None
            return self._record_to_relation(record)

    async def get_graph_metrics(self) -> dict[str, Any]:
        """
        获取关系图谱统计信息，供 /v1/metrics 端点使用。
        """
        query = """
        MATCH ()-[r]->()
        RETURN
            count(r) AS total_relations,
            avg(r.confidence) AS avg_confidence,
            count(CASE WHEN r.status = 'active' THEN 1 END) AS active_count,
            count(CASE WHEN r.status = 'pending_review' THEN 1 END) AS pending_review_count,
            count(CASE WHEN r.status = 'conflicted' THEN 1 END) AS conflicted_count,
            count(CASE WHEN r.status = 'archived' THEN 1 END) AS archived_count
        """
        node_query = "MATCH (n) RETURN count(n) AS total_nodes"

        async with self._driver.session(database=self._db) as session:
            rel_result = await session.run(query)
            rel_record = await rel_result.single()
            node_result = await session.run(node_query)
            node_record = await node_result.single()

        return {
            "total_nodes": node_record["total_nodes"] if node_record else 0,
            "total_relations": rel_record["total_relations"] if rel_record else 0,
            "avg_confidence": round(rel_record["avg_confidence"] or 0.0, 4) if rel_record else 0.0,
            "active_count": rel_record["active_count"] if rel_record else 0,
            "pending_review_count": rel_record["pending_review_count"] if rel_record else 0,
            "conflicted_count": rel_record["conflicted_count"] if rel_record else 0,
            "archived_count": rel_record["archived_count"] if rel_record else 0,
        }

    async def get_pending_review_relations(
        self,
        limit: int = 50,
    ) -> list[RelationObject]:
        """
        获取待人工审核的关系列表（Human-in-the-Loop 工作队列）。
        """
        query = """
        MATCH ()-[r]->()
        WHERE r.status = 'pending_review'
        RETURN r, type(r) AS rel_type,
               startNode(r).id AS src_id, startNode(r).node_type AS src_type,
               endNode(r).id AS tgt_id, endNode(r).node_type AS tgt_type
        ORDER BY r.confidence DESC
        LIMIT $limit
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, limit=limit)
            records = await result.data()
        return [self._record_to_relation(r) for r in records]

    # ─── 内部转换 ──────────────────────────────────────────────────

    @staticmethod
    def _record_to_relation(record: dict[str, Any]) -> RelationObject:
        """将 Neo4j 查询结果转换为 RelationObject。"""
        r = record["r"]
        return RelationObject(
            id=r["id"],
            relation_type=record["rel_type"],
            source_node_id=record["src_id"],
            source_node_type=record["src_type"],
            target_node_id=record["tgt_id"],
            target_node_type=record["tgt_type"],
            confidence=r["confidence"],
            provenance=r["provenance"],
            provenance_detail=r.get("provenance_detail", ""),
            status=r["status"],
            half_life_days=r.get("half_life_days", 90),
            updated_at=datetime.fromisoformat(r["updated_at"]),
            conflict_with=r.get("conflict_with", []),
        )
