"""
db/connection.py  (Day 4 — updated)
══════════════════════════════════════════════════════════════════
Supports two modes:
  Local dev  → direct URL (ALLOYDB_USE_CONNECTOR=false)
  Cloud Run  → Cloud SQL Python Connector (ALLOYDB_USE_CONNECTOR=true)
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

logger   = logging.getLogger("db")
settings = get_settings()

_engine          : AsyncEngine | None        = None
_session_factory : async_sessionmaker | None = None


# ── Option A: Direct URL (local dev) ─────────────────────────────────────────
def _create_engine_direct() -> AsyncEngine:
    return create_async_engine(
        settings.ALLOYDB_URL,
        pool_size     = 5,
        max_overflow  = 10,
        pool_pre_ping = True,
        echo          = settings.DEBUG,
    )


# ── Option B: Cloud SQL Connector (Cloud Run → AlloyDB) ───────────────────────
from google.cloud.sql.connector import Connector

_connector: Connector | None = None  # global


from google.cloud.sql.connector import Connector

_connector: Connector | None = None  # ✅ global singleton


from google.cloud.sql.connector import Connector
import asyncio

_connector: Connector | None = None


def _create_engine_connector() -> AsyncEngine:
    import asyncpg

    async def getconn():
        global _connector

        loop = asyncio.get_running_loop()  # ✅ get correct loop

        # ✅ bind connector to THIS loop
        if _connector is None:
            _connector = Connector(loop=loop)

        conn = await _connector.connect_async(
            settings.ALLOYDB_INSTANCE,
            "asyncpg",
            user=settings.ALLOYDB_DB_USER,
            password=settings.ALLOYDB_DB_PASS,
            db=settings.ALLOYDB_DB_NAME,
        )
        return conn

    return create_async_engine(
        "postgresql+asyncpg://",
        async_creator=getconn,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )

async def init_db() -> None:
    """Call once at FastAPI startup."""
    global _engine, _session_factory

    if settings.ALLOYDB_USE_CONNECTOR:
        logger.info("DB: using Cloud SQL Connector → %s", settings.ALLOYDB_INSTANCE)
        _engine = _create_engine_connector()
    else:
        logger.info("DB: using direct URL → %s", settings.ALLOYDB_URL[:40])
        _engine = _create_engine_direct()

    _session_factory = async_sessionmaker(
        _engine,
        class_          = AsyncSession,
        expire_on_commit = False,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ DB connected and tables verified")

async def close_db() -> None:
    global _engine, _connector

    if _engine:
        await _engine.dispose()

    if _connector:
        await _connector.close()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise