"""
pipeline/langgraph_trigger.py  (Day 3 — updated)
Handles richer output: interview slots, offer letters, report, audit decisions.
"""

from __future__ import annotations
import logging

from agents.manager import run_pipeline
from db.connection import get_session
from db import crud
from models import HireRequest, HireResponse, HiringStage, CandidateResult, CandidateStatus

logger = logging.getLogger("pipeline")


async def run_hiring_pipeline(request: HireRequest, request_id: str) -> HireResponse:
    payload = {
        "job_id"         : request.job_id,
        "job_title"      : request.job_title,
        "job_description": request.job_description,
        "required_skills": request.required_skills,
        "resumes"        : [r.model_dump() for r in request.resumes],
        "max_shortlist"  : request.max_shortlist,
        "notify_emails"  : request.notify_emails,
    }

    # ── Run LangGraph pipeline ────────────────────────────────────────────────
    result = await run_pipeline(payload, run_id=request_id)

    # ── Persist to AlloyDB ────────────────────────────────────────────────────
    try:
        async with get_session() as session:
            # Save shortlisted candidates with full data
            await crud.save_candidates(
                session,
                job_id     = request.job_id,
                run_id     = request_id,
                candidates = result.get("shortlisted", []),
            )

            # Save full audit trail from all agents
            decisions = result.get("decisions", [])
            if decisions:
                await crud.save_audit_decisions(
                    session,
                    job_id    = request.job_id,
                    run_id    = request_id,
                    decisions = decisions,
                )

            logger.info("✅ Persisted full pipeline results for job_id=%s", request.job_id)

    except Exception as exc:
        logger.warning("DB persist failed (non-fatal): %s", exc)

    # ── Build FastAPI response ─────────────────────────────────────────────────
    shortlisted_out = [
        CandidateResult(
            candidate_name   = c["candidate_name"],
            email            = c["email"],
            score            = c.get("score", 0.0),
            status           = CandidateStatus(c.get("status", "pending")),
            interview_slot   = c.get("interview_slot"),
            offer_letter_url = c.get("offer_letter"),
            notes            = c.get("reasoning"),
        )
        for c in result.get("shortlisted", [])
    ]

    return HireResponse(
        job_id          = result["job_id"],
        stage           = HiringStage(result.get("stage", "screening")),
        shortlisted     = shortlisted_out,
        rejected_count  = result.get("rejected_count", 0),
        report_url      = result.get("report_url"),
        audit_log_id    = result.get("audit_log_id"),
        pipeline_run_id = request_id,
    )