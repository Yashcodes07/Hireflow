"""
agents/offer_drafter.py  (Day 5 — updated with MCP integrations)
══════════════════════════════════════════════════════════════════
Now calls:
  - Notes MCP → saves offer drafts to Firestore
  - Email MCP → sends offer letter emails to candidates
  - Task MCP  → creates offer follow-up tasks
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, CandidateDict, DecisionDict, Stage
from agents.prompts import OFFER_DRAFTER_SYSTEM, OFFER_DRAFTER_USER
from mcp.notes_mcp import save_offer_draft
from mcp.email_mcp import send_offer_letter
from mcp.task_manager_mcp import create_offer_tasks

logger = logging.getLogger("offer_drafter")

_client = genai.Client(
    vertexai = True,
    project  = "project-agent-491814",
    location = "us-central1",
)
MODEL = "gemini-2.5-flash"


def _format_candidates_list(candidates: list[CandidateDict]) -> str:
    return "\n".join(
        f"{i}. {c['candidate_name']} <{c['email']}>\n"
        f"   Score: {c.get('score', 'N/A')} | Interview: {c.get('interview_slot', 'Completed')}"
        for i, c in enumerate(candidates, 1)
    )


async def offer_drafter_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    if not shortlisted:
        logger.warning("[OfferDrafter] No shortlisted candidates — skipping")
        return {"stage": Stage.OFFER}

    logger.info("[OfferDrafter] Drafting offers for %d candidates", len(shortlisted))

    # ── Step 1: Ask Gemini to draft offer letters ─────────────────────────────
    prompt = f"{OFFER_DRAFTER_SYSTEM}\n\n" + OFFER_DRAFTER_USER.format(
        job_title       = state["job_title"],
        candidates_list = _format_candidates_list(shortlisted),
        count           = len(shortlisted),
    )

    offers: list[dict] = []
    try:
        response = await _client.aio.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        offers = json.loads(raw)
        if not isinstance(offers, list):
            offers = []
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[OfferDrafter] Gemini parse failed: %s", exc)

    offer_map: dict[str, dict] = {o["email"]: o for o in offers}
    updated_shortlisted: list[CandidateDict] = []
    decisions: list[DecisionDict] = []

    for candidate in shortlisted:
        offer = offer_map.get(candidate["email"], {})
        letter_text = offer.get("letter", "Offer letter pending.")
        salary      = offer.get("salary_inr")
        start_date  = offer.get("start_date", "TBD")

        # ── Step 2: Notes MCP → save offer draft to Firestore ────────────────
        await save_offer_draft(
            job_id         = state["job_id"],
            candidate_email= candidate["email"],
            offer_text     = letter_text,
            salary_inr     = salary,
            start_date     = start_date,
        )

        # ── Step 3: Email MCP → send offer letter email ───────────────────────
        await send_offer_letter(
            candidate_name  = candidate["candidate_name"],
            candidate_email = candidate["email"],
            job_title       = state["job_title"],
            offer_text      = letter_text,
        )

        # ── Step 4: Task MCP → create follow-up task ─────────────────────────
        await create_offer_tasks(
            job_id          = state["job_id"],
            candidate_name  = candidate["candidate_name"],
            candidate_email = candidate["email"],
        )

        updated = CandidateDict(
            candidate_name = candidate["candidate_name"],
            email          = candidate["email"],
            resume_text    = candidate.get("resume_text"),
            resume_b64     = candidate.get("resume_b64"),
            score          = candidate.get("score"),
            rank           = candidate.get("rank"),
            status         = candidate.get("status", "shortlisted"),
            reasoning      = candidate.get("reasoning"),
            interview_slot = candidate.get("interview_slot"),
            offer_letter   = letter_text,
        )
        updated_shortlisted.append(updated)

        decisions.append(DecisionDict(
            agent     = "offer_drafter",
            action    = "Offer drafted + saved + emailed",
            target    = candidate["email"],
            reasoning = f"Salary: ₹{salary} | Start: {start_date} | Notes: saved | Email: sent",
            timestamp = datetime.now(timezone.utc).isoformat(),
        ))

        logger.info(
            "[OfferDrafter] ✅ %s — ₹%s | Email sent | Notes saved",
            candidate["candidate_name"], salary,
        )

    return {
        "stage"      : Stage.OFFER,
        "shortlisted": updated_shortlisted,
        "decisions"  : decisions,
    }