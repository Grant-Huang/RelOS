# RelOS — Relation Operating System

> **工厂里最有价值的不是数据，而是数据背后的关系。**
> RelOS 是工业场景下的关系操作系统——让工厂知识可计算、可推理、可演化。

---

## 项目定位

RelOS 是 Nexus AI Platform 三层架构的核心中间层（L2），在现有 MES/ERP 之上构建一层**可推理的认知中间层**：

```
┌─────────────────────────────────────┐
│  L3  AgentNexus   自然语言 / 意识层  │  ← 大脑皮层
├─────────────────────────────────────┤
│  L2  RelOS ★     关系记忆 / 推理层  │  ← 海马体（本仓库）
├─────────────────────────────────────┤
│  L1  Nexus Ops    执行 / 感知层      │  ← 脊髓与四肢
└─────────────────────────────────────┘
```

**核心哲学**：关系是工业知识的第一公民。系统的竞争壁垒随关系数据的积累而增长（数据飞轮）。

---

## 功能概览

| 场景 | 传统做法 | RelOS 做法 | 核心价值 |
|------|---------|-----------|---------|
| 设备故障分析 | 老工程师经验 + 人工排查 | 告警 → 关系图推理 → Top 根因 + 置信度 | 维修时间 45 min → 10 min |
| 工单延误预警 | 事后复盘 | 实时感知报警影响工单，提前 30 分钟预警 | 计划达成率提升 15–25% |
| 质量异常溯源 | 8D 报告，平均 3 天 | 工艺-设备-物料-人员关系链自动生成 | 闭环速度提升 3–5 倍 |
| 产能调度优化 | 排产员经验 + APS | OEE-工单-瓶颈关系驱动的 Agent 建议 | 产能利用率提升 8–15% |

---

## 快速开始

### 环境要求
- Python 3.11+
- Docker & Docker Compose
- Anthropic API Key

### 启动开发环境

```bash
# 1. 克隆仓库
git clone https://github.com/Grant-Huang/RelOS.git
cd RelOS

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

# 3. 启动 Neo4j + Redis
docker compose up -d

# 4. 安装依赖
pip install -e ".[dev]"

# 5. 注入 MVP 测试数据（设备故障场景）
python scripts/seed_neo4j.py

# 6. 启动 API 服务
uvicorn relos.main:app --reload --port 8000

# 7. 运行 MVP 演示
python scripts/simulate_alarm.py
```

### API 文档
启动后访问：http://localhost:8000/docs

---

## 项目结构

```
relos/
├── CLAUDE.md                    # Claude Code 项目上下文
├── pyproject.toml               # 依赖 & 工具链
├── docker-compose.yml           # 开发环境
├── Dockerfile                   # 多阶段构建
├── relos/
│   ├── config.py                # 配置（pydantic-settings）
│   ├── main.py                  # FastAPI 入口
│   ├── core/
│   │   ├── models.py            # RelationObject & 枚举
│   │   ├── engine.py            # 合并 / 衰减 / 人工反馈
│   │   └── repository.py        # Neo4j CRUD & 子图提取
│   ├── ingestion/
│   │   └── pipeline.py          # 多源接入 & 标准化
│   ├── context/
│   │   └── compiler.py          # 六层剪枝 & 子图→Prompt
│   ├── decision/
│   │   └── workflow.py          # LangGraph 五节点工作流
│   ├── action/
│   │   └── engine.py            # 八状态机 & Shadow Mode
│   └── api/v1/
│       ├── health.py
│       ├── relations.py
│       └── decisions.py
├── tests/
│   └── unit/                    # 41 个单元测试
├── scripts/
│   ├── seed_neo4j.py            # 注入测试数据
│   └── simulate_alarm.py        # 端到端演示
└── docs/                        # 完整设计文档
```

---

## 开发状态

| Sprint | 状态 | 内容 |
|--------|------|------|
| Sprint 1（Week 1–4） | ✅ 完成 | MVP 核心：关系引擎 + 规则决策 + Shadow Mode API |
| Sprint 2（Week 5–8） | ✅ 完成 | LangGraph 工作流 + Action Engine + Dockerfile |
| Sprint 3（Week 9–12）| 🔲 计划中 | Temporal.io + Excel 导入 + 专家初始化 UI |
| Sprint 4（Week 13–18）| 🔲 计划中 | 多租户 + 行业本体模板 + SaaS 化 |

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [PRD.md](docs/PRD.md) | 产品需求文档 |
| [architecture.md](docs/architecture.md) | 系统架构设计 |
| [data-model.md](docs/data-model.md) | 数据模型设计 |
| [api.md](docs/api.md) | API 接口规范 |
| [ux-flow.md](docs/ux-flow.md) | 用户体验与交互流程 |
| [design-plan.md](docs/design-plan.md) | 设计计划 |
| [dev-plan.md](docs/dev-plan.md) | 开发计划 |
| [test-plan.md](docs/test-plan.md) | 测试计划 |

---

## 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| API | FastAPI + uvicorn | 异步 REST 服务 |
| 图数据库 | Neo4j 5.x | 关系存储与图遍历 |
| 数据校验 | Pydantic v2 | Schema & 约束 |
| LLM 编排 | LangGraph | 决策工作流 |
| LLM | Anthropic Claude | 根因分析推理 |
| 缓存 / 队列 | Redis | 任务队列 |
| 工作流 | Temporal.io | 生产级操作编排（Sprint 3）|
| 日志 | structlog | 结构化日志 |
| 测试 | pytest + pytest-asyncio | 单元 & 集成测试 |

---

## License

MIT © 2026 Nexus AI Platform
