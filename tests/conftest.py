"""
tests/conftest.py
-----------------
共享测试 Fixture（跨所有测试层级）。

- 单元测试：无外部依赖的工厂 Fixture
- 集成测试：提供 Neo4j / Redis 连接（标记 @pytest.mark.integration）
- E2E 测试：提供完整 FastAPI TestClient（标记 @pytest.mark.e2e）

使用方式：
  pytest tests/unit/       # 只跑单元测试（无需 Docker）
  pytest tests/ -m mvp     # 跑冒烟测试
  pytest tests/ -m integration  # 需要 Docker Compose 启动
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from relos.core.models import RelationObject, RelationStatus, SourceType

# ─── 通用工厂 Fixture ─────────────────────────────────────────────────

@pytest.fixture
def make_relation():
    """返回一个工厂函数，用于创建测试用 RelationObject。"""
    def _factory(
        relation_type: str = "DEVICE__TRIGGERS__ALARM",
        source_node_id: str = "device-M1",
        source_node_type: str = "Device",
        target_node_id: str = "alarm-001",
        target_node_type: str = "Alarm",
        confidence: float = 0.80,
        provenance: SourceType = SourceType.SENSOR_REALTIME,
        status: RelationStatus = RelationStatus.ACTIVE,
        properties: dict[str, Any] | None = None,
    ) -> RelationObject:
        return RelationObject(
            relation_type=relation_type,
            source_node_id=source_node_id,
            source_node_type=source_node_type,
            target_node_id=target_node_id,
            target_node_type=target_node_type,
            confidence=confidence,
            provenance=provenance,
            status=status,
            properties=properties or {},
        )
    return _factory


@pytest.fixture
def sample_alarm_event() -> dict[str, str]:
    """标准测试告警事件（JSON 可序列化）。"""
    return {
        "alarm_id": "ALM-VIB-001",
        "device_id": "CNC-M1",
        "alarm_code": "VIB-001",
        "alarm_description": "主轴振动超限 18.3mm/s",
        "severity": "medium",
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ─── 集成测试 Fixture（需要 Neo4j）────────────────────────────────────

@pytest.fixture(scope="session")
def neo4j_url() -> str:
    """Neo4j 测试实例 URL（从环境变量读取，默认 localhost）。"""
    import os
    return os.getenv("NEO4J_URI", "bolt://localhost:7687")


@pytest.fixture(scope="session")
def neo4j_auth() -> tuple[str, str]:
    """Neo4j 认证信息。"""
    import os
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    return (user, password)


# ─── E2E Fixture（完整 FastAPI 应用）────────────────────────────────────

@pytest.fixture
def test_app():
    """
    创建 FastAPI TestClient（不连接真实 Neo4j）。
    适用于路由注册测试、Schema 验证、Middleware 测试。
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from relos.api.v1 import decisions, expert_init, metrics, relations

    app = FastAPI(title="RelOS Test")
    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
    app.include_router(expert_init.router, prefix="/v1/expert-init", tags=["expert-init"])
    app.include_router(metrics.router, prefix="/v1/metrics", tags=["metrics"])

    return TestClient(app)
