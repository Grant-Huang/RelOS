"""
relos/ingestion/document/entity_resolver.py
---------------------------------------------
实体别名解析器：将文档中的自然语言实体名映射到图谱中的规范 node_id。

制造企业最大的数据质量问题之一：同一个设备有 5 种写法。
本模块维护别名字典，供解析和 LLM 抽取阶段使用。

别名字典来源（优先级从高到低）：
  1. expert-init 阶段工程师录入（可通过 API 动态添加）
  2. seed_neo4j.py 内置的演示数据别名
  3. 自动模糊匹配（仅作为 fallback，需要置信度惩罚）

使用方式：
  resolver = EntityResolver()
  node_id, node_type = resolver.resolve("1号焊接机")
  # → ("machine-M3", "Machine")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResolvedEntity:
    node_id: str
    node_type: str
    canonical_name: str
    matched_alias: str
    exact_match: bool = True   # False 表示模糊匹配，置信度应有惩罚


# ─── 演示数据的内置别名字典（与 seed_neo4j.py 保持同步）─────────────────

# Machine 节点
_MACHINE_ALIASES: dict[str, tuple[str, str]] = {
    # alias → (node_id, canonical_name)
    "machine-m3":   ("machine-M3", "焊接机 M3"),
    "m3":           ("machine-M3", "焊接机 M3"),
    "焊机3":        ("machine-M3", "焊接机 M3"),
    "3号焊机":      ("machine-M3", "焊接机 M3"),
    "1号焊接机":    ("machine-M3", "焊接机 M3"),
    "wj-03":        ("machine-M3", "焊接机 M3"),
    "machine-m4":   ("machine-M4", "冲压机 M4"),
    "m4":           ("machine-M4", "冲压机 M4"),
    "冲压机1":      ("machine-M4", "冲压机 M4"),
    "1号冲压机":    ("machine-M4", "冲压机 M4"),
    "cj-01":        ("machine-M4", "冲压机 M4"),
    "machine-m5":   ("machine-M5", "装配机器人 M5"),
    "m5":           ("machine-M5", "装配机器人 M5"),
    "装配机器人":   ("machine-M5", "装配机器人 M5"),
    "装配机1":      ("machine-M5", "装配机器人 M5"),
    "robot-01":     ("machine-M5", "装配机器人 M5"),
    # MVP 设备（来自 seed_neo4j.py）
    "device-m1":    ("device-M1", "焊接机 M1"),
    "m1":           ("device-M1", "焊接机 M1"),
    "焊接机m1":     ("device-M1", "焊接机 M1"),
}

# Line 节点
_LINE_ALIASES: dict[str, tuple[str, str]] = {
    "line-l1":  ("line-L1", "冲压线 L1"),
    "l1":       ("line-L1", "冲压线 L1"),
    "冲压线":   ("line-L1", "冲压线 L1"),
    "line-l2":  ("line-L2", "焊接线 L2"),
    "l2":       ("line-L2", "焊接线 L2"),
    "焊接线":   ("line-L2", "焊接线 L2"),
    "line-l3":  ("line-L3", "装配线 L3"),
    "l3":       ("line-L3", "装配线 L3"),
    "装配线":   ("line-L3", "装配线 L3"),
}

# Supplier 节点
_SUPPLIER_ALIASES: dict[str, tuple[str, str]] = {
    "supplier-a":   ("supplier-A", "华盛钢材"),
    "华盛钢材":     ("supplier-A", "华盛钢材"),
    "华盛":         ("supplier-A", "华盛钢材"),
    "a供应商":      ("supplier-A", "华盛钢材"),
    "supplier-b":   ("supplier-B", "东方塑料"),
    "东方塑料":     ("supplier-B", "东方塑料"),
    "b供应商":      ("supplier-B", "东方塑料"),
}

# Material 节点
_MATERIAL_ALIASES: dict[str, tuple[str, str]] = {
    "material-steel-q235":  ("material-steel-q235", "Q235 钢板"),
    "q235":                 ("material-steel-q235", "Q235 钢板"),
    "q235钢板":             ("material-steel-q235", "Q235 钢板"),
    "优质钢板":             ("material-steel-q235", "Q235 钢板"),
    "material-abs-plastic": ("material-abs-plastic", "ABS 塑料颗粒"),
    "abs":                  ("material-abs-plastic", "ABS 塑料颗粒"),
    "abs塑料":              ("material-abs-plastic", "ABS 塑料颗粒"),
}

# Component 节点
_COMPONENT_ALIASES: dict[str, tuple[str, str]] = {
    "component-bearing-m3":  ("component-bearing-M3", "轴承（M3）"),
    "轴承":                  ("component-bearing-M3", "轴承（M3）"),
    "m3轴承":                ("component-bearing-M3", "轴承（M3）"),
    "component-cooling-m3":  ("component-cooling-M3", "冷却系统（M3）"),
    "冷却系统":              ("component-cooling-M3", "冷却系统（M3）"),
    "散热系统":              ("component-cooling-M3", "冷却系统（M3）"),
}

# FailureMode 虚拟节点（文档摄取中新建）
_FAILURE_MODE_ALIASES: dict[str, tuple[str, str]] = {
    "轴承磨损":   ("fm-bearing-wear",   "轴承磨损"),
    "轴承故障":   ("fm-bearing-wear",   "轴承磨损"),
    "过热":       ("fm-overheat",       "过热故障"),
    "焊接过热":   ("fm-overheat",       "过热故障"),
    "电气故障":   ("fm-electrical",     "电气故障"),
    "断路":       ("fm-electrical",     "电气故障"),
    "冷却失效":   ("fm-cooling-fail",   "冷却失效"),
    "冷却不足":   ("fm-cooling-fail",   "冷却失效"),
}

# Operator 节点
_OPERATOR_ALIASES: dict[str, tuple[str, str]] = {
    "operator-li":    ("operator-LiGong",  "李工"),
    "李工":           ("operator-LiGong",  "李工"),
    "李师傅":         ("operator-LiGong",  "李工"),
    "operator-wang":  ("operator-WangGong","王工"),
    "王工":           ("operator-WangGong","王工"),
    "王师傅":         ("operator-WangGong","王工"),
}

# ─── 全局别名表（按 node_type 索引）────────────────────────────────────

_ALIAS_TABLES: dict[str, dict[str, tuple[str, str]]] = {
    "Machine":     _MACHINE_ALIASES,
    "Line":        _LINE_ALIASES,
    "Supplier":    _SUPPLIER_ALIASES,
    "Material":    _MATERIAL_ALIASES,
    "Component":   _COMPONENT_ALIASES,
    "FailureMode": _FAILURE_MODE_ALIASES,
    "Operator":    _OPERATOR_ALIASES,
}

# 全局扁平查找表（alias_normalized → (node_id, node_type, canonical_name)）
# 注意：key 必须在这里就 normalize，查询时的 key 也会 normalize，才能匹配。
def _normalize(text: str) -> str:
    """标准化别名用于查找：小写 + 去空格 + 去连字符/下划线。"""
    return re.sub(r"[\s\-_]", "", text.lower())


# 构建 normalized key → (node_id, node_type, canonical_name) 的扁平表
_FLAT_LOOKUP: dict[str, tuple[str, str, str]] = {}
for _ntype, _table in _ALIAS_TABLES.items():
    for _alias, (_nid, _cname) in _table.items():
        _FLAT_LOOKUP[_normalize(_alias)] = (_nid, _ntype, _cname)

# 按 type 的 normalized 快查表
_TYPED_LOOKUP: dict[str, dict[str, tuple[str, str]]] = {
    ntype: {_normalize(alias): val for alias, val in table.items()}
    for ntype, table in _ALIAS_TABLES.items()
}


class EntityResolver:
    """
    实体别名解析器。

    resolve() 方法支持两种模式：
      - 指定 node_type：只在该类型别名表中查找
      - 不指定 node_type：在全局扁平表中查找（可能有歧义）

    未找到时，返回"新建节点"的规范 ID（小写 + 下划线）。
    """

    def __init__(self) -> None:
        # 支持运行时动态添加别名（expert-init 场景）
        self._extra_aliases: dict[str, tuple[str, str, str]] = {}

    def add_alias(
        self,
        alias: str,
        node_id: str,
        node_type: str,
        canonical_name: str,
    ) -> None:
        """动态添加别名（不持久化，重启后丢失）。"""
        self._extra_aliases[_normalize(alias)] = (node_id, node_type, canonical_name)

    def resolve(
        self,
        name: str,
        node_type: Optional[str] = None,
    ) -> ResolvedEntity:
        """
        解析名称到规范实体。

        查找顺序：
        1. 动态别名（expert-init 录入）
        2. 内置别名（演示数据）
        3. 返回"新节点"占位 ID（snake_case）
        """
        key = _normalize(name)

        # 1. 动态别名优先
        if key in self._extra_aliases:
            nid, ntype, cname = self._extra_aliases[key]
            return ResolvedEntity(
                node_id=nid, node_type=ntype, canonical_name=cname,
                matched_alias=name, exact_match=True,
            )

        # 2. 指定类型时，在该类型的 normalized 表中查找
        if node_type and node_type in _TYPED_LOOKUP:
            table = _TYPED_LOOKUP[node_type]
            if key in table:
                nid, cname = table[key]
                return ResolvedEntity(
                    node_id=nid, node_type=node_type, canonical_name=cname,
                    matched_alias=name, exact_match=True,
                )

        # 3. 全局扁平表查找
        if key in _FLAT_LOOKUP:
            nid, ntype, cname = _FLAT_LOOKUP[key]
            return ResolvedEntity(
                node_id=nid,
                node_type=node_type or ntype,
                canonical_name=cname,
                matched_alias=name,
                exact_match=True,
            )

        # 4. 未找到 → 生成新节点占位 ID
        generated_id = (node_type or "node").lower() + "-" + re.sub(r"\s+", "_", name.strip())
        return ResolvedEntity(
            node_id=generated_id,
            node_type=node_type or "Unknown",
            canonical_name=name,
            matched_alias=name,
            exact_match=False,
        )

    def resolve_pair(
        self,
        src_name: str,
        src_type: str,
        tgt_name: str,
        tgt_type: str,
    ) -> tuple[ResolvedEntity, ResolvedEntity]:
        """同时解析源和目标实体。"""
        return (
            self.resolve(src_name, src_type),
            self.resolve(tgt_name, tgt_type),
        )
