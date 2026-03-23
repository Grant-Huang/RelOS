"""
relos/main.py
-------------
FastAPI 应用入口。

生命周期管理：
- startup: 初始化 Neo4j driver、Redis 连接、创建图约束
- shutdown: 优雅关闭所有连接
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase

from relos.api.v1 import decisions, expert_init, health, metrics, ontology, relations, scenarios
from relos.config import settings
from relos.middleware.jwt_auth import JWTAuthMiddleware
from relos.middleware.langsmith_tracing import LangSmithTracingMiddleware, setup_langsmith_tracing
from relos.middleware.rate_limit import RateLimitMiddleware

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理：负责初始化和清理外部连接。"""

    # ── Startup ──────────────────────────────
    logger.info("relos_starting", env=settings.ENV, neo4j_uri=settings.NEO4J_URI)

    # 初始化 Neo4j 异步 driver
    app.state.neo4j_driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    # 验证 Neo4j 连接
    await app.state.neo4j_driver.verify_connectivity()
    logger.info("neo4j_connected")

    # 创建图约束（幂等操作，重启安全）
    await _create_graph_constraints(app.state.neo4j_driver)

    # 初始化 LangSmith 追踪（Sprint 3 Week 11）
    langsmith_enabled = setup_langsmith_tracing(
        project=settings.LANGSMITH_PROJECT,
        enabled=settings.LANGSMITH_ENABLED,
    )
    app.state.langsmith_enabled = langsmith_enabled

    # 初始化 Temporal.io 客户端（Sprint 3 Week 10）
    if not settings.SHADOW_MODE:
        from relos.action.temporal_workflows import temporal_client
        await temporal_client.connect()
        app.state.temporal_client = temporal_client
        logger.info("temporal_client_initialized")

    logger.info("relos_ready")
    yield

    # ── Shutdown ─────────────────────────────
    await app.state.neo4j_driver.close()
    if hasattr(app.state, "temporal_client"):
        await app.state.temporal_client.close()
    logger.info("relos_shutdown")


async def _create_graph_constraints(driver: object) -> None:
    """
    在 Neo4j 中创建必要的唯一约束和索引。
    幂等：已存在则跳过。
    """
    constraints = [
        # 关系 ID 唯一性约束（通过节点属性实现）
        "CREATE CONSTRAINT device_id_unique IF NOT EXISTS FOR (n:Device) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT alarm_id_unique IF NOT EXISTS FOR (n:Alarm) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT operator_id_unique IF NOT EXISTS FOR (n:Operator) REQUIRE n.id IS UNIQUE",  # noqa: E501
        # 全文索引（用于语义搜索）
        "CREATE INDEX relation_confidence IF NOT EXISTS FOR ()-[r]-() ON (r.confidence)",
        "CREATE INDEX relation_status IF NOT EXISTS FOR ()-[r]-() ON (r.status)",
    ]

    from neo4j import AsyncDriver
    assert isinstance(driver, AsyncDriver)

    async with driver.session(database="neo4j") as session:
        for stmt in constraints:
            try:
                await session.run(stmt)
            except Exception as e:
                # 约束已存在时忽略错误，记录警告
                logger.warning("constraint_skip", stmt=stmt[:60], reason=str(e)[:100])


def create_app() -> FastAPI:
    """工厂函数：创建并配置 FastAPI 应用实例。"""

    app = FastAPI(
        title="RelOS API",
        description="Relation Operating System — 工业关系图的认知中间层",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS（开发环境允许所有来源）──────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENV == "development" else settings.ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── JWT 认证中间件（Sprint 4 Week 15-16）──────────────────────
    app.add_middleware(JWTAuthMiddleware)

    # ── API 限流中间件（Sprint 4 Week 15-16）──────────────────────
    app.add_middleware(RateLimitMiddleware)

    # ── LangSmith 追踪中间件（Sprint 3 Week 11）────────────────────
    app.add_middleware(LangSmithTracingMiddleware)

    # ── 注册路由 ──────────────────────────────────────────────────
    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])
    app.include_router(expert_init.router, prefix="/v1/expert-init", tags=["expert-init"])
    app.include_router(metrics.router, prefix="/v1/metrics", tags=["metrics"])
    app.include_router(ontology.router, prefix="/v1/ontology", tags=["ontology"])
    app.include_router(scenarios.router, prefix="/v1/scenarios", tags=["scenarios"])

    return app


# 模块级实例（uvicorn 使用）
app = create_app()
