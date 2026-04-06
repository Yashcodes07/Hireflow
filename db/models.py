"""
db/models.py
══════════════════════════════════════════════════════════════════
SQLAlchemy ORM models — mirrors your architecture diagram tables:

  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
  │ candidates │  │ interviews │  │   offers   │  │ audit_log  │
  └────────────┘  └────────────┘  └────────────┘  └────────────┘

Run `python -m db.models` to print the CREATE TABLE statements (no DB needed).
Run alembic / db.connection.init_db() to create tables in AlloyDB.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, Integer, Text,
    DateTime, ForeignKey, Enum as SAEnum, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── 1. Candidates ─────────────────────────────────────────────────────────────

class Candidate(Base):
    """
    One row per candidate per job.
    Populated by the Resume Screener agent.
    """
    __tablename__ = "candidates"

    id             = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id         = Column(String(64),  nullable=False, index=True)
    run_id         = Column(String(128), nullable=True)

    # Identity
    candidate_name = Column(String(200), nullable=False)
    email          = Column(String(200), nullable=False, index=True)

    # Resume
    resume_text    = Column(Text,   nullable=True)
    resume_b64     = Column(Text,   nullable=True)  # store PDF as base64

    # Screener output
    score          = Column(Float,  nullable=True)
    rank           = Column(Integer,nullable=True)
    status         = Column(
        SAEnum("pending", "shortlisted", "rejected", "hired", name="candidate_status"),
        default="pending",
        nullable=False,
    )
    reasoning      = Column(Text, nullable=True)

    # Timestamps
    created_at     = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at     = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    interviews     = relationship("Interview", back_populates="candidate", lazy="selectin")
    offer          = relationship("Offer",     back_populates="candidate", uselist=False, lazy="selectin")

    def __repr__(self) -> str:
        return f"<Candidate {self.candidate_name} score={self.score} status={self.status}>"


# ── 2. Interviews ─────────────────────────────────────────────────────────────

class Interview(Base):
    """
    Interview slots — populated by the Scheduler sub-agent (Day 3).
    """
    __tablename__ = "interviews"

    id           = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    candidate_id = Column(UUID(as_uuid=False), ForeignKey("candidates.id"), nullable=False)
    job_id       = Column(String(64), nullable=False, index=True)

    # Slot info
    slot_start   = Column(DateTime(timezone=True), nullable=True)
    slot_end     = Column(DateTime(timezone=True), nullable=True)
    panel        = Column(JSON, nullable=True)           # list of interviewer emails
    calendar_event_id = Column(String(200), nullable=True)  # Google Calendar event ID

    # Feedback (filled post-interview)
    feedback     = Column(Text, nullable=True)
    feedback_score = Column(Float, nullable=True)

    # Status
    status       = Column(
        SAEnum("scheduled", "completed", "cancelled", name="interview_status"),
        default="scheduled",
    )

    created_at   = Column(DateTime(timezone=True), default=_now)
    updated_at   = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    candidate    = relationship("Candidate", back_populates="interviews")


# ── 3. Offers ─────────────────────────────────────────────────────────────────

class Offer(Base):
    """
    Offer letters — populated by the Offer Drafter sub-agent (Day 3).
    """
    __tablename__ = "offers"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    candidate_id    = Column(UUID(as_uuid=False), ForeignKey("candidates.id"), nullable=False)
    job_id          = Column(String(64), nullable=False, index=True)

    # Letter content
    letter_text     = Column(Text,    nullable=True)
    letter_url      = Column(String(500), nullable=True)  # GCS signed URL

    # Compensation
    salary          = Column(Float,   nullable=True)
    currency        = Column(String(10), default="INR")
    start_date      = Column(DateTime(timezone=True), nullable=True)

    # Status
    status          = Column(
        SAEnum("draft", "sent", "accepted", "declined", name="offer_status"),
        default="draft",
    )

    created_at      = Column(DateTime(timezone=True), default=_now)
    updated_at      = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    candidate       = relationship("Candidate", back_populates="offer")


# ── 4. Audit Log ──────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Every agent decision is written here for full pipeline traceability.
    Required for compliance / hiring audit.
    """
    __tablename__ = "audit_log"

    id         = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    job_id     = Column(String(64),  nullable=False, index=True)
    run_id     = Column(String(128), nullable=True)

    agent      = Column(String(64),  nullable=False)   # "screener" | "scheduler" etc.
    action     = Column(String(200), nullable=False)
    target     = Column(String(200), nullable=False)   # candidate email or "all"
    reasoning  = Column(Text,        nullable=True)
    meta_data   = Column(JSON,        nullable=True)    # any extra context

    timestamp  = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)


# ── Dev helper: print DDL ─────────────────────────────────────────────────────
if __name__ == "__main__":
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    print("Tables created:", [t[0] for t in tables])
    print("✅ Schema OK")