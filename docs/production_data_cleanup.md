# 上线前数据与演示清理

本文档说明如何在生产环境**不携带演示图谱与演示 JSON**，并保留可维护的清理步骤。

## 1. 演示数据位置

| 类型 | 位置 | 用途 |
|------|------|------|
| 告警快速选择 / 公开知识示例段落 | [relos/demo_data/](../relos/demo_data/) | `GET /v1/config/quick-alarms`、`GET /v1/config/text-samples` |
| LLM 关系抽取 mock（无 `ANTHROPIC_API_KEY` 或 LLM 调用失败降级） | `relos/demo_data/llm_extract_mock_relations.json`（可选镜像 `data/demo/`） | `llm_extractor` 按模板类型读取；生产可**删除或清空**以禁用演示级抽取草稿，或**仅配置 API Key** 走真实模型 |
| 复合场景决策包样例 | `relos/demo_data/composite_decision_packages.json`（可选镜像 `data/demo/`） | Agent 对接样例、前端/文档稳定演示 |
| 仓库根目录 `data/demo/` | 可选副本，与 `relos/demo_data` 内容可手动同步 | 文档引用 |
| Neo4j 场景与待审关系 | 由脚本写入 | `scripts/seed_neo4j.py`、`scripts/seed_demo_scenarios.py` |

生产若**不需要**演示快捷入口：可改为返回空列表（删除或清空 `relos/demo_data` 下对应 JSON），或通过配置开关关闭 `app_config` 路由（需改代码）。

### LLM Mock 与上线严格模式

| 变量 | 开发典型值 | 生产建议 |
|------|------------|----------|
| `ALLOW_LLM_MOCK` | `true`（可无 Key 走 `llm_extract_mock_relations.json`） | `false`（`docker-compose.prod.yml` 已默认 `false`） |
| `ANTHROPIC_API_KEY` | 可选 | **必填**（关闭 Mock 后无 Key 会拒绝抽取） |
| `SHADOW_MODE` | `true`（适合演示 `ActionBundle`） | 按真实执行要求决定；未打通外部执行层前建议仍保持 `true` |

关闭 Mock 后若仍无 Key 或 LLM 调用失败，接口会返回 **503**，并在结构化日志中记录事件 `llm_extraction_blocked` / `llm_no_mock_fallback` / `public_knowledge_extract_unavailable`（含 `reason` 字段）。文档异步任务会将错误写入 `DocumentRecord.error_message`。

## 2. 禁止在生产执行的脚本

- `python scripts/seed_demo_scenarios.py` — 注入场景 7–12 及大量演示关系（含 `pending_review` 提示队列）。
- 任何仅用于演示复合场景的 `curl` / 批量导入脚本，也不应对真实生产库执行。
- 若生产库仅需空壳：只跑必要的 schema/约束，不跑上述 seed。

## 3. Neo4j 清理思路

- **独立 database**：开发用 `neo4j`，生产用单独库名，从源头隔离。
- **或按标签/前缀删除**：若演示关系 ID 均以 `demo-rel-` 开头，可执行 Cypher（**先在备份库验证**）：

```cypher
MATCH ()-[r]->()
WHERE r.id STARTS WITH 'demo-rel-'
DELETE r
```

节点清理需根据实际模型设计 `MATCH (n) WHERE n.id STARTS WITH 'demo-' DETACH DELETE n` 等，**务必与团队数据规范一致后再执行**。

若已运行过复合场景一期并需要清理决策包 / 动作包节点，可额外执行（先备份）：

```cypher
MATCH (d:DecisionPackage)
WHERE d.incident_id STARTS WITH 'incident-'
DELETE d;

MATCH (b:ActionBundle)
WHERE b.bundle_id STARTS WITH 'bundle-decision-incident-'
DELETE b;

MATCH (r:DecisionReviewRecord)
WHERE r.decision_id STARTS WITH 'decision-incident-'
DELETE r;
```

## 4. 埋点与内存状态

- `GET /v1/telemetry/events` / `runtime-feed` 依赖进程内内存，重启即空；生产应替换为持久化消息队列或分析库（见 `telemetry.py` 注释）。

## 5. 前端行为

- 各页已**不再使用页面内大块 mock 顶替 API 成功**；无数据时展示空状态与 seed 指引。
- 确保生产环境 `Vite`/`nginx` 将 `/v1` 代理到真实 API，避免前端仅看到网络错误。

## 6. 复合场景一期的额外清理建议

如果生产环境不希望暴露复杂场景演示能力，还应额外确认：

- `docs/` 中的演示说明可保留，但不应把演示接口暴露给真实业务入口
- 不保留以下演示数据：
  - `relos/demo_data/composite_decision_packages.json`
  - `data/demo/composite_decision_packages.json`
- 不在生产库中保留通过 `incident-*`、`decision-*`、`bundle-decision-*` 生成的演示决策包与动作包
- 不向生产前端默认展示复杂场景 quick alarms 或 demo 文本样例

如果环境目标是“客户演示 / 沙箱 / 培训”，则可保留上述内容，但应同时满足：

- `SHADOW_MODE=true`
- `ALLOW_LLM_MOCK=true` 或配置真实 `ANTHROPIC_API_KEY`
- 不连接真实 MES/MRO/WMS 写回链路
