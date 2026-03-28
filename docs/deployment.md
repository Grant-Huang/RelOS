# RelOS 部署文档

> 适用版本：Sprint 4+（含 Web 工作台说明）
> 更新日期：2026-03-28

---

## 目录

1. [快速开始（开发环境）](#1-快速开始开发环境)
2. [生产部署（单机私有化）](#2-生产部署单机私有化)
3. [生产部署（多机 / K8s）](#3-生产部署多机--k8s)
4. [环境变量完整参考](#4-环境变量完整参考)
5. [生产安全检查清单](#5-生产安全检查清单)
6. [CI/CD 流水线](#6-cicd-流水线)
7. [健康检查与监控](#7-健康检查与监控)
8. [故障排查](#8-故障排查)

---

## 1. 快速开始（开发环境）

### 前置条件

| 依赖 | 最低版本 | 用途 |
|------|---------|------|
| Docker Desktop | 24.x | 容器运行时 |
| Docker Compose | v2.x | 多服务编排 |
| Python | 3.11+ | 本地开发 / 测试 |
| Git | 2.x | 代码版本管理 |

### 启动步骤

```bash
# 1. 克隆仓库
git clone <repo-url> RelOS && cd RelOS

# 2. 复制环境变量模板
cp .env.example .env
# 编辑 .env，至少填写 ANTHROPIC_API_KEY

# 3. 启动所有服务（Neo4j + Redis + API）
docker compose up -d

# 4. 验证服务状态
curl http://localhost:8000/v1/health
# 预期：{"status":"healthy","neo4j":"connected","version":"..."}

# 5. 注入测试数据（可选）
python scripts/seed_neo4j.py
python scripts/simulate_alarm.py
```

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| RelOS API | `8000` | REST API 主入口；**业务联调与 Swagger 默认入口** |
| Web 工作台（可选） | `3000`（默认） | 仓库 `frontend/` 通过 `npm run dev` 启动，**非** Docker Compose 内置服务 |
| Neo4j Browser | `7474` | 图数据库 **Neo4j 自带** Web UI；用于 Cypher 与图数据排查，**易与「产品首页」混淆**，见下文说明 |
| Neo4j Bolt | `7687` | Bolt 协议（驱动 / Browser 连接） |
| Redis | `6379` | 缓存 / 限流队列 |

**勿混淆**：

- 向最终用户或车间推广时，**首页**应为 **API 对接的应用** 或 **自托管的 `frontend` 构建产物**，而不是 `7474`。
- `7474` 登录框中的用户名/密码是 **Neo4j 数据库账号**（Compose 默认常为 `neo4j` / `relos_dev`，以 `NEO4J_AUTH` 为准），与 RelOS 业务用户体系无关。

### 常用开发命令

```bash
# API 文档（Swagger UI）
open http://localhost:8000/docs

# 运行单元测试
pytest tests/unit -v

# 运行集成测试（需要 Neo4j 和 Redis 运行中）
pytest tests/integration -v -m mvp

# 代码格式化
ruff check . --fix && ruff format .

# 类型检查
mypy relos/ --ignore-missing-imports

# 停止所有服务
docker compose down

# 清除所有数据重新开始
docker compose down -v
```

---

## 2. 生产部署（单机私有化）

> **适用场景**：中小型工厂，单台服务器（8 核 16G 内存），不依赖公有云。

### 2.1 服务器准备

```bash
# 安装 Docker（Ubuntu 22.04 示例）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker

# 验证
docker --version  # Docker version 24.x+
docker compose version  # Docker Compose version v2.x+
```

### 2.2 配置生产环境变量

```bash
# 创建并填写生产配置
cp .env.example .env.prod
nano .env.prod
```

**必填项**（见[第 4 节](#4-环境变量完整参考)完整列表）：

```bash
ENV=production
NEO4J_PASSWORD=<强密码，至少16位，含大小写字母+数字+符号>
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET_KEY=<随机生成的64字符密钥>
JWT_ENABLED=true
SHADOW_MODE=false                    # 关闭 Shadow Mode 后才会真实执行操作
ALLOWED_ORIGINS=https://your-domain.com
RATE_LIMIT_ENABLED=true
```

**生成安全密钥**：

```bash
# 生成 JWT 密钥
python -c "import secrets; print(secrets.token_hex(32))"
```

### 2.3 启动生产服务

```bash
# 使用生产 Compose 文件
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f api

# 验证健康状态
curl http://localhost:8000/v1/health
```

### 2.4 反向代理（Nginx，推荐）

```nginx
# /etc/nginx/sites-available/relos
server {
    listen 443 ssl;
    server_name relos.your-factory.com;

    ssl_certificate     /etc/ssl/certs/relos.crt;
    ssl_certificate_key /etc/ssl/private/relos.key;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # LLM 分析最长 30s，需要较大超时
        proxy_read_timeout  30s;
        proxy_send_timeout  30s;
    }
}
```

### 2.5 数据备份

```bash
# Neo4j 数据备份（每日 cron）
docker exec relos-neo4j neo4j-admin database dump neo4j \
  --to-path=/backup/neo4j-$(date +%Y%m%d).dump

# 将备份文件同步到远程存储
rsync -az /backup/ backup-server:/relos-backups/
```

---

## 3. 生产部署（多机 / K8s）

> **适用场景**：大型工厂或 SaaS 多租户，需要高可用和横向扩展。

### 3.1 部署架构

```
                    ┌──────────────────┐
                    │   Load Balancer  │
                    │  (Nginx / AWS ALB)│
                    └────────┬─────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
       RelOS API         RelOS API        RelOS API
       (Pod 1)           (Pod 2)          (Pod 3)
            │                │                │
            └────────────────┼────────────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                                 ▼
    Neo4j Causal Cluster               Redis Sentinel
    (3 节点，1主2从)                  (3 节点，高可用)
```

### 3.2 Docker 镜像构建

```bash
# 构建生产镜像（不含开发工具）
docker build \
  --target production \
  --tag relos:v0.4.0 \
  --build-arg BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --build-arg GIT_COMMIT=$(git rev-parse HEAD) \
  .

# 推送到私有镜像仓库
docker tag relos:v0.4.0 registry.your-factory.com/relos:v0.4.0
docker push registry.your-factory.com/relos:v0.4.0
```

### 3.3 K8s 部署要点

```yaml
# 关键 Deployment 配置
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: relos-api
          image: registry.your-factory.com/relos:v0.4.0
          env:
            - name: NEO4J_URI
              value: "bolt://neo4j-cluster:7687"  # Causal Cluster bolt+routing://
            - name: REDIS_URL
              value: "redis://redis-sentinel:6379/0"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          readinessProbe:
            httpGet:
              path: /v1/health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /v1/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
```

### 3.4 Neo4j 生产配置

```bash
# Neo4j Causal Cluster 关键配置
NEO4J_causal__clustering_minimum__core__cluster__size__at__formation=3
NEO4J_causal__clustering_initial__discovery__members=neo4j-1:5000,neo4j-2:5000,neo4j-3:5000
NEO4J_dbms_memory_heap_initial__size=2G
NEO4J_dbms_memory_heap_max__size=4G
NEO4J_dbms_memory_pagecache_size=2G
```

### 3.5 多租户隔离

多租户模式下，每个工厂使用独立的 Neo4j 数据库（非共用 schema）：

```bash
# 配置多租户
MULTI_TENANT_ENABLED=true
DEFAULT_FACTORY_ID=factory-default

# JWT Token 中包含 factory_id，API 自动路由到对应数据库：
# factory-001 → Neo4j database: factory_001
# factory-002 → Neo4j database: factory_002
```

---

## 4. 环境变量完整参考

### 4.1 基础设施

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `ENV` | `development` | ✅ | 运行环境，`development` 或 `production` |
| `NEO4J_URI` | `bolt://localhost:7687` | ✅ | Neo4j Bolt 连接地址 |
| `NEO4J_USER` | `neo4j` | ✅ | Neo4j 用户名 |
| `NEO4J_PASSWORD` | `relos_dev` | ✅ | **生产环境必须更换** |
| `REDIS_URL` | `redis://localhost:6379/0` | ✅ | Redis 连接 URL |

### 4.2 LLM / Anthropic

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `ANTHROPIC_API_KEY` | `""` | ✅ | 从 [console.anthropic.com](https://console.anthropic.com) 获取 |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | — | LLM 模型 ID |

### 4.3 决策引擎阈值

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RULE_ENGINE_MIN_CONFIDENCE` | `0.75` | ≥ 此值走规则引擎（零 Token 消耗） |
| `HITL_TRIGGER_CONFIDENCE` | `0.50` | < 此值触发 Human-in-the-Loop |

### 4.4 Shadow Mode

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SHADOW_MODE` | `true` | `true`=只记录日志不执行；**生产就绪后设为 `false`** |

### 4.5 安全（JWT / CORS / 限流）

| 变量 | 默认值 | 必填（生产）| 说明 |
|------|--------|-----------|------|
| `JWT_ENABLED` | `false` | ✅ | 生产环境必须设为 `true` |
| `JWT_SECRET_KEY` | `relos-dev-secret-...` | ✅ | **生产必须替换为随机64字符密钥** |
| `JWT_ALGORITHM` | `HS256` | — | JWT 签名算法 |
| `ALLOWED_ORIGINS` | `[]` | ✅ | CORS 白名单，如 `["https://your-domain.com"]` |
| `RATE_LIMIT_ENABLED` | `false` | — | 启用 API 限流 |
| `RATE_LIMIT_REQUESTS` | `100` | — | 每窗口最大请求数 |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | — | 限流窗口（秒） |

### 4.6 多租户

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MULTI_TENANT_ENABLED` | `false` | 启用工厂级数据隔离 |
| `DEFAULT_FACTORY_ID` | `factory-default` | 单租户模式下的默认工厂 ID |

### 4.7 可观测性（可选）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LANGSMITH_ENABLED` | `false` | 启用 LLM 调用追踪 |
| `LANGSMITH_API_KEY` | `""` | LangSmith API Key |
| `LANGSMITH_PROJECT` | `relos-production` | 追踪项目名称 |

### 4.8 Temporal.io（可选，Action Engine 生产执行）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `TEMPORAL_HOST` | `localhost:7233` | Temporal Server 地址 |
| `TEMPORAL_NAMESPACE` | `default` | Temporal 命名空间 |
| `TEMPORAL_TASK_QUEUE` | `relos-actions` | Action 任务队列名 |

---

## 5. 生产安全检查清单

部署前逐项确认：

```
基础安全
[ ] NEO4J_PASSWORD 已更换为强密码（≥ 16 位）
[ ] JWT_ENABLED=true
[ ] JWT_SECRET_KEY 已替换为随机密钥（python -c "import secrets; print(secrets.token_hex(32))"）
[ ] ALLOWED_ORIGINS 已配置实际域名（不使用 *）
[ ] ANTHROPIC_API_KEY 通过 .env 或 K8s Secret 注入（不在代码中出现）

业务安全
[ ] SHADOW_MODE 已确认是否需要关闭（false = 真实执行操作）
[ ] JWT Token 有效期已评估（默认 24h，工业场景建议 8h）
[ ] 确认 HITL_TRIGGER_CONFIDENCE 阈值符合当前场景安全要求

网络安全
[ ] Neo4j 端口 7474/7687 不对外暴露（仅内网访问）
[ ] Redis 端口 6379 不对外暴露
[ ] API 服务通过 Nginx/ALB 对外，启用 HTTPS
[ ] 防火墙仅开放 443（HTTPS）端口

生产就绪
[ ] RATE_LIMIT_ENABLED=true
[ ] 数据备份脚本已配置（建议每日 cron）
[ ] 日志收集已配置（structlog → ELK / 云日志）
[ ] 监控告警已配置（/v1/health 心跳检测）
```

---

## 6. CI/CD 流水线

`.github/workflows/ci.yml` 包含 4 个 Job，按 PR / push 触发：

| Job | 触发条件 | 说明 |
|-----|---------|------|
| `Lint & Type Check` | 所有 push / PR | ruff + mypy 代码质量检查 |
| `Unit Tests` | 所有 push / PR | 105 个单元测试，覆盖率 ≥ 70% |
| `Integration Tests` | 仅 main 分支 push | 需要 Neo4j + Redis 服务，运行 MVP 标记测试 |
| `Docker Build` | 所有 push / PR | 验证 Dockerfile 可正常构建 |

### 发布流程

```bash
# 1. 从 main 创建 release 分支
git checkout -b release/v0.4.0 main

# 2. 更新版本号（pyproject.toml）
# version = "0.4.0"

# 3. 构建并标记镜像
docker build --target production -t relos:v0.4.0 .

# 4. 推送镜像
docker push registry.your-factory.com/relos:v0.4.0

# 5. 在目标服务器拉取并重启
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --no-deps api
```

---

## 7. 健康检查与监控

### 7.1 健康检查端点

```bash
GET /v1/health

# 响应示例（正常）
{
  "status": "healthy",
  "neo4j": "connected",
  "version": "0.4.0",
  "shadow_mode": false,
  "timestamp": "2026-03-23T10:00:00Z"
}

# Neo4j 断开时
{
  "status": "degraded",
  "neo4j": "disconnected",
  ...
}
```

### 7.2 关键指标监控

```bash
GET /v1/metrics

# 关注指标
{
  "total_relations": 347,
  "avg_confidence": 0.783,       # 正常：> 0.6
  "active_ratio": 0.833,         # 正常：> 0.7，过低说明 pending 积压
  "pending_review_count": 42,    # 告警：> 50 需关注 HITL 队列
  "conflicted_count": 8,         # 告警：> 20 需人工干预
  "review_backlog": 42           # 与 pending_review_count 相同
}
```

### 7.3 建议告警规则

| 指标 | 告警阈值 | 处理建议 |
|------|---------|---------|
| `/v1/health` 连续失败 | ≥ 3 次（30s） | 重启 API 服务，检查 Neo4j 连接 |
| `pending_review_count` | > 50 | 通知值班工程师处理 HITL 队列 |
| `conflicted_count` | > 30 | 可能有数据质量问题，排查数据源 |
| `avg_confidence` | < 0.5 | 知识库质量下降，补录专家关系 |
| API P95 响应时间 | > 8s | 检查 LLM 调用，考虑调整阈值减少 LLM 路由 |

---

## 8. 故障排查

### 8.1 API 无法启动

```bash
# 查看启动日志
docker compose logs api --tail=50

# 常见原因 1：Neo4j 未就绪
# 日志：ServiceUnavailable: Unable to connect to database
# 解法：等待 Neo4j 启动完成（healthcheck 需要 30-60s）
docker compose ps  # 查看 neo4j 是否 healthy

# 常见原因 2：ANTHROPIC_API_KEY 未配置
# 日志：anthropic.AuthenticationError
# 解法：在 .env 中填写 ANTHROPIC_API_KEY
```

### 8.2 决策引擎超时

```bash
# 症状：POST /v1/decisions/analyze-alarm 返回 500，日志有 asyncio.TimeoutError
# 原因：LLM 响应超过 15s 硬超时

# 解法 1：检查 Anthropic API 连通性
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'

# 解法 2：调高 HITL 阈值减少 LLM 调用
HITL_TRIGGER_CONFIDENCE=0.6   # 更多走 HITL 而非 LLM
```

### 8.3 Neo4j 连接问题

```bash
# 检查 Neo4j 状态
docker compose exec neo4j cypher-shell -u neo4j -p $NEO4J_PASSWORD "RETURN 1"

# APOC 插件未加载（子图提取失败）
# 日志：ProcedureNotFound: apoc.path.subgraphAll
# 解法：确保 docker-compose.yml 中有 NEO4J_PLUGINS: '["apoc"]'
docker compose restart neo4j

# 约束创建失败（第一次启动）
# 日志：ConstraintValidationFailed
# 这是幂等操作，重启 API 即可
docker compose restart api
```

### 8.4 用户反馈「首页是 Neo4j 登录」

**现象**：浏览器打开某地址后出现 **Connect to instance**、要求输入 Neo4j 密码。

**原因**：访问的是 **`http://<host>:7474`（Neo4j Browser）**，属于数据库管理界面，并非 RelOS 业务 UI。

**处理**：

1. 向用户说明正确入口：**API** `http://<host>:8000/docs` 或 **Web 工作台**（`frontend` 构建/`npm run dev` 的站点，常见开发端口 `3000`）。
2. 若仅需验证部署：`curl http://<host>:8000/v1/health`。
3. 若确实要登录 Neo4j Browser：使用 `NEO4J_AUTH` 配置的用户名与密码（默认参考 `docker-compose.yml` 中 `neo4j/${NEO4J_PASSWORD:-relos_dev}`）。

### 8.5 Redis 限流误触发

```bash
# 症状：所有请求返回 429 Too Many Requests
# 检查限流 Key
docker compose exec redis redis-cli keys "relos:rate:*"

# 手动清除限流计数（紧急解除）
docker compose exec redis redis-cli del "relos:rate:factory-001:$(date +%s | cut -c1-9)"

# 永久方案：提高限流阈值
RATE_LIMIT_REQUESTS=500
```

### 8.6 Excel 导入失败

```bash
# 症状：POST /v1/expert-init/upload-excel 返回 422
# 常见原因：列名不匹配

# 支持的列名（中英文均可）：
# 英文：source_node_id, source_node_type, target_node_id, target_node_type,
#       relation_type, confidence, provenance, provenance_detail, extracted_by, half_life_days
# 中文：源节点ID, 源节点类型, 目标节点ID, 目标节点类型,
#       关系类型, 置信度, 来源类型, 来源详情, 录入人, 半衰期(天)

# 使用 dry_run=true 验证不写入
curl -X POST "http://localhost:8000/v1/expert-init/upload-excel?dry_run=true" \
  -F "file=@your-data.xlsx"
```

---

## 附录：版本历史

| 版本 | Sprint | 主要变更 |
|------|--------|---------|
| v0.1.0 | Sprint 1 | 核心关系引擎、Neo4j 存储、FastAPI 基础路由 |
| v0.2.0 | Sprint 2 | 决策工作流（LangGraph）、Action Engine（Shadow Mode）|
| v0.3.0 | Sprint 3 | Excel 导入、专家初始化 API、LangSmith、Temporal 脚手架 |
| v0.4.0 | Sprint 4 | JWT 认证、多租户隔离、API 限流、CI/CD、行业本体模板 |
