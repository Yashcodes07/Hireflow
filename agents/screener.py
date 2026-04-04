"""
agents/screener.py
══════════════════════════════════════════════════════════════════
Resume Screener Sub-Agent

Responsibilities:
  1. Loop through every candidate in HiringState.candidates
  2. Call Gemini 2.5 Flash with resume + JD
  3. Parse JSON score response
  4. Mark candidates shortlisted / rejected
  5. Sort by score, apply max_shortlist cap
  6. Append decisions to audit trail
  7. Save results to AlloyDB (candidates table)

Returns updated HiringState slice.
"""

from __future__ import annotations
import json
import logging
import base64
from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from agents.state import HiringState, CandidateDict, DecisionDict, Stage
from agents.prompts import SCREENER_SYSTEM, SCREENER_USER

logger = logging.getLogger("screener")


# ── LLM singleton (re-used across calls in the same process) ─────────────────
def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,        # low = more consistent scoring
        max_output_tokens=512,
    )


# ── Resume extraction ─────────────────────────────────────────────────────────

def _extract_resume_text(candidate: CandidateDict) -> str:
    """Return plain text from whichever resume field is present."""
    if candidate.get("resume_text"):
        return candidate["resume_text"]
    if candidate.get("resume_b64"):
        try:
            return base64.b64decode(candidate["resume_b64"]).decode("utf-8", errors="replace")
        except Exception:
            return "[Could not decode resume PDF — base64 parse error]"
    return "[No resume content provided]"


# ── Single candidate scorer ───────────────────────────────────────────────────

async def _score_candidate(
    llm: ChatGoogleGenerativeAI,
    candidate: CandidateDict,
    state: HiringState,
) -> CandidateDict:
    """Call Gemini once per candidate. Returns updated CandidateDict."""
    resume_content = _extract_resume_text(candidate)

    prompt = SCREENER_USER.format(
        job_title       = state["job_title"],
        job_description = state["job_description"],
        required_skills = ", ".join(state.get("required_skills", [])),
        candidate_name  = candidate["candidate_name"],
        resume_content  = resume_content,
    )

    messages = [
        SystemMessage(content=SCREENER_SYSTEM),
        HumanMessage(content=prompt),
    ]

    score     = 0.0
    status    = "rejected"
    reasoning = ""

    try:
        response  = await llm.ainvoke(messages)
        raw       = response.content.strip()

        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result    = json.loads(raw)
        score     = float(result.get("score", 0))
        status    = result.get("status", "rejected")
        reasoning = result.get("reasoning", "")

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Score parse failed for %s: %s", candidate["email"], exc)
        score, status, reasoning = 0.0, "rejected", f"Scoring error: {exc}"

    # ── Build updated candidate — explicitly set all fields, no ** spread ──
    updated = CandidateDict(
        candidate_name = candidate["candidate_name"],
        email          = candidate["email"],
        resume_text    = candidate.get("resume_text"),
        resume_b64     = candidate.get("resume_b64"),
        status         = status,      # ← only set once now
        score          = round(score, 2),
        reasoning      = reasoning,
    )
    return updated

# ── Main node function (called by LangGraph) ──────────────────────────────────

async def screener_node(state: HiringState) -> dict:
    """
    LangGraph node.
    Input:  full HiringState
    Output: partial dict with updated keys (LangGraph merges automatically)
    """
    logger.info("[Screener] Starting — %d candidates", len(state["candidates"]))

    llm        = _get_llm()
    candidates = state["candidates"]
    max_sl     = state.get("max_shortlist", 5)

    # ── Score all candidates (sequential to respect API rate limits) ──────────
    scored: list[CandidateDict] = []
    for candidate in candidates:
        updated = await _score_candidate(llm, candidate, state)
        scored.append(updated)
        logger.debug(
            "[Screener] %s → score=%.1f status=%s",
            updated["candidate_name"], updated["score"], updated["status"],
        )

    # ── Sort by score descending ──────────────────────────────────────────────
    scored.sort(key=lambda c: c.get("score", 0), reverse=True)

    # ── Apply max_shortlist cap ───────────────────────────────────────────────
    #    Even if Gemini said "shortlisted", enforce the cap
    shortlisted_count = 0
    final: list[CandidateDict] = []
    for i, c in enumerate(scored):
        rank = i + 1
        if c.get("status") == "shortlisted" and shortlisted_count < max_sl:
            c = CandidateDict(**{**c, "rank": rank, "status": "shortlisted"})
            shortlisted_count += 1
        else:
            c = CandidateDict(**{**c, "rank": rank, "status": "rejected"})
        final.append(c)

    shortlisted = [c for c in final if c["status"] == "shortlisted"]
    rejected    = [c for c in final if c["status"] == "rejected"]

    logger.info(
        "[Screener] Done — shortlisted=%d rejected=%d",
        len(shortlisted), len(rejected),
    )

    # ── Build audit decisions ─────────────────────────────────────────────────
    decisions: list[DecisionDict] = [
        DecisionDict(
            agent     = "screener",
            action    = f"Scored and {'shortlisted' if c['status'] == 'shortlisted' else 'rejected'}",
            target    = c["email"],
            reasoning = c.get("reasoning", ""),
            timestamp = datetime.now(timezone.utc).isoformat(),
        )
        for c in final
    ]

    return {
        "stage"          : Stage.SCREENING,
        "candidates"     : final,
        "shortlisted"    : shortlisted,
        "rejected_count" : len(rejected),
        "decisions"      : decisions,   # LangGraph appends via operator.add
    }