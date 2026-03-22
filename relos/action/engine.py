"""
relos/action/engine.py
----------------------
Action Engine：执行状态机 + Shadow Mode。

设计文档 §7.1 的八状态执行状态机：

  PENDING → PRE_FLIGHT_CHECK → APPROVED → EXECUTING → COMPLETED
                                    ↓
                               REJECTED (人工否决)
                                    ↓
                         FAILED (执行失败，可重试)
                                    ↓
                              ROLLED_BACK (回滚成功)

Shadow Mode（MVP 默认开启）：
  - Pre-flight Check 照常执行（验证参数合法性）
  - EXECUTING 阶段只记录日志，不实际执行任何操作
  - 所有状态转换正常记录，供后续审计

设计原则：
  - 不因赶进度跳过 Pre-flight Check（设计文档 §5.4）
  - 每次状态转换必须记录 operator_id + timestamp（工业合规需求）
  - 操作日志不可变：只追加，不修改
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────
# 状态枚举（八状态机）
# ─────────────────────────────────────────────

class ActionStatus(str, Enum):
    PENDING          = "pending"           # 待执行，刚创建
    PRE_FLIGHT_CHECK = "pre_flight_check"  # 执行前五步验证
    APPROVED         = "approved"          # 验证通过，等待执行
    REJECTED         = "rejected"          # 人工拒绝或验证失败
    EXECUTING        = "executing"         # 正在执行（Shadow Mode 下只记日志）
    COMPLETED        = "completed"         # 执行成功
    FAILED           = "failed"            # 执行失败，可重试
    ROLLED_BACK      = "rolled_back"       # 已回滚


# ─────────────────────────────────────────────
# 数据模型
# ─────────────────────────────────────────────

class ActionLog(BaseModel):
    """状态转换日志（只追加，不可变）。"""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    from_status: ActionStatus
    to_status: ActionStatus
    operator_id: str
    reason: str = ""
    shadow_mode: bool = True


class ActionRecord(BaseModel):
    """
    一次操作记录（对应决策引擎的一次推荐执行）。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alarm_id: str
    device_id: str
    recommended_cause: str
    action_description: str             # 要执行的操作，例如"检查主轴轴承"
    status: ActionStatus = ActionStatus.PENDING
    shadow_mode: bool = True            # MVP 默认 True：只记录，不执行
    logs: list[ActionLog] = Field(default_factory=list)
    pre_flight_results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────
# Pre-flight Check（五步验证）
# ─────────────────────────────────────────────

class PreFlightResult(BaseModel):
    passed: bool
    checks: dict[str, bool]     # 每步验证的结果
    failure_reason: str = ""


def run_pre_flight_checks(action: ActionRecord) -> PreFlightResult:
    """
    执行前五步验证（设计文档 §7.2）。
    即使在 Shadow Mode 下也必须执行：验证保证参数合法性。

    五步检查：
    1. 设备 ID 格式合法（防止注入）
    2. 操作描述非空且长度合理
    3. 告警 ID 存在（非孤立操作）
    4. 操作类型在白名单内（MVP：仅允许"检查"类操作）
    5. 重复操作检查（同设备同告警 24 小时内不重复执行）
    """
    checks: dict[str, bool] = {}
    failure_reasons: list[str] = []

    # 检查 1：设备 ID 格式
    checks["device_id_valid"] = (
        bool(action.device_id)
        and len(action.device_id) < 100
        and action.device_id.replace("-", "").replace("_", "").isalnum()
    )
    if not checks["device_id_valid"]:
        failure_reasons.append(f"设备 ID 格式非法: {action.device_id!r}")

    # 检查 2：操作描述
    checks["action_description_valid"] = (
        bool(action.action_description)
        and 5 <= len(action.action_description) <= 500
    )
    if not checks["action_description_valid"]:
        failure_reasons.append("操作描述为空或超长")

    # 检查 3：告警 ID 存在
    checks["alarm_id_present"] = bool(action.alarm_id)
    if not checks["alarm_id_present"]:
        failure_reasons.append("告警 ID 缺失，不允许无源操作")

    # 检查 4：操作类型白名单（MVP：只允许建议性操作，不允许控制类）
    allowed_keywords = ["检查", "查看", "确认", "记录", "测量", "check", "inspect", "verify"]
    checks["action_type_safe"] = any(
        kw in action.action_description.lower() for kw in allowed_keywords
    )
    if not checks["action_type_safe"]:
        failure_reasons.append(
            "MVP 阶段仅允许建议性操作（检查/确认类），控制类操作需升级 Shadow Mode 配置"
        )

    # 检查 5：重复操作（MVP 简化：仅检查 alarm_id 是否已处理）
    # TODO: 接入 Redis，检查 24 小时内同 alarm_id 的操作记录
    checks["no_duplicate"] = True   # MVP 占位，默认通过

    all_passed = all(checks.values())

    return PreFlightResult(
        passed=all_passed,
        checks=checks,
        failure_reason="；".join(failure_reasons) if failure_reasons else "",
    )


