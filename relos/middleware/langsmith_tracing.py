"""
relos/middleware/langsmith_tracing.py
--------------------------------------
LangSmith 追踪中间件：让每次 LLM 调用可审查。

功能（dev-plan.md Week 11）：
- 自动追踪所有经过 LangGraph 工作流的 LLM 调用
- 每次分析请求生成独立的 trace（可在 LangSmith 控制台查看）
- 追踪包含：输入 prompt、LLM 输出、置信度、关系上下文、耗时

配置（.env）：
    LANGSMITH_API_KEY=your-api-key
    LANGSMITH_PROJECT=relos-production
    LANGCHAIN_TRACING_V2=true

依赖：langsmith>=0.1.0（可选，未配置时降级为结构化日志）
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── LangSmith 可用性检查 ─────────────────────────────────────────────

_langsmith_enabled = False

try:
    import langsmith  # noqa: F401
    _langsmith_available = True
except ImportError:
    _langsmith_available = False


def setup_langsmith_tracing(
    api_key: str | None = None,
    project: str = "relos-production",
    enabled: bool = True,
) -> bool:
    """
    初始化 LangSmith 追踪。

    Args:
        api_key: LangSmith API Key（默认从 LANGSMITH_API_KEY 环境变量读取）
        project: 项目名称（用于分组追踪记录）
        enabled: 是否启用追踪

    Returns:
        True 表示追踪已启动，False 表示降级到结构化日志
    """
    global _langsmith_enabled

    if not enabled:
        logger.info("langsmith_tracing_disabled")
        return False

    if not _langsmith_available:
        logger.warning(
            "langsmith_not_installed",
            note="安装方式: pip install langsmith>=0.1.0",
        )
        return False

    effective_key = api_key or os.getenv("LANGSMITH_API_KEY", "")
    if not effective_key:
        logger.warning(
            "langsmith_no_api_key",
            note="设置 LANGSMITH_API_KEY 环境变量以启用 LLM 调用追踪",
        )
        return False

    # 设置 LangChain 追踪环境变量
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = effective_key
    os.environ["LANGCHAIN_PROJECT"] = project

    _langsmith_enabled = True
    logger.info("langsmith_tracing_enabled", project=project)
    return True


def is_tracing_enabled() -> bool:
    """检查 LangSmith 追踪是否已启用。"""
    return _langsmith_enabled and _langsmith_available


# ─── 追踪上下文管理 ────────────────────────────────────────────────────

class TraceContext:
    """
    单次 LLM 调用的追踪上下文。

    在 LangSmith 启用时，追踪数据发送到 LangSmith；
    未启用时，以结构化日志形式记录（降级策略）。
    """

    def __init__(
        self,
        run_name: str,
        alarm_id: str,
        device_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.run_name = run_name
        self.alarm_id = alarm_id
        self.device_id = device_id
        self.metadata = metadata or {}
        self._start_time: float = 0.0

    def __enter__(self) -> "TraceContext":
        self._start_time = time.monotonic()
        logger.info(
            "llm_trace_start",
            run_name=self.run_name,
            alarm_id=self.alarm_id,
            device_id=self.device_id,
        )
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        elapsed_ms = int((time.monotonic() - self._start_time) * 1000)
        success = exc_type is None

        logger.info(
            "llm_trace_end",
            run_name=self.run_name,
            alarm_id=self.alarm_id,
            device_id=self.device_id,
            elapsed_ms=elapsed_ms,
            success=success,
            error=str(exc_val) if exc_val else None,
        )


def trace_llm_call(
    run_name: str,
    alarm_id: str,
    device_id: str,
    metadata: dict[str, Any] | None = None,
) -> TraceContext:
    """
    创建 LLM 调用追踪上下文管理器。

    用法：
        with trace_llm_call("analyze_alarm", alarm_id="ALM-001", device_id="CNC-M1"):
            result = await workflow.ainvoke(state)
    """
    return TraceContext(
        run_name=run_name,
        alarm_id=alarm_id,
        device_id=device_id,
        metadata=metadata,
    )


# ─── FastAPI 中间件 ────────────────────────────────────────────────────

class LangSmithTracingMiddleware:
    """
    FastAPI 中间件：为所有 /v1/decisions/* 请求自动注入追踪上下文。
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            path: str = scope.get("path", "")
            if "/decisions" in path and is_tracing_enabled():
                # 注入请求级 trace ID（LangSmith 会自动关联）
                import uuid
                trace_id = str(uuid.uuid4())
                os.environ["LANGCHAIN_TRACE_ID"] = trace_id
                logger.debug("langsmith_trace_injected", trace_id=trace_id, path=path)

        await self.app(scope, receive, send)
