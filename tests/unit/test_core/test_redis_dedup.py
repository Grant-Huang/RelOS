"""
tests/unit/test_core/test_redis_dedup.py
-----------------------------------------
Pre-flight 步骤 5 Redis 去重检查单元测试。

使用 unittest.mock 模拟 Redis，无需真实 Redis 实例。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from relos.action.engine import (
    ActionRecord,
    _check_no_duplicate_via_redis,
    run_pre_flight_checks,
)


def make_action(alarm_id: str = "ALM-001", device_id: str = "device-M1") -> ActionRecord:
    return ActionRecord(
        alarm_id=alarm_id,
        device_id=device_id,
        recommended_cause="测试",
        action_description="检查设备",
    )


@pytest.mark.unit
class TestRedisDeduplication:

    def test_no_duplicate_check_present_in_preflight(self) -> None:
        """Pre-flight 结果中应包含 no_duplicate 检查项"""
        action = make_action()
        with patch("relos.action.engine._check_no_duplicate_via_redis", return_value=True):
            result = run_pre_flight_checks(action)
        assert "no_duplicate" in result.checks

    def test_duplicate_causes_preflight_failure(self) -> None:
        """检测到重复时，no_duplicate=False 且 Pre-flight 失败"""
        action = make_action()
        with patch("relos.action.engine._check_no_duplicate_via_redis", return_value=False):
            result = run_pre_flight_checks(action)
        assert result.checks["no_duplicate"] is False
        assert result.passed is False

    def test_non_duplicate_passes_preflight(self) -> None:
        """无重复时，no_duplicate=True，Pre-flight 正常"""
        action = make_action()
        with patch("relos.action.engine._check_no_duplicate_via_redis", return_value=True):
            result = run_pre_flight_checks(action)
        assert result.checks["no_duplicate"] is True

    def test_import_error_defaults_to_pass(self) -> None:
        """redis 模块未安装时应降级为通过（不阻断操作流程）"""
        action = make_action()

        mock_redis = MagicMock()
        mock_redis.from_url.side_effect = ImportError("No module named 'redis'")

        with patch.dict("sys.modules", {"redis": None}):
            result = _check_no_duplicate_via_redis(action)
        assert result is True  # 降级通过

    def test_redis_connection_error_defaults_to_pass(self) -> None:
        """Redis 连接失败时应降级为通过"""
        action = make_action()

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.side_effect = ConnectionError("Redis unreachable")

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            # 强制重新执行函数，让其从 sys.modules 中拿到 mock
            result = _check_no_duplicate_via_redis(action)
        assert result is True  # 降级通过

    def test_first_call_returns_true(self) -> None:
        """首次调用（无已有记录）应返回 True，并写入去重标记"""
        action = make_action()

        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = None  # 无已有记录

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_instance

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            result = _check_no_duplicate_via_redis(action)

        assert result is True
        mock_redis_instance.setex.assert_called_once()  # 应写入 Redis

    def test_duplicate_call_returns_false(self) -> None:
        """同一 alarm+device 已有记录时应返回 False"""
        action = make_action()

        mock_redis_instance = MagicMock()
        mock_redis_instance.get.return_value = b"existing-action-id"  # 已有记录

        mock_redis_module = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_instance

        with patch.dict("sys.modules", {"redis": mock_redis_module}):
            result = _check_no_duplicate_via_redis(action)

        assert result is False
        mock_redis_instance.setex.assert_not_called()  # 已有记录，不重写
