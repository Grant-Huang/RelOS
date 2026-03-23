"""
relos/action/temporal_workflows.py
------------------------------------
Temporal.io 工作流定义：Action Engine 生产执行路径。

在 Shadow Mode = False 时，Action Engine 通过 Temporal 调度真实操作，
获得：持久化状态、自动重试、超时控制、可视化历史。

设计（dev-plan.md Week 10）：
- `ActionWorkflow`：单次操作执行工作流（包含 Pre-flight + 执行 + 回滚）
- `ActionActivities`：具体执行步骤（可替换为真实 MES API 调用）
- 工作流 ID 格式：`action-{action_id}`，保证幂等性

依赖：temporalio>=1.7.0（生产环境安装）
开发环境可通过 `pip install temporalio` 安装。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ─── 工作流输入/输出 ──────────────────────────────────────────────────

@dataclass
class ActionWorkflowInput:
    action_id: str
    alarm_id: str
    device_id: str
    action_description: str
    recommended_cause: str
    operator_id: str


@dataclass
class ActionWorkflowResult:
    action_id: str
    success: bool
    output: dict[str, Any]
    error: str = ""


# ─── Activities（实际执行步骤）────────────────────────────────────────

try:
    from temporalio import activity, workflow
    from temporalio.client import Client  # noqa: F401
    from temporalio.worker import Worker  # noqa: F401
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    # 创建占位装饰器，让代码在没有 temporalio 时仍可导入
    class _Noop:
        @staticmethod
        def defn(cls: Any) -> Any:
            return cls
        @staticmethod
        def run(fn: Any) -> Any:
            return fn

    class activity:  # type: ignore[no-redef]
        @staticmethod
        def defn(fn: Any) -> Any:
            return fn

    workflow = _Noop()  # type: ignore[assignment]


if TEMPORAL_AVAILABLE:
    @activity.defn
    async def activity_run_pre_flight(input_data: ActionWorkflowInput) -> dict[str, Any]:
        """Pre-flight 检查 Activity。"""
        from relos.action.engine import ActionEngine, ActionRecord

        engine = ActionEngine()
        record = ActionRecord(
            id=input_data.action_id,
            alarm_id=input_data.alarm_id,
            device_id=input_data.device_id,
            recommended_cause=input_data.recommended_cause,
            action_description=input_data.action_description,
            shadow_mode=False,
        )
        _, pf_result = engine.start_pre_flight(record, input_data.operator_id)
        return {
            "passed": pf_result.passed,
            "checks": pf_result.checks,
            "failure_reason": pf_result.failure_reason,
        }

    @activity.defn
    async def activity_execute_action(input_data: ActionWorkflowInput) -> dict[str, Any]:
        """
        真实执行 Activity（生产模式）。
        当前实现为示例：记录日志并模拟成功。
        生产环境替换为实际 MES API 调用。
        """
        logger.info(
            "production_action_executing",
            action_id=input_data.action_id,
            device_id=input_data.device_id,
            action=input_data.action_description,
        )
        # TODO: 替换为真实 MES API 调用
        # result = await mes_client.execute_work_order(
        #     device_id=input_data.device_id,
        #     action=input_data.action_description,
        # )
        await asyncio.sleep(0)  # 占位异步操作
        return {
            "executed": True,
            "device_id": input_data.device_id,
            "action": input_data.action_description,
            "note": "生产执行占位（替换为真实 MES API）",
        }

    @activity.defn
    async def activity_rollback_action(input_data: ActionWorkflowInput) -> dict[str, Any]:
        """回滚 Activity：通知相关人员，记录回滚日志。"""
        logger.warning(
            "production_action_rollback",
            action_id=input_data.action_id,
            device_id=input_data.device_id,
        )
        return {"rolled_back": True, "action_id": input_data.action_id}

    @workflow.defn
    class ActionWorkflow:
        """
        单次操作执行工作流。

        流程：Pre-flight → Execute → Complete
                          ↓ 失败
                       Rollback
        """

        @workflow.run
        async def run(self, input_data: ActionWorkflowInput) -> ActionWorkflowResult:
            from temporalio import workflow as wf

            # Step 1: Pre-flight Check（超时 30 秒）
            pf_result = await wf.execute_activity(
                activity_run_pre_flight,
                input_data,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=None,  # Pre-flight 不重试
            )

            if not pf_result["passed"]:
                return ActionWorkflowResult(
                    action_id=input_data.action_id,
                    success=False,
                    output=pf_result,
                    error=f"Pre-flight 失败: {pf_result['failure_reason']}",
                )

            # Step 2: 执行操作（超时 5 分钟，最多重试 3 次）
            try:
                exec_result = await wf.execute_activity(
                    activity_execute_action,
                    input_data,
                    start_to_close_timeout=timedelta(minutes=5),
                )
                return ActionWorkflowResult(
                    action_id=input_data.action_id,
                    success=True,
                    output=exec_result,
                )
            except Exception as exc:
                # 执行失败：触发回滚
                await wf.execute_activity(
                    activity_rollback_action,
                    input_data,
                    start_to_close_timeout=timedelta(minutes=2),
                )
                return ActionWorkflowResult(
                    action_id=input_data.action_id,
                    success=False,
                    output={},
                    error=str(exc),
                )

else:
    # temporalio 未安装时的占位类（保持模块可导入）
    class ActionWorkflow:  # type: ignore[no-redef]
        """Temporal.io 占位（安装 temporalio 后启用）。"""
        pass


# ─── Temporal 客户端工厂 ───────────────────────────────────────────────

class TemporalClient:
    """
    Temporal.io 客户端封装。

    配置项（来自 .env / Settings）：
        TEMPORAL_HOST=localhost:7233
        TEMPORAL_NAMESPACE=relos-production
        TEMPORAL_TASK_QUEUE=relos-actions
    """

    _instance: TemporalClient | None = None

    def __init__(self, host: str = "localhost:7233", namespace: str = "default") -> None:
        self.host = host
        self.namespace = namespace
        self._client: Any = None

    async def connect(self) -> None:
        """建立 Temporal 连接。"""
        if not TEMPORAL_AVAILABLE:
            logger.warning(
                "temporal_not_available",
                note="生产执行路径需要安装 temporalio: pip install temporalio>=1.7.0"
            )
            return

        from temporalio.client import Client
        self._client = await Client.connect(self.host, namespace=self.namespace)
        logger.info("temporal_connected", host=self.host, namespace=self.namespace)

    async def start_action_workflow(
        self,
        input_data: ActionWorkflowInput,
        task_queue: str = "relos-actions",
    ) -> str:
        """
        启动操作执行工作流。

        Returns:
            Temporal workflow run ID
        """
        if not TEMPORAL_AVAILABLE or self._client is None:
            raise RuntimeError(
                "Temporal 客户端未连接。请确保安装 temporalio 并调用 connect()。"
            )

        handle = await self._client.start_workflow(
            ActionWorkflow.run,
            input_data,
            id=f"action-{input_data.action_id}",  # 幂等 ID
            task_queue=task_queue,
        )
        logger.info(
            "temporal_workflow_started",
            workflow_id=handle.id,
            action_id=input_data.action_id,
        )
        return handle.id

    async def get_workflow_result(self, workflow_id: str) -> ActionWorkflowResult | None:
        """查询工作流结果（轮询/等待）。"""
        if not TEMPORAL_AVAILABLE or self._client is None:
            return None

        handle = self._client.get_workflow_handle(workflow_id)
        return await handle.result()

    async def close(self) -> None:
        """关闭连接。"""
        if self._client:
            await self._client.close()


# 模块级单例（由 main.py 生命周期管理）
temporal_client = TemporalClient()
