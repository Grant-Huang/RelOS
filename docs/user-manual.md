# RelOS 系统使用操作手册

> **版本**：v0.4.0（Sprint 4）
> **适用角色**：维修工程师、设备管理员、IT 集成人员
> **更新日期**：2026-03-25（补充 `knowledge_phase` / `phase_weight` 口径）

---

## 手册说明

本手册分为两个部分：

- **第一部分：功能说明** — 系统有什么功能，每个功能做什么
- **第二部分：使用场景** — 在实际工作中怎么用，步骤是什么

**系统核心价值**：RelOS 将老工程师的维修经验和历史故障数据转化为结构化知识，帮助任何维修人员快速找到设备故障根因，减少停机时间。

---

# 第一部分：功能说明

## 1. 系统架构概览

```
你发送告警信息
      ↓
RelOS 查询历史关系知识库
      ↓
根因分析引擎（规则引擎 / AI 分析）
      ↓
推荐根因 + 置信度
      ↓
工程师确认 → 知识库自动优化（数据飞轮）
```

## 2. 核心概念

理解下面这些概念，就能理解系统的工作原理：

### 2.1 关系（Relation）

系统用"关系"来存储知识。一条关系就是一句话：

```
"1号机振动超限告警" → 70% 概率是 → "主轴轴承故障"
```

每条关系有：
- **置信度（0.0～1.0）**：越接近 1.0 越可信
- **来源**：工程师经验 / 传感器 / MES 系统 / AI 分析
- **状态**：活跃 / 待审核 / 冲突 / 已归档
- **半衰期**：多少天后置信度降低一半（经验知识 365 天，物理关系 10 年）
- **知识阶段（`knowledge_phase`）**：这条知识来自哪个建设阶段（初始化 / 专家访谈 / 文档预训练 / 运行强化）
- **阶段权重（`phase_weight`，0.0～1.0）**：不同阶段对最终可信度的调节系数；未填写时由系统按阶段给默认值

**四阶段与默认阶段权重（与数据模型、API 文档一致）**：

| knowledge_phase | 含义 | 默认 phase_weight |
|-----------------|------|-------------------|
| `bootstrap` | 公共知识初始化（公开资料、行业模板等） | 0.35 |
| `interview` | 专家访谈、单条/批量专家录入 | 0.90 |
| `pretrain` | 企业文档导入、AI 抽取后提交图谱（见 `/v1/documents/*`） | 0.70 |
| `runtime` | 运行期反馈、在线强化（如 `POST /v1/relations/{id}/feedback`） | 1.00 |

### 2.2 数据飞轮

系统越用越聪明的机制：

```
1. 告警发生 → 系统给出推荐
2. 工程师确认"正确" → 该知识置信度 +0.15
3. 工程师否定"不对" → 该知识置信度 -0.30
4. 积累足够数据后 → 推荐准确率持续提高
```

### 2.3 Shadow Mode（影子模式）

- **开启时（默认）**：系统分析结果只记录日志，不实际发出工单
- **关闭时（生产就绪）**：系统可以真实触发操作

> 建议先用 Shadow Mode 运行 2-4 周，验证推荐准确率 > 70% 后再关闭。

---

## 3. 功能模块详解

### 3.1 告警分析（核心功能）

**功能**：输入一个设备告警，系统自动给出根因推荐

**接口**：`POST /v1/decisions/analyze-alarm`

**输入字段**：

| 字段 | 说明 | 是否必填 | 示例 |
|------|------|---------|------|
| `alarm_id` | 告警唯一编号 | ✅ | `ALM-20260322-001` |
| `device_id` | 设备节点 ID | ✅ | `device-M1` |
| `alarm_code` | 告警代码 | ✅ | `VIB-001` |
| `alarm_description` | 告警详细描述 | ✅ | `振动值18.3mm/s，超过阈值12.5mm/s` |
| `severity` | 严重程度 | ❌ | `low` / `medium` / `high` / `critical` |
| `force_hitl` | 强制人工审核 | ❌ | `false` |

