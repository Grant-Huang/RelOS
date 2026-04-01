# RelOS 支持复杂场景的最小增量清单

本文档面向 `RelOS` 自身，定义为了支撑两个复杂场景而建议增加的最小能力集合。目标是：

- 不把 `RelOS` 变成多 Agent 总编排器
- 不要求第一阶段就接通外部真实系统
- 保留现有 demo 页面
- 优先让 `RelOS` 自身的图谱、推理、HITL、Shadow 能力变得可展示

## 一、最小能力目标

RelOS 第一阶段只需做到以下四件事：

1. 接收并表达“复合扰动事件”
2. 输出“结构化决策包”
3. 支持“决策级 HITL 审核”
4. 生成“Shadow ActionBundle”

做到这四点，就足以支撑两个复杂场景的 RelOS-only 演示版本。

## 二、建议新增的数据模型

## 1. 复合事件模型

建议新增：

- `CompositeDisturbanceEvent`
- `CompositeSubEvent`

### 建议字段

#### CompositeDisturbanceEvent

- `incident_id`
- `factory_id`
- `scenario_type`
- `priority`
- `goal`
- `time_window_start`
- `time_window_end`
- `events: list[CompositeSubEvent]`

#### CompositeSubEvent

- `event_id`
- `event_type`
- `source_system`
- `occurred_at`
- `entity_id`
- `entity_type`
- `severity`
- `summary`
- `payload`

### 建议 event_type

- `rush_order`
- `machine_anomaly`
- `material_shortage`
- `quality_degradation`
- `tooling_shortage`

## 2. 决策包模型

建议新增：

- `DecisionPackage`
- `CandidatePlan`
- `DecisionAction`

### DecisionPackage 建议字段

- `decision_id`
- `incident_id`
- `title`
- `incident_summary`
- `risk_level`
- `recommended_plan_id`
- `candidate_plans`
- `recommended_actions`
- `evidence_relations`
- `requires_human_review`
- `review_reason`
- `trace_id`

### CandidatePlan 建议字段

- `plan_id`
- `name`
- `summary`
- `assumptions`
- `risk_level`
- `estimated_delivery_impact`
- `estimated_quality_impact`
- `estimated_capacity_impact`

### DecisionAction 建议字段

- `action_id`
- `action_type`
- `target_system`
- `target_entity`
- `summary`
- `risk_level`
- `requires_human_review`
- `payload_preview`

## 3. 决策级审核模型

建议新增：

- `DecisionReviewRecord`

### 建议字段

- `decision_id`
- `status`
- `reviewed_by`
- `review_comment`
- `selected_plan_id`
- `approved_actions`
- `rejected_actions`
- `reviewed_at`

## 4. 动作组合包模型

建议新增：

- `ActionBundle`

### 建议字段

- `bundle_id`
- `decision_id`
- `status`
- `actions`
- `shadow_mode`
- `execution_notes`

## 三、建议新增的 API

## 1. 复合场景分析

建议新增一个新的场景 API，而不是挤进现有单告警接口：

- `POST /v1/scenarios/composite-disturbance/analyze`

请求体：

- `CompositeDisturbanceEvent`

响应体：

- `DecisionPackage`

## 2. 决策包查询

- `GET /v1/scenarios/composite-disturbance/{incident_id}`

用途：

- 前端复盘 / 演示详情
- AgentNexus 读取结构化结果

## 3. 决策级 HITL 队列

- `GET /v1/decisions/pending-review`
- `POST /v1/decisions/{decision_id}/review`

用途：

- 支持中风险方案确认
- 与现有关系级 `pending-review` 区分开

## 4. ActionBundle 查询

- `GET /v1/decisions/{decision_id}/actions`

用途：

- 展示 Shadow 动作包
- 对接后续外部系统执行层

## 四、建议新增的内部模块

## 1. disturbance_linker

职责：

- 把多个子事件映射到图谱节点
- 建立复合扰动上下文
- 输出统一的上下文对象

输入：

- `CompositeDisturbanceEvent`

输出：

- `incident context`
- `related node ids`
- `runtime evidence relations`

## 2. composite_context_builder

职责：

- 为复杂场景生成统一的 `ContextBlock`
- 按设备、订单、质量、物料几个维度组织证据

