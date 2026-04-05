"""
agents/screener.py  (Vertex AI version — no API key needed)
"""

from __future__ import annotations
import json
import asyncio
import logging
import base64
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, CandidateDict, DecisionDict, Stage
from agents.prompts import SCREENER_SYSTEM, SCREENER_USER

logger = logging.getLogger("screener")

# ── Vertex AI client ──────────────────────────────────────────────────────────
_client = genai.Client(
    vertexai=True,
    project="project-agent-491814",
    location="us-central1",
)
MODEL = "gemini-2.5-flash"


def _extract_resume_text(candidate: CandidateDict) -> str:
    if candidate.get("resume_text"):
        return candidate["resume_text"]
    if candidate.get("resume_b64"):
        try:
            return base64.b64decode(candidate["resume_b64"]).decode("utf-8", errors="replace")
        except Exception:
            return "[Could not decode resume]"
    return "[No resume content provided]"


async def _score_candidate(candidate: CandidateDict, state: HiringState) -> CandidateDict:
    resume_content = _extract_resume_text(candidate)

    prompt = f"{SCREENER_SYSTEM}\n\n" + SCREENER_USER.format(
        job_title       = state["job_title"],
        job_description = state["job_description"],
        required_skills = ", ".join(state.get("required_skills", [])),
        candidate_name  = candidate["candidate_name"],
        resume_content  = resume_content,
    )

    score     = 0.0
    status    = "rejected"
    reasoning = ""

    try:
        response = await _client.aio.models.generate_content(
            model    = MODEL,
            contents = prompt,
        )
        raw = response.text.strip()

        # Extract JSON from anywhere in response
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        result    = json.loads(raw)
        score     = float(result.get("score", 0))
        status    = result.get("status", "rejected")
        reasoning = result.get("reasoning", "")

    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Score parse failed for %s: %s", candidate["email"], exc)
        score, status, reasoning = 0.0, "rejected", f"Scoring error: {exc}"

    return CandidateDict(
        candidate_name = candidate["candidate_name"],
        email          = candidate["email"],
        resume_text    = candidate.get("resume_text"),
        resume_b64     = candidate.get("resume_b64"),
        status         = status,
        score          = round(score, 2),
        reasoning      = reasoning,
    )


async def screener_node(state: HiringState) -> dict:
    logger.info("[Screener] Starting — %d candidates", len(state["candidates"]))

    candidates = state["candidates"]
    max_sl     = state.get("max_shortlist", 5)

    scored: list[CandidateDict] = []
    for candidate in candidates:
        updated = await _score_candidate(candidate, state)
        scored.append(updated)
        logger.info(
            "[Screener] %s → score=%.1f status=%s",
            updated["candidate_name"], updated.get("score", 0), updated.get("status"),
        )

    scored.sort(key=lambda c: c.get("score", 0), reverse=True)

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

    logger.info("[Screener] Done — shortlisted=%d rejected=%d", len(shortlisted), len(rejected))

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
        "stage"         : Stage.SCREENING,
        "candidates"    : final,
        "shortlisted"   : shortlisted,
        "rejected_count": len(rejected),
        "decisions"     : decisions,
    }