**输出字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| `recommended_cause` | 推荐根因 | `主轴轴承磨损` |
| `confidence` | 推荐置信度 | `0.85` (85%) |
| `reasoning` | 推理依据 | `基于张工20年经验...` |
| `engine_used` | 使用的引擎 | `rule_engine` / `llm` / `hitl` |
| `requires_human_review` | 是否需要人工审核 | `false` |
| `shadow_mode` | 影子模式状态 | `true` |

**管理层/高层自解释字段（新增）**：

除了给一线工程师的 `reasoning` 之外，系统还会返回一组“可追溯解释”字段，适合老中层/高层快速判断与追责审计：

| 字段 | 说明 | 适用人群 |
|------|------|----------|
| `explanation_summary` | 一屏摘要：结论 + 置信度 + 主要证据阶段贡献 | 高层 |
| `evidence_relations` | 证据关系最小集合（可追溯到具体关系 ID 与来源） | 中层/审计 |
| `phase_contributions` | 按 `knowledge_phase` 汇总的阶段贡献（解释阶段权重影响） | 中层 |
| `confidence_trace_id` | 解释追踪 ID（用于日志/埋点/回放） | IT/审计 |

示例（节选）：

```json
{
  "explanation_summary": "推荐：component-bearing-M1 异常；置信度 0.85；主要证据阶段：interview（约 65%）",
  "evidence_relations": [
    {
      "id": "rel-001",
      "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
      "confidence": 0.70,
      "provenance": "manual_engineer",
      "knowledge_phase": "interview",
      "phase_weight": 0.90,
      "status": "active",
      "provenance_detail": "张工 20 年经验总结"
    }
  ],
  "phase_contributions": [
    {"knowledge_phase": "interview", "score": 0.63, "share": 0.65},
    {"knowledge_phase": "runtime", "score": 0.34, "share": 0.35}
  ],
  "confidence_trace_id": "conf-trace-..."
}
```

**三种推理路径**：

```
情况1：知识丰富，置信度 ≥ 0.75
   → 规则引擎直接推断（最快，< 500ms，不消耗 AI）

情况2：知识有限，置信度 0.5~0.75
   → AI 辅助分析（3-8秒，消耗 AI Token）

情况3：知识不足或新设备，置信度 < 0.5
   → 触发人工审核（HITL），通知工程师处理
```

---

### 3.2 专家知识录入

**功能**：将有经验的工程师的知识录入系统

**方式一：单条录入**

接口：`POST /v1/expert-init`

```json
{
  "source_node_id": "alarm-VIB-001",
  "source_node_type": "Alarm",
  "target_node_id": "component-bearing-M1",
  "target_node_type": "Component",
  "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
  "confidence": 0.85,
  "knowledge_phase": "interview",
  "phase_weight": 0.90,
  "provenance_detail": "20年经验，高温下振动告警85%是轴承问题",
  "engineer_id": "zhang-engineer"
}
```

**方式二：批量录入**

接口：`POST /v1/expert-init/batch`

将多条知识打包成数组一次提交（最多 100 条）。

**方式三：Excel 批量导入**

接口：`POST /v1/expert-init/upload-excel`

> 最适合 IT 集成人员从 MES/ERP 系统导出数据后批量导入。

**Excel 模板格式**：

| 源节点ID | 源节点类型 | 目标节点ID | 目标节点类型 | 关系类型 | 置信度 | 知识阶段（可选）| 阶段权重（可选）|
|---------|----------|----------|------------|---------|-------|----------------|----------------|
| alarm-VIB-001 | Alarm | component-bearing-M1 | Component | ALARM__INDICATES__COMPONENT_FAILURE | 0.85 | interview | 0.90 |
| device-M1 | Device | alarm-VIB-001 | Alarm | DEVICE__TRIGGERS__ALARM | 0.90 | interview | 0.90 |

> 💡 **小提示**：列名支持中英文，顺序不限。`knowledge_phase` / `phase_weight` 可省略，省略时服务端按阶段给默认权重（专家录入一般为 `interview` / `0.90`）。

