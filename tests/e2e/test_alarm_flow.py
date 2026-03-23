"""
tests/e2e/test_alarm_flow.py
-----------------------------
E2E 冒烟测试：告警 → 根因分析完整流程。

标记：@pytest.mark.e2e
需要：运行中的 Neo4j 实例（docker compose up -d）

运行方式：
  pytest tests/e2e/ -v -m e2e

这些测试验证：
1. API 路由可访问
2. Schema 验证正确（Pydantic）
3. 工作流端到端集成（Mock LLM）
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.e2e


@pytest.mark.skip(reason="E2E 测试需要 Neo4j 实例，在 CI 中按需启用")
class TestAlarmAnalysisFlow:
    """E2E：告警分析完整流程测试（需要 Neo4j）"""

    def test_health_check_returns_ok(self, test_app) -> None:
        """服务健康检查应返回 200。"""
        response = test_app.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_analyze_alarm_returns_recommendation(
        self, test_app, sample_alarm_event, monkeypatch
    ) -> None:
        """
        告警分析端点应返回根因推荐。
        Mock Neo4j 和 LangGraph，只验证 API 层行为。
        """
        # TODO: Sprint 4 Week 12 集成测试实现
        # 需要：mock RelationRepository.get_subgraph + mock workflow.ainvoke
        pytest.skip("集成测试需要 Sprint 4 Week 12 实现")

    def test_expert_init_single_relation(self, test_app, make_relation) -> None:
        """专家初始化端点应接受单条关系并返回 201。"""
        pytest.skip("需要真实 Neo4j 连接")

    def test_pending_review_not_shadowed_by_relation_id(self, test_app) -> None:
        """
        D-01 回归：GET /v1/relations/pending-review 应命中静态路由，
        而不是被 /{relation_id} 遮蔽导致 404。
        （此测试不需要 Neo4j，可以在无数据库时运行）
        """
        pytest.skip("需要 app.state.neo4j_driver 注入，改用 test_route_order.py 做单元回归")
