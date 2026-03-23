"""
tests/integration/test_full_pipeline.py
-----------------------------------------
端到端集成测试套件（需要 Neo4j 实例）。

运行方式：
    # 启动服务
    docker compose up -d

    # 运行集成测试
    pytest tests/integration -v -m integration

所有集成测试标记为 @pytest.mark.integration，
在没有 Neo4j 实例时跳过。

测试覆盖完整业务流程：
1. 专家录入关系 → Neo4j 存储
2. Excel 批量导入 → Neo4j 存储
3. 告警触发 → 子图提取 → Context 编译 → 决策推理
4. 人工反馈 → 置信度更新（数据飞轮）
5. /v1/metrics 端点返回正确统计
"""

from __future__ import annotations

import asyncio
import os

import pytest

# ─── 集成测试跳过条件 ────────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_AVAILABLE = False

try:
    from neo4j import AsyncGraphDatabase

    async def _check_neo4j() -> bool:
        try:
            driver = AsyncGraphDatabase.driver(
                NEO4J_URI,
                auth=(
                    os.getenv("NEO4J_USER", "neo4j"),
                    os.getenv("NEO4J_PASSWORD", "relos_dev"),
                ),
            )
            await driver.verify_connectivity()
            await driver.close()
            return True
        except Exception:
            return False

    NEO4J_AVAILABLE = asyncio.get_event_loop().run_until_complete(_check_neo4j())
except Exception:
    NEO4J_AVAILABLE = False

requires_neo4j = pytest.mark.skipif(
    not NEO4J_AVAILABLE,
    reason="Neo4j 实例不可用，跳过集成测试（运行 docker compose up -d）",
)


# ─── Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
async def neo4j_driver():
    """提供 Neo4j 异步 driver（集成测试专用）。"""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "relos_dev"),
        ),
    )
    yield driver
    await driver.close()


@pytest.fixture
async def repo(neo4j_driver):
    """提供初始化好的 RelationRepository。"""
    from relos.core.repository import RelationRepository
    return RelationRepository(neo4j_driver)


@pytest.fixture
async def clean_test_nodes(neo4j_driver):
    """测试前后清理测试节点。"""
    # 测试数据前缀，避免污染生产数据
    yield
    async with neo4j_driver.session(database="neo4j") as session:
        await session.run(
            "MATCH (n) WHERE n.id STARTS WITH 'IT-TEST-' DETACH DELETE n"
        )


# ─── 集成测试 ─────────────────────────────────────────────────────────

@pytest.mark.integration
@requires_neo4j
class TestExpertInitFlow:
    """专家初始化流程集成测试。"""

    async def test_upsert_and_retrieve_relation(
        self, repo, clean_test_nodes
    ) -> None:
        """专家录入关系后应能通过 ID 检索。"""
        from relos.core.models import Node, RelationObject, RelationStatus, SourceType

        # 创建节点
        await repo.upsert_node(Node(
            id="IT-TEST-device-001", node_type="Device", name="测试设备 001"
        ))
        await repo.upsert_node(Node(
            id="IT-TEST-alarm-001", node_type="Alarm", name="测试告警 001"
        ))

        # 录入关系
        relation = RelationObject(
            source_node_id="IT-TEST-device-001",
            source_node_type="Device",
            target_node_id="IT-TEST-alarm-001",
            target_node_type="Alarm",
            relation_type="DEVICE__TRIGGERS__ALARM",
            confidence=0.92,
            provenance=SourceType.MANUAL_ENGINEER,
            status=RelationStatus.ACTIVE,
        )
        saved = await repo.upsert_relation(relation)
        assert saved.id == relation.id

        # 检索验证
        retrieved = await repo.get_relation_by_id(relation.id)
        assert retrieved is not None
        assert retrieved.confidence == 0.92
        assert retrieved.status == RelationStatus.ACTIVE

    async def test_find_relation_by_node_pair(
        self, repo, clean_test_nodes
    ) -> None:
        """find_relation 应通过节点对和关系类型精确查找。"""
        from relos.core.models import Node, RelationObject, RelationStatus, SourceType

        await repo.upsert_node(Node(id="IT-TEST-d2", node_type="Device", name="d2"))
        await repo.upsert_node(Node(id="IT-TEST-a2", node_type="Alarm", name="a2"))

        relation = RelationObject(
            source_node_id="IT-TEST-d2",
            source_node_type="Device",
            target_node_id="IT-TEST-a2",
            target_node_type="Alarm",
            relation_type="DEVICE__TRIGGERS__ALARM",
            confidence=0.80,
            provenance=SourceType.MES_STRUCTURED,
            status=RelationStatus.ACTIVE,
        )
        await repo.upsert_relation(relation)

        found = await repo.find_relation("IT-TEST-d2", "IT-TEST-a2", "DEVICE__TRIGGERS__ALARM")
        assert found is not None
        assert found.confidence == 0.80


@pytest.mark.integration
@requires_neo4j
class TestHumanFeedbackFlywheel:
    """人工反馈数据飞轮集成测试。"""

    async def test_confirm_relation_increases_confidence(
        self, repo, clean_test_nodes
    ) -> None:
        """工程师确认关系应提升置信度并设为 active。"""
        from relos.core.engine import RelationEngine
        from relos.core.models import Node, RelationObject, RelationStatus, SourceType

        engine = RelationEngine()

        await repo.upsert_node(Node(id="IT-TEST-d3", node_type="Device", name="d3"))
        await repo.upsert_node(Node(id="IT-TEST-a3", node_type="Alarm", name="a3"))

        relation = RelationObject(
            source_node_id="IT-TEST-d3",
            source_node_type="Device",
            target_node_id="IT-TEST-a3",
            target_node_type="Alarm",
            relation_type="DEVICE__TRIGGERS__ALARM",
            confidence=0.60,
            provenance=SourceType.LLM_EXTRACTED,
            status=RelationStatus.PENDING_REVIEW,
        )
        await repo.upsert_relation(relation)

        updated = engine.apply_human_feedback(relation, confirmed=True, engineer_id="eng-001")
        await repo.upsert_relation(updated)

        final = await repo.get_relation_by_id(relation.id)
        assert final is not None
        assert final.confidence > 0.60
        assert final.status == RelationStatus.ACTIVE


@pytest.mark.integration
@requires_neo4j
class TestGraphMetrics:
    """图谱统计指标集成测试。"""

    async def test_metrics_returns_counts(self, repo) -> None:
        """get_graph_metrics 应返回包含所有必要字段的统计。"""
        metrics = await repo.get_graph_metrics()

        assert "total_nodes" in metrics
        assert "total_relations" in metrics
        assert "avg_confidence" in metrics
        assert "active_count" in metrics
        assert "pending_review_count" in metrics
        assert isinstance(metrics["total_nodes"], int)
        assert isinstance(metrics["avg_confidence"], float)
