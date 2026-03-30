"""
relos/config.py
---------------
应用配置，使用 pydantic-settings 从环境变量读取。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 环境
    ENV: str = "development"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "relos_dev"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # 无 API Key 时是否允许从 demo JSON 走 Mock 抽取（上线请设为 false）
    ALLOW_LLM_MOCK: bool = True

    # CORS（生产环境）
    ALLOWED_ORIGINS: list[str] = []

    # 决策引擎：置信度阈值
    RULE_ENGINE_MIN_CONFIDENCE: float = 0.75   # 高于此值走规则引擎，不消耗 LLM Token
    HITL_TRIGGER_CONFIDENCE: float = 0.5       # 低于此值触发 Human-in-the-Loop

    # Shadow Mode（MVP 默认开启：只记录不执行）
    SHADOW_MODE: bool = True

    # LangSmith 追踪（Sprint 3 Week 11）
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "relos-production"
    LANGSMITH_ENABLED: bool = False     # 配置 API Key 后改为 True

    # Temporal.io 工作流（Sprint 3 Week 10）
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "relos-actions"

    # JWT 认证（Sprint 4 Week 15-16）
    JWT_ENABLED: bool = False                          # 生产环境改为 True
    JWT_SECRET_KEY: str = "relos-dev-secret-change-in-prod"
    JWT_ALGORITHM: str = "HS256"

    # 多租户工厂隔离（Sprint 4 Week 15-16）
    DEFAULT_FACTORY_ID: str = "factory-default"        # 单租户模式默认工厂 ID
    MULTI_TENANT_ENABLED: bool = False                 # 生产多租户模式

    # API 限流（Sprint 4 Week 15-16）
    RATE_LIMIT_ENABLED: bool = False                   # 生产环境改为 True
    RATE_LIMIT_REQUESTS: int = 100                     # 每窗口最大请求数
    RATE_LIMIT_WINDOW_SECONDS: int = 60               # 限流窗口（秒）


settings = Settings()
