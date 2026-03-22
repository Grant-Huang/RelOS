# ────────────────────────────────────────────────────────────────
# RelOS Dockerfile
# 多阶段构建：builder（安装依赖）+ production（精简运行时）
# ────────────────────────────────────────────────────────────────

# ── 阶段 1：依赖构建 ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# 系统依赖（neo4j driver 需要 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖声明，利用 Docker 层缓存
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "pydantic>=2.9.0" \
        "pydantic-settings>=2.6.0" \
        "neo4j>=5.26.0" \
        "langgraph>=0.2.0" \
        "langchain-anthropic>=0.3.0" \
        "redis[hiredis]>=5.2.0" \
        "structlog>=24.4.0" \
        "python-dotenv>=1.0.0" \
        "httpx>=0.28.0" \
        "anthropic>=0.40.0"


# ── 阶段 2：开发模式（热重载，挂载源码）─────────────────────────
FROM python:3.11-slim AS development

WORKDIR /app

# 从 builder 复制安装好的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 额外安装开发工具
RUN pip install --no-cache-dir pytest pytest-asyncio ruff

# 不复制源码（docker-compose 通过 volume 挂载）
EXPOSE 8000
CMD ["uvicorn", "relos.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# ── 阶段 3：生产模式（精简镜像）──────────────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

# 从 builder 复制安装好的包
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制源码（生产环境不挂载）
COPY relos/ ./relos/

# 非 root 用户运行（安全最佳实践）
RUN useradd --no-create-home --shell /bin/false relos
USER relos

EXPOSE 8000

# 生产模式：不使用 --reload，worker 数量由环境变量控制
CMD ["uvicorn", "relos.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--access-log"]
