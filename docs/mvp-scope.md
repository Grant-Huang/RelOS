# MVP 范围文档（Sprint 1：第 1–4 周）

## MVP 唯一目标

> 让**一个工程师**在演示结束时说："这个东西有用。"

量化标准：
- 设备故障告警 → 根因推荐，端到端 < 3 秒
- 推荐置信度可见（不是黑盒）
- 工程师确认/否定后，置信度实时更新可见

## Sprint 1 四周计划

### 第 1 周：数据基础
- [ ] Neo4j 部署 + 图约束创建
- [ ] 种子数据注入（`scripts/seed_neo4j.py`）
- [ ] 专家初始化：与客户工程师 1 小时会议，录入初始关系

### 第 2 周：核心引擎
- [ ] RelationEngine 合并/衰减逻辑（已完成）
- [ ] RelationRepository Neo4j CRUD（已完成）
- [ ] FastAPI 基础路由（health + relations + decisions）

### 第 3 周：HITL 界面
- [ ] `/pending-review` 端点（已完成）
- [ ] 简单 React 审批界面（仅需 confirm/reject 两个按钮）
- [ ] 置信度反馈闭环可演示

### 第 4 周：Shadow Mode 验证
- [ ] 10 个历史告警案例回放
- [ ] 每个案例的推荐结果 vs 工程师实际处理对比
- [ ] 数据整理为演示 PPT（给客户管理层）

## 明确不做（MVP 范围外）

- ❌ LLM 集成（Sprint 2 实现）
- ❌ Action Engine 真实执行（Shadow Mode 只记录日志）
- ❌ 多租户权限管理
- ❌ 与现有 MES/ERP 的 API 集成（Excel 导入即可）
- ❌ 生产级监控告警（Prometheus/Grafana）
- ❌ 部署自动化（CI/CD）
