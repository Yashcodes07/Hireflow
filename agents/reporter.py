"""
agents/reporter.py  (Vertex AI version — no API key needed)
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, DecisionDict, Stage
from agents.prompts import REPORTER_SYSTEM, REPORTER_USER

logger = logging.getLogger("reporter")

# ── Vertex AI client ──────────────────────────────────────────────────────────
_client = genai.Client(
    vertexai=True,
    project="project-agent-491814",
    location="us-central1",
)
MODEL = "gemini-2.5-flash"


def _format_scores(candidates: list) -> str:
    lines = []
    for c in candidates:
        lines.append(
            f"- {c['candidate_name']} <{c['email']}> | "
            f"Score: {c.get('score', 'N/A')} | "
            f"Status: {c.get('status', 'N/A')}"
        )
    return "\n".join(lines) if lines else "No candidates"


def _format_decisions(decisions: list) -> str:
    if not decisions:
        return "No decisions recorded"
    lines = []
    for d in decisions:
        lines.append(f"- [{d['agent']}] {d['action']} → {d['target']}")
    return "\n".join(lines[-10:])


async def reporter_node(state: HiringState) -> dict:
    logger.info("[Reporter] Generating report for job_id=%s", state.get("job_id"))

    all_candidates = state.get("candidates", [])
    shortlisted    = state.get("shortlisted", [])
    rejected_count = state.get("rejected_count", 0)
    decisions      = state.get("decisions", [])

    prompt = f"{REPORTER_SYSTEM}\n\n" + REPORTER_USER.format(
        job_title         = state["job_title"],
        job_id            = state["job_id"],
        total             = len(all_candidates),
        shortlisted_count = len(shortlisted),
        rejected_count    = rejected_count,
        scores_list       = _format_scores(all_candidates),
        decisions_summary = _format_decisions(decisions),
    )

    report: dict = {}
    try:
        response = await _client.aio.models.generate_content(
            model    = MODEL,
            contents = prompt,
        )
        raw = response.text.strip()

        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]

        report = json.loads(raw)

    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[Reporter] Failed to parse report: %s", exc)
        report = {
            "title"                 : f"Hiring Report — {state['job_title']}",
            "summary"               : "Report generation encountered an issue.",
            "total_applicants"      : len(all_candidates),
            "shortlisted_count"     : len(shortlisted),
            "rejected_count"        : rejected_count,
            "shortlist_rate_pct"    : round(len(shortlisted) / max(len(all_candidates), 1) * 100, 1),
            "key_findings"          : [],
            "recommended_next_steps": [],
            "generated_at"          : datetime.now(timezone.utc).isoformat(),
        }

    audit_log_id = f"audit-{state.get('job_id')}-{state.get('run_id', 'x')[:8]}"

    logger.info(
        "[Reporter] Report complete — shortlist_rate=%.1f%%",
        report.get("shortlist_rate_pct", 0),
    )

    return {
        "stage"       : Stage.REPORT,
        "report_url"  : None,
        "audit_log_id": audit_log_id,
        "decisions"   : [DecisionDict(
            agent     = "reporter",
            action    = "Hiring report generated",
            target    = "all",
            reasoning = report.get("summary", ""),
            timestamp = datetime.now(timezone.utc).isoformat(),
        )],
    }
