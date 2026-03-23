"""
relos/middleware/jwt_auth.py
----------------------------
JWT 认证中间件（Sprint 4 Week 15-16）。

职责：
- 验证 Authorization: Bearer <token> header
- 解码 JWT，提取 engineer_id、factory_id、role
- 将认证信息注入 request.state，供端点使用
- 不认证的路径：/health、/docs、/redoc、/openapi.json

JWT Payload 约定：
  {
    "sub": "engineer_id",
    "factory_id": "factory-001",
    "role": "engineer" | "readonly" | "admin",
    "exp": <unix timestamp>
  }

配置：
  JWT_SECRET_KEY  : HMAC-SHA256 签名密钥
  JWT_ALGORITHM   : 默认 HS256
  JWT_ENABLED     : False（开发环境），True（生产）
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# 无需认证的路径前缀
_PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def _decode_jwt(token: str, secret: str, algorithm: str) -> dict[str, Any]:
    """
    解码并验证 JWT。
    使用 PyJWT（可选依赖），若未安装则做基础 base64 解码（仅开发用）。
    """
    try:
        import jwt as pyjwt
        payload = pyjwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except ImportError:
        # PyJWT 未安装：开发环境下用 base64 宽松解码（不验证签名）
        import base64
        import json
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format") from None
        # base64url decode payload
        payload_b64 = parts[1] + "=="  # 补 padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception as exc:
        raise ValueError(f"JWT decode error: {exc}") from exc


def _is_public_path(path: str) -> bool:
    """判断请求路径是否在无需认证的白名单中。"""
    for public in _PUBLIC_PATHS:
        if path == public or path.startswith(public + "/"):
            return True
    return False


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    JWT 认证中间件。

    认证流程：
    1. 检查是否在公共路径（直接放行）
    2. 提取 Authorization header 中的 Bearer token
    3. 解码验证 JWT
    4. 将 engineer_id、factory_id、role 注入 request.state
    5. 过期或无效 token → 401
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        from relos.config import settings

        # JWT 未启用时直接放行（开发环境）
        if not settings.JWT_ENABLED:
            request.state.engineer_id = "dev-engineer"
            request.state.factory_id = settings.DEFAULT_FACTORY_ID
            request.state.role = "engineer"
            return await call_next(request)

        # 公共路径放行
        if _is_public_path(request.url.path):
            return await call_next(request)

        # 提取 Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                content='{"detail":"Missing or invalid Authorization header"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header[len("Bearer "):]

        try:
            payload = _decode_jwt(token, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)
        except ValueError as exc:
            logger.warning("jwt_decode_failed", error=str(exc), path=request.url.path)
            return Response(
                content=f'{{"detail":"Invalid token: {exc}"}}',
                status_code=401,
                media_type="application/json",
            )

        # 验证过期时间
        exp = payload.get("exp", 0)
        if exp and exp < time.time():
            return Response(
                content='{"detail":"Token expired"}',
                status_code=401,
                media_type="application/json",
            )

        # 注入认证信息到 request.state
        request.state.engineer_id = payload.get("sub", "unknown")
        request.state.factory_id = payload.get("factory_id", settings.DEFAULT_FACTORY_ID)
        request.state.role = payload.get("role", "readonly")

        logger.debug(
            "jwt_authenticated",
            engineer_id=request.state.engineer_id,
            factory_id=request.state.factory_id,
            path=request.url.path,
        )

        return await call_next(request)


def require_role(required_role: str) -> Any:
    """
    FastAPI 依赖项：验证请求方角色权限。

    用法：
        @router.post("/", dependencies=[Depends(require_role("engineer"))])
    """
    from fastapi import Depends

    async def _check_role(request: Request) -> None:
        role = getattr(request.state, "role", "readonly")
        _ROLE_HIERARCHY = {"readonly": 0, "engineer": 1, "admin": 2}
        if _ROLE_HIERARCHY.get(role, 0) < _ROLE_HIERARCHY.get(required_role, 99):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: requires '{required_role}', got '{role}'",
            )

    return Depends(_check_role)
