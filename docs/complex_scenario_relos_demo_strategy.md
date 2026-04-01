# 复杂场景的 RelOS-only 演示策略

本文档回答一个核心问题：

> 在保留当前 RelOS demo 页面不删除、不推翻的前提下，如何最大限度只利用 RelOS 自身来演示这两个复杂场景？

结论是：第一阶段不要追求“多 Agent 全链真实执行”，而是优先把 `RelOS` 自己最强的四个价值点讲清楚：

- 多源事件如何进入统一关系上下文
- 关系图谱如何支撑复合推理
- 中风险运营决策如何进入 HITL
- 决策动作如何以 Shadow Mode 形成可审计执行包

## 一、保留哪些现有 demo 页面

当前建议继续保留并复用以下页面：

- `frontend/src/pages/AlarmAnalysis.jsx`
- `frontend/src/pages/runtime/PromptLabeling.jsx`
- `frontend/src/pages/LineEfficiency.jsx`
- `frontend/src/pages/StrategicSim.jsx`
- `frontend/src/pages/knowledge/KnowledgeDocuments.jsx`

这些页面已经覆盖了：

- 告警/异常输入
- 待审队列
- 产能与协同分析
- 资源与风险权衡
- 文档知识沉淀

因此不需要先大拆大改 UI。

## 二、RelOS-only 演示原则

### 原则 1：不演“真执行”，演“受控决策包”

这两个复杂场景里，真实 MES/WMS/MRO 回写是最后一公里，不是第一阶段 RelOS 的核心价值。

第一阶段应该把演示重点放在：

- 事件如何关联
- 为什么给出这个建议
- 风险等级是什么
- 哪些动作必须人工确认
- 系统打算如何执行（Shadow）

### 原则 2：不演“多 Agent 编排器”，演“多视角结构化推理结果”

真正的 Task DAG 与多 Agent 并行，第二阶段交给 AgentNexus。

在 RelOS-only 演示中，可以把结果表达成：

- 产能可行性摘要
- 维护优先级摘要
- 物料 / 工装可用性摘要
- 风险与依赖条件

也就是说，先演“结果包”，暂不演“编排器本体”。

### 原则 3：不新增一堆孤立 demo 页面

优先使用现有页组合承载复杂场景。

只有在以下条件同时满足时，才建议新增一个复合扰动页：

1. 现有 4 个页面无法承载统一事件上下文
2. 需要在一个页面里同时看事件、风险、建议、HITL、Shadow 包

## 三、如何用现有页面承载两个复杂场景

## 场景一：半导体封装工厂

### 页面映射

#### 1. `AlarmAnalysis`

承载内容：

- `SMT-02` 偏移报警的首要原因建议
- 设备历史模式匹配
- 与送料器齿轮磨损的证据关系

演示重点：

- 虽然表面上是“偏移报警”，但 RelOS 能把设备历史异常模式和工艺依赖关联起来

#### 2. `LineEfficiency`

承载内容：

- 插单对产能的冲击
- `SMT-02` 异常对可用产能的影响
- 物料仅剩 1.5 小时用量带来的协同风险

演示重点：

- 不是只看一台机报警，而是把设备、物料、产能、订单放到同一因果链

#### 3. `PromptLabeling`

承载内容：

- 中风险决策包进入人工审核
- 人工确认“是否 14:15 前停机维护”“是否采用 SMT-02 + SMT-04 组合方案”

演示重点：

- RelOS 不是自动拍板，而是把中风险决策显式送入 HITL

#### 4. `StrategicSim`

承载内容：

- 不同插单优先级或停机窗口下的风险变化
- 不同设备组合排产方案的交付风险变化

演示重点：

- RelOS 支撑的是“方案对比”和“风险解释”

## 场景二：汽车零部件制造

### 页面映射

#### 1. `AlarmAnalysis`

承载内容：

- `CNC-07` 振动异常的主轴轴承磨损推理
- `B 线 CPK 下降` 与 `CNC-07` 的证据关联

#### 2. `LineEfficiency`

承载内容：

- 大客户插单对产能结构的影响
- `CNC-07` 停机后由 `CNC-09` 与 `CNC-12` 承接的排产影响
- 质量异常对生产节奏的约束

