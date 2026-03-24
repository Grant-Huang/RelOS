"""
relos/core/models.py
--------------------
RelOS 的核心数据模型。

设计原则（来自设计文档）：
- 关系是第一公民：所有知识以 RelationObject 表达
- 置信度 + 来源可溯：每条关系都携带 confidence 和 provenance
- 不完美可用：关系从 pending_review 开始，人工确认后才升为 active
- 冲突保留：冲突关系不删除，标注为 conflicted 后保留完整历史
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

# ─────────────────────────────────────────────
# 枚举：来源类型
# ─────────────────────────────────────────────

class SourceType(StrEnum):
    """
    关系的来源类型。

    不同来源对应不同的：
    - 初始置信度区间
    - 合并时的 alpha 权重（加权滑动平均）
    - 衰减半衰期 half_life_days
    """
    MANUAL_ENGINEER     = "manual_engineer"      # 工程师手动输入，最高可信度
    SENSOR_REALTIME     = "sensor_realtime"      # 传感器实时数据，高可信度
    MES_STRUCTURED      = "mes_structured"       # MES/ERP 结构化导入
    LLM_EXTRACTED       = "llm_extracted"        # LLM 从文本中抽取，置信度上限 0.85
    INFERENCE           = "inference"            # 系统从已有关系推断
    STRUCTURED_DOCUMENT = "structured_document"  # 结构化文档（FMEA/CMMS工单），规则解析
    EXPERT_DOCUMENT     = "expert_document"      # 专家文档（8D报告/案例库），LLM抽取+人工标注


class RelationStatus(StrEnum):
    """
    关系的生命周期状态。

    状态流转：
    pending_review → active（人工审核通过）
    active → conflicted（发现冲突关系）
    conflicted → active（冲突解决）
    active / conflicted → archived（关系过期或被替代）
    """
    PENDING_REVIEW = "pending_review"   # 待审核（LLM 抽取的关系强制进入此状态）
    ACTIVE         = "active"           # 已激活，可用于推理
    CONFLICTED     = "conflicted"       # 与其他关系冲突，暂停推理使用
    ARCHIVED       = "archived"         # 已归档，不参与推理但保留历史


# ─────────────────────────────────────────────
# 核心 Schema：RelationObject
# ─────────────────────────────────────────────

class RelationObject(BaseModel):
    """
    RelOS 中所有关系的统一表达单元。

    这是整个系统最重要的 Schema——所有来源的关系信号
    最终都必须收敛到这个格式，才能进入图存储。

    置信度初始化规则（设计文档 §3.2）：
    - manual_engineer:  0.90 – 1.00
    - sensor_realtime:  0.80 – 0.95
    - mes_structured:   0.75 – 0.90
    - llm_extracted:    0.50 – 0.85（硬上限 0.85）
    - inference:        0.40 – 0.75
    """

    # ── 身份 ──────────────────────────────────
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="全局唯一关系 ID"
    )
    relation_type: str = Field(
        description="关系类型，格式：DOMAIN__VERB__DOMAIN，例如 DEVICE__TRIGGERS__ALARM"
    )

    # ── 关系两端 ──────────────────────────────
    source_node_id: str = Field(description="起始节点 ID")
    source_node_type: str = Field(description="起始节点类型，例如 Device, Operator, Component")
    target_node_id: str = Field(description="终止节点 ID")
    target_node_type: str = Field(description="终止节点类型")

    # ── 置信度 ────────────────────────────────
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="关系置信度，0.0–1.0"
    )

    # ── 来源与溯源 ────────────────────────────
    provenance: SourceType = Field(description="关系来源类型")
    provenance_detail: str = Field(
        default="",
        description="来源详情，例如告警 ID、文档片段、工单号"
    )
    extracted_by: str | None = Field(
        default=None,
        description="抽取者：工程师 ID 或 LLM 模型名称"
    )

    # ── 时间与衰减 ────────────────────────────
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    half_life_days: int = Field(
        default=90,
        description="置信度半衰期（天）。按关系类型配置：设备告警 90 天，操作员操作 30 天"
    )

    # ── 生命周期状态 ──────────────────────────
    status: RelationStatus = Field(
        default=RelationStatus.PENDING_REVIEW,
        description="关系状态。LLM 抽取的关系强制从 pending_review 开始"
    )

    # ── 冲突追踪 ──────────────────────────────
    conflict_with: list[str] = Field(
        default_factory=list,
        description="与本关系冲突的 RelationObject ID 列表。冲突不删除，只标注"
    )

    # ── 扩展属性 ──────────────────────────────
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="关系的额外属性，例如 {frequency: 5, severity: 'high'}"
    )

    @model_validator(mode="after")
    def apply_llm_constraints(self) -> RelationObject:
        """
        LLM 抽取关系的双重约束（model_validator 确保所有字段已初始化后再校验）：
        1. 置信度硬上限 0.85（防止系统过度信任 AI 抽取的非结构化知识）
        2. 强制 pending_review（LLM 关系不允许直接变为 active）
        """
        if self.provenance == SourceType.LLM_EXTRACTED:
            if self.confidence > 0.85:
                self.confidence = 0.85
            if self.status == RelationStatus.ACTIVE:
                self.status = RelationStatus.PENDING_REVIEW
        return self


# ─────────────────────────────────────────────
# 节点模型
# ─────────────────────────────────────────────

class Node(BaseModel):
    """
    图中的实体节点（设备、部件、操作员、告警、工单等）。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = Field(description="节点类型，例如 Device, Alarm, Operator, Component")
    name: str = Field(description="节点人类可读名称")
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ─────────────────────────────────────────────
# 合并结果模型（Relation Core Engine 输出）
# ─────────────────────────────────────────────

