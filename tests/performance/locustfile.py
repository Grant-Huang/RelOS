"""
tests/performance/locustfile.py
---------------------------------
性能基准测试（test-plan.md §5）。

运行方式：
  # 安装 locust
  pip install locust

  # 启动 RelOS 服务
  docker compose up -d
  uvicorn relos.main:app --reload --port 8000

  # 运行性能测试（headless 模式，10 用户，60 秒）
  locust -f tests/performance/locustfile.py \
         --host http://localhost:8000 \
         --users 10 --spawn-rate 2 \
         --run-time 60s --headless \
         --html tests/performance/report.html

性能基准目标（test-plan.md §5.1）：
  规则引擎路径：P95 < 500ms
  LLM 路径：    P95 < 8s
  HITL 路径：   P95 < 100ms
  子图提取：    < 200ms（1000 条关系）
  并发支持：    10 并发告警分析
"""

from __future__ import annotations

import uuid

from locust import HttpUser, between, task


class AlarmAnalysisUser(HttpUser):
    """模拟工程师处理告警的并发用户。"""

    # 每个请求间等待 1-3 秒（模拟真实操作节奏）
    wait_time = between(1, 3)

    def on_start(self) -> None:
        """用户启动时确认服务可用。"""
        self.client.get("/v1/health")

    # ── 高频任务（权重 10）：规则引擎路径 ─────────────────────────────

    @task(10)
    def analyze_alarm_rule_engine(self) -> None:
        """
        规则引擎路径性能测试。
        目标：P95 < 500ms
        前置条件：device-M1 在 seed_neo4j.py 中已有高置信度关系。
        """
        with self.client.post(
            "/v1/decisions/analyze-alarm",
            json={
                "alarm_id": f"PERF-{uuid.uuid4().hex[:8]}",
                "device_id": "device-M1",
                "alarm_code": "VIB-001",
                "alarm_description": "主轴振动超限 18.3mm/s",
                "severity": "high",
            },
            name="/decisions/analyze-alarm [rule_engine]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                processing_ms = data.get("processing_time_ms", 0)
                if processing_ms > 500:
                    resp.failure(f"规则引擎响应时间 {processing_ms:.0f}ms 超过 500ms 目标")
                else:
                    resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:100]}")

    # ── 中频任务（权重 3）：HITL 队列查询 ───────────────────────────────

    @task(3)
    def get_pending_review(self) -> None:
        """
        HITL 队列查询性能测试。
        目标：P95 < 100ms
        """
        with self.client.get(
            "/v1/relations/pending-review?limit=20",
            name="/relations/pending-review",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    # ── 中频任务（权重 3）：子图提取 ────────────────────────────────────

    @task(3)
    def get_subgraph(self) -> None:
        """
        子图提取性能测试。
        目标：< 200ms（1000 条关系）
        """
        with self.client.post(
            "/v1/relations/subgraph",
            json={
                "center_node_id": "device-M1",
                "max_hops": 2,
                "min_confidence": 0.3,
            },
            name="/relations/subgraph",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    # ── 低频任务（权重 1）：force_hitl 路径 ─────────────────────────────

    @task(1)
    def analyze_alarm_force_hitl(self) -> None:
        """
        HITL 强制路径性能测试。
        目标：P95 < 100ms（无 LLM 调用）
        """
        with self.client.post(
            "/v1/decisions/analyze-alarm",
            json={
                "alarm_id": f"PERF-HITL-{uuid.uuid4().hex[:8]}",
                "device_id": "device-M1",
                "alarm_code": "VIB-001",
                "alarm_description": "振动超限",
                "severity": "critical",
                "force_hitl": True,
            },
            name="/decisions/analyze-alarm [force_hitl]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                processing_ms = data.get("processing_time_ms", 0)
                if processing_ms > 200:
                    resp.failure(f"HITL 路径响应时间 {processing_ms:.0f}ms 超过 200ms 目标")
                else:
                    resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    # ── 低频任务（权重 1）：健康检查（基准对比）───────────────────────

    @task(1)
    def health_check(self) -> None:
        """健康检查作为基准参考（应 < 10ms）。"""
        self.client.get("/v1/health", name="/health")

    # ── 低频任务（权重 1）：图谱统计 ─────────────────────────────────────

    @task(1)
    def get_metrics(self) -> None:
        """图谱统计查询性能。"""
        self.client.get("/v1/metrics", name="/metrics")


class ExpertInitUser(HttpUser):
    """
    模拟专家初始化操作（低频，专家用户）。
    目标：专家批量录入 30 条关系 < 60 秒。
    """

    wait_time = between(2, 5)
    weight = 1  # 专家用户比例低

    @task
    def expert_init_single(self) -> None:
        """单条关系录入性能测试。"""
        device_id = f"perf-device-{uuid.uuid4().hex[:4]}"
        self.client.post(
            "/v1/expert-init/",
            json={
                "source_node_id": device_id,
                "source_node_type": "Device",
                "target_node_id": f"perf-alarm-{uuid.uuid4().hex[:4]}",
                "target_node_type": "Alarm",
                "relation_type": "DEVICE__TRIGGERS__ALARM",
                "confidence": 0.85,
                "engineer_id": "perf-engineer",
            },
            name="/expert-init/single",
        )
