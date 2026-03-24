# RelOS Demo 场景手册

**版本**: Sprint 3 Week 12 扩展版
**适用对象**: 销售演示、产品评审、客户 POC
**场景体系**: 12 个完整场景（基础 6 + 中层 3 + 高层 3）

---

## 一、场景体系总览

```
高层（战略级）：CEO / 董事会  → 场景 10、11、12
中层（运营级）：COO / 部门总监 → 场景 7、8、9
基层（执行级）：工程师 / 操作员 → 场景 1–6（MVP 核心）
```

### 场景矩阵

| 编号 | 场景名称 | 层级 | 核心问题 | 主要端点 |
|------|---------|------|---------|---------|
| S-01 | 设备故障根因分析 | 基层 | 告警为什么响？ | `POST /v1/decisions/analyze-alarm` |
| S-02 | 质量缺陷模式发现 | 基层 | 为什么不良率高？ | `POST /v1/decisions/analyze-alarm` |
| S-03 | 经验沉淀（故障处理）| 基层 | 怎么修？ | `POST /v1/relations/` |
| S-04 | 生产决策优化 | 基层 | 怎么排产？ | `POST /v1/decisions/analyze-alarm` |
| S-05 | 库存异常分析 | 基层 | 为什么缺/多？ | `GET /v1/relations/subgraph/{node}` |
| S-06 | 人因分析 | 基层 | 谁/为什么出问题？ | `POST /v1/decisions/analyze-alarm` |
| **S-07** | **产线效率瓶颈识别** | **中层** | **哪条产线拖慢整体？** | `GET /v1/scenarios/line-efficiency` |
| **S-08** | **跨部门协同问题** | **中层** | **为什么生产采购对不上？** | `GET /v1/scenarios/cross-dept-analysis` |
| **S-09** | **异常处理效率分析** | **中层** | **哪些问题处理得慢？** | `GET /v1/scenarios/issue-resolution` |
| **S-10** | **企业级风险雷达** | **高层** | **现在最大风险是什么？** | `GET /v1/scenarios/risk-radar` |
| **S-11** | **资源配置优化** | **高层** | **资源投在哪最有效？** | `GET /v1/scenarios/resource-optimization` |
| **S-12** | **战略决策模拟** | **高层** | **扩产会不会出问题？** | `POST /v1/scenarios/strategic-simulation` |

---

## 二、环境准备（演示前必做）

### 1. 启动依赖服务

```bash
docker compose up -d
# 等待约 30 秒，验证：
curl http://localhost:8000/v1/health
# 预期：{"status": "ok", "neo4j": "connected"}
```

### 2. 注入演示数据

```bash
# 第一步：注入 MVP 基础数据（设备故障场景）
python scripts/seed_neo4j.py

# 第二步：注入中高层演示场景数据
python scripts/seed_demo_scenarios.py

# 预期输出：
# ✓ [Line] 产线 L1（冲压线）
# ✓ [Line] 产线 L2（焊接线）
# ... 共 30+ 个节点，33 条关系
```

### 3. 启动 API

```bash
uvicorn relos.main:app --reload --port 8000
```

---

## 三、高层演示剧本（3 分钟版）

> **演示主题**：让企业从"看报表"变成"直接获得决策"

### 开场白（20 秒）

```
今天大多数企业都有大量数据，
但真正的问题是：管理层依然要靠开会和经验做决策。

我们做的事情很简单——
让系统直接告诉你：问题是什么，为什么，以及该怎么做。
```

---

### 第一幕：发现问题（CEO 视角）

**话术**：
```
假设你是 CEO，你只问一个问题：
"现在最大的风险是什么？"
```

**演示操作**：

```bash
curl http://localhost:8000/v1/scenarios/risk-radar
```

**预期响应**（演示要点）：

```json
{
  "risk_domains": [
    {"name": "供应链中断风险", "score_pct": 68, "trend": "rising", "level": "high"},
    {"name": "质量波动风险",   "score_pct": 52, "trend": "stable", "level": "medium"},
    {"name": "设备稳定性风险", "score_pct": 41, "trend": "rising", "level": "medium"}
  ],
  "top_risk": {"name": "供应链中断风险", "score_pct": 68},
  "top_risk_causal_chain": [
    "供应商 A（华盛钢材）交期不稳定，准时率 43%",
    "Q235 钢板库存仅剩 22%（4.5/20 吨）",
    "2 个在制工单面临延误，交付承诺风险 ↑"
  ],
  "overall_risk_level": "high"
}
```

