# 前端主路由与后端 API 对齐清单

本文档对应「前后端功能对齐与演示数据外置」验收：各页依赖的接口、演示数据来源与说明。

| 路由 | 页面 | 主要 API | 演示 / 配置数据位置 |
|------|------|----------|---------------------|
| `/runtime/dashboard` | RuntimeDashboard | `GET /v1/metrics`、`GET /v1/telemetry/runtime-feed` | 统计来自图谱；事件流来自埋点（空则空状态） |
| `/runtime/automation` | AutomationMonitor | `GET /v1/telemetry/events` | 无静态假行；依赖埋点或空状态 |
| `/runtime/prompt` | PromptLabeling | `GET /v1/relations/pending-review`、`POST .../feedback` | 待审关系由 Neo4j seed 注入 |
| `/knowledge/public` | KnowledgePublic | `POST /v1/knowledge/public/extract`、`POST /v1/relations/` | 抽取走后端（无 Key 时用后端 mock 模板，非前端常量） |
| `/knowledge/documents` | KnowledgeDocuments | `/v1/documents/*` | 上传与抽取由后端完成 |
| `/knowledge/expert` | KnowledgeExpert（Interview + ExpertInit） | `/v1/interview/*`、`/v1/expert-init`、`/v1/documents/*` | 模板枚举可在后续 `GET /v1/config/*` 外置 |
| `/system/kb-status` | KbStatus | `GET /v1/metrics`（含分布字段）、`GET /v1/documents/` | 关系类型 / 来源 / 阶段来自 Neo4j 聚合 |
| `/alarm` | AlarmAnalysis | `/v1/decisions/analyze-alarm/stream` 等 | 快速告警预设见 `relos/demo_data/quick_alarms.json` + `GET /v1/config/quick-alarms` |
| `/line-efficiency` | LineEfficiency | `GET /v1/scenarios/line-efficiency` 等 | `scripts/seed_demo_scenarios.py` |
| `/strategic-sim` | StrategicSim | `POST /v1/scenarios/strategic-simulation`、`GET .../resource-optimization` | 同上；失败不伪造成功响应 |

## Seed 顺序（开发 / 演示）

1. `python scripts/seed_neo4j.py` — MVP 基础节点与关系  
2. `python scripts/seed_demo_scenarios.py` — 场景 7–12 与提示标注待审队列等  

详见 [production_data_cleanup.md](./production_data_cleanup.md) 了解上线前如何跳过 demo 与清理数据。

**说明**：仓库下 `data/demo/` 可与 `relos/demo_data/` 保持内容同步供人工查阅；运行时以后者为准。
