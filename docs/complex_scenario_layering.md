# 复杂场景分层改造说明

本文档针对以下两个复杂场景，明确哪些改造应由 `RelOS` 负责，哪些应由 `AgentNexus` 负责，哪些必须通过外部 `MES / ERP / WMS / MRO` 接口或 MCP 化能力完成。

- 场景一：半导体封装工厂 `插单 + SMT-02 偏移报警 + 0402 卷料短缺`
- 场景二：汽车零部件制造 `大客户插单 + CNC-07 振动异常 + B 线 CPK 下降`

本文档的目标不是直接实现全链，而是保证系统边界清晰，避免把 `RelOS` 膨胀成“既做图谱、又做多 Agent 编排、还做外部执行”的大杂烩。

## 一、边界结论

结合以下现有定义：

- `docs/PRD.md`
- `docs/architecture.md`
- `relos/context/compiler.py`

建议仍然严格维持三层：

- `L2 RelOS`：关系记忆、关系联动、结构化推理、HITL、Shadow Action
- `L3 AgentNexus`：意图解析、Task DAG、多 Agent 协同、自然语言确认
- `L1 外部系统 / Nexus Ops / MCP`：MES、ERP、WMS、MRO、设备信号与真实执行

## 二、为什么这两个场景不能只靠现有单告警流转

当前 RelOS 已具备：

- 单设备/单告警的根因分析
- 关系级 pending review 队列
- Shadow Mode 动作状态机
- 场景分析页（产线效率、协同、资源优化、战略模拟）

但这两个新场景属于“多扰动并发”，核心变化不在于某一条关系变复杂，而在于：

1. 多个事件要在时间窗内汇聚为一个共同上下文。
2. 决策目标不再是“解释一个告警”，而是“同时保障交期、质量、设备稳定性”。
3. 输出不再只是 `recommended_cause`，而要变成 `decision package`。
4. 人工确认对象从“单条关系”升级成“结构化决策包 / 动作组合包”。

## 三、哪些属于 RelOS 必须修改

### 1. 复合扰动输入模型

RelOS 需要新增高于 `AlarmEvent` 的统一运行时输入模型，例如：

- `CompositeDisturbanceEvent`
- `CompositeEventEnvelope`

建议字段：

- `incident_id`
- `factory_id`
- `time_window_start`
- `time_window_end`
- `top_goal`
- `events[]`
- `priority`
- `affected_assets[]`
- `affected_orders[]`

`events[]` 内部可包含：

- `rush_order_event`
- `machine_alert_event`
- `material_shortage_event`
- `quality_degradation_event`

### 2. 复合扰动关联器

RelOS 需要新增一层 `disturbance linker`，负责把不同来源事件映射到统一图谱上下文：

- 订单 -> 工序 -> 设备依赖
- 设备 -> 历史故障模式
- 物料 -> 工单 / 工序 / 供应商
- 质量 -> 产线 / 设备 / 批次

这一层的职责是：

- 找到已知图谱节点
- 建立临时运行时证据边
- 输出统一子图上下文

### 3. 决策结果从“根因推荐”升级为“结构化决策包”

RelOS 需要新增新的输出模型，例如 `DecisionPackage`：

- `incident_id`
- `incident_summary`
- `risk_level`
- `recommended_actions[]`
- `candidate_plans[]`
- `dependencies[]`
- `evidence_relations[]`
- `human_review_required`
- `trace_id`

其中 `recommended_actions[]` 仍然是结构化动作，不是自然语言编排文本。

### 4. 决策级 HITL 队列

当前 `PromptLabeling` 更偏关系审核。复杂场景需要新增决策级 HITL：

- 决策包进入待审队列
- 审核对象是“停机窗口 / 排产方案 / 资源动作”
- 审核后保留完整审计链

建议新增：

- `decision_review` 模型
- `decision_hitl_queue`
- API：
  - `GET /v1/decisions/pending-review`
  - `POST /v1/decisions/{decision_id}/review`

### 5. Action Engine 升级为 ActionBundle / ExecutionPlan

RelOS 当前有单动作状态机，但复杂场景需要动作组合：

- 停机维护工单
- 排产调整请求
- 备料 / 调拨请求
- 人员工单 / pad 推送

建议新增：

- `ActionBundle`
- `ExecutionPlan`
- `target_system`
- `payload_preview`
- `execute_intent`

仍然默认 `Shadow Mode`，只生成结构化执行包，不直接调用外部系统。

### 6. 图谱本体与 demo 数据扩展

为支撑这两个场景，RelOS 需要增加如下节点与关系表达：

#### 新节点类型建议

- `CustomerOrder`
- `ProductionBatch`
- `Machine`
- `ProcessCapability`
- `MaterialLot`
- `Supplier`
- `Feeder`
- `Tool`
- `Fixture`
- `QualityMetric`
- `ScheduleWindow`
- `DecisionPackageNode`

#### 新关系类型建议

