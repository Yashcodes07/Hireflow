"""
config.py — Central settings loader using Pydantic BaseSettings.
Reads from environment variables / .env file automatically.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "HR Hiring Gateway"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Auth ─────────────────────────────────────────────
    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Static API key (fallback / service-to-service)
    API_KEY_HEADER: str = "X-API-Key"
    VALID_API_KEYS: list[str] = ["dev-key-replace-me"]

    # ── LangGraph / Agents ───────────────────────────────
    LANGGRAPH_ENDPOINT: str = "http://localhost:8001"   # swap for Cloud Run URL
    AGENT_TIMEOUT_SECONDS: int = 120

    # ── Google Cloud ─────────────────────────────────────
    GCP_PROJECT_ID: str = "my-gcp-project"
    ALLOYDB_URL: str = "postgresql+asyncpg://user:pass@/db?host=/cloudsql/proj:region:instance"

    # ── Observability ────────────────────────────────────
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "hr-hiring-pipeline"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings — import this everywhere."""
    return Settings()
