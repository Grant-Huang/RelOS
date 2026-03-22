# RelOS 架构决策文档

> 此文档供 Claude Code 按需读取（在 CLAUDE.md 中以 `@docs/architecture.md` 引用）。
> 仅在处理跨模块架构或关键技术决策时加载。

## 层间边界规则（不可违反）

| 规则 | 说明 |
|------|------|
| RelOS 不执行操作 | 所有生产操作通过 Action Engine 的 Shadow Mode 记录，MVP 阶段不实际执行 |
| RelOS 不直接对话 | 自然语言接口由 AgentNexus 负责，RelOS 只输出结构化 ContextBlock |
| 关系不删除 | 冲突和过期的关系标注为 `conflicted`/`archived`，保留完整历史 |
| LLM 结果待审 | 任何 LLM 抽取的关系，confidence 上限 0.85，强制进入 `pending_review` |

## 技术选型理由

### 为什么用 Neo4j 而不是向量数据库？
工厂知识的核心价值是**关系**（设备↔故障、工艺↔质量），不是语义相似度。
Neo4j 的图遍历可以精确查询 "设备 M1 通过哪些路径导致告警 A？"，向量数据库做不到。

### 为什么用 LangGraph 而不是 LangChain Expression Language？
LangGraph 支持有状态的循环图（Cyclic Graph），可以表达"推理→人工确认→继续推理"这类
需要中间状态的 HITL 工作流。LCEL 是线性管道，不支持。

### 为什么用 Temporal.io 而不是 Airflow / Celery？
- Airflow：为批处理 DAG 设计，不适合事件驱动的实时告警工作流
- Celery：无内置的故障恢复和状态持久化，Action Engine 需要严格的操作审计
- Temporal：原生支持长时运行 + 失败重试 + 完整操作历史，适合工业场景的合规需求

## 置信度设计哲学

置信度不是"概率"，而是"知识可信程度"的量化表达：
- 不追求绝对精确，0.7 和 0.75 的区别不重要
- 关键是区分：高可信（>0.75）、中等（0.5-0.75）、不确定（<0.5）
- 衰减机制确保"旧知识"不会永久占据高置信度位置

## MVP 后的演进方向

1. **Sprint 2**：Context Engine → LangGraph 接入 → LLM 融合决策真实实现
2. **Sprint 3**：Action Engine 状态机 + Temporal 工作流（Shadow Mode 可选关闭）
3. **Sprint 4**：多租户隔离 + 行业本体模板（汽车/3C）
4. **Sprint 5**：关系图谱可视化编辑器（前端）
