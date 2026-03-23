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


settings = Settings()