**UI 对应展示**：
```
【企业风险雷达】

🔴 供应链风险：68%  ↑ 上升
🟠 质量风险：  52%  → 稳定
🟡 设备风险：  41%  ↑ 上升

▶ 点击"供应链风险"查看根因
```

---

### 第二幕：理解原因（COO 视角）

**话术**：
```
系统不是给你数据，而是给你"因果关系"。
```

**演示操作**：

```bash
curl http://localhost:8000/v1/scenarios/cross-dept-analysis
```

**预期响应**（演示要点）：

```json
{
  "causal_chain": [
    "供应商 A（华盛钢材）准时率仅 43%",
    "Q235 钢板库存降至安全库存 22%",
    "2 个工单因缺料被迫推迟（样本 6/10）",
    "平均每工单延误 3 天，影响交付承诺"
  ],
  "delay_attribution": {
    "采购部门（供应商管理）": 47.8,
    "生产部门（排产调整）": 21.7,
    "计划部门（安全库存设置）": 30.5
  },
  "total_delay_days": 6
}
```

**UI 对应展示**：
```
【交付风险原因路径】

供应商 A 延迟
    ↓
Q235 钢板短缺（4.5 吨 / 需 20 吨）
    ↓
WO-001、WO-002 被迫停工
    ↓
交付延误 3 天 × 2 个工单

责任分布：
  采购：48%  生产：22%  计划：30%
```

---

### 第三幕：做出决策（资源配置）

**话术**：
```
更重要的是，它告诉你该做什么、怎么投资最值。
```

**演示操作**：

```bash
curl http://localhost:8000/v1/scenarios/resource-optimization
```

**预期响应**（演示要点）：

```json
{
  "recommendations": [
    {
      "rank": 1,
      "resource_name": "设备维护团队",
      "roi_pct": 35,
      "investment_rmb": 360000,
      "impact_description": "可减少交付延误 41%"
    },
    {
      "rank": 2,
      "resource_name": "供应商管理专员",
      "roi_pct": 28,
      "investment_rmb": 180000,
      "impact_description": "可减少交付延误 31%"
    }
  ],
  "priority_action": "优先投入：设备维护团队（ROI 最高，预计 8 个月回本）"
}
```

---

### 第四幕：预测未来（战略决策）

**话术**：
```
如果 CEO 问："明年我们要扩产 30%，有没有风险？"
系统可以直接回答。
```

**演示操作**：

```bash
curl -X POST http://localhost:8000/v1/scenarios/strategic-simulation \
  -H "Content-Type: application/json" \
  -d '{"expansion_pct": 30}'
```

**预期响应**：

```json
{
  "expansion_pct": 30,
  "delivery_risk_change_pct": 27.0,
  "failure_rate_change_pct": 18.0,
  "quality_risk_change_pct": 12.0,
  "risk_level": "high",
  "causal_chain": [
    "订单量 +30%",
    "产线负载：70% → 91%（+21%）",
    "设备故障率预计上升 18%（弹性系数 1.8）",
    "质量缺陷率预计上升 12%",
    "交付风险综合上升 27%"
  ],
  "recommendations": [
    "建议扩产前完成 M3 维修保养（消除当前 18.5h/周停机隐患）",
    "将供应商 A 准时率提升至 80% 以上，否则扩产后缺料风险 ×2",
    "夜班增配有经验维修工"
  ]
}
```

---

### 收尾话术

```
传统企业：
  数据 → 报表 → 人分析 → 开会 → 决策（周期：数天）

RelOS：
  数据 → 系统理解关系 → 直接给答案 → 执行（周期：实时）

我们不是在做一个 BI 系统，
而是在构建企业的"决策操作系统"。
```

---

## 四、中层演示剧本（生产经理 / 运营总监）

### 场景7：产线效率瓶颈（生产经理）

**话术**：
```
每天早上，生产经理最想知道：
"今天哪条产线拖慢了整体？"
```

**操作**：

```bash
curl http://localhost:8000/v1/scenarios/line-efficiency
```

**预期响应要点**：