## 3. decision_package_builder

职责：

- 从图谱证据和规则结果生成结构化决策包

## 4. action_bundle_builder

职责：

- 从决策包导出一组 Shadow 动作
- 生成 `target_system + payload_preview`

## 五、建议新增的状态机

当前已有关系审核和动作状态机，但复杂场景还需要新增：

## 决策包状态机

- `draft`
- `pending_review`
- `approved`
- `rejected`
- `shadow_planned`
- `executed`
- `rolled_back`

### 含义

- `draft`：RelOS 已生成决策包但尚未进入审核
- `pending_review`：等待主管 / 工程师确认
- `approved`：方案已通过
- `rejected`：方案被驳回
- `shadow_planned`：动作包已生成但未真实执行
- `executed`：后续若外部系统回写成功可进入
- `rolled_back`：策略取消或回退

## 六、建议增加的 seed / mock 数据

## 1. 半导体封装场景

建议新增：

- `CustomerOrder`
- `Machine: SMT-02 / SMT-04`
- `MaterialLot: 0402 电阻`
- `Supplier`
- `Feeder`
- `Process: BGA 封装`
- `DecisionPackageNode`

关系示例：

- `ORDER__REQUIRES__CAPACITY`
- `MACHINE__SUPPORTS__PROCESS`
- `MACHINE__SHOWS__ANOMALY`
- `MATERIAL__DEPLETES__PROCESS`
- `SUPPLIER__SUPPORTS__MATERIAL`
- `MACHINE__CAUSES__QUALITY_RISK`

## 2. 汽车零部件场景

建议新增：

- `CustomerOrder`
- `Machine: CNC-07 / CNC-09 / CNC-12`
- `Tool: φ32 铣刀`
- `Fixture`
- `QualityMetric: BLine_CPK`
- `Process: 精密壳体加工`

关系示例：

- `ORDER__REQUIRES__CAPACITY`
- `MACHINE__SHOWS__ANOMALY`
- `MACHINE__IMPACTS__QUALITY`
- `QUALITY__CONSTRAINS__SCHEDULE`
- `RESOURCE__REQUIRES__MRO_ITEM`

## 3. 决策级 mock 数据

建议补一份专门给前端 demo 使用的 mock 数据，例如：

- `relos/demo_data/composite_decision_packages.json`
- `data/demo/composite_decision_packages.json`

它可以用于：

- 在未接完整后端逻辑前先演示决策包 UI
- 为后续 AgentNexus 接入提供稳定样例

## 七、与现有 demo 页的映射建议

## 1. `AlarmAnalysis`

可承载：

- 设备异常主因
- 首要推荐动作
- 核心证据关系

不适合承载：

- 完整多事件全景

## 2. `PromptLabeling`

可承载：

- 中风险决策包审核
- 审核动作与审计记录

建议：

- 增加“关系审核 / 决策审核”双模式

## 3. `LineEfficiency`

可承载：

- 产能影响
- 协同链
- 质量 / 物料 / 瓶颈影响

## 4. `StrategicSim`

可承载：

- 多方案风险对比
- 资源动作优先级

## 八、建议的第一阶段开发顺序

1. 新增复合扰动模型与分析 API
2. 新增 disturbance linker
3. 新增 DecisionPackage 输出
4. 新增决策级 HITL 队列
5. 新增 ActionBundle Shadow 输出
6. 补两套 seed 数据
7. 最后再决定是否需要新页面

## 九、建议暂缓的内容

以下内容不建议在第一阶段放进 RelOS：

- Task DAG 真编排
- 多 Agent 调度器
- `/decide` 对话确认
- 真正外部系统回写
- 自动改排程 / 自动停机 / 自动调拨

这些都属于第二阶段或第三阶段。

## 十、最终目标

第一阶段最理想的结果不是“RelOS 全都做了”，而是：

- RelOS 清楚表达两个复杂场景的数据结构
- RelOS 能给出结构化决策包
- RelOS 能把决策包送进 HITL
- RelOS 能生成 Shadow ActionBundle
- 现有 demo 页面仍能承载核心演示

这样既能尽快讲出两个复杂场景，也不会破坏 RelOS 当前作为 L2 关系操作系统的定位。