- `ORDER__REQUIRES__CAPACITY`
- `ORDER__HAS__PRIORITY`
- `MACHINE__SUPPORTS__PROCESS`
- `MACHINE__SHOWS__ANOMALY`
- `MACHINE__IMPACTS__QUALITY`
- `MATERIAL__SUPPORTS__ORDER`
- `MATERIAL__DEPLETES__PROCESS`
- `QUALITY__CONSTRAINS__SCHEDULE`
- `SUPPLIER__SUPPORTS__MATERIAL`
- `RESOURCE__REQUIRES__MRO_ITEM`
- `EVENT__TRIGGERS__DISTURBANCE`
- `DISTURBANCE__REQUIRES__DECISION`

## 四、哪些属于 AgentNexus 必须修改

### 1. 顶层目标解析

这两个场景的顶层目标都不是简单的单设备诊断，而是：

- 保交付
- 控质量扩散
- 控设备风险

这类目标聚合应该由 `AgentNexus` 负责，而不是 RelOS。

### 2. Task DAG 生成与调度

以下能力应属于 AgentNexus：

- 维护 Agent
- 调度 Agent
- 物料 Agent
- 质量 Agent
- 生产 Agent
- 并行执行
- 依赖节点
- 重试与超时策略

RelOS 只提供各 Agent 所需的 `ContextBlock / DecisionPackage`。

### 3. 多 Agent 结果汇总

你描述中的以下部分，建议放在 AgentNexus：

- “三 Agent 推理摘要”
- “两种排产方案”
- “主管可读的结构化推送文本”
- `/decide` 一类自然语言确认入口

RelOS 输出的是结构化依据，不负责自然语言协调层。

### 4. 人机对话与继续编排

一旦进入：

- 主管通过自然语言选择方案 B
- Agent 再次改写 DAG
- 多 Agent 根据审批结果继续动作分发

就已经属于 AgentNexus 或其上层工作台，而不是 RelOS。

## 五、哪些必须由外部系统 / MCP 实现

### 1. MES / APS

需要提供的能力：

- 获取实时排产
- 更新排产计划
- 查询设备当前在制批次
- 查询设备可用产能

推荐 MCP 能力名：

- `mes.get_schedule`
- `mes.get_machine_wip`
- `mes.get_machine_capacity`
- `mes.update_schedule`

### 2. ERP / 订单系统

需要提供的能力：

- 获取插单信息
- 获取订单优先级
- 更新订单承诺时间或状态

推荐：

- `erp.get_rush_order`
- `erp.get_order_priority`
- `erp.update_order_status`

### 3. WMS / 物料仓储

需要提供的能力：

- 查询可用库存与剩余工时
- 发起紧急调拨
- 查询备料预计到位时间

推荐：

- `wms.check_material_hours_remaining`
- `wms.get_transfer_eta`
- `wms.create_transfer_request`

### 4. MRO / 工装刀具系统

需要提供的能力：

- 查询刀具与夹具库存
- 发起紧急领用 / 调拨
- 查询替代件可用性

推荐：

- `mro.check_tool_inventory`
- `mro.check_fixture_inventory`
- `mro.create_urgent_request`

### 5. CMMS / 维修系统

需要提供的能力：

- 创建维修工单
- 查询维修历史
- 更新维修完成状态

推荐：

- `cmms.create_maintenance_workorder`
- `cmms.get_machine_history`
- `cmms.update_workorder_status`

### 6. 设备信号 / SPC / QMS

需要提供的能力：

- 实时设备告警与波形
- 质量指标 / CPK / SPC 数据
- 批次质量状态

推荐：

- `iot.get_machine_alerts`
- `spc.get_cpk_window`
- `qms.get_batch_quality_status`

## 六、建议的最小可交付顺序

### Phase 1：只做 RelOS 自身可演示部分

目标：

- 不依赖 AgentNexus
- 不依赖真实 MES/MRO 执行
- 先把“复合扰动 -> 决策包 -> HITL -> Shadow 执行包”跑通

应完成：

- 新的复合事件模型
- 决策包模型
- 决策级 HITL 队列
- ActionBundle Shadow 输出
- 两个场景的 seed 数据与 demo 数据

### Phase 2：AgentNexus 接入

目标：

- 在 RelOS 之上加上 Task DAG 和多 Agent 汇总

应完成：

- 多 Agent 规划器
- Task DAG 执行与状态管理
- `/decide` 自然语言确认入口
- Agent 汇总卡片 / 推送

### Phase 3：外部系统 MCP 化

目标：

- 从“演示推理”走向“受控执行”

应完成：

- MES / ERP / WMS / MRO / CMMS 的 MCP 封装
- 低风险动作自动化
- 中高风险动作人工确认后受控回写

## 七、最关键的设计原则

1. `RelOS` 不变成总调度器。
2. `AgentNexus` 不重复实现图谱记忆与关系推理。
3. 外部执行系统保持独立，通过 MCP 或受控网关接入。
4. 所有“真执行”都必须晚于 RelOS 的 `Shadow + 审计` 能力。

只有这样，这两个复杂场景才能既讲得通，又不破坏当前系统边界。
