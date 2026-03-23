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

- RelationObject v1.0：当前版本（Sprint 1–2）
- 新增字段策略：Pydantic `Optional` 字段 + 默认值，向后兼容
- 破坏性变更：需要数据迁移脚本 + 版本号升级

### 5.2 数据迁移原则

- 关系数据只追加，不修改历史记录
- schema 变更通过 Neo4j SET 语句逐步迁移
- 迁移脚本放 `scripts/migrations/` 目录，以日期命名
