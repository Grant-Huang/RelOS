# RelOS 数据模型设计文档

**版本**：v1.0  
**日期**：2026 年 3 月

---

## 1. 核心模型：RelationObject

RelationObject 是整个系统最重要的数据单元，所有知识均以此格式表达。

```python
class RelationObject(BaseModel):
    # 身份
    id: str                          # UUID，全局唯一
    relation_type: str               # 格式：DOMAIN__VERB__DOMAIN
                                     # 例：DEVICE__TRIGGERS__ALARM

    # 关系两端
    source_node_id: str              # 起始节点 ID
    source_node_type: str            # 起始节点类型
    target_node_id: str              # 终止节点 ID
    target_node_type: str            # 终止节点类型

    # 置信度
    confidence: float                # 0.0–1.0
    phase_weight: float              # 阶段权重（0.0–1.0）
    knowledge_phase: KnowledgePhase  # 知识阶段枚举

    # 来源与溯源
    provenance: SourceType           # 来源类型枚举
    provenance_detail: str           # 来源详情（告警 ID / 文档片段 / 工单号）
    extracted_by: str | None         # 工程师 ID 或 LLM 模型名

    # 时间与衰减
    created_at: datetime
    updated_at: datetime
    half_life_days: int              # 置信度半衰期（天）

    # 生命周期
    status: RelationStatus           # pending_review / active / conflicted / archived

    # 冲突追踪
    conflict_with: list[str]         # 冲突的 relation ID 列表

    # 扩展属性
    properties: dict[str, Any]       # 业务扩展字段
```

### 1.1 relation_type 命名规范

格式：`SOURCE_TYPE__VERB__TARGET_TYPE`（全大写，双下划线分隔）

| relation_type | 含义 |
|--------------|------|
| `DEVICE__TRIGGERS__ALARM` | 设备触发告警 |
| `ALARM__INDICATES__COMPONENT_FAILURE` | 告警指示部件故障 |
| `COMPONENT__PART_OF__DEVICE` | 部件属于设备 |
| `OPERATOR__PERFORMS__OPERATION` | 操作员执行操作 |
| `ALARM__CORRELATES__ALARM` | 告警之间相关 |
| `PROCESS__AFFECTS__QUALITY` | 工艺影响质量 |
| `MATERIAL__CAUSES__DEFECT` | 物料导致缺陷 |

### 1.2 置信度初始化规则

| 来源类型 | 置信度区间 | 合并 alpha | 半衰期 |
|---------|-----------|-----------|-------|
| `manual_engineer` | 0.90–1.00 | 0.30 | 365 天 |
| `sensor_realtime` | 0.80–0.95 | 0.50 | 90 天 |
| `mes_structured` | 0.75–0.90 | 0.40 | 90 天 |
| `llm_extracted` | 0.50–**0.85**（硬上限）| 0.20 | 90 天 |
| `inference` | 0.40–0.75 | 0.15 | 60 天 |
| `structured_document` | 0.65–0.85 | 0.35 | 90 天 |
| `expert_document` | 0.50–0.85 | 0.25 | 90 天 |

> **Sprint 3 新增**：`structured_document`（FMEA/CMMS 工单规则解析）和 `expert_document`（8D 报告/交接班日志，LLM 抽取 + 人工标注）来源类型由文档摄取 Pipeline 自动设置，无需手动指定。

### 1.2b 阶段权重（phase_weight）规则

为保证多渠道知识在同一图谱中可解释、可治理，RelationObject 新增阶段字段：

| knowledge_phase | 阶段说明 | phase_weight（建议初始值） |
|----------------|---------|---------------------------|
| `bootstrap` | 阶段 1：公共知识初始化 | 0.35 |
| `interview` | 阶段 2：专家访谈调研 | 0.90 |
| `pretrain` | 阶段 3：企业文档预训练 | 0.70 |
| `runtime` | 阶段 4：运行期在线强化 | 1.00 |

说明：
- `phase_weight` 是**可配置默认值**，允许按行业/工厂微调。
- 阶段 2、3 支持多轮强化；每次强化属于新的观测事件，不覆盖历史溯源。
- 运行期（阶段 4）产生的确认/否定反馈应写入关系更新日志，并可提升 `knowledge_phase` 到 `runtime`。

### 1.2c 最终置信度计算建议

写入图谱的 `confidence` 为最终可用置信度，建议由以下因素共同作用：

```text
confidence_final = clamp(
  confidence_observed
  * phase_weight
  * freshness_decay(t)
  * source_adjustment(alpha),
  0.0, 1.0
)
```

其中：
- `confidence_observed`：该次观测的原始置信度（输入或抽取结果）
- `phase_weight`：阶段权重（本文新增）
- `freshness_decay(t)`：基于 `half_life_days` 的时间衰减因子
- `source_adjustment(alpha)`：按来源类型设置的合并/可信度调节因子

实现建议：
- 关系对象中持久化 `confidence`（最终值）和 `phase_weight`（解释因子）
- 计算过程写入 `properties.confidence_trace`，便于审计与回放

### 1.2d properties 持久化约定（实现对齐，新增）

Neo4j 的关系属性不支持直接存储嵌套 Map/Dict（只能存原子类型或其数组），因此：

- API / Python 模型层仍使用 `properties: dict[str, Any]`
- Neo4j 存储层将其序列化为 `properties_json: string`（JSON 字符串）
- 读取时再反序列化回 `properties`

该约定用于支持阶段 4 的“无感标注上下文”、解释性追踪（如 `properties.confidence_trace`）等扩展字段，同时保持图存储兼容性。

### 1.3 关系状态流转

