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


settings = Settings()
