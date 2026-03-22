"""
tests/unit/test_core/test_action_engine.py
------------------------------------------
Action Engine 状态机单元测试。
无外部依赖（纯计算逻辑）。
"""

import pytest

from relos.action.engine import (
    ActionEngine,
    ActionRecord,
    ActionStatus,
    PreFlightResult,
    run_pre_flight_checks,
)


# ─── 辅助 ──────────────────────────────────────────────────────────

def make_action(
    alarm_id: str = "ALM-001",
    device_id: str = "device-M1",
    action_description: str = "检查主轴轴承磨损情况",
    shadow_mode: bool = True,
) -> ActionRecord:
    return ActionRecord(
        alarm_id=alarm_id,
        device_id=device_id,
        recommended_cause="轴承磨损",
        action_description=action_description,
        shadow_mode=shadow_mode,
    )


# ─── Pre-flight Check 测试 ─────────────────────────────────────────

class TestPreFlightChecks:

    def test_valid_action_passes_all_checks(self) -> None:
        """合法操作请求应通过全部五步验证"""
        action = make_action()
        result = run_pre_flight_checks(action)

        assert result.passed is True
        assert all(result.checks.values())

    def test_empty_device_id_fails(self) -> None:
        """空设备 ID 应触发检查失败"""
        action = make_action(device_id="")
        result = run_pre_flight_checks(action)

        assert result.passed is False
        assert result.checks["device_id_valid"] is False

    def test_control_action_blocked(self) -> None:
        """控制类操作（非检查类）应被白名单拦截"""
        action = make_action(action_description="停止 1 号机运行并断电")
        result = run_pre_flight_checks(action)

        assert result.passed is False
        assert result.checks["action_type_safe"] is False
        assert "MVP" in result.failure_reason

    def test_too_short_description_fails(self) -> None:
        """过短的操作描述应失败"""
        action = make_action(action_description="查")   # 1 个字，低于 5 字下限
        result = run_pre_flight_checks(action)

        assert result.passed is False
        assert result.checks["action_description_valid"] is False

    def test_empty_alarm_id_fails(self) -> None:
        """无告警来源的操作应被拦截"""
        action = make_action(alarm_id="")
        result = run_pre_flight_checks(action)

        assert result.passed is False
        assert result.checks["alarm_id_present"] is False


# ─── 状态机流转测试 ────────────────────────────────────────────────

class TestActionEngineStateMachine:

    def setup_method(self) -> None:
        self.engine = ActionEngine()

    def test_create_starts_at_pending(self) -> None:
        """新建操作记录初始状态为 PENDING"""
        action = self.engine.create(
            alarm_id="ALM-001",
            device_id="device-M1",
            recommended_cause="轴承磨损",
            action_description="检查主轴轴承",
        )
        assert action.status == ActionStatus.PENDING

    def test_valid_action_reaches_completed_in_shadow_mode(self) -> None:
        """合法操作 + Shadow Mode → 完整流转到 COMPLETED"""
        action = self.engine.create(
            alarm_id="ALM-001",
            device_id="device-M1",
            recommended_cause="轴承磨损",
            action_description="检查主轴轴承磨损情况",
            shadow_mode=True,
        )
        action, pf_result = self.engine.start_pre_flight(action, "engineer-01")
        assert pf_result.passed
        assert action.status == ActionStatus.APPROVED

        action = self.engine.execute(action, "engineer-01")
        assert action.status == ActionStatus.COMPLETED

    def test_failed_preflight_reaches_rejected(self) -> None:
        """Pre-flight 失败 → 状态为 REJECTED"""
        action = self.engine.create(
            alarm_id="ALM-001",
            device_id="",              # 非法设备 ID，触发失败
            recommended_cause="未知",
            action_description="检查设备",
            shadow_mode=True,
        )
        action, pf_result = self.engine.start_pre_flight(action, "engineer-01")

        assert not pf_result.passed
        assert action.status == ActionStatus.REJECTED

    def test_logs_are_append_only(self) -> None:
        """每次状态转换都追加日志，日志不可变"""
        action = self.engine.create(
            alarm_id="ALM-001",
            device_id="device-M1",
            recommended_cause="轴承磨损",
            action_description="检查主轴轴承磨损情况",
            shadow_mode=True,
        )
        assert len(action.logs) == 0

        action, _ = self.engine.start_pre_flight(action, "engineer-01")
        # start_pre_flight 触发两次转换：PENDING→PRE_FLIGHT_CHECK→APPROVED
        assert len(action.logs) == 2

        action = self.engine.execute(action, "engineer-01")
        # execute 再触发两次：APPROVED→EXECUTING→COMPLETED
        assert len(action.logs) == 4

    def test_execute_requires_approved_status(self) -> None:
        """只有 APPROVED 状态的操作可以执行"""
        action = make_action()   # PENDING 状态
        with pytest.raises(ValueError, match="APPROVED"):
            self.engine.execute(action, "engineer-01")

    def test_shadow_mode_default_is_true(self) -> None:
        """创建操作时 Shadow Mode 默认为 True"""
        action = self.engine.create(
            alarm_id="ALM-001",
            device_id="device-M1",
            recommended_cause="x",
            action_description="检查设备",
        )
        assert action.shadow_mode is True
