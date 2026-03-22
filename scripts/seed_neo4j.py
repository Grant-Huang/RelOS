"""
scripts/seed_neo4j.py
---------------------
MVP 测试数据注入脚本：设备故障分析场景。

注入内容：
- 3 台设备（车间 A 的 M1、M2、M3）
- 历史告警关系（含置信度和来源）
- 部件关系（轴承、冷却系统）
- 操作员关系

使用方式：
    python scripts/seed_neo4j.py

前置条件：
    docker compose up -d neo4j（确保 Neo4j 已启动）
"""

import asyncio
import sys

sys.path.insert(0, ".")

from neo4j import AsyncGraphDatabase

from relos.config import settings
from relos.core.models import RelationObject, RelationStatus, SourceType
from relos.core.repository import RelationRepository


# ─── 测试数据定义 ──────────────────────────────────────────────────

# 节点（设备、告警、部件、操作员）
NODES = [
    # 设备节点
    {"id": "device-M1", "node_type": "Device", "name": "1 号机（注塑机）",
     "properties": {"location": "车间A", "model": "海天 MA900", "install_year": 2019}},
    {"id": "device-M2", "node_type": "Device", "name": "2 号机（注塑机）",
     "properties": {"location": "车间A", "model": "海天 MA900", "install_year": 2020}},

    # 告警节点
    {"id": "alarm-VIB-001", "node_type": "Alarm", "name": "振动超限告警",
     "properties": {"alarm_code": "VIB-001", "severity": "high"}},
    {"id": "alarm-TEMP-002", "node_type": "Alarm", "name": "温度过高告警",
     "properties": {"alarm_code": "TEMP-002", "severity": "medium"}},

    # 部件节点
    {"id": "component-bearing-M1", "node_type": "Component", "name": "1 号机主轴轴承",
     "properties": {"type": "rolling_bearing", "manufacturer": "NSK"}},
    {"id": "component-coolant-M1", "node_type": "Component", "name": "1 号机冷却系统",
     "properties": {"type": "water_cooling"}},

    # 操作员节点
    {"id": "operator-zhang", "node_type": "Operator", "name": "张工",
     "properties": {"experience_years": 20, "specialty": "机械维修"}},
]

# 关系（含置信度，模拟老工程师的隐性知识）
RELATIONS = [
    # 设计文档中的经典案例：
    # "1 号机在高温天气下的振动报警 70% 是轴承问题，另 30% 是冷却液不足"
    RelationObject(
        id="rel-001",
        relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
        source_node_id="alarm-VIB-001",
        source_node_type="Alarm",
        target_node_id="component-bearing-M1",
        target_node_type="Component",
        confidence=0.70,                        # 70% 是轴承问题
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail="张工 20 年经验总结：高温天气振动告警，轴承问题概率 70%",
        extracted_by="human:operator-zhang",
        half_life_days=365,
        status=RelationStatus.ACTIVE,
    ),
    RelationObject(
        id="rel-002",
        relation_type="ALARM__INDICATES__COMPONENT_FAILURE",
        source_node_id="alarm-VIB-001",
        source_node_type="Alarm",
        target_node_id="component-coolant-M1",
        target_node_type="Component",
        confidence=0.30,                        # 30% 是冷却液不足
        provenance=SourceType.MANUAL_ENGINEER,
        provenance_detail="张工：振动告警也可能是冷却液不足导致热膨胀",
        extracted_by="human:operator-zhang",
        half_life_days=365,
        status=RelationStatus.ACTIVE,
    ),
    RelationObject(
        id="rel-003",
        relation_type="DEVICE__TRIGGERS__ALARM",
        source_node_id="device-M1",
        source_node_type="Device",
        target_node_id="alarm-VIB-001",
        target_node_type="Alarm",
        confidence=0.85,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="MES 历史工单：过去 6 个月触发 8 次",
        half_life_days=90,
        status=RelationStatus.ACTIVE,
        properties={"frequency_6month": 8, "last_occurrence": "2026-03-01"},
    ),
    RelationObject(
        id="rel-004",
        relation_type="COMPONENT__PART_OF__DEVICE",
        source_node_id="component-bearing-M1",
        source_node_type="Component",
        target_node_id="device-M1",
        target_node_type="Device",
        confidence=1.0,
        provenance=SourceType.MES_STRUCTURED,
        provenance_detail="设备台账",
        half_life_days=3650,            # 物理关系：10 年半衰期
        status=RelationStatus.ACTIVE,
    ),
]


# ─── 主函数 ────────────────────────────────────────────────────────

async def seed() -> None:
    print("🌱 开始注入 MVP 测试数据（设备故障分析场景）...")
    print(f"   Neo4j: {settings.NEO4J_URI}")

    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    await driver.verify_connectivity()
    print("✓  Neo4j 连接成功")

    repo = RelationRepository(driver)

    # 注入节点
    print(f"\n📌 注入 {len(NODES)} 个节点...")
    from relos.core.models import Node
    for node_data in NODES:
        node = Node(
            id=node_data["id"],
            node_type=node_data["node_type"],
            name=node_data["name"],
            properties=node_data.get("properties", {}),
        )
        await repo.upsert_node(node)
        print(f"   ✓ {node.node_type}: {node.name}")

    # 注入关系
    print(f"\n🔗 注入 {len(RELATIONS)} 条关系...")
    for rel in RELATIONS:
        await repo.upsert_relation(rel)
        print(f"   ✓ [{rel.confidence:.2f}] {rel.source_node_id} --{rel.relation_type}--> {rel.target_node_id}")

    await driver.close()

    print("\n✅ 种子数据注入完成！")
    print("   现在可以运行：python scripts/simulate_alarm.py")


if __name__ == "__main__":
    asyncio.run(seed())
