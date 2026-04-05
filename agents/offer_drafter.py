"""
agents/offer_drafter.py  (Vertex AI version — no API key needed)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, CandidateDict, DecisionDict, Stage
from agents.prompts import OFFER_DRAFTER_SYSTEM, OFFER_DRAFTER_USER

logger = logging.getLogger("offer_drafter")

# ── Vertex AI client ──────────────────────────────────────────────────────────
_client = genai.Client(
    vertexai=True,
    project="project-agent-491814",
    location="us-central1",
)
MODEL = "gemini-2.5-flash"


def _format_candidates_list(candidates: list[CandidateDict]) -> str:
    lines = []
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"{i}. {c['candidate_name']} <{c['email']}>\n"
            f"   Score: {c.get('score', 'N/A')} | "
            f"Interview: {c.get('interview_slot', 'Completed')}"
        )
    return "\n".join(lines)


async def offer_drafter_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    if not shortlisted:
        logger.warning("[OfferDrafter] No shortlisted candidates — skipping")
        return {"stage": Stage.OFFER}

    logger.info("[OfferDrafter] Drafting offers for %d candidates", len(shortlisted))

    prompt = f"{OFFER_DRAFTER_SYSTEM}\n\n" + OFFER_DRAFTER_USER.format(
        job_title       = state["job_title"],
        candidates_list = _format_candidates_list(shortlisted),
        count           = len(shortlisted),
    )

    offers: list[dict] = []
    try:
        response = await _client.aio.models.generate_content(
            model    = MODEL,
            contents = prompt,
        )
        raw = response.text.strip()

        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        offers = json.loads(raw)
        if not isinstance(offers, list):
            offers = []

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[OfferDrafter] Failed to parse offers: %s", exc)
        offers = []

    offer_map: dict[str, dict] = {o["email"]: o for o in offers}

    updated_shortlisted: list[CandidateDict] = []
    decisions: list[DecisionDict] = []

    for candidate in shortlisted:
        offer = offer_map.get(candidate["email"], {})

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
            offer_letter   = offer.get("letter", ""),
        )
        updated_shortlisted.append(updated)

        decisions.append(DecisionDict(
            agent     = "offer_drafter",
            action    = "Offer letter drafted",
            target    = candidate["email"],
            reasoning = (
                f"Salary: ₹{offer.get('salary_inr', 'TBD')} | "
                f"Start: {offer.get('start_date', 'TBD')} | "
                f"Valid until: {offer.get('offer_valid_until', 'TBD')}"
            ),
            timestamp = datetime.now(timezone.utc).isoformat(),
        ))

        logger.info(
            "[OfferDrafter] Offer drafted for %s — salary ₹%s",
            candidate["candidate_name"], offer.get("salary_inr", "TBD"),
        )

    return {
        "stage"      : Stage.OFFER,
        "shortlisted": updated_shortlisted,
        "decisions"  : decisions,
    }