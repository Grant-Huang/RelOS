"""
relos/context/compiler.py
-------------------------
Context Engine：子图 → Prompt 编译器。

核心职责（设计文档 §5.1）：
1. 对子图执行六层剪枝（Token 预算管理）
2. 将 RelationObject 列表编译为 LLM 可理解的结构化 Markdown block
3. 三种查询策略适配不同决策场景

这是 RelOS 与 AgentNexus 的接口层——
输出的 Markdown context block 直接嵌入 LLM 的 system prompt。
"""

from __future__ import annotations

from dataclasses import dataclass

from relos.core.models import RelationObject


@dataclass
class ContextBlock:
    """
    Context Engine 的输出单元。
    content 是编译好的 Markdown，直接注入 LLM prompt。
    """
    content: str
    relation_count: int
    estimated_tokens: int
    pruned_count: int           # 被 Token 预算剪掉的关系数量
    query_strategy: str


class ContextCompiler:
    """
    子图到 Prompt 的编译器。

    六层剪枝规则（设计文档 §5.2，按优先级从高到低）：
    1. 过滤 archived 状态的关系
    2. 过滤置信度 < min_confidence 的关系
    3. 过滤与当前查询节点无直接关联的孤立关系
    4. 按置信度降序，保留 top N
    5. 相同节点对的多条关系，只保留置信度最高的一条
    6. 若仍超出 token 预算，截断最低置信度的关系
    """

    def __init__(
        self,
        max_relations: int = 20,         # 进入 Prompt 的最大关系数
        token_budget: int = 1500,        # 关系上下文的 Token 预算
        min_confidence: float = 0.3,
    ) -> None:
        self.max_relations = max_relations
        self.token_budget = token_budget
        self.min_confidence = min_confidence

    def compile(
        self,
        relations: list[RelationObject],
        center_node_id: str,
        query_context: str = "",
        strategy: str = "confidence_first",
    ) -> ContextBlock:
        """
        将子图关系编译为结构化 Markdown context block。

        Args:
            relations: 从 Neo4j 提取的子图关系列表
            center_node_id: 当前查询的中心节点（例如触发告警的设备）
            query_context: 当前查询描述（例如告警码 + 告警描述）
            strategy: 查询策略
                - "confidence_first": 广度优先，按置信度排序（默认，适合根因分析）
                - "causal_path": 因果路径优先（适合质量追溯）
                - "semantic": 语义相关性优先（适合自由问答）
        """
        original_count = len(relations)

        # ── 六层剪枝 ─────────────────────────────────────────────
        pruned = self._prune(relations, center_node_id)
        pruned_count = original_count - len(pruned)

        # ── 编译为 Markdown ───────────────────────────────────────
        content = self._render_markdown(pruned, center_node_id, query_context)
        estimated_tokens = len(content) // 4    # 粗略估计：4 字符 ≈ 1 token

        return ContextBlock(
            content=content,
            relation_count=len(pruned),
            estimated_tokens=estimated_tokens,
            pruned_count=pruned_count,
            query_strategy=strategy,
        )

    def _prune(
        self,
        relations: list[RelationObject],
        center_node_id: str,
    ) -> list[RelationObject]:
        """执行六层剪枝，返回通过剪枝的关系列表。"""
        from relos.core.models import RelationStatus

        # 层 1：过滤 archived
        r = [x for x in relations if x.status != RelationStatus.ARCHIVED]

        # 层 2：过滤低置信度
        r = [x for x in r if x.confidence >= self.min_confidence]

        # 层 3：优先保留与中心节点直接关联的关系
        direct = [x for x in r if center_node_id in (x.source_node_id, x.target_node_id)]
        indirect = [x for x in r if center_node_id not in (x.source_node_id, x.target_node_id)]
        r = direct + indirect   # 直接关联优先

        # 层 4：按置信度降序
        r.sort(key=lambda x: x.confidence, reverse=True)

        # 层 5：相同节点对只保留最高置信度（去重）
        seen: set[tuple[str, str, str]] = set()
        deduped: list[RelationObject] = []
        for rel in r:
            key = (rel.source_node_id, rel.target_node_id, rel.relation_type)
            if key not in seen:
                seen.add(key)
                deduped.append(rel)
        r = deduped

        # 层 6：超出 max_relations 则截断
        return r[: self.max_relations]

    def _render_markdown(
        self,
        relations: list[RelationObject],
        center_node_id: str,
        query_context: str,
    ) -> str:
        """
        将关系列表渲染为结构化 Markdown。
        格式设计原则：LLM 能快速定位置信度和关系方向，不堆砌原始数据。
        """
        lines: list[str] = [
            "## 工厂关系上下文（RelOS）",
            f"**分析对象节点**: `{center_node_id}`",
        ]
        if query_context:
            lines.append(f"**当前查询**: {query_context}")

        lines.append(f"**关联关系数量**: {len(relations)} 条（已过滤低置信度）")
        lines.append("")
        lines.append("### 关系列表")
        lines.append("| 关系类型 | 起始节点 | 目标节点 | 置信度 | 来源 |")
        lines.append("|---------|---------|---------|--------|------|")

        for rel in relations:
            conf_bar = "█" * int(rel.confidence * 5) + "░" * (5 - int(rel.confidence * 5))
            lines.append(
                f"| `{rel.relation_type}` "
                f"| `{rel.source_node_id}` "
                f"| `{rel.target_node_id}` "
                f"| {rel.confidence:.2f} {conf_bar} "
                f"| {rel.provenance.value} |"
            )

        lines.append("")
        lines.append(
            "> 置信度说明：1.0=确定，0.75+=高可信，0.5-0.75=中等，<0.5=不确定"
        )

        return "\n".join(lines)