```json
{
  "lines": [
    {"line_id": "line-L2", "efficiency_pct": 64, "status": "bottleneck"},
    {"line_id": "line-L3", "efficiency_pct": 81, "status": "normal"},
    {"line_id": "line-L1", "efficiency_pct": 92, "status": "normal"}
  ],
  "bottleneck_line_id": "line-L2",
  "bottleneck_machine_id": "machine-M3",
  "bottleneck_contribution_pct": 42.0,
  "root_cause_path": [
    "设备 machine-M3 停机频繁",
    "告警：焊接过热告警（7天内 9 次，环比 +80%）",
    "产线 line-L2 效率损失 28%",
    "占总延误贡献 42%"
  ]
}
```

**UI 展示**：
```
【产线效率看板】

L1 冲压线：████████████ 92%  ✓ 正常
L2 焊接线：████████     64%  ⚠ 瓶颈
L3 装配线：██████████   81%  ✓ 正常

瓶颈原因：设备 M3 故障
  → 过去 7 天告警 9 次（环比 +80%）
  → 累计停机 18.5 小时
  → 影响 L2 效率 42%
```

---

### 场景9：异常处理效率（设备经理）

**话术**：
```
"为什么有些问题总是处理很慢？哪个班次效率低？"
```

**操作**：

```bash
curl http://localhost:8000/v1/scenarios/issue-resolution
```

**预期响应要点**：

```json
{
  "issue_type_summary": [
    {"display_name": "轴承磨损", "avg_resolution_hours": 2.7, "status": "slow"},
    {"display_name": "电气故障", "avg_resolution_hours": 1.1, "status": "normal"},
    {"display_name": "冷却系统", "avg_resolution_hours": 0.7, "status": "normal"}
  ],
  "shift_comparison": {
    "night_avg_hours": 3.0,
    "day_avg_hours": 1.3,
    "night_vs_day_ratio": 2.31
  },
  "insight": "夜班处理时间比白班平均长 131%，轴承类问题最为突出（平均 2.7 小时）"
}
```

**UI 展示**：
```
【异常处理效率分析】

故障类型平均处理时长：
  轴承磨损：██████ 2.7h  ⚠ 偏慢
  电气故障：███    1.1h  ✓
  冷却系统：██     0.7h  ✓

班次对比：
  夜班：3.0h   白班：1.3h
  📊 夜班比白班慢 131%

根因：夜班经验均值 4.2 年 vs 白班 11.8 年
建议：针对轴承维修开展夜班专项培训
```

---

## 五、全场景 API 速查

### 基础场景（MVP）

```bash
# S-01/02/04/06：告警分析（核心流程）
curl -X POST http://localhost:8000/v1/decisions/analyze-alarm \
  -H "Content-Type: application/json" \
  -d '{"alarm_id":"alarm-VIB-001","device_id":"device-M1","alarm_code":"VIB-001","alarm_description":"振动超限"}'

# S-03：工程师录入经验关系
curl -X POST http://localhost:8000/v1/relations/ \
  -H "Content-Type: application/json" \
  -d '{"source_node_id":"alarm-VIB-001","source_node_type":"Alarm","target_node_id":"component-bearing-M1","target_node_type":"Component","relation_type":"ALARM__INDICATES__COMPONENT_FAILURE","confidence":0.75,"provenance":"manual_engineer","half_life_days":365}'

# S-05：子图查询（设备相关所有关系）
curl "http://localhost:8000/v1/relations/subgraph/device-M1?hops=2"
```

### 中层场景（新增）

```bash
# S-07：产线效率瓶颈
curl http://localhost:8000/v1/scenarios/line-efficiency

# S-08：跨部门协同问题
curl http://localhost:8000/v1/scenarios/cross-dept-analysis

# S-09：异常处理效率
curl http://localhost:8000/v1/scenarios/issue-resolution
```

### 高层场景（新增）

```bash
# S-10：企业风险雷达
curl http://localhost:8000/v1/scenarios/risk-radar

# S-11：资源配置优化
curl http://localhost:8000/v1/scenarios/resource-optimization

# S-12：扩产影响模拟（默认 +30%）
curl -X POST http://localhost:8000/v1/scenarios/strategic-simulation \
  -H "Content-Type: application/json" \
  -d '{"expansion_pct": 30}'

# S-12 变体：保守扩产 +15%
curl -X POST http://localhost:8000/v1/scenarios/strategic-simulation \
  -H "Content-Type: application/json" \
  -d '{"expansion_pct": 15}'
```