class MergeResult(BaseModel):
    """
    关系合并操作的结果。
    合并算法：加权滑动平均，alpha 因来源类型而异（设计文档 §4.1）
    """
    relation_id: str
    previous_confidence: float
    new_confidence: float
    alpha_used: float           # 本次合并使用的 alpha 值
    merge_count: int            # 该关系被合并的累计次数
    conflict_detected: bool = False
    conflict_relation_ids: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────
# 置信度衰减配置
# ─────────────────────────────────────────────

# 按关系类型配置半衰期（天）
# 设计文档 §4.2：使用指数衰减函数 confidence(t) = c0 * 0.5^(t/half_life)
HALF_LIFE_CONFIG: dict[str, int] = {
    # ── 基础场景（设备故障分析）────────────────────────────────
    "DEVICE__TRIGGERS__ALARM":           90,
    "OPERATOR__PERFORMS__OPERATION":     30,
    "COMPONENT__PART_OF__DEVICE":        365,   # 物理关系，衰减慢
    "ALARM__CORRELATES__ALARM":          60,
    "ALARM__INDICATES__COMPONENT_FAILURE": 180,

    # ── 场景7：产线效率瓶颈识别 ────────────────────────────────
    "LINE__CONTAINS__MACHINE":           3650,  # 产线-设备结构关系，极慢衰减
    "MACHINE__CAUSES__DOWNTIME":         7,     # 停机记录，快速过期
    "MACHINE__BELONGS_TO__LINE":         3650,

    # ── 场景8：跨部门协同（生产 vs 采购）──────────────────────
    "SUPPLIER__PROVIDES__MATERIAL":      60,
    "MATERIAL__USED_IN__WORKORDER":      30,
    "SUPPLIER__DELAYS__MATERIAL":        14,    # 延迟记录，2 周内有效
    "WORKORDER__BLOCKED_BY__SHORTAGE":   7,

    # ── 场景9：异常处理效率 ────────────────────────────────────
    "ALARM__CAUSES__ISSUE":              30,
    "ISSUE__RESOLVED_BY__OPERATOR":      90,    # 经验关联
    "SHIFT__HANDLES__ISSUE":             30,

    # ── 场景10：企业级风险雷达 ─────────────────────────────────
    "ISSUE__CONTRIBUTES_TO__RISK":       14,    # 风险贡献，动态更新快
    "ALARM__ELEVATES__RISK":             7,

    # ── 场景11：资源配置优化 ───────────────────────────────────
    "RESOURCE__REDUCES__ISSUE":          90,    # 资源投入与问题减少的关联
    "ISSUE__REQUIRES__RESOURCE":         60,

    # ── 场景12：战略决策模拟 ───────────────────────────────────
    "CAPACITY__AFFECTS__FAILURE_RATE":   180,   # 产能-故障率关联，历史规律
    "LOAD__INCREASES__RISK":             30,

    "DEFAULT":                           90,
}

# 按来源类型配置合并 alpha（加权滑动平均权重）
# alpha 越高，新观测的影响越大
ALPHA_CONFIG: dict[SourceType, float] = {
    SourceType.MANUAL_ENGINEER:     0.3,   # 工程师确认：稳定，新观测权重低
    SourceType.SENSOR_REALTIME:     0.5,   # 传感器：实时性强，新观测权重高
    SourceType.MES_STRUCTURED:      0.4,
    SourceType.LLM_EXTRACTED:       0.2,   # LLM：不确定性高，保守更新
    SourceType.INFERENCE:           0.15,
    SourceType.STRUCTURED_DOCUMENT: 0.35,  # 结构化文档：可信度介于 MES 和工程师之间
    SourceType.EXPERT_DOCUMENT:     0.25,  # 专家文档：LLM+人工，保守更新
}
