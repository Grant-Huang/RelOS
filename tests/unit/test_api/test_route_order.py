"""
tests/unit/test_api/test_route_order.py
----------------------------------------
T-08：FastAPI 路由注册顺序回归测试。

防止静态路径（/pending-review）被参数化路径（/{relation_id}）遮蔽。
这是 D-01 修复后的回归保护，确保路由顺序不被意外还原。

注意：此文件使用 TestClient（同步），不需要 Neo4j 或 Redis。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from relos.api.v1.relations import router as relations_router

# ─── 辅助工厂 ────────────────────────────────────────────────────────

def make_test_app() -> FastAPI:
    """创建最小 FastAPI 应用，只挂载 relations 路由，用于路由顺序测试。"""
    app = FastAPI()
    app.include_router(relations_router, prefix="/v1/relations")
    return app


# ─── 路由注册顺序测试 ─────────────────────────────────────────────────

@pytest.mark.unit
class TestRouteOrder:

    def test_pending_review_route_is_registered_before_relation_id(self) -> None:
        """T-08：/pending-review 路由必须在 /{relation_id} 之前注册。

        FastAPI/Starlette 按定义顺序匹配路由，若顺序错误，
        GET /v1/relations/pending-review 会被匹配为 GET /{relation_id}，
        导致查找 relation_id="pending-review" 而返回 404。
        """
        app = make_test_app()
        routes = [r.path for r in app.routes]  # type: ignore[union-attr]

        pending_path = "/v1/relations/pending-review"
        rel_id_path = "/v1/relations/{relation_id}"

        assert pending_path in routes, f"路由 {pending_path} 未注册"
        assert rel_id_path in routes, f"路由 {rel_id_path} 未注册"

        pending_idx = routes.index(pending_path)
        rel_id_idx = routes.index(rel_id_path)

        assert pending_idx < rel_id_idx, (
            f"路由顺序错误：/pending-review（位置 {pending_idx}）"
            f"应在 /{{relation_id}}（位置 {rel_id_idx}）之前注册。"
            f"这会导致 /pending-review 被错误地当作 relation_id 参数处理。"
        )

    def test_subgraph_route_is_registered_before_relation_id(self) -> None:
        """T-08：/subgraph POST 路由也必须在 /{relation_id} 之前注册"""
        app = make_test_app()
        routes = [r.path for r in app.routes]  # type: ignore[union-attr]

        assert "/v1/relations/subgraph" in routes
        assert "/v1/relations/{relation_id}" in routes

        subgraph_idx = routes.index("/v1/relations/subgraph")
        rel_id_idx = routes.index("/v1/relations/{relation_id}")

        assert subgraph_idx < rel_id_idx

    def test_all_expected_routes_registered(self) -> None:
        """T-08：验证所有期望的关系路由都已注册（防止意外漏注册）"""
        app = make_test_app()
        routes = {r.path for r in app.routes}  # type: ignore[union-attr]

        expected = {
            "/v1/relations/pending-review",
            "/v1/relations/subgraph",
            "/v1/relations/",
            "/v1/relations/{relation_id}",
            "/v1/relations/{relation_id}/feedback",
        }
        missing = expected - routes
        assert not missing, f"以下路由未注册: {missing}"
