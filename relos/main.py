"""
relos/main.py
-------------
FastAPI 应用入口。

生命周期管理：
- startup: 初始化 Neo4j driver、Redis 连接、创建图约束
- shutdown: 优雅关闭所有连接
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j import AsyncGraphDatabase

from relos.api.v1 import decisions, health, relations
from relos.config import settings

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

    logger.info("relos_ready")
    yield

    # ── Shutdown ─────────────────────────────
    await app.state.neo4j_driver.close()
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
        "CREATE CONSTRAINT operator_id_unique IF NOT EXISTS FOR (n:Operator) REQUIRE n.id IS UNIQUE",
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

    # ── 注册路由 ──────────────────────────────────────────────────
    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(relations.router, prefix="/v1/relations", tags=["relations"])
    app.include_router(decisions.router, prefix="/v1/decisions", tags=["decisions"])

    return app


# 模块级实例（uvicorn 使用）
app = create_app()
