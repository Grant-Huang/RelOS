"""
scripts/simulate_alarm.py
-------------------------
MVP 演示脚本：模拟设备告警，触发完整的根因分析流程。

演示流程：
1. 发送振动超限告警（1 号机）
2. RelOS 提取设备子图
3. 规则引擎返回根因推荐
4. 打印推荐结果 + 置信度

使用方式：
    # 先启动 API 服务
    uvicorn relos.main:app --reload

    # 再运行此脚本
    python scripts/simulate_alarm.py
"""

import asyncio
import json
import sys
from datetime import datetime

sys.path.insert(0, ".")

import httpx


API_BASE = "http://localhost:8000/v1"


async def simulate() -> None:
    print("🚨 模拟设备告警事件...")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:

        # Step 1: 健康检查
        resp = await client.get(f"{API_BASE}/health")
        health = resp.json()
        print(f"✓  API 状态: {health['status']} | Neo4j: {health['neo4j']}")

        # Step 2: 发送告警事件（1 号机振动超限）
        alarm_event = {
            "alarm_id": f"ALM-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            "device_id": "device-M1",
            "alarm_code": "VIB-001",
            "alarm_description": "主轴振动值超过阈值 12.5mm/s，当前值 18.3mm/s，环境温度 38°C",
            "severity": "high",
            "timestamp": datetime.utcnow().isoformat(),
        }

        print(f"\n📡 发送告警事件：")
        print(f"   设备: {alarm_event['device_id']}")
        print(f"   告警码: {alarm_event['alarm_code']}")
        print(f"   描述: {alarm_event['alarm_description']}")

        resp = await client.post(
            f"{API_BASE}/decisions/analyze-alarm",
            json=alarm_event,
        )

        if resp.status_code != 200:
            print(f"\n❌ API 错误: {resp.status_code}")
            print(resp.text)
            return

        result = resp.json()

        # Step 3: 打印推荐结果
        print("\n" + "=" * 60)
        print("🎯 根因分析结果")
        print("=" * 60)
        print(f"  推荐根因:    {result['recommended_cause']}")
        print(f"  置信度:      {result['confidence']:.1%}")
        print(f"  决策引擎:    {result['engine_used']}")
        print(f"  需人工审核:  {'是 ⚠️' if result['requires_human_review'] else '否 ✓'}")
        print(f"  Shadow Mode: {'开启（仅记录，未执行）' if result['shadow_mode'] else '关闭'}")
        print(f"\n  推理依据:")
        print(f"  {result['reasoning']}")

        if result["supporting_relations"]:
            print(f"\n  支撑关系 ID:")
            for rel_id in result["supporting_relations"]:
                print(f"    - {rel_id}")

        print("\n" + "=" * 60)

        # Step 4: 模拟工程师反馈（确认根因）
        if result["supporting_relations"]:
            rel_id = result["supporting_relations"][0]
            print(f"\n👷 模拟工程师反馈：确认关系 {rel_id}")

            feedback_resp = await client.post(
                f"{API_BASE}/relations/{rel_id}/feedback",
                json={"engineer_id": "operator-zhang", "confirmed": True},
            )

            if feedback_resp.status_code == 200:
                updated = feedback_resp.json()
                print(f"  ✓ 置信度更新：→ {updated['confidence']:.2f}（数据飞轮 +1）")
            else:
                print(f"  ⚠️ 反馈提交失败: {feedback_resp.status_code}")

    print("\n✅ MVP 演示完成！")
    print("   系统成功完成：告警接收 → 子图提取 → 根因推荐 → 工程师反馈 → 置信度更新")


if __name__ == "__main__":
    asyncio.run(simulate())
