# RelOS 开发计划

**版本**：v1.0  
**日期**：2026 年 3 月  
**总周期**：18 个月（Sprint 1–5）  
**团队规模**：MVP 阶段 4 人，产品化阶段 8–10 人

---

## 1. 开发原则

1. **先深后广**：先把 RelOS（中间层）做扎实，再连接 AgentNexus 和 Nexus Ops
2. **价值优先**：每个 Sprint 必须有可演示、可量化的客户价值
3. **测试先行**：核心算法（合并/衰减/反馈）先写测试，再写实现
4. **接口优先**：模块间接口文档先于实现代码（`docs/api.md` 先更新）
5. **Shadow Mode 保护**：Sprint 3 前 Shadow Mode 必须默认开启，不得跳过

6. **可解释性与可测量性**：所有面向业务的推荐必须提供可追溯解释字段（证据关系 + 阶段贡献），且必须有对应埋点以验证易用性改进效果

---

## 2. 团队结构

### MVP 阶段（Sprint 1–2，4 人）

| 角色 | 职责 | 关键技能 |
|------|------|---------|
| 架构师 / 技术负责人 | RelOS 整体架构、Core Engine、LangGraph 集成 | Python、Neo4j、LangGraph |
| 后端工程师 | Relation Repository、FastAPI 接口、Kafka 集成 | Python、Neo4j Cypher、FastAPI |
| AI 工程师 | Prompt 工程、LLM Pipeline、置信度算法调优 | Prompt Engineering、RAG、LangSmith |
| 领域专家 / PM | 制造场景翻译、客户沟通、专家初始化主持 | MOM/MES 经验、产品设计 |

### 产品化阶段（Sprint 3–4，增加 4 人）

| 新增角色 | 职责 |
|---------|------|
| 前端 / UX 工程师 | HITL 界面、专家初始化向导、图谱可视化 |
| 数据工程师 | Excel 导入 Pipeline、MES API 适配器、数据质量 |
| DevOps 工程师 | K8s 部署、CI/CD、监控告警、私有化方案 |
| 算法工程师 | 关系推理优化、置信度模型改进、Graph+Vector 混合检索 |

---

## 3. Sprint 计划详细

### ✅ Sprint 1：MVP 核心（Week 1–4，已完成）

**目标**：4 周内跑通告警→根因分析完整闭环

| Week | 任务 | 负责人 | 完成状态 |
|------|------|--------|---------|
| Week 1 | RelationObject Schema 设计 + Pydantic 模型 | 架构师 | ✅ |
| Week 1 | RelationEngine 合并/衰减/反馈算法 | 架构师 | ✅ |
| Week 1 | 核心算法单元测试（19 个）| AI 工程师 | ✅ |
| Week 2 | Neo4j RelationRepository（CRUD + 子图）| 后端 | ✅ |
| Week 2 | FastAPI 应用入口 + 生命周期管理 | 后端 | ✅ |
| Week 2 | docker-compose.yml（Neo4j + Redis）| 后端 | ✅ |
| Week 3 | Context Engine 六层剪枝 + Prompt 编译 | AI 工程师 | ✅ |
| Week 3 | 规则引擎决策（无 LLM）| 架构师 | ✅ |
| Week 3 | API 路由（health / relations / decisions）| 后端 | ✅ |
| Week 4 | 种子数据脚本（张工经验录入）| PM | ✅ |
| Week 4 | 端到端演示脚本 | PM | ✅ |
| Week 4 | Shadow Mode 验证（10 个历史案例）| 全员 | ✅ |

**Sprint 1 交付指标**：
- ✅ 41 个单元测试全部通过
- ✅ API 端到端可运行
- ✅ Shadow Mode 默认开启

---

### ✅ Sprint 2：LLM 集成（Week 5–8，已完成）

**目标**：接入 Claude，LangGraph 工作流上线

| Week | 任务 | 负责人 | 完成状态 |
|------|------|--------|---------|
| Week 5 | LangGraph 工作流设计（五节点）| 架构师 | ✅ |
| Week 5 | node_extract_context 实现 | 架构师 | ✅ |
| Week 6 | node_llm_analyze（Claude API 集成）| AI 工程师 | ✅ |
| Week 6 | node_rule_engine / node_hitl / node_no_data | 架构师 | ✅ |
| Week 7 | Action Engine 八状态机 + Pre-flight Check | 后端 | ✅ |
| Week 7 | /v1/decisions/execute-action 端点 | 后端 | ✅ |
| Week 8 | Dockerfile 多阶段构建 | DevOps | ✅ |
| Week 8 | 决策工作流单元测试（22 个）| AI 工程师 | ✅ |

**Sprint 2 交付指标**：
- ✅ 41 个单元测试（Sprint 1）+ 64 个新测试 = 总计 **105 个**单元测试
- ✅ LangGraph 工作流可运行
- ✅ Action Engine Shadow Mode 完整

---

### 🔄 Sprint 3：生产化基础（Week 9–12，进行中）

**目标**：让第一家标杆客户能在真实生产环境使用

#### Week 9：数据导入与专家初始化 ✅

| 任务 | 负责人 | 完成状态 |
|------|--------|----------|
| Excel 批量导入 Pipeline（`scripts/import_excel.py`）| 数据工程师 | ✅ |
| Excel 导入核心引擎（`relos/ingestion/excel_importer.py`）| 数据工程师 | ✅ |
| `/v1/expert-init` API 端点（单条/批量/Excel 上传）| 后端 | ✅ |
| Excel 导入单元测试（15 个）| 数据工程师 | ✅ |
| 字段映射配置（中英文列名 → RelationObject）| PM | ✅ |

#### Week 10：Temporal.io 工作流 ✅

| 任务 | 负责人 | 完成状态 |
|------|--------|----------|
| Temporal.io 客户端集成（`relos/action/temporal_workflows.py`）| 架构师 | ✅ |
| ActionWorkflow 五步工作流定义（Pre-flight → Execute → Rollback）| 架构师 | ✅ |
| Action Engine 生产执行路径（Shadow Mode = false）| 架构师 | ✅ |

#### Week 11：可观测性 ✅

| 任务 | 负责人 | 完成状态 |
|------|--------|----------|
| LangSmith 追踪中间件（`relos/middleware/langsmith_tracing.py`）| AI 工程师 | ✅ |
| `/v1/metrics` 端点（关系图谱统计）| 后端 | ✅ |
| Pre-flight 步骤 5 Redis 去重检查（24h 防重复）| 后端 | ✅ |

#### Week 12：易用性与解释性契约（新增）

| 任务 | 负责人 | 完成状态 |
|------|--------|----------|
| 冻结解释协议：`explanation_summary` / `evidence_relations` / `phase_contributions` / `confidence_trace_id` | PM + 架构师 | ✅ |
| 阶段化字段落库：`knowledge_phase` / `phase_weight`（服务端默认回填）| 后端 | ✅ |
| 无感标注闭环：反馈事件自动标记 `runtime` / `phase_weight=1.00` | 后端 | ✅ |
| 易用性埋点最小规范（见 `docs/test-plan.md §1.4`）| PM + 前端 | 🔄 |
| `_find_existing()` 实现（关系合并语义修复）| 架构师 | ✅ |
| `datetime.utcnow()` 废弃警告修复 | 全员 | ✅ |

#### Week 12：集成测试 + 客户部署 ✅

| 任务 | 负责人 | 完成状态 |
|------|--------|----------|
| 集成测试套件（`tests/integration/test_decisions_api.py`，8 个 IT）| 全员 | ✅ |
| 集成测试套件（`tests/integration/test_relations_api.py`，20 个 IT）| 全员 | ✅ |
| E2E 测试（`tests/e2e/test_alarm_flow.py`，5 大场景 12 个测试）| 全员 | ✅ |
| Action 记录持久化（`relos/action/repository.py`，Neo4j 存储）| 架构师 | ✅ |
| 性能测试基准（`tests/performance/locustfile.py`）| 全员 | ✅ |
| GitHub Actions CI/CD（`.github/workflows/ci.yml`）| DevOps | ✅ |
| 客户环境部署文档 | DevOps | 🔲 |
| 第一家标杆客户上线 Shadow Mode | PM + 全员 | 🔲 |

**Sprint 3 成功标准**：
- [x] Excel 导入 100 条历史告警关系，准确率 > 95%（见 `scripts/import_excel.py --min-accuracy 0.95`）
- [x] 专家初始化 1 小时内录入 30 条核心关系（`POST /v1/expert-init/batch`）
- [ ] 第一家客户完成 Shadow Mode 部署
- [x] LangSmith 中可查看每次 LLM 调用详情（配置 `LANGSMITH_API_KEY` 后自动启用）
- [x] 集成测试套件（40 个 IT）+ E2E 测试（12 个）全部就绪

---

### 🔄 Sprint 4：产品化（Week 13–18，进行中）

#### Week 13–14：前端 UI

| 任务 | 优先级 | 工作量 | 完成状态 |
|------|--------|--------|---------|
| React 项目初始化 + Design System | P0 | 3 天 | 🔲 |
| 告警根因分析卡片组件 | P0 | 2 天 | 🔲 |
| HITL 审批界面 | P0 | 3 天 | 🔲 |
| 专家初始化向导 | P1 | 4 天 | 🔲 |
| Excel 导入界面 | P1 | 2 天 | 🔲 |

#### Week 15–16：多租户与安全 ✅

| 任务 | 优先级 | 工作量 | 完成状态 |
|------|--------|--------|---------|
| JWT 认证中间件（`relos/middleware/jwt_auth.py`）| P0 | 3 天 | ✅ |
| 工厂级数据隔离（`factory_id` 注入 + Neo4j DB 路由配置）| P0 | 3 天 | ✅ |
| API 限流（`relos/middleware/rate_limit.py`，Redis 固定窗口）| P1 | 2 天 | ✅ |
| 操作权限控制（`require_role()` FastAPI 依赖项）| P1 | 2 天 | ✅ |
| GitHub Actions CI/CD（`.github/workflows/ci.yml`）| P0 | 1 天 | ✅ |

#### Week 17–18：行业本体模板 ✅

| 任务 | 优先级 | 工作量 | 完成状态 |
|------|--------|--------|---------|
| 汽车零部件行业本体模板（`relos/ontology/templates.py`）| P1 | 5 天 | ✅ |
| 3C 电子行业本体模板（`relos/ontology/templates.py`）| P2 | 5 天 | ✅ |
| 模板导入端点（`POST /v1/ontology/templates/{industry}/import`）| P1 | 2 天 | ✅ |

**Sprint 4 成功标准**：
- [ ] 2 家付费客户正式使用（非 Shadow Mode）
- [ ] HITL 界面工程师确认率 > 70%
- [x] JWT + 多租户基础设施就绪（`JWT_ENABLED=True` 即可启用）
- [x] 行业本体模板可 dry-run 预览后批量导入

---

### 🔲 Sprint 5：平台化（Month 6–18，长期）

| 方向 | 任务 | 预计时间 |
|------|------|---------|
| 知识图谱可视化 | React + D3.js 图谱编辑器 | 2 个月 |
| AgentNexus 集成 | WebSocket 接口 + Context Block 协议 | 1 个月 |
| 私有化部署包 | K8s Helm Chart + 离线安装包 | 1 个月 |
| MES 适配器库 | 数跑、宝信、工业富联接口适配 | 3 个月 |
| 模型精调 | 基于 5000+ 标注关系微调专属模型 | 2 个月 |

---

## 4. 技术债务管理

| 已知技术债 | 影响 | 计划处理时间 |
|-----------|------|------------|
| Action 操作记录存储在内存（`_action_store`）| 服务重启丢失 | ✅ Sprint 3 Week 12 已修复（`relos/action/repository.py` Neo4j 持久化）|
| `_find_existing()` 未实现 | 关系合并依赖 MERGE 语义 | ✅ Sprint 3 已修复 |
| `datetime.utcnow()` 已废弃 | DeprecationWarning | ✅ Sprint 3 已修复 |
| 无 API 认证 | 安全风险 | ✅ Sprint 4 已修复（JWT 中间件，生产启用 `JWT_ENABLED=True`）|
| Context Engine 未接入 LangSmith | LLM 调用无追踪 | ✅ Sprint 3 已修复 |
| 重复操作检查（Pre-flight 步骤 5）为占位 | 可能重复执行 | ✅ Sprint 3 已修复（Redis 实现）|
| HITL 触发条件 2/3 未实现 | 关键 + 冲突场景跳过人工 | ✅ Sprint 4 已修复 |
| LLM 调用无超时保护 | 超时挂起整个请求 | ✅ Sprint 4 已修复（15s asyncio.wait_for）|

---

## 5. 里程碑与交付物

| 里程碑 | 时间 | 交付物 | 验收标准 |
|--------|------|--------|---------|
| M1：MVP 可演示 | Week 4 | 运行中的 API + 演示视频 | 工程师确认率 > 60% |
| M2：LLM 接入 | Week 8 | LangGraph 工作流 | 41 个测试通过 |
| M3：标杆客户上线 | Week 12 | 生产部署 + Shadow Mode | 1 家客户正在使用 |
| M4：首次付费 | Week 18 | 完整产品 + 合同 | 首年 ARR > 50 万元 |
| M5：规模化 | Month 12 | 3 家付费客户 + 行业模板 | ARR > 200 万元 |

---

## 6. 风险与应对

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| AI 人才招募困难 | 高 | 高 | 核心岗位薪酬对标互联网大厂；考虑外包部分 AI 工程工作 |
| Anthropic API 稳定性 | 中 | 中 | 实现 LLM Provider 接口抽象层，支持切换国内模型（百度/阿里）|
| 客户数据安全顾虑 | 高 | 高 | Sprint 4 优先完成私有化部署方案，不强制要求公有云 |
| 大厂竞争（西门子/SAP）| 中 | 中 | 18–24 个月内快速在 3+ 家客户建立深度绑定和数据飞轮壁垒 |
| 关系图谱冷启动 | 高 | 中 | 专家初始化 + Excel 导入 + 行业本体模板三重方案降低冷启动门槛 |