---

## 六、演示数据说明

### 演示数据构成（注入后）

| 数据类别 | 数量 | 说明 |
|---------|------|------|
| 产线节点 | 3 | L1（92%）、L2（64% 瓶颈）、L3（81%）|
| 机器节点 | 3 | M3（问题机）、M4（正常）、M5（正常）|
| 供应商 | 2 | A（准时率 43%）、B（准时率 94%）|
| 物料 | 2 | Q235 钢板（库存告急）、ABS 塑料（正常）|
| 工单 | 3 | WO-001/002（延误）、WO-003（正常）|
| 故障记录 | 5 | 轴承 ×3、电气 ×1、冷却 ×1 |
| 操作员 | 2 | 李工（夜班/3年）、王工（白班/15年）|
| 风险节点 | 3 | 供应链 68%、质量 52%、设备 41% |
| 资源节点 | 3 | 维保团队、供应商管理、夜班培训 |
| **关系总计** | **33** | 跨越 12 种关系类型 |

### 置信度设计意图

| 场景 | 关键关系 | 置信度 | 来源 | 设计意图 |
|------|---------|--------|------|---------|
| S-07 | M3→L2 停机贡献 | 0.88 | manual_engineer | 工程师评估，高可信 |
| S-07 | M3→焊接过热 | 0.91 | sensor_realtime | 传感器实测，最高 |
| S-08 | 供应商A→延迟 | 0.86 | mes_structured | MES 90天记录 |
| S-08 | 工单缺料阻塞 | 0.95 | mes_structured | 明确事实记录 |
| S-09 | 夜班处理效率低 | 0.85 | mes_structured | 多条记录支撑 |
| S-10 | 电弧→质量风险 | 0.76 | llm_extracted | LLM 推断，待审核 |
| S-11 | 夜班培训ROI | 0.75 | llm_extracted | LLM 估算，需确认 |
| S-12 | 产能-故障弹性 | 0.78 | inference | 历史规律推演 |

---

## 七、数据来源与系统集成（参考）

| 场景 | 优先数据源 | MVP 降级方案 |
|------|-----------|------------|
| S-07 产线效率 | MES（工单）+ Andon（停机）| MES + 手工停机记录 |
| S-08 跨部门协同 | ERP（库存）+ SRM（供应商）+ MES | ERP + MES（不接 SRM）|
| S-09 异常处理 | Andon（告警）+ 维修系统 + HR | Andon + Excel 维修记录 |
| S-10 风险雷达 | 组合场景 7+8+9 | 最少接 Andon + MES |
| S-11 资源优化 | 全部来源 + 财务系统 | 主观估算置信度 < 0.8 |
| S-12 战略模拟 | 历史关系推演 | 无需新数据，基于现有图 |

---

## 八、UI 结构建议（给前端/设计师）

### 页面架构

```
首页（大屏）
├── 企业态势概览（S-10 风险雷达数据）
│   ├── 三大风险域评分（动态数字）
│   └── 点击 → 进入因果分析页
│
├── 今日关键问题（Top 3）
│   └── 点击 → 进入对应场景页
│
└── 快捷操作
    ├── 输入告警（→ S-01 分析流程）
    └── 战略模拟（→ S-12 滑条输入）

中层分析页（Tab 切换）
├── 产线效率（S-07）
│   └── 横向进度条 + 点击展开根因
├── 跨部门协同（S-08）
│   └── 因果链展示 + 责任分布饼图
└── 异常效率（S-09）
    └── 故障类型条形图 + 班次对比

高层决策页
├── 资源配置（S-11）
│   └── ROI 排名卡片
└── 战略模拟（S-12）
    ├── 滑条输入（扩产比例）
    └── 实时输出风险变化
```

### 核心设计原则

- **问题驱动**：不是菜单驱动，用户从"问题"进入分析
- **三屏故事**：发现问题 → 理解原因 → 做出决策
- **置信度可见**：每个推断都显示置信度（教育用户理解系统局限）
- **行动导向**：每个分析页结尾必须有"下一步建议"

---

*文档版本：Sprint 3 Week 12 | RelOS Demo v0.2.0*