**专家知识录入的特殊规则**：
- 置信度按原值保存（不压缩）
- 状态直接变为"活跃"（不需要人工审核）
- 这是因为专家自己就是审核者

---

### 3.3 关系管理

#### 查询单条关系

```
GET /v1/relations/{relation_id}
```

返回关系的完整信息，包括置信度、状态、历史等。

#### 提交工程师反馈（数据飞轮核心操作）

```
POST /v1/relations/{relation_id}/feedback
```

```json
{
  "engineer_id": "zhang-engineer",
  "confirmed": true
}
```

- `confirmed: true` → 置信度 +0.15，状态变为"活跃"
- `confirmed: false` → 置信度 -0.30，若低于 0.2 则归档

该接口属于**运行期强化（阶段 4）**：服务端会将本次反馈关联为 `knowledge_phase = "runtime"`，并可将关系按策略标记为运行期权重（默认 `phase_weight = 1.00`）。请求体仍只需 `engineer_id` 与 `confirmed`，无需手写阶段字段。

#### 查询设备子图

```
POST /v1/relations/subgraph
```

```json
{
  "center_node_id": "device-M1",
  "max_hops": 2,
  "min_confidence": 0.3
}
```

返回以指定设备为中心的所有相关关系，用于查看设备的完整知识图谱。

#### 待审核队列（HITL 队列）

```
GET /v1/relations/pending-review?limit=50
```

返回所有等待工程师确认的关系（主要来自 AI 分析结果）。

---

### 3.4 操作执行（Action Engine）

**功能**：在工程师确认根因后，创建检查任务

**接口**：`POST /v1/decisions/execute-action`

```json
{
  "alarm_id": "ALM-20260322-001",
  "device_id": "device-M1",
  "recommended_cause": "轴承磨损",
  "action_description": "检查主轴轴承磨损情况",
  "operator_id": "zhang-engineer"
}
```

**安全限制**：`action_description` 必须包含以下关键词之一：
`检查`、`查看`、`确认`、`记录`、`测量`

> 这是 MVP 安全设计：只允许记录性操作，不允许控制类操作（如"停止设备"）

**8 步状态机**：

```
待处理 → 验证中 → 已通过 → 执行中 → 已完成
                 ↓
               已拒绝（未通过安全检查）
```

Shadow Mode 下：所有操作记录日志，不实际执行

---

### 3.5 图谱统计

**功能**：查看知识库的整体健康状况

**接口**：`GET /v1/metrics`

**关键指标解读**：

| 指标 | 正常范围 | 异常说明 |
|------|---------|---------|
| `avg_confidence` | > 0.6 | 过低说明知识质量差，需要更多专家录入 |
| `active_ratio` | > 0.7 | 过低说明 pending 积压，需要工程师审核 |
| `pending_review_count` | < 50 | 过高需要关注 HITL 队列 |
| `conflicted_count` | < 20 | 过高说明知识库有冲突，需要人工干预 |

---

# 第二部分：使用场景

## 场景一：设备发生告警，快速定位根因

**背景**：1 号注塑机出现振动超限告警，操作员不确定是什么问题

**角色**：生产线操作员 / 维修工程师

### 操作步骤

**步骤 1**：发送告警到 RelOS

```bash
curl -X POST http://localhost:8000/v1/decisions/analyze-alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_id": "ALM-20260322-001",
    "device_id": "device-M1",
    "alarm_code": "VIB-001",
    "alarm_description": "主轴振动超限 18.3mm/s，当前环境温度 38摄氏度",
    "severity": "high"
  }'
```

**步骤 2**：查看分析结果

```json
{
  "recommended_cause": "component-bearing-M1 异常",
  "confidence": 0.70,
  "reasoning": "规则引擎：张工20年经验，高温天气振动告警70%是轴承问题",
  "engine_used": "rule_engine",
  "requires_human_review": false
}
```

**步骤 3**：工程师前往检查轴承

**步骤 4**：确认结果后提交反馈

