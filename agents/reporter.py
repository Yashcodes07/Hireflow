"""
agents/reporter.py  (Day 5 — updated with MCP integrations)
══════════════════════════════════════════════════════════════════
Now calls:
  - Email MCP → sends hiring report to HR team
  - Notes MCP → saves pipeline snapshot
  - Task MCP  → creates report review task
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from google import genai
from agents.state import HiringState, DecisionDict, Stage
from agents.prompts import REPORTER_SYSTEM, REPORTER_USER
from mcp.email_mcp import send_hr_report
from mcp.notes_mcp import save_pipeline_snapshot
from mcp.task_manager_mcp import create_report_task

logger = logging.getLogger("reporter")

_client = genai.Client(
    vertexai = True,
    project  = "project-agent-491814",
    location = "us-central1",
)
MODEL = "gemini-2.5-flash"


def _format_scores(candidates: list) -> str:
    return "\n".join(
        f"- {c['candidate_name']} <{c['email']}> | Score: {c.get('score','N/A')} | Status: {c.get('status','N/A')}"
        for c in candidates
    ) or "No candidates"


def _format_decisions(decisions: list) -> str:
    if not decisions:
        return "No decisions recorded"
    return "\n".join(
        f"- [{d['agent']}] {d['action']} → {d['target']}"
        for d in decisions[-10:]
    )


async def reporter_node(state: HiringState) -> dict:
    logger.info("[Reporter] Generating report for job_id=%s", state.get("job_id"))

    all_candidates = state.get("candidates", [])
    shortlisted    = state.get("shortlisted", [])
    rejected_count = state.get("rejected_count", 0)
    decisions      = state.get("decisions", [])

    # ── Step 1: Generate report with Gemini ───────────────────────────────────
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
        response = await _client.aio.models.generate_content(model=MODEL, contents=prompt)
        raw = response.text.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            raw = raw[start:end]
        report = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("[Reporter] Gemini parse failed: %s", exc)
        report = {
            "title"              : f"Hiring Report — {state['job_title']}",
            "summary"            : "Pipeline completed successfully.",
            "total_applicants"   : len(all_candidates),
            "shortlisted_count"  : len(shortlisted),
            "rejected_count"     : rejected_count,
            "shortlist_rate_pct" : round(len(shortlisted) / max(len(all_candidates), 1) * 100, 1),
            "key_findings"       : [],
            "generated_at"       : datetime.now(timezone.utc).isoformat(),
        }

    audit_log_id = f"audit-{state.get('job_id')}-{state.get('run_id', 'x')[:8]}"

    # ── Step 2: Email MCP → send report to HR team ────────────────────────────
    for hr_email in state.get("notify_emails", []):
        await send_hr_report(
            hr_email    = hr_email,
            job_title   = state["job_title"],
            job_id      = state["job_id"],
            report_data = report,
        )

    # ── Step 3: Notes MCP → save pipeline snapshot ────────────────────────────
    await save_pipeline_snapshot(
        job_id = state["job_id"],
        run_id = state.get("run_id", "unknown"),
        state  = {
            "stage"           : str(state.get("stage")),
            "shortlisted_count": len(shortlisted),
            "rejected_count"  : rejected_count,
            "report"          : report,
        },
    )

    # ── Step 4: Task MCP → create report review task ──────────────────────────
    await create_report_task(job_id=state["job_id"])

    logger.info(
        "[Reporter] ✅ Report done — shortlist_rate=%.1f%% | Emails sent | Snapshot saved",
        report.get("shortlist_rate_pct", 0),
    )

    return {
        "stage"       : Stage.REPORT,
        "report_url"  : None,
        "audit_log_id": audit_log_id,
        "decisions"   : [DecisionDict(
            agent     = "reporter",
            action    = "Report generated + emailed + snapshot saved",
            target    = "all",
            reasoning = report.get("summary", ""),
            timestamp = datetime.now(timezone.utc).isoformat(),
        )],
    }