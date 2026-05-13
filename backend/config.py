"""
Configuration settings for TrustBrain backend.
Loads from environment variables with sensible defaults.
"""

import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    API_TITLE: str = "TrustBrain Open Source"
    API_VERSION: str = "0.2.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://traciq:traciq_dev@localhost:5432/traciq_db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Qdrant (vector search) — optional
    QDRANT_URL: Optional[str] = os.getenv("QDRANT_URL", None)

    # JWT/Auth
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # LLM API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY", None)

    # Ollama support for local LLM
    OLLAMA_API_URL: str = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
    OLLAMA_ENABLED: bool = os.getenv("OLLAMA_ENABLED", "False").lower() == "true"

    # Embedding model (sentence-transformers)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # Trace settings
    BATCH_SIZE: int = 100
    BATCH_TIMEOUT_MS: int = 5000
    MAX_TRACE_SIZE_MB: int = 10

    # Evaluation settings
    MAX_CONCURRENT_EVALS: int = 5
    EVAL_TIMEOUT_SECONDS: int = 300

    # Online scoring
    ONLINE_SCORING_SAMPLE_RATE: float = 1.0  # Global default sample rate

    # Gateway cache (in-process; Redis-backed in production)
    GATEWAY_CACHE_TTL_SECONDS: int = 3600

    # Feature flags
    TOPICS_ENABLED: bool = os.getenv("TOPICS_ENABLED", "True").lower() == "true"
    SEMANTIC_SEARCH_ENABLED: bool = os.getenv("SEMANTIC_SEARCH_ENABLED", "True").lower() == "true"
    GATEWAY_ENABLED: bool = os.getenv("GATEWAY_ENABLED", "True").lower() == "true"

    # Phase 3: Enterprise
    # SSO / OIDC — app-level defaults (orgs can override via SSOConfig)
    SSO_ENABLED: bool = os.getenv("SSO_ENABLED", "False").lower() == "true"
    SSO_APP_BASE_URL: str = os.getenv("SSO_APP_BASE_URL", "http://localhost:8000")

    # Email — app-level SMTP defaults (orgs can override via EmailConfig)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST", None)
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME", None)
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD", None)
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    SMTP_FROM_ADDRESS: str = os.getenv("SMTP_FROM_ADDRESS", "alerts@trustbrain.local")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "TrustBrain Alerts")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
