"""
db/crud.py
══════════════════════════════════════════════════════════════════
All database read/write operations.
Agents import functions from here — never write raw SQL in agent code.
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Candidate, Interview, Offer, AuditLog
from agents.state import CandidateDict, DecisionDict

logger = logging.getLogger("db.crud")


# ── Candidates ────────────────────────────────────────────────────────────────

async def save_candidates(
    session: AsyncSession,
    job_id: str,
    run_id: str,
    candidates: list[CandidateDict],
) -> list[Candidate]:
    """Upsert all candidates for a job run. Returns ORM objects with DB ids."""
    rows: list[Candidate] = []

    for c in candidates:
        # Check if already exists (re-run / idempotency)
        existing = await session.scalar(
            select(Candidate).where(
                Candidate.job_id == job_id,
                Candidate.email  == c["email"],
            )
        )

        if existing:
            # Update
            existing.score     = c.get("score")
            existing.rank      = c.get("rank")
            existing.status    = c.get("status", "pending")
            existing.reasoning = c.get("reasoning")
            existing.updated_at = datetime.now(timezone.utc)
            rows.append(existing)
        else:
            # Insert
            row = Candidate(
                job_id         = job_id,
                run_id         = run_id,
                candidate_name = c["candidate_name"],
                email          = c["email"],
                resume_text    = c.get("resume_text"),
                resume_b64     = c.get("resume_b64"),
                score          = c.get("score"),
                rank           = c.get("rank"),
                status         = c.get("status", "pending"),
                reasoning      = c.get("reasoning"),
            )
            session.add(row)
            rows.append(row)

    await session.flush()   # assigns IDs without committing
    logger.info("Saved %d candidates for job_id=%s", len(rows), job_id)
    return rows


async def get_shortlisted(session: AsyncSession, job_id: str) -> list[Candidate]:
    result = await session.execute(
        select(Candidate)
        .where(Candidate.job_id == job_id, Candidate.status == "shortlisted")
        .order_by(Candidate.rank)
    )
    return list(result.scalars().all())


# ── Audit Log ─────────────────────────────────────────────────────────────────

async def save_audit_decisions(
    session: AsyncSession,
    job_id: str,
    run_id: str,
    decisions: list[DecisionDict],
) -> None:
    """Bulk-insert all agent decisions into audit_log."""
    for d in decisions:
        log = AuditLog(
            job_id    = job_id,
            run_id    = run_id,
            agent     = d["agent"],
            action    = d["action"],
            target    = d["target"],
            reasoning = d["reasoning"],
            timestamp = datetime.fromisoformat(d["timestamp"]),
        )
        session.add(log)

    await session.flush()
    logger.info("Saved %d audit decisions for job_id=%s", len(decisions), job_id)


async def get_audit_trail(session: AsyncSession, job_id: str) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.job_id == job_id)
        .order_by(AuditLog.timestamp)
    )
    return list(result.scalars().all())


# ── Interviews ────────────────────────────────────────────────────────────────

async def save_interview_slot(
    session: AsyncSession,
    candidate_id: str,
    job_id: str,
    slot_start: datetime,
    slot_end: datetime,
    panel: list[str],
    calendar_event_id: str | None = None,
) -> Interview:
    interview = Interview(
        candidate_id      = candidate_id,
        job_id            = job_id,
        slot_start        = slot_start,
        slot_end          = slot_end,
        panel             = panel,
        calendar_event_id = calendar_event_id,
        status            = "scheduled",
    )
    session.add(interview)
    await session.flush()
    return interview


# ── Offers ────────────────────────────────────────────────────────────────────

async def save_offer(
    session: AsyncSession,
    candidate_id: str,
    job_id: str,
    letter_text: str,
    salary: float | None = None,
    letter_url: str | None = None,
) -> Offer:
    offer = Offer(
        candidate_id = candidate_id,
        job_id       = job_id,
        letter_text  = letter_text,
        letter_url   = letter_url,
        salary       = salary,
        status       = "draft",
    )
    session.add(offer)
    await session.flush()
    return offer