"""
relos/action/repository.py
--------------------------
Action 操作记录的 Neo4j 持久化。

解决技术债：_action_store 存内存导致服务重启后记录丢失（dev-plan.md §4）。

存储设计：
  - ActionRecord → Neo4j 节点，label = :ActionRecord
  - logs 字段序列化为 JSON 字符串存储（Neo4j 不支持嵌套对象）
  - pre_flight_results 同样序列化为 JSON
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from neo4j import AsyncDriver

from relos.action.engine import ActionLog, ActionRecord, ActionStatus

logger = structlog.get_logger(__name__)


class ActionRepository:
    """ActionRecord 的 Neo4j 持久化层。"""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    async def save(self, action: ActionRecord) -> ActionRecord:
        """保存或更新 ActionRecord（MERGE on id）。"""
        query = """
        MERGE (a:ActionRecord {id: $id})
        SET a += {
            alarm_id:           $alarm_id,
            device_id:          $device_id,
            recommended_cause:  $recommended_cause,
            action_description: $action_description,
            status:             $status,
            shadow_mode:        $shadow_mode,
            logs_json:          $logs_json,
            pre_flight_json:    $pre_flight_json,
            created_at:         $created_at,
            updated_at:         $updated_at
        }
        RETURN a
        """
        async with self._driver.session(database=self._db) as session:
            await session.run(
                query,
                id=action.id,
                alarm_id=action.alarm_id,
                device_id=action.device_id,
                recommended_cause=action.recommended_cause,
                action_description=action.action_description,
                status=action.status.value,
                shadow_mode=action.shadow_mode,
                logs_json=json.dumps([_log_to_dict(lg) for lg in action.logs]),
                pre_flight_json=json.dumps(action.pre_flight_results),
                created_at=action.created_at.isoformat(),
                updated_at=action.updated_at.isoformat(),
            )
        logger.debug("action_saved", action_id=action.id, status=action.status.value)
        return action

    async def get_by_id(self, action_id: str) -> ActionRecord | None:
        """按 ID 查询 ActionRecord，不存在返回 None。"""
        query = "MATCH (a:ActionRecord {id: $id}) RETURN a"
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, id=action_id)
            record = await result.single()
            if not record:
                return None
            return _node_to_action(record["a"])


# ─── 序列化辅助 ──────────────────────────────────────────────────────

def _log_to_dict(log: ActionLog) -> dict[str, Any]:
    return {
        "timestamp": log.timestamp.isoformat(),
        "from_status": log.from_status.value,
        "to_status": log.to_status.value,
        "operator_id": log.operator_id,
        "reason": log.reason,
        "shadow_mode": log.shadow_mode,
    }


def _node_to_action(node: Any) -> ActionRecord:
    from datetime import datetime, timezone

    logs_raw: list[dict[str, Any]] = json.loads(node.get("logs_json", "[]"))
    logs = [
        ActionLog(
            timestamp=datetime.fromisoformat(lg["timestamp"]),
            from_status=ActionStatus(lg["from_status"]),
            to_status=ActionStatus(lg["to_status"]),
            operator_id=lg["operator_id"],
            reason=lg.get("reason", ""),
            shadow_mode=lg.get("shadow_mode", True),
        )
        for lg in logs_raw
    ]

    pre_flight: dict[str, Any] = json.loads(node.get("pre_flight_json", "{}"))

    return ActionRecord(
        id=node["id"],
        alarm_id=node["alarm_id"],
        device_id=node["device_id"],
        recommended_cause=node["recommended_cause"],
        action_description=node["action_description"],
        status=ActionStatus(node["status"]),
        shadow_mode=node["shadow_mode"],
        logs=logs,
        pre_flight_results=pre_flight,
        created_at=datetime.fromisoformat(node["created_at"]).replace(tzinfo=timezone.utc),
        updated_at=datetime.fromisoformat(node["updated_at"]).replace(tzinfo=timezone.utc),
    )