```bash
# 如果确认是轴承问题（运行期强化：服务端记为 knowledge_phase=runtime，phase_weight 按策略可为 1.00）
curl -X POST http://localhost:8000/v1/relations/rel-001/feedback \
  -H "Content-Type: application/json" \
  -d '{"engineer_id": "zhang-engineer", "confirmed": true}'
```

**结果**：
- 该知识的置信度从 0.70 提升到 0.85
- 下次相同告警，推荐置信度更高
- 系统越来越准确（数据飞轮）

---

## 场景二：新来工程师录入老师傅的经验

**背景**：老工程师张工即将退休，他的 20 年经验需要传承到系统中

**角色**：IT 实施人员 / 新工程师（帮助录入）

### 操作步骤

**方式 A：逐条录入（适合少量经验）**

```bash
curl -X POST http://localhost:8000/v1/expert-init \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "alarm-TEMP-002",
    "source_node_type": "Alarm",
    "target_node_id": "component-coolant-M1",
    "target_node_type": "Component",
    "relation_type": "ALARM__INDICATES__COMPONENT_FAILURE",
    "confidence": 0.90,
    "knowledge_phase": "interview",
    "phase_weight": 0.90,
    "provenance_detail": "张工：温度告警90%是冷却系统问题，检查冷却液水位和泵",
    "engineer_id": "zhang-engineer"
  }'
```

**方式 B：Excel 批量录入（适合大量经验）**

1. 下载 Excel 模板（格式见上文 3.2 节）
2. 与张工一起填写每一条经验
3. 上传导入：

```bash
curl -X POST "http://localhost:8000/v1/expert-init/upload-excel?engineer_id=zhang-engineer" \
  -F "file=@张工经验库.xlsx"
```

4. 系统返回导入结果：

```json
{
  "success_count": 28,
  "failed_count": 2,
  "errors": [
    {"row": 15, "error": "关系类型格式不正确"},
    {"row": 23, "error": "置信度超出范围 0.0-1.0"}
  ]
}
```

5. 修正错误行后重新上传

**验证录入成功**：

```bash
# 查询刚录入的某条关系
curl http://localhost:8000/v1/relations/subgraph \
  -H "Content-Type: application/json" \
  -d '{"center_node_id": "device-M1", "max_hops": 2}'
```

---

## 场景三：从 MES/ERP 系统批量导入历史数据

**背景**：工厂 MES 系统中有 5 年的维修工单记录，需要批量导入

**角色**：IT 集成人员

### 操作步骤

**步骤 1**：从 MES 系统导出数据为 Excel 格式

确保 Excel 包含以下列（支持中英文列名）：

| 列名（中文）| 列名（英文）| 必填 | 说明 |
|-----------|-----------|------|------|
| 源节点ID | source_node_id | ✅ | 设备或告警编号 |
| 源节点类型 | source_node_type | ✅ | Device/Alarm/Component |
| 目标节点ID | target_node_id | ✅ | 故障部件编号 |
| 目标节点类型 | target_node_type | ✅ | Component/Device/Alarm |
| 关系类型 | relation_type | ✅ | 见下方关系类型表 |
| 置信度 | confidence | ❌ | 0.0~1.0，默认 0.75 |
| 来源详情 | provenance_detail | ❌ | 工单号、日期等 |
| 知识阶段 | knowledge_phase | ❌ | `interview` / `pretrain` 等，省略时由系统推断 |
| 阶段权重 | phase_weight | ❌ | 0.0~1.0，省略时按 `knowledge_phase` 默认回填 |

**支持的关系类型**：

| 关系类型 | 含义 |
|---------|------|
| `ALARM__INDICATES__COMPONENT_FAILURE` | 告警 → 部件故障 |
| `DEVICE__TRIGGERS__ALARM` | 设备 → 触发告警 |
| `COMPONENT__PART_OF__DEVICE` | 部件 → 属于设备 |
| `OPERATOR__PERFORMS__OPERATION` | 操作员 → 执行操作 |
| `ALARM__CORRELATES__ALARM` | 告警 → 关联告警 |

**步骤 2**：先用 dry_run 模式验证数据格式（不写入数据库）

```bash
curl -X POST "http://localhost:8000/v1/expert-init/upload-excel?dry_run=true" \
  -F "file=@MES历史数据.xlsx"
```

**步骤 3**：确认无误后正式导入

```bash
curl -X POST "http://localhost:8000/v1/expert-init/upload-excel" \
  -F "file=@MES历史数据.xlsx"
```

**步骤 4**：验证导入结果

```bash
curl http://localhost:8000/v1/metrics
```

查看 `total_relations` 是否增加了预期数量。

---

## 场景四：处理 AI 分析产生的待审核队列

**背景**：系统用 AI 分析了一批告警，生成了需要工程师确认的知识

**角色**：维修工程师（有设备知识的人）

### 什么时候会产生待审核关系？

- AI 分析告警后，自动抽取了新的故障关系
- 置信度 < 0.85 的 AI 结论（按规定不能自动生效）
- 系统自动推断的新关系

### 操作步骤

**步骤 1**：查看待审核队列

```bash
curl http://localhost:8000/v1/relations/pending-review?limit=20
```

返回列表，每条包含：
- 关系描述（谁 → 什么关系 → 谁）
- 置信度
- 来源（AI 分析 / 系统推断）
- 推理依据

**步骤 2**：逐条审核

对每条关系，根据自己的经验判断：

```bash
# 情况A：认为正确，确认
curl -X POST http://localhost:8000/v1/relations/{relation_id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"engineer_id": "zhang-engineer", "confirmed": true}'

# 情况B：认为不对，否定
curl -X POST http://localhost:8000/v1/relations/{relation_id}/feedback \
  -H "Content-Type: application/json" \
  -d '{"engineer_id": "zhang-engineer", "confirmed": false}'
```

**建议**：每天检查一次待审核队列，保持队列 < 20 条。

---

## 场景五：监控系统知识库健康状况

**背景**：设备管理员需要定期了解知识库质量

**角色**：设备管理员 / 工厂主管

### 操作步骤

**定期查询统计数据**：

```bash
curl http://localhost:8000/v1/metrics
```

**解读结果**：

```json
{
  "total_nodes": 128,           // 知识库中的节点总数（设备、告警、部件等）
  "total_relations": 347,       // 知识关系总数
  "avg_confidence": 0.783,      // 平均置信度（目标：>0.7）
  "active_count": 289,          // 正在使用的活跃关系数
  "pending_review_count": 42,   // 等待工程师审核的关系数（目标：<50）
  "conflicted_count": 8,        // 有冲突的关系数（目标：<20）
  "archived_count": 8,          // 已归档（废弃）的关系数
  "active_ratio": 0.833         // 活跃率（目标：>0.7）
}
```

**健康判断标准**：

```
✅ 健康状态：
   - avg_confidence > 0.7
   - active_ratio > 0.7
   - pending_review_count < 50
   - conflicted_count < 20

⚠️ 需要关注：
   - pending_review_count > 50 → 请工程师处理审核队列
   - avg_confidence < 0.6 → 需要补录更多专家知识
   - conflicted_count > 20 → 需要工程师解决知识冲突
```

---

## 场景六：行业本体模板快速启动

**背景**：新工厂没有任何历史数据，需要快速建立基础知识库

**角色**：IT 实施人员

### 支持的行业模板

| 行业 | 说明 | 关系数量 |
|------|------|---------|
| `automotive` | 汽车零部件制造（焊接、冲压场景） | 7 条 |
| `electronics_3c` | 3C 电子制造（SMT、AOI 场景） | 8 条 |

### 操作步骤

**步骤 1**：选择行业模板，预览内容（dry_run）

```bash
curl -X POST "http://localhost:8000/v1/ontology/templates/automotive/import?dry_run=true"
```

**步骤 2**：确认模板内容适合工厂，正式导入

```bash
curl -X POST "http://localhost:8000/v1/ontology/templates/automotive/import"
```

**步骤 3**：模板关系导入后状态为"待审核"

工程师根据工厂实际情况，逐条确认或否认（见场景四）

**步骤 4**：补充工厂特有知识（见场景二）

---

# 附录

## API 基础信息

| 项目 | 值 |
|------|---|
| 基础 URL | `http://localhost:8000/v1` |
| 接口文档 | `http://localhost:8000/docs` |
| 数据格式 | JSON |
| 编码 | UTF-8 |

## 完整 API 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/metrics` | GET | 图谱统计 |
| `/relations` | POST | 创建/合并关系 |
| `/relations/{id}` | GET | 查询单条关系 |
| `/relations/{id}/feedback` | POST | 提交工程师反馈 |
| `/relations/subgraph` | POST | 查询设备子图 |
| `/relations/pending-review` | GET | 待审核队列 |
| `/decisions/analyze-alarm` | POST | 告警根因分析 |
| `/decisions/execute-action` | POST | 执行操作任务 |
| `/decisions/action/{id}` | GET | 查询操作状态 |
| `/expert-init` | POST | 专家单条录入 |
| `/expert-init/batch` | POST | 专家批量录入 |
| `/expert-init/upload-excel` | POST | Excel 文件导入 |
| `/ontology/templates/{industry}/import` | POST | 行业模板导入 |

## 关系状态说明

| 状态 | 中文 | 说明 |
|------|------|------|
| `active` | 活跃 | 参与推理计算 |
| `pending_review` | 待审核 | 等待工程师确认（AI 结果默认此状态）|
| `conflicted` | 冲突 | 与其他关系矛盾，暂停使用 |
| `archived` | 已归档 | 置信度太低被废弃，保留历史记录 |

## 来源类型说明

| 来源 | 英文 | 特点 |
|------|------|------|
| 工程师手动录入 | `manual_engineer` | 最可信，直接活跃，无上限 |
| 传感器实时数据 | `sensor_realtime` | 高频，alpha=0.5 |
| MES/ERP 导入 | `mes_structured` | 结构化，alpha=0.4 |
| AI 分析抽取 | `llm_extracted` | 置信度上限 0.85，强制待审核 |
| 系统推断 | `inference` | 自动生成，alpha=0.3 |

## 知识阶段与阶段权重（knowledge_phase / phase_weight）

与 `docs/data-model.md`、`docs/api.md` 一致：每条关系可携带**知识阶段**与**阶段权重**，用于解释“这条知识从哪一阶段进入图谱、对最终置信度如何加权”。调用 API 时：

- **专家单条/批量/Excel 录入**：建议显式写 `knowledge_phase: "interview"` 与 `phase_weight: 0.90`（也可省略，由服务端默认）。
- **文档摄取提交到图谱**（`POST /v1/documents/{doc_id}/commit`）：服务端通常写入 `knowledge_phase: "pretrain"`、`phase_weight: 0.70`。
- **工程师反馈**（`POST /v1/relations/{id}/feedback`）：无需在 JSON 里写阶段字段；系统按**运行期强化**处理，对应 `runtime` / 默认 `1.00`。

## 置信度参考

| 置信度范围 | 含义 | 处理方式 |
|----------|------|---------|
| 0.9 ~ 1.0 | 非常可信 | 规则引擎直接推断 |
| 0.75 ~ 0.9 | 高度可信 | 规则引擎推断 |
| 0.5 ~ 0.75 | 中等可信 | AI 辅助分析 |
| 0.2 ~ 0.5 | 低可信度 | 触发人工审核 |
| < 0.2 | 不可信 | 自动归档 |

## 错误码说明

| HTTP 状态码 | 含义 | 常见原因 |
|-----------|------|---------|
| `200` | 成功 | - |
| `201` | 创建成功 | 新关系已入库 |
| `400` | 请求格式错误 | 字段类型错误，置信度超范围等 |
| `404` | 资源不存在 | 关系 ID 不存在 |
| `422` | 参数验证失败 | 缺少必填字段 |
| `429` | 请求过频 | 超出限流阈值（生产环境）|
| `500` | 服务器错误 | 查看日志排查 |
| `503` | 服务不可用 | Neo4j 或 Redis 未连接 |
