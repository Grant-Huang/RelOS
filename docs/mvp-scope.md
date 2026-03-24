# MVP 范围文档（持续更新）

## MVP 唯一目标

> 让**一个工程师**在演示结束时说："这个东西有用。"

量化标准：
- 设备故障告警 → 根因推荐，端到端 < 3 秒
- 推荐置信度可见（不是黑盒）
- 工程师确认/否定后，置信度实时更新可见

---

## Sprint 1（第 1–4 周）：核心基础 ✅

### 完成项
- [x] Neo4j 部署 + 图约束创建
- [x] 种子数据注入（`scripts/seed_neo4j.py`）
- [x] RelationEngine 合并/衰减逻辑
- [x] RelationRepository Neo4j CRUD
- [x] FastAPI 基础路由（health + relations + decisions）
- [x] `/pending-review` 端点（HITL 工作队列）
- [x] Shadow Mode 执行状态机（只记录日志）
- [x] 10 个历史告警案例回放验证

### 明确不做（Sprint 1 范围外）
- ❌ LLM 集成（Sprint 2 实现）
- ❌ Action Engine 真实执行（Shadow Mode 只记录日志）
- ❌ 多租户权限管理
- ❌ 生产级监控告警（Prometheus/Grafana）
- ❌ 部署自动化（CI/CD）

---

## Sprint 2（第 5–8 周）：LLM 集成 ✅

### 完成项
- [x] Decision Engine 三路分流（规则 / LLM / HITL）
- [x] Claude API 集成（LangChain-Anthropic）
- [x] 上下文子图抽取（六层剪枝，Token 预算 1500）
- [x] Prompt 编译为结构化 Markdown 表格
- [x] 告警根因分析端点（`POST /v1/decisions/analyze-alarm`）
- [x] LLM 置信度上限 0.85 + 强制 pending_review

---

## Sprint 3（第 9–12 周）：中高层场景 + 文档摄取 ✅

### Week 9–10：中层运营场景
- [x] 专家初始化端点（`POST /v1/expert-init/batch`）
- [x] 图谱统计端点（`GET /v1/metrics/summary`）
- [x] Temporal.io 工作流客户端（Shadow Mode 延伸）
- [x] 本体管理端点（`GET /v1/ontology/`）

### Week 11–12：高层演示场景 + 文档摄取
- [x] **场景 7–12**（`GET/POST /v1/scenarios/*`）
  - S-07 产线效率瓶颈识别
  - S-08 跨部门协同问题定位
  - S-09 异常处理效率分析
  - S-10 企业级风险雷达
  - S-11 资源配置优化建议
  - S-12 战略决策模拟（扩产影响）
- [x] **文档摄取 + AI 标注工作流**（`/v1/documents/*`）
  - 支持 xlsx（CMMS 维修工单 / FMEA / 供应商交期）
  - 支持 docx（8D 质量报告 / 交接班日志）
  - AI 关系抽取（Claude API，无 Key 时 Mock 模式）
  - 人工标注 API（approve / reject / modify）
  - 提交写入 Neo4j 图谱
- [x] 样本文档生成脚本（`scripts/generate_sample_docs.py`）
- [x] 新增 SourceType：`structured_document`、`expert_document`
- [x] 演示数据种子脚本（`scripts/seed_demo_scenarios.py`）
- [x] LangSmith 追踪中间件

### Sprint 3 新增文件清单

```
relos/ingestion/document/
  __init__.py
  models.py          文档摄取数据模型
  excel_parser.py    xlsx 模板解析（CMMS/FMEA/供应商）
  word_parser.py     docx 解析（8D/交接班）
  llm_extractor.py   Claude AI 关系抽取（含 mock 模式）
  entity_resolver.py 实体别名解析（自然语言 → node_id）
  store.py           内存文档记录存储（MVP）

relos/api/v1/
  scenarios.py       场景 7–12 聚合分析端点
  documents.py       文档摄取 API（上传/标注/提交）

scripts/
  seed_demo_scenarios.py  中高层演示种子数据（30节点/33关系）
  generate_sample_docs.py 5个演示样本文档（3xlsx+2docx）

sample_docs/
  cmms_maintenance_orders.xlsx
  fmea_analysis.xlsx
  supplier_delivery_records.xlsx
  8d_quality_report.docx
  shift_handover_log.docx

tests/unit/test_ingestion/test_document/
  test_entity_resolver.py
  test_excel_parser.py
  test_word_parser.py
  test_llm_extractor.py
```

---

## Sprint 4（计划中）：生产化

### 优先事项
- [ ] JWT 认证（Bearer Token）
- [ ] 多租户隔离（tenant_id 注入图谱查询）
- [ ] Prometheus + Grafana 监控
- [ ] 文档存储持久化（Redis 替换内存 Store）
- [ ] CI/CD（GitHub Actions）
- [ ] 实体解析增强（向量相似度替代纯别名）
- [ ] 文档 ingestion pipeline 批处理（>100 页文档）

### 不在 Sprint 4 范围
- ❌ AgentNexus L3 集成（单独项目）
- ❌ Nexus Ops L1 真实设备控制
- ❌ 多语言支持（仅简体中文）