# ─────────────────────────────────────────────
# Action Engine 状态机
# ─────────────────────────────────────────────

class ActionEngine:
    """
    执行状态机控制器。
    在 Shadow Mode 下，所有"执行"操作只写日志。
    """

    def create(
        self,
        alarm_id: str,
        device_id: str,
        recommended_cause: str,
        action_description: str,
        shadow_mode: bool = True,
    ) -> ActionRecord:
        """创建新的操作记录，初始状态 PENDING。"""
        record = ActionRecord(
            alarm_id=alarm_id,
            device_id=device_id,
            recommended_cause=recommended_cause,
            action_description=action_description,
            shadow_mode=shadow_mode,
        )
        logger.info(
            "action_created",
            action_id=record.id,
            device_id=device_id,
            shadow_mode=shadow_mode,
        )
        return record

    def start_pre_flight(
        self,
        action: ActionRecord,
        operator_id: str,
    ) -> tuple[ActionRecord, PreFlightResult]:
        """
        触发 Pre-flight Check（PENDING → PRE_FLIGHT_CHECK → APPROVED/REJECTED）。
        返回更新后的 ActionRecord 和检查结果。
        """
        action = self._transition(action, ActionStatus.PRE_FLIGHT_CHECK, operator_id)
        result = run_pre_flight_checks(action)

        if result.passed:
            action = self._transition(
                action, ActionStatus.APPROVED, operator_id,
                reason="Pre-flight 五步检查全部通过"
            )
        else:
            action = self._transition(
                action, ActionStatus.REJECTED, operator_id,
                reason=f"Pre-flight 失败: {result.failure_reason}"
            )

        action.pre_flight_results = result.checks
        return action, result

    def execute(
        self,
        action: ActionRecord,
        operator_id: str,
    ) -> ActionRecord:
        """
        执行操作（APPROVED → EXECUTING → COMPLETED/FAILED）。

        Shadow Mode = True（MVP 默认）：
            只记录日志，打印"Shadow: 应执行 {action_description}"，不实际操作。

        Shadow Mode = False（生产模式，Sprint 3 实现）：
            调用实际执行接口（Temporal 工作流）。
        """
        if action.status != ActionStatus.APPROVED:
            raise ValueError(
                f"操作状态必须为 APPROVED 才能执行，当前状态: {action.status}"
            )

        action = self._transition(action, ActionStatus.EXECUTING, operator_id)

        if action.shadow_mode:
            # Shadow Mode：只记录，不实际执行
            logger.info(
                "shadow_mode_execution",
                action_id=action.id,
                device_id=action.device_id,
                action_description=action.action_description,
                note="Shadow Mode 开启：此操作未实际执行，仅记录日志",
            )
            action = self._transition(
                action, ActionStatus.COMPLETED, operator_id,
                reason="[Shadow Mode] 操作已记录，未实际执行"
            )
        else:
            # 生产模式（Sprint 3：接入 Temporal.io 工作流）
            # TODO: await temporal_client.start_workflow(...)
            raise NotImplementedError(
                "生产执行模式在 Sprint 3 实现（需 Temporal.io 集成）"
            )

        return action

    def reject(
        self,
        action: ActionRecord,
        operator_id: str,
        reason: str,
    ) -> ActionRecord:
        """人工拒绝操作。"""
        return self._transition(action, ActionStatus.REJECTED, operator_id, reason=reason)

    # ─── 内部辅助 ──────────────────────────────────────────────────

    def _transition(
        self,
        action: ActionRecord,
        new_status: ActionStatus,
        operator_id: str,
        reason: str = "",
    ) -> ActionRecord:
        """执行状态转换，追加不可变日志。"""
        log_entry = ActionLog(
            from_status=action.status,
            to_status=new_status,
            operator_id=operator_id,
            reason=reason,
            shadow_mode=action.shadow_mode,
        )
        action.logs.append(log_entry)
        action.status = new_status
        action.updated_at = datetime.utcnow()

        logger.info(
            "action_state_transition",
            action_id=action.id,
            from_status=log_entry.from_status,
            to_status=new_status,
            operator_id=operator_id,
            shadow_mode=action.shadow_mode,
        )
        return action