```
                    LLM 抽取
                      ↓
              [pending_review]
                      │
         工程师确认   │   工程师否定
              ↓       │       ↓
          [active]    │  confidence < 0.2
              │       │       ↓
   发现冲突   │       │   [archived]
              ↓       │
         [conflicted] │
              │       │
   冲突解决   │       │
              ↓       │
          [active] ───┘
              │
   关系过期/被替代
              ↓
          [archived]（保留历史，不删除）
```

---

## 2. 节点模型

```python
class Node(BaseModel):
    id: str                         # 全局唯一
    node_type: str                  # Device / Alarm / Operator / Component / Material / Process
    name: str                       # 人类可读名称
    properties: dict[str, Any]      # 扩展属性
    created_at: datetime
```

### 2.1 节点类型定义

| node_type | 描述 | 示例 |
|-----------|------|------|
| `Device` | 生产设备 | 注塑机、CNC 机床、传送带 |
| `Alarm` | 设备告警 | 振动超限、温度过高、压力异常 |
| `Component` | 设备部件 | 主轴轴承、冷却系统、液压泵 |
| `Operator` | 操作员 / 工程师 | 维修工程师、操作员 |
| `WorkOrder` | 生产工单 | 加工任务、维修工单 |
| `Material` | 原材料 / 物料 | 钢材批次、润滑油型号 |
| `Process` | 工艺参数 | 注射速度、温度曲线 |
| `QualityDefect` | 质量缺陷 | 尺寸超差、表面划痕 |

---

## 3. Neo4j 图模型

### 3.1 图结构示意

```
(Device:device-M1 {name: "1号机"})
        │
        │ [DEVICE__TRIGGERS__ALARM {confidence: 0.85}]
        ▼
(Alarm:alarm-VIB-001 {alarm_code: "VIB-001"})
        │
        │ [ALARM__INDICATES__COMPONENT_FAILURE {confidence: 0.70}]
        ▼
(Component:component-bearing-M1 {name: "主轴轴承"})
        │
        │ [COMPONENT__PART_OF__DEVICE {confidence: 1.0}]
        ▼
(Device:device-M1)  ← 形成闭环

(Alarm:alarm-VIB-001)
        │
        │ [ALARM__INDICATES__COMPONENT_FAILURE {confidence: 0.30}]
        ▼
(Component:component-coolant-M1 {name: "冷却系统"})
```

### 3.2 关键 Cypher 查询

**子图提取（设备中心，2 跳）**：
```cypher
MATCH (center {id: $device_id})
CALL apoc.path.subgraphAll(center, {
    maxLevel: 2,
    relationshipFilter: '>'
})
YIELD relationships
UNWIND relationships AS r
WITH r
WHERE r.confidence >= 0.3
  AND r.status IN ['active']
RETURN r, type(r) AS rel_type,
       startNode(r).id AS src_id,
       endNode(r).id AS tgt_id
ORDER BY r.confidence DESC
```

**待审关系队列**：
```cypher
MATCH ()-[r]->()
WHERE r.status = 'pending_review'
RETURN r ORDER BY r.confidence DESC LIMIT 50
```

**置信度更新（人工确认）**：
```cypher
MATCH ()-[r {id: $rel_id}]->()
SET r.confidence = $new_confidence,
    r.status = $new_status,
    r.updated_at = $now
```

### 3.3 索引与约束

```cypher
-- 节点唯一性约束
CREATE CONSTRAINT device_id_unique IF NOT EXISTS
  FOR (n:Device) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT alarm_id_unique IF NOT EXISTS
  FOR (n:Alarm) REQUIRE n.id IS UNIQUE;

-- 关系查询索引
CREATE INDEX relation_confidence IF NOT EXISTS
  FOR ()-[r]-() ON (r.confidence);

CREATE INDEX relation_status IF NOT EXISTS
  FOR ()-[r]-() ON (r.status);
```

---

## 4. Action Engine 模型

```python
class ActionRecord(BaseModel):
    id: str                          # UUID
    alarm_id: str                    # 关联告警
    device_id: str                   # 关联设备
    recommended_cause: str           # 推荐根因
    action_description: str          # 操作描述
    status: ActionStatus             # 八状态枚举
    shadow_mode: bool                # True=只记录不执行
    logs: list[ActionLog]            # 不可变审计日志
    pre_flight_results: dict         # 五步验证结果
    created_at: datetime
    updated_at: datetime

class ActionLog(BaseModel):
    timestamp: datetime              # 不可变
    from_status: ActionStatus
    to_status: ActionStatus
    operator_id: str
    reason: str
    shadow_mode: bool
```

---

## 5. 数据版本与迁移策略

### 5.1 Schema 版本管理

- RelationObject v1.0：基础版本（Sprint 1–2）
- RelationObject v1.1：新增 `knowledge_phase`、`phase_weight`（阶段化知识治理）
- 新增字段策略：Pydantic `Optional` 字段 + 默认值，向后兼容
- 破坏性变更：需要数据迁移脚本 + 版本号升级

### 5.2 数据迁移原则

- 关系数据只追加，不修改历史记录
- schema 变更通过 Neo4j SET 语句逐步迁移
- 迁移脚本放 `scripts/migrations/` 目录，以日期命名

### 5.3 v1.1 迁移步骤（新增）

1. 给历史关系补全默认阶段字段（建议先按来源推断）：
   - `manual_engineer` → `interview`
   - `structured_document` / `expert_document` → `pretrain`
   - `sensor_realtime` / `inference` → `runtime`
   - 其他未知来源 → `bootstrap`
2. 依据阶段设置默认 `phase_weight`。
3. 保留旧关系 `confidence` 不回写重算，后续在新增观测中逐步自然校准。
