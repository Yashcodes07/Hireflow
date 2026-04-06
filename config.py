"""
config.py  (Day 4 — updated)
Adds LangSmith, AlloyDB Cloud SQL Connector, and Cloud Run settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str = "HR Hiring Gateway"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Auth ──────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    API_KEY_HEADER: str = "X-API-Key"
    VALID_API_KEYS: list[str] = ["dev-key-replace-me"]

    # ── Google Cloud ──────────────────────────────────────────────────────────
    GCP_PROJECT_ID: str = "project-agent-491814"
    GCP_REGION: str = "us-central1"

    # ── Vertex AI (Day 3) ─────────────────────────────────────────────────────
    VERTEX_MODEL: str = "gemini-2.5-flash"

    # ── AlloyDB (Day 4) ───────────────────────────────────────────────────────
    # Local dev: postgresql+asyncpg://user:pass@localhost:5432/hrdb
    # Cloud Run: uses Cloud SQL connector (set ALLOYDB_USE_CONNECTOR=true)
    ALLOYDB_URL: str = "postgresql+asyncpg://hruser:hrpassword@localhost:5432/hrdb"
    ALLOYDB_USE_CONNECTOR: bool = False          # set True on Cloud Run
    ALLOYDB_INSTANCE: str = ""                   # e.g. project:region:instance
    ALLOYDB_DB_NAME: str = "hrdb"
    ALLOYDB_DB_USER: str = "hruser"
    ALLOYDB_DB_PASS: str = "hrpassword"
   

    # ── LangSmith (Day 4) ─────────────────────────────────────────────────────
    LANGSMITH_TRACING: bool = False              # set True to enable
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "hr-hiring-pipeline"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    langgraph_endpoint: str | None = None
    # ── Agent timeout ─────────────────────────────────────────────────────────
    AGENT_TIMEOUT_SECONDS: int = 180
    GOOGLE_API_KEY: str | None = None
    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()