# RelOS 快速上手指南

> **适合人群**：第一次部署 RelOS 的工程师 / 实施人员
> **预计时间**：30 分钟内完成首次运行
> **系统支持**：Windows 10/11、macOS 12+、Ubuntu 20.04/22.04
> **覆盖能力**：单告警分析 + 复合场景一期（DecisionPackage / 决策级 HITL / ActionBundle）

---

## 目录

- [第一步：安装必要工具](#第一步安装必要工具)
  - [Windows 安装](#windows)
  - [macOS 安装](#macos)
  - [Linux (Ubuntu) 安装](#linux-ubuntu)
- [第二步：下载项目](#第二步下载项目)
- [第三步：配置环境变量](#第三步配置环境变量)
- [第四步：启动服务](#第四步启动服务)
- [第五步：注入测试数据](#第五步注入测试数据)
- [第六步：运行演示](#第六步运行演示)
- [验证成功标志](#验证成功标志)
- [常见问题](#常见问题)

---

## 第一步：安装必要工具

RelOS 运行需要以下两个工具：

| 工具 | 用途 | 最低版本 |
|------|------|---------|
| **Docker Desktop** | 运行数据库（Neo4j）和缓存（Redis） | 24.x |
| **Python** | 运行 API 服务和脚本 | 3.11+ |

---

### Windows

#### 安装 Docker Desktop

1. 打开浏览器，访问：https://www.docker.com/products/docker-desktop/
2. 点击 **"Download for Windows"** 下载安装包
3. 双击安装包，一路点击 **"Next"** 直到完成
4. 安装完成后**重启电脑**
5. 重启后桌面右下角会出现 Docker 小鲸鱼图标 🐳，等待图标变绿色

**验证安装：**
```
打开「命令提示符」(Win+R → 输入 cmd → 回车)
输入：docker --version
看到类似 "Docker version 24.x.x" 即成功
```

#### 安装 Python 3.11

1. 访问：https://www.python.org/downloads/
2. 点击 **"Download Python 3.11.x"**（选择最新 3.11 版本）
3. 运行安装包，**必须勾选** "Add Python to PATH" ✅
4. 点击 **"Install Now"**

**验证安装：**
```
打开命令提示符
输入：python --version
看到类似 "Python 3.11.x" 即成功
```

> ⚠️ **注意**：如果输入 `python` 提示不是内部命令，需要重新安装并确保勾选了 "Add to PATH"

---

### macOS

#### 安装 Docker Desktop

1. 访问：https://www.docker.com/products/docker-desktop/
2. 选择 **"Download for Mac"**（注意选择对应芯片：Apple Silicon 或 Intel）
3. 打开下载的 `.dmg` 文件，将 Docker 拖入 Applications 文件夹
4. 从 Applications 打开 Docker，顶部菜单栏出现 🐳 图标即启动成功

**验证安装：**
```bash
# 打开「终端」(Command+空格 → 搜索"终端")
docker --version
# 看到 "Docker version 24.x.x" 即成功
```

#### 安装 Python 3.11

推荐使用 Homebrew 安装（最简单）：

```bash
# 第一步：安装 Homebrew（如已安装跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 第二步：安装 Python 3.11
brew install python@3.11

# 验证
python3.11 --version
```

或者直接从官网下载：https://www.python.org/downloads/macos/

---

### Linux (Ubuntu)

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# 验证 Docker
docker --version

# 安装 Python 3.11
sudo apt update
sudo apt install -y python3.11 python3.11-pip python3.11-venv

# 验证 Python
python3.11 --version
```

---

## 第二步：下载项目

打开终端（Terminal / 命令提示符），执行：

```bash
# 下载项目代码
git clone <项目仓库地址> RelOS

# 进入项目目录
cd RelOS
```

> 如果没有安装 Git，请先安装：
> - **Windows**：https://git-scm.com/download/win
> - **macOS**：`brew install git`
> - **Linux**：`sudo apt install git`

---

## 第三步：配置环境变量

环境变量告诉系统如何连接各种服务（数据库、AI 接口等）。

### 3.1 复制配置模板

```bash
# Windows (命令提示符)
copy .env.example .env

# macOS / Linux (终端)
cp .env.example .env
```

### 3.2 填写必要配置

用文本编辑器打开 `.env` 文件：
- **Windows**：右键 `.env` → 用记事本打开
- **macOS/Linux**：`nano .env`

**必须填写的内容（只需改这一项）：**

```bash
# 找到这一行，把 sk-ant-... 替换为你的真实 API Key
ANTHROPIC_API_KEY=sk-ant-你的真实密钥
```

> 📍 **如何获取 Anthropic API Key**：
> 1. 访问 https://console.anthropic.com
> 2. 注册/登录账号
> 3. 点击 "API Keys" → "Create Key"
> 4. 复制生成的密钥

如果你只做本地演示，也可以保留：

```bash
ALLOW_LLM_MOCK=true
SHADOW_MODE=true
```

这样即使没有真实执行链路，也能稳定演示文档抽取和复合场景的 Shadow 动作包。

**开发测试时，其他配置保持默认即可。**

---

## 第四步：启动服务

在项目根目录（RelOS 文件夹内）执行：

```bash
docker compose up -d
```

这个命令会自动启动 3 个服务：
- **Neo4j**（图数据库，用来存储关系知识）
- **Redis**（缓存，用于防重复操作）
- **API 服务**（RelOS 核心接口）

**等待约 30-60 秒**，然后检查状态：

```bash
docker compose ps
```

看到所有服务状态为 `healthy` 或 `Up` 即启动成功：

```
NAME         STATUS          PORTS
relos-neo4j  Up (healthy)    0.0.0.0:7474->7474/tcp
relos-redis  Up (healthy)    0.0.0.0:6379->6379/tcp
relos-api    Up              0.0.0.0:8000->8000/tcp
```

**验证 API 服务正常：**

```bash
# 方式一：浏览器访问（推荐新手）
# 打开浏览器，输入：http://localhost:8000/v1/health
# 看到 {"status":"ok","neo4j":"ok"} 即成功

# 方式二：命令行验证
curl http://localhost:8000/v1/health
```

---

## 第五步：注入测试数据

安装 Python 依赖（仅需执行一次）：

```bash
# Windows
pip install -e ".[dev]"

# macOS / Linux（Homebrew Python 常无 pip/python 命令，任选其一）
pip3 install -e ".[dev]"
# 或（推荐，与具体 pip 可执行文件名无关）
python3 -m pip install -e ".[dev]"
```

注入 MVP 与复合场景演示数据：

```bash
# Windows
python scripts/seed_neo4j.py
python scripts/seed_demo_scenarios.py

# macOS / Linux（若提示 command not found: python，请用 python3）
python3 scripts/seed_neo4j.py
python3 scripts/seed_demo_scenarios.py
```

成功后会看到：

```
🌱 开始注入 MVP 测试数据（设备故障分析场景）...
   Neo4j: bolt://localhost:7687
✓  Neo4j 连接成功

📌 注入 7 个节点...
   ✓ Device: 1 号机（注塑机）
   ✓ Device: 2 号机（注塑机）
   ✓ Alarm: 振动超限告警
   ✓ Alarm: 温度过高告警
   ✓ Component: 1 号机主轴轴承
   ✓ Component: 1 号机冷却系统
   ✓ Operator: 张工

🔗 注入 4 条关系...
   ✓ [0.70] alarm-VIB-001 --ALARM__INDICATES__COMPONENT_FAILURE--> component-bearing-M1
   ✓ [0.30] alarm-VIB-001 --ALARM__INDICATES__COMPONENT_FAILURE--> component-coolant-M1
   ✓ [0.85] device-M1 --DEVICE__TRIGGERS__ALARM--> alarm-VIB-001
   ✓ [1.00] component-bearing-M1 --COMPONENT__PART_OF__DEVICE--> device-M1

✅ 种子数据注入完成！
```

如果你要演示两套复杂场景，还应看到 `seed_demo_scenarios.py` 的输出中包含：

```text
复杂场景 → POST /v1/scenarios/composite-disturbance/analyze
```

---

## 第六步：运行演示

```bash
# Windows
python scripts/simulate_alarm.py

# macOS / Linux（无 python 命令时）
python3 scripts/simulate_alarm.py
```

成功后会看到完整的告警分析流程：

```
🚨 模拟设备告警事件...
============================================================
✓  API 状态: ok | Neo4j: ok

📡 发送告警事件：
   设备: device-M1
   告警码: VIB-001
   描述: 主轴振动值超过阈值 12.5mm/s，当前值 18.3mm/s，环境温度 38°C

============================================================
🎯 根因分析结果
============================================================
  推荐根因:    component-bearing-M1 异常（近 6 个月触发 8 次）
  置信度:      70.0%
  决策引擎:    rule_engine
  需人工审核:  否 ✓
  Shadow Mode: 开启（仅记录，未执行）

  推理依据:
  规则引擎基于 1 条指示性关系推断，...

👷 模拟工程师反馈：确认关系 rel-001
  ✓ 置信度更新：→ 0.85（数据飞轮 +1）

✅ MVP 演示完成！
```

---

## 第六步 A：运行复合场景演示（推荐）

在完成 `seed_neo4j.py` 和 `seed_demo_scenarios.py` 后，可以直接调用复合场景一期接口：

```bash
curl -X POST http://localhost:8000/v1/scenarios/composite-disturbance/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "incident-semicon-001",
    "factory_id": "fab-01",
    "scenario_type": "semiconductor_packaging",
    "priority": "high",
    "goal": "保障插单交付并控制设备与物料风险",
    "time_window_start": "2026-03-30T13:47:00+08:00",
    "time_window_end": "2026-03-30T13:51:00+08:00",
    "events": [
      {
        "event_id": "evt-001",
        "event_type": "rush_order",
        "source_system": "ERP",
        "occurred_at": "2026-03-30T13:47:00+08:00",
        "entity_id": "order-BGA-rush-500",
        "entity_type": "CustomerOrder",
        "severity": "high",
        "summary": "紧急插单 500 件 BGA",
        "payload": {}
      },
      {
        "event_id": "evt-002",
        "event_type": "machine_anomaly",
        "source_system": "MES",
        "occurred_at": "2026-03-30T13:48:00+08:00",
        "entity_id": "machine-SMT-02",
        "entity_type": "Machine",
        "severity": "high",
        "summary": "SMT-02 贴装偏移接近工艺上限 80%",
        "payload": {}
      }
    ]
  }'
```

成功后会返回：

- `DecisionPackage`
- `candidate_plans`
- `recommended_actions`
- `requires_human_review`
- `status=pending_review`

接着可验证决策级 HITL：

```bash
curl http://localhost:8000/v1/decisions/pending-review
curl http://localhost:8000/v1/decisions/decision-incident-semicon-001/actions
```

---

## 验证成功标志

完成以上步骤后，你应该能访问：

| 地址 | 内容 | 期望结果 |
|------|------|---------|
| http://localhost:8000/v1/health | API 健康检查 | `{"status":"ok"}` |
| http://localhost:8000/docs | 交互式 API 文档 | Swagger UI 界面 |
| http://localhost:3000 | Web 知识工作台（需执行下方「可选」步骤） | RelOS 运行时/知识训练界面 |
| http://localhost:7474 | Neo4j 图数据库界面 | Neo4j Browser（**不是**业务首页，见 Q8） |
| http://localhost:8000/v1/metrics | 图谱统计数据 | 节点和关系数量 |
| http://localhost:8000/v1/scenarios/composite-disturbance | 复合场景待审摘要 | 能列出已分析的复杂场景 |

> Neo4j Browser 登录：用户名 `neo4j`，密码 `relos_dev`（若在 `.env` 中设置了 `NEO4J_PASSWORD`，则使用该密码）

---

## 可选：启动 Web 知识工作台

> 适合需要图形界面操作 **运行时仪表盘、提示标注、三层知识训练** 的用户（详见 [用户操作手册 — Web 知识工作台](user-manual.md)）。

**前置**：已安装 **Node.js 18+**（与 `frontend/package.json` 一致即可）。

```bash
cd frontend
npm install
npm run dev
```

终端会打印本地访问地址（一般为 **http://localhost:3000**）。根路径会自动进入 **运行时仪表盘**；侧栏可切换到「知识训练」「系统监控」等分组。

若你已注入复合场景 seed，还可以配合以下页面讲述复杂场景：

- `AlarmAnalysis`
- `LineEfficiency`
- `StrategicSim`
- `PromptLabeling`

---

## 常见问题

### Q1：Docker 启动后 API 无法访问

**现象**：`curl http://localhost:8000/v1/health` 报错或超时

**解决步骤**：
```bash
# 查看 API 服务日志
docker compose logs api --tail=30

# 最常见原因：Neo4j 还没启动完，等待 60 秒后重试
# 或者重启 API 服务
docker compose restart api
```

---

### Q2：Windows 上 `docker compose up` 报错

**现象**：`error during connect: ... pipe/docker_engine`

**原因**：Docker Desktop 没有运行

**解决**：在开始菜单找到 **Docker Desktop** 并打开，等待右下角图标变绿色后再试

---

### Q3：`pip install` 报错 "No module named pip"

**Windows 解决**：
```
python -m ensurepip --upgrade
python -m pip install -e ".[dev]"
```

**macOS/Linux 解决**：
```bash
python3.11 -m pip install -e ".[dev]"
```

---

### Q4：seed_neo4j.py 报错 "ServiceUnavailable"

**原因**：Neo4j 尚未完全启动

**解决**：
```bash
# 检查 Neo4j 状态
docker compose ps neo4j

# 若不是 healthy 状态，等待 30 秒后重试
# Neo4j 首次启动需要 1-2 分钟
docker compose logs neo4j --tail=20
```

---

### Q5：ANTHROPIC_API_KEY 相关错误

**现象**：`simulate_alarm.py` 运行时提示 API 认证失败

**解决**：
1. 确认 `.env` 文件中的 `ANTHROPIC_API_KEY` 已正确填写
2. 重启 API 服务让新配置生效：
```bash
docker compose restart api
```

如果你当前只是演示环境，也可以确认：

```bash
ALLOW_LLM_MOCK=true
```

这样文档摄取和样例关系抽取会走 demo mock。

---

### Q6：macOS Apple Silicon（M1/M2/M3）运行问题

若遇到架构兼容问题：
```bash
# 设置 Docker 平台
export DOCKER_DEFAULT_PLATFORM=linux/amd64
docker compose up -d
```

---

### Q7：端口占用错误

**现象**：`bind: address already in use`

**解决**：查找并结束占用端口的进程

```bash
# macOS / Linux
lsof -i :8000 | grep LISTEN
kill -9 <PID>

# Windows (命令提示符)
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

---

### Q8：打开浏览器却是 Neo4j「Connect to instance」，是不是装错了？

**不是。** `http://localhost:7474` 是 **Neo4j Browser**（图数据库管理工具），本来就会要求连接 **Bolt**（如 `localhost:7687`）并输入数据库账号密码。

- **RelOS 业务界面**：请用 **http://localhost:8000/docs**（API）或启动前端后的 **http://localhost:3000**（工作台）。
- **Neo4j** 始终在后台为 API 提供图存储；只有排错或看图谱时才需要打开 7474。

更多说明见 [用户操作手册 §1.1](user-manual.md)。

---

### Q9：复合场景接口返回 404 或空列表

**常见原因**：

1. 没有执行 `scripts/seed_demo_scenarios.py`
2. 当前尚未调用 `POST /v1/scenarios/composite-disturbance/analyze`
3. Neo4j 中没有导入复杂场景节点和关系

**解决**：

```bash
python3 scripts/seed_neo4j.py
python3 scripts/seed_demo_scenarios.py
```

然后重新调用复合场景分析接口。

---

## 下一步

- 📖 阅读 [用户操作手册](user-manual.md) 了解完整功能
- 🔧 阅读 [部署文档](deployment.md) 进行生产环境部署
- 📡 阅读 [API 文档](api.md) 了解所有接口详情
- 🌐 访问 http://localhost:8000/docs 直接在浏览器中测试 API
