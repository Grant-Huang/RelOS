# RelOS — Relation Operating System

## 项目定位
RelOS 是工业场景下的**关系操作系统**，在现有 MES/ERP 之上构建一层可推理的认知中间层。
核心哲学：**关系是工业知识的第一公民**，系统的价值随关系数据的积累而增长（数据飞轮）。

## 三层系统分工
| 层 | 组件 | 职责 | 类比 |
|---|---|---|---|
| L3 | AgentNexus | 自然语言 / 意识 | 大脑皮层 |
| L2 | **RelOS** (本仓库) | 关系记忆 / 推理 | 海马体 |
| L1 | Nexus Ops | 执行 / 感知 | 脊髓与四肢 |

> RelOS **只负责**关系的存储、推理与上下文生成；不直接执行操作，不直接对话。

## 架构速览
```
ingestion/     → 多源数据接入，语义标准化，输出 RelationObject
core/          → 关系合并、置信度衰减、冲突管理（Neo4j 图存储）
context/       → 子图抽取、Token 预算剪枝、Prompt 编译
decision/      → 规则引擎 + LLM 融合，Human-in-the-Loop 触发
action/        → 执行状态机，Shadow Mode（MVP 默认只记录日志）
api/           → FastAPI REST 接口，v1 版本
```

## 技术栈
- **Python 3.11+** / **FastAPI** (异步优先)
- **Neo4j 5.x** (图数据库，关系存储)
- **Pydantic v2** (数据校验 + Schema)
- **LangGraph** (LLM 编排，Decision Engine)
- **Redis** (任务队列 / 缓存)
- **Temporal.io** (工作流，Action Engine，替代 Airflow)
- **pytest** + **pytest-asyncio** (测试)

## 常用命令
```bash
# 启动开发环境（Neo4j + Redis）
docker compose up -d

# 启动 API 服务
uvicorn relos.main:app --reload --port 8000

# 运行测试
pytest tests/unit -v
pytest tests/integration -v -m mvp

# 注入测试数据（设备故障场景）
python scripts/seed_neo4j.py
python scripts/simulate_alarm.py

# 代码格式化
ruff check . --fix && ruff format .

# 类型检查
mypy relos/
```

## MVP 范围（第一场景：设备故障分析）
MVP 目标：4 周内可演示，以**设备故障告警→根因推荐**为核心流程。

**不在 MVP 范围内：**
- Action Engine 真实执行（Shadow Mode 只记录日志）
- AgentNexus 集成（Context Engine 输出 Markdown block 即止）
- 多租户 / 权限管理
- 生产级监控告警

## 核心数据模型
所有关系统一为 `RelationObject`，关键字段：
- `confidence: float`（0.0–1.0，LLM 抽取上限 0.85）
- `provenance: SourceType`（来源类型影响 alpha 衰减系数）
- `half_life_days: int`（按关系类型配置，设备告警 90 天）
- `status: Literal["active","pending_review","conflicted","archived"]`

> LLM 抽取的关系**强制**进入 `pending_review`，不自动变为 `active`。

## 代码规范
- 异步优先：所有 I/O 操作使用 `async/await`
- 所有公共函数必须有类型注解
- 每个模块有对应的 `tests/unit/test_<module>/` 目录
- 中文注释说明业务逻辑，英文注释说明技术实现
- 新增 API 端点必须在 `docs/api.md` 中同步更新

## 参考文档（按需读取）
- 整体架构决策 → `@docs/architecture.md`
- API 规范 → `@docs/api.md`
- MVP 详细范围 → `@docs/mvp-scope.md`
- 关系模型 Schema → `@relos/core/models.py`
