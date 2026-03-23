"""
tests/unit/test_context/test_compiler.py
-----------------------------------------
Context Engine 编译器单元测试。
"""


from relos.context.compiler import ContextCompiler
from relos.core.models import RelationObject, RelationStatus, SourceType


def make_relation(
    src: str = "device-001",
    tgt: str = "alarm-001",
    confidence: float = 0.8,
    relation_type: str = "DEVICE__TRIGGERS__ALARM",
    status: RelationStatus = RelationStatus.ACTIVE,
) -> RelationObject:
    return RelationObject(
        relation_type=relation_type,
        source_node_id=src,
        source_node_type="Device",
        target_node_id=tgt,
        target_node_type="Alarm",
        confidence=confidence,
        provenance=SourceType.SENSOR_REALTIME,
        status=status,
    )


class TestPruning:

    def setup_method(self) -> None:
        self.compiler = ContextCompiler(max_relations=5)

    def test_archived_relations_pruned(self) -> None:
        """层 1：archived 关系不进入 Prompt"""
        relations = [
            make_relation(confidence=0.9, status=RelationStatus.ACTIVE),
            make_relation(tgt="alarm-002", confidence=0.8, status=RelationStatus.ARCHIVED),
        ]
        block = self.compiler.compile(relations, center_node_id="device-001")
        assert block.relation_count == 1
        assert block.pruned_count == 1

    def test_low_confidence_pruned(self) -> None:
        """层 2：低置信度关系被过滤"""
        compiler = ContextCompiler(min_confidence=0.5)
        relations = [
            make_relation(confidence=0.8),
            make_relation(tgt="alarm-002", confidence=0.2),
        ]
        block = compiler.compile(relations, center_node_id="device-001")
        assert block.relation_count == 1

    def test_max_relations_limit(self) -> None:
        """层 6：超过 max_relations 时截断"""
        compiler = ContextCompiler(max_relations=3)
        relations = [
            make_relation(tgt=f"alarm-{i:03d}", confidence=0.9 - i * 0.05)
            for i in range(10)
        ]
        block = compiler.compile(relations, center_node_id="device-001")
        assert block.relation_count == 3

    def test_dedup_same_node_pair(self) -> None:
        """层 5：相同节点对只保留最高置信度的关系"""
        relations = [
            make_relation(confidence=0.9),
            make_relation(confidence=0.6),   # 同节点对，低置信度应被去重
        ]
        block = self.compiler.compile(relations, center_node_id="device-001")
        assert block.relation_count == 1


class TestLayer3Prioritization:
    """T-02：层 3 直接关联优先（设计文档 §5.2 层 3）"""

    def test_direct_relations_appear_before_indirect(self) -> None:
        """直接关联的关系应排在间接关系之前，即使间接关系置信度更高"""
        center = "device-001"
        # 间接关系：置信度更高，但与 center_node 无直接关联
        indirect = make_relation(src="other-A", tgt="other-B", confidence=0.95)
        # 直接关系：置信度较低，但与 center_node 直接关联
        direct = make_relation(src=center, tgt="alarm-001", confidence=0.70)

        compiler = ContextCompiler(max_relations=5)
        block = compiler.compile([indirect, direct], center_node_id=center)

        # 两条都应出现
        assert block.relation_count == 2
        # 直接关联应先出现（ContextBlock 内容中 center 先于 other-A）
        assert block.content.index(center) < block.content.index("other-A")

    def test_indirect_only_still_included_when_under_max(self) -> None:
        """间接关系在未超出 max_relations 时仍应被保留"""
        center = "device-001"
        indirect = make_relation(src="other-X", tgt="other-Y", confidence=0.8)
        compiler = ContextCompiler(max_relations=5)
        block = compiler.compile([indirect], center_node_id=center)
        assert block.relation_count == 1

    def test_direct_relations_win_when_max_exceeded(self) -> None:
        """max_relations=1 时，直接关系优先于间接关系保留"""
        center = "device-001"
        indirect = make_relation(src="other-A", tgt="other-B", confidence=0.99)
        direct = make_relation(src=center, tgt="alarm-001", confidence=0.50)
        compiler = ContextCompiler(max_relations=1)
        block = compiler.compile([indirect, direct], center_node_id=center)
        assert block.relation_count == 1
        assert center in block.content


class TestMarkdownOutput:

    def test_output_contains_table(self) -> None:
        """编译输出应包含关系表格的 Markdown 表头"""
        compiler = ContextCompiler()
        relations = [make_relation()]
        block = compiler.compile(relations, "device-001", "告警 A001")

        assert "| 关系类型" in block.content
        assert "DEVICE__TRIGGERS__ALARM" in block.content

    def test_empty_relations_returns_valid_block(self) -> None:
        """空关系列表不应报错，应返回有效的 ContextBlock"""
        compiler = ContextCompiler()
        block = compiler.compile([], "device-001")

        assert block.relation_count == 0
        assert block.content is not None
