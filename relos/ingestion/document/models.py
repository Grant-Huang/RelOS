"""
relos/ingestion/document/models.py
------------------------------------
文档摄取模块的内部数据模型。

生命周期：
  uploaded → parsing → extracting → pending_review → committed / failed

ExtractedRelationDraft 与 RelationObject 的区别：
  - Draft 是"候选"：包含 AI 抽取的证据原文、置信度评估
  - 经人工标注（approve / reject / modify）后，才转换为 RelationObject 写入图谱

TemplateType 对应 parse + 提示词策略：
  - 结构化模板（CMMS / FMEA / SUPPLIER）：规则解析，confidence 较高
  - 非结构化模板（QUALITY_8D / SHIFT_HANDOVER）：LLM 抽取，confidence 适中
  - UNKNOWN：全量交给 LLM，confidence 较低
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class TemplateType(StrEnum):
    """已知文档模板类型。影响解析策略和 LLM 提示词选择。"""
    CMMS_MAINTENANCE  = "cmms_maintenance"   # 设备维修工单（Excel）
    FMEA              = "fmea"               # FMEA 失效模式分析（Excel）
    SUPPLIER_DELIVERY = "supplier_delivery"  # 供应商交期记录（Excel）
    QUALITY_8D        = "quality_8d"         # 8D 质量异常报告（Word）
    SHIFT_HANDOVER    = "shift_handover"     # 交接班日志（Word）
    UNKNOWN           = "unknown"            # 未识别，全量 LLM 处理


class DocumentStatus(StrEnum):
    """文档处理状态机。"""
    UPLOADED       = "uploaded"        # 上传完成，等待解析
    PARSING        = "parsing"         # 正在解析文件结构
    EXTRACTING     = "extracting"      # AI 正在抽取关系
    PENDING_REVIEW = "pending_review"  # 等待人工标注
    COMMITTED      = "committed"       # 已提交到图谱
    FAILED         = "failed"          # 处理失败


class AnnotationStatus(StrEnum):
    """单条候选关系的标注状态。"""
    PENDING  = "pending"   # 待审
    APPROVED = "approved"  # 人工确认
    REJECTED = "rejected"  # 人工拒绝
    MODIFIED = "modified"  # 人工修改了置信度或关系类型


class ParsedRow(BaseModel):
    """结构化文档中的一行数据（Excel 行 / Word 表格行）。"""
    row_index: int
    fields: dict[str, str]   # 列名 → 单元格值（均转为字符串）


class ParsedDocument(BaseModel):
    """文件解析后的结构化中间表示，交给 LLM 抽取器使用。"""
    template_type: TemplateType
    source_filename: str
    rows: list[ParsedRow] = []
    sections: dict[str, str] = {}   # Word 文档的章节：标题 → 正文


class ExtractedRelationDraft(BaseModel):
    """
    AI 抽取出的候选关系，等待人工标注。

    id 使用短 UUID，便于 API URL 和前端展示。
    evidence 是原文片段，让标注员理解抽取依据。
    reasoning 是 AI 的推理说明，帮助标注员决策。
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # 来源节点
    source_node_id: str
    source_node_name: str
    source_node_type: str
    # 目标节点
    target_node_id: str
    target_node_name: str
    target_node_type: str
    # 关系
    relation_type: str
    confidence: float
    # AI 抽取元数据
    evidence: str        # 原文证据片段（最多 200 字）
    reasoning: str       # AI 推理说明（最多 100 字）
    # 标注状态
    annotation_status: AnnotationStatus = AnnotationStatus.PENDING
    modified_confidence: Optional[float] = None   # 人工修改后的置信度
    modified_relation_type: Optional[str] = None  # 人工修改后的关系类型
    annotated_at: Optional[datetime] = None
    annotated_by: Optional[str] = "engineer"

    @property
    def effective_confidence(self) -> float:
        """返回最终置信度（人工修改优先）。"""
        return self.modified_confidence if self.modified_confidence is not None else self.confidence

    @property
    def effective_relation_type(self) -> str:
        """返回最终关系类型（人工修改优先）。"""
        return self.modified_relation_type or self.relation_type


class DocumentRecord(BaseModel):
    """文档处理记录（全生命周期）。MVP 阶段存储在内存中。"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    filename: str
    file_size_bytes: int
    template_type: TemplateType
    status: DocumentStatus = DocumentStatus.UPLOADED
    error_message: Optional[str] = None
    extracted_relations: list[ExtractedRelationDraft] = []
    committed_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    def pending_count(self) -> int:
        return sum(1 for r in self.extracted_relations
                   if r.annotation_status == AnnotationStatus.PENDING)

    def approved_count(self) -> int:
        return sum(1 for r in self.extracted_relations
                   if r.annotation_status in (AnnotationStatus.APPROVED, AnnotationStatus.MODIFIED))
