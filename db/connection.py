"""
db/connection.py
══════════════════════════════════════════════════════════════════
Async SQLAlchemy engine + session factory for AlloyDB / PostgreSQL.

Local dev  → set ALLOYDB_URL=postgresql+asyncpg://user:pass@localhost/hrdb
Cloud Run  → use Cloud SQL Python Connector (uncomment section below)
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from config import get_settings
from db.models import Base

logger = logging.getLogger("db")
settings = get_settings()

# ── Engine (created once at startup) ─────────────────────────────────────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


# ── Option A: Direct URL (local dev / Cloud Run with public IP) ───────────────
def _create_engine_from_url() -> AsyncEngine:
    return create_async_engine(
        settings.ALLOYDB_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )


# ── Option B: Cloud SQL Python Connector (recommended for Cloud Run) ──────────
# Uncomment this block and set GCP_PROJECT_ID, instance details in .env
#
# from google.cloud.sql.connector import AsyncConnector
# import asyncpg
#
# async def _getconn(connector: AsyncConnector):
#     return await connector.connect_async(
#         f"{settings.GCP_PROJECT_ID}:us-central1:hr-alloydb",
#         "asyncpg",
#         user="hr_user",
#         password="...",
#         db="hrdb",
#     )
#
# def _create_engine_with_connector() -> AsyncEngine:
#     connector = AsyncConnector()
#     return create_async_engine(
#         "postgresql+asyncpg://",
#         async_creator=lambda: _getconn(connector),
#         pool_size=5,
#         echo=settings.DEBUG,
#     )


async def init_db() -> None:
    """Call once at FastAPI startup to create tables and warm the pool."""
    global _engine, _session_factory

    _engine = _create_engine_from_url()
    # _engine = _create_engine_with_connector()   # Cloud Run

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables if they don't exist (use Alembic in production)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ DB connected and tables verified")


async def close_db() -> None:
    """Call at FastAPI shutdown."""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("DB connection pool closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency-injectable async session context manager."""
    if _session_factory is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise