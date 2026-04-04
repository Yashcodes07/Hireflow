"""
agents/state.py
══════════════════════════════════════════════════════════════════
HiringState — the single TypedDict that flows through every node
in the LangGraph graph.

All sub-agents READ from and WRITE to this object.
LangGraph merges updates automatically between nodes.
"""

from __future__ import annotations
from typing import Annotated, Any
from typing_extensions import TypedDict
import operator
from enum import Enum


# ── Stage enum (mirrors models.py HiringStage) ───────────────────────────────
class Stage(str, Enum):
    INIT         = "init"
    SCREENING    = "screening"
    INTERVIEWING = "interviewing"
    OFFER        = "offer"
    REPORT       = "report"
    DONE         = "done"
    ERROR        = "error"


# ── Candidate dict (lightweight — full record lives in AlloyDB) ───────────────
class CandidateDict(TypedDict, total=False):
    candidate_name : str
    email          : str
    resume_text    : str | None
    resume_b64     : str | None
    score          : float          # 0-100, set by screener
    rank           : int            # 1-based, set by screener
    status         : str            # pending / shortlisted / rejected
    reasoning      : str            # LLM explanation for the score
    interview_slot : str | None     # set by scheduler
    offer_letter   : str | None     # set by offer drafter
    db_id          : str | None     # AlloyDB row id once saved


# ── Decision audit trail ──────────────────────────────────────────────────────
class DecisionDict(TypedDict):
    agent       : str   # "screener" | "scheduler" | "offer_drafter" | "reporter"
    action      : str   # human-readable description
    target      : str   # candidate email or "all"
    reasoning   : str
    timestamp   : str   # ISO-8601


# ── The shared state ──────────────────────────────────────────────────────────
class HiringState(TypedDict, total=False):
    # ── Input (set once by gateway) ──────────────────────────────────────────
    job_id          : str
    job_title       : str
    job_description : str
    required_skills : list[str]
    max_shortlist   : int
    notify_emails   : list[str]
    run_id          : str                   # LangSmith trace / request ID

    # ── Pipeline state ────────────────────────────────────────────────────────
    stage           : Stage
    candidates      : list[CandidateDict]   # mutated by each sub-agent

    # ── Decisions log (append-only — LangGraph merges with operator.add) ─────
    decisions       : Annotated[list[DecisionDict], operator.add]

    # ── Outputs ───────────────────────────────────────────────────────────────
    shortlisted     : list[CandidateDict]
    rejected_count  : int
    report_url      : str | None
    audit_log_id    : str | None
    error           : str | None            # set on any agent failure


# ── Helper: build initial state from a gateway HireRequest ───────────────────
def build_initial_state(payload: dict[str, Any], run_id: str) -> HiringState:
    return HiringState(
        job_id          = payload["job_id"],
        job_title       = payload["job_title"],
        job_description = payload["job_description"],
        required_skills = payload.get("required_skills", []),
        max_shortlist   = payload.get("max_shortlist", 5),
        notify_emails   = payload.get("notify_emails", []),
        run_id          = run_id,
        stage           = Stage.INIT,
        candidates      = [
            CandidateDict(
                candidate_name = r["candidate_name"],
                email          = r["email"],
                resume_text    = r.get("resume_text"),
                resume_b64     = r.get("resume_b64"),
                status         = "pending",
            )
            for r in payload.get("resumes", [])
        ],
        decisions       = [],
        shortlisted     = [],
        rejected_count  = 0,
        report_url      = None,
        audit_log_id    = None,
        error           = None,
    )