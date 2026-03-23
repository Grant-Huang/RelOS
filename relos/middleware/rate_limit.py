"""
relos/middleware/rate_limit.py
------------------------------
Redis 限流中间件（Sprint 4 Week 15-16）。

策略：固定窗口计数器（Fixed Window Counter）
- Key: relos:rate:{factory_id}:{window_ts}
- 每个工厂在 RATE_LIMIT_WINDOW_SECONDS 内最多 RATE_LIMIT_REQUESTS 个请求
- 超限时返回 429，并在响应头中提供 Retry-After

依赖：
- Redis（由 REDIS_URL 配置）
- request.state.factory_id（由 JWTAuthMiddleware 注入）
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)

_RATE_LIMIT_KEY_PREFIX = "relos:rate"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    基于 Redis 的 API 限流中间件。

    限流维度：factory_id（多租户隔离）+ 时间窗口
    未启用时直接放行（RATE_LIMIT_ENABLED=False）。
    Redis 不可用时降级放行（graceful degradation）。
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        from relos.config import settings

        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        # 获取工厂 ID（由 JWT 中间件注入，或默认）
        factory_id = getattr(request.state, "factory_id", settings.DEFAULT_FACTORY_ID)

        allowed, remaining, retry_after = _check_rate_limit(
            factory_id=factory_id,
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                factory_id=factory_id,
                path=request.url.path,
            )
            return Response(
                content='{"detail":"Rate limit exceeded. Please retry later."}',
                status_code=429,
                media_type="application/json",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def _check_rate_limit(
    factory_id: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """
    检查限流状态。

    Returns:
        (allowed, remaining, retry_after_seconds)
    """
    from relos.config import settings

    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)

        # 固定窗口：按 window_seconds 对齐的时间戳作为 key 后缀
        window_ts = int(time.time()) // window_seconds
        key = f"{_RATE_LIMIT_KEY_PREFIX}:{factory_id}:{window_ts}"

        current = r.incr(key)
        if current == 1:
            r.expire(key, window_seconds)

        remaining = max(0, max_requests - current)
        retry_after = window_seconds - (int(time.time()) % window_seconds)

        if current > max_requests:
            return False, 0, retry_after
        return True, remaining, 0

    except ImportError:
        # Redis 未安装：开发环境放行
        return True, max_requests, 0
    except Exception as exc:
        # Redis 不可用：降级放行，记录警告
        logger.warning("rate_limit_redis_error", error=str(exc)[:100])
        return True, max_requests, 0


# 导入修复
from fastapi import Request  # noqa: E402