#### 3. `PromptLabeling`

承载内容：

- 中风险确认：`CNC-07` 当前在制品完成后停机
- 方案 B 进入人工确认

#### 4. `StrategicSim`

承载内容：

- “继续用 CNC-07” 与 “停机切换产能” 两种策略的风险对比
- 工装刀具短缺对执行路径的影响

## 四、如果只允许最小前端改动，推荐怎么做

### 方案 A：完全不新增页面

做法：

- 扩展 seed 数据
- 扩展后端返回字段
- 在现有页面中通过更贴近场景的 mock/demo 数据承载复杂场景

适合：

- 最小改动
- 快速演示
- 优先验证 RelOS 的模型与数据表达

缺点：

- 观众需要你口头说明“这是复合扰动场景的某个切片”
- 不够像完整运营驾驶舱

### 方案 B：只新增 1 个页面 `复合扰动决策包`

做法：

- 保留所有旧页面
- 增加一个新页面，比如 `/runtime/composite-disturbance`
- 页面内容集中展示：
  - 事件流
  - 关联对象
  - 风险等级
  - 决策包
  - HITL 状态
  - Shadow ActionBundle

适合：

- 你希望观众一眼看出“这是复合场景，不是单告警”
- 但仍然坚持以 RelOS 为主，而不是先做 AgentNexus

这是本轮如果需要 UI 增量时，最推荐的唯一新增页面。

## 五、RelOS-only 第一阶段建议新增的数据与能力

### 1. 两套场景 seed 数据

建议新增：

- 半导体封装场景 seed
- 汽车零部件场景 seed

这些 seed 至少应覆盖：

- 订单
- 设备
- 物料 / 工装
- 质量指标
- 风险节点
- 候选动作
- HITL 决策包节点或关系

### 2. 决策包 mock / API

建议新增：

- `GET /v1/scenarios/composite-disturbance/{incident_id}`
- 或 `POST /v1/scenarios/composite-disturbance/analyze`

返回结构应包含：

- `incident_summary`
- `related_events`
- `risk_level`
- `decision_package`
- `shadow_action_bundle`
- `requires_human_review`

### 3. 决策级待审队列

建议新增：

- `GET /v1/decisions/pending-review`
- `POST /v1/decisions/{id}/review`

这样 `PromptLabeling` 可以升级成：

- 继续保留关系审核
- 同时可展示复杂场景的决策包审核

## 六、推荐的演示路线

### 5 分钟版

1. `AlarmAnalysis`：展示设备异常与历史模式匹配
2. `LineEfficiency`：展示订单、设备、物料/质量形成的因果链
3. `PromptLabeling`：展示中风险决策包进入人工审核
4. `StrategicSim`：展示方案切换与风险对比

### 12 分钟版

1. 先讲复合扰动背景
2. `AlarmAnalysis`：讲设备与质量 / 物料关联证据
3. `LineEfficiency`：讲产能、协同与交付影响
4. `PromptLabeling`：讲 HITL 的运营确认闭环
5. `StrategicSim`：讲不同方案风险与资源动作
6. 最后补一句：第二阶段由 AgentNexus 接管 Task DAG 与多 Agent 编排

## 七、什么不该在第一阶段做

以下内容建议第二阶段再做：

- 自然语言 `/decide`
- 多 Agent 实时编排面板
- 真正的 MES / WMS / MRO 回写
- 自动停机、自动改排程、自动调拨

否则会让 RelOS 的边界被稀释，也会显著增加演示不稳定性。

## 八、最终建议

如果你的目标是：

- 保留现有 RelOS demo 页面
- 尽快讲出两个复杂场景
- 最大限度强调 RelOS 自身价值

那么最优方案是：

1. 先只扩展 RelOS 的数据模型、seed、决策包、决策级 HITL 和 Shadow ActionBundle。
2. 先用现有页面组合演示复杂场景。
3. 若页面承载仍不够，再只新增一个“复合扰动决策包”页面。
4. 等 RelOS 的最小演示版本稳定后，再让 AgentNexus 叠加多 Agent 与 `/decide` 能力。

这样可以保证：

- RelOS 的核心价值先被看见
- demo 页面继续保留
- 后续向 AgentNexus 和外部系统扩展时不会返工边界
