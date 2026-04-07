"""
agents/scheduler.py  (Day 5 — updated with MCP integrations)
══════════════════════════════════════════════════════════════════
Now calls:
  - Calendar MCP → creates Google Calendar events
  - Email MCP    → sends interview invite emails
  - Task MCP     → creates feedback collection tasks
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, CandidateDict, DecisionDict, Stage
from agents.prompts import SCHEDULER_SYSTEM, SCHEDULER_USER
from mcp.calendar_mcp import create_interview_event
from mcp.email_mcp import send_interview_invite
from mcp.task_manager_mcp import create_interview_tasks

logger = logging.getLogger("scheduler")

_client = genai.Client(
    vertexai = True,
    project  = "project-agent-491814",
    location = "us-central1",
)
MODEL = "gemini-2.5-flash"


def _format_candidates_list(candidates: list[CandidateDict]) -> str:
    return "\n".join(
        f"{i}. {c['candidate_name']} <{c['email']}> — Score: {c.get('score', 'N/A')}"
        for i, c in enumerate(candidates, 1)
    )


async def scheduler_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    if not shortlisted:
        logger.warning("[Scheduler] No shortlisted candidates — skipping")
        return {"stage": Stage.INTERVIEWING}

    logger.info("[Scheduler] Scheduling interviews for %d candidates", len(shortlisted))

    # ── Step 1: Ask Gemini for interview slots ────────────────────────────────
    prompt = f"{SCHEDULER_SYSTEM}\n\n" + SCHEDULER_USER.format(
        job_title       = state["job_title"],
        candidates_list = _format_candidates_list(shortlisted),
        notify_emails   = ", ".join(state.get("notify_emails", [])) or "hr@company.com",
        count           = len(shortlisted),
    )

    slots: list[dict] = []
    try:
        response = await _client.aio.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        slots = json.loads(raw)
        if not isinstance(slots, list):
            slots = []
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[Scheduler] Gemini parse failed: %s", exc)

    slot_map: dict[str, dict] = {s["email"]: s for s in slots}
    updated_shortlisted: list[CandidateDict] = []
    decisions: list[DecisionDict] = []

    for candidate in shortlisted:
        slot = slot_map.get(candidate["email"], {})
        slot_date = slot.get("slot_date", "TBD")
        slot_time = slot.get("slot_time", "10:00")
        panel     = slot.get("panel", state.get("notify_emails", []))

        # ── Step 2: Calendar MCP → create Google Calendar event ──────────────
        cal_result = await create_interview_event(
            candidate_name  = candidate["candidate_name"],
            candidate_email = candidate["email"],
            job_title       = state["job_title"],
            slot_date       = slot_date,
            slot_time       = slot_time,
            duration_mins   = slot.get("duration_minutes", 60),
            panel_emails    = panel,
        )
        meet_link = cal_result.get("meet_link", slot.get("meeting_link", "TBD"))

        # ── Step 3: Email MCP → send invite email ────────────────────────────
        await send_interview_invite(
            candidate_name  = candidate["candidate_name"],
            candidate_email = candidate["email"],
            job_title       = state["job_title"],
            slot_date       = slot_date,
            slot_time       = slot_time,
            meet_link       = meet_link,
        )

        # ── Step 4: Task MCP → create feedback collection task ───────────────
        await create_interview_tasks(
            job_id          = state["job_id"],
            candidate_name  = candidate["candidate_name"],
            candidate_email = candidate["email"],
            slot_date       = slot_date,
        )

        slot_str = f"{slot_date} {slot_time} (technical) — {meet_link}"

        updated = CandidateDict(
            candidate_name = candidate["candidate_name"],
            email          = candidate["email"],
            resume_text    = candidate.get("resume_text"),
            resume_b64     = candidate.get("resume_b64"),
            score          = candidate.get("score"),
            rank           = candidate.get("rank"),
            status         = candidate.get("status", "shortlisted"),
            reasoning      = candidate.get("reasoning"),
            interview_slot = slot_str,
        )
        updated_shortlisted.append(updated)

        decisions.append(DecisionDict(
            agent     = "scheduler",
            action    = "Interview scheduled + invite sent",
            target    = candidate["email"],
            reasoning = f"Slot: {slot_str} | Calendar: {cal_result.get('event_id', 'stub')}",
            timestamp = datetime.now(timezone.utc).isoformat(),
        ))

        logger.info("[Scheduler] ✅ %s → %s", candidate["candidate_name"], slot_str)

    shortlisted_emails = {c["email"] for c in shortlisted}
    updated_all = [c for c in state.get("candidates", []) if c["email"] not in shortlisted_emails]
    updated_all.extend(updated_shortlisted)

    return {
        "stage"      : Stage.INTERVIEWING,
        "shortlisted": updated_shortlisted,
        "candidates" : updated_all,
        "decisions"  : decisions,
    }