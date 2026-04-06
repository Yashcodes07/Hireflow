"""
observability/langsmith_tracer.py
══════════════════════════════════════════════════════════════════
LangSmith tracing setup.

Enables:
  - Full pipeline trace per /hire request
  - Per-agent spans (screener, scheduler, offer_drafter, reporter)
  - Input/output logging for every Gemini call
  - Error tracking with full stack traces
  - Evaluation metrics (scores, shortlist rate)

Usage:
  from observability.langsmith_tracer import setup_langsmith, trace_pipeline_run
"""

from __future__ import annotations
import os
import logging
from functools import wraps
from typing import Any

logger = logging.getLogger("langsmith")


def setup_langsmith(settings) -> bool:
    """
    Call once at app startup.
    Returns True if LangSmith is enabled and configured.
    """
    if not settings.LANGSMITH_TRACING:
        logger.info("LangSmith tracing disabled — set LANGSMITH_TRACING=true to enable")
        return False

    if not settings.LANGSMITH_API_KEY:
        logger.warning("LangSmith tracing enabled but LANGSMITH_API_KEY not set — skipping")
        return False

    # Set environment variables that LangSmith SDK reads automatically
    os.environ["LANGCHAIN_TRACING_V2"]  = "true"
    os.environ["LANGCHAIN_API_KEY"]     = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"]     = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"]    = settings.LANGSMITH_ENDPOINT

    logger.info(
        "✅ LangSmith tracing enabled — project=%s endpoint=%s",
        settings.LANGSMITH_PROJECT,
        settings.LANGSMITH_ENDPOINT,
    )
    return True


def trace_pipeline_run(
    run_id: str,
    job_id: str,
    result: dict,
) -> None:
    """
    Log final pipeline metrics to LangSmith as feedback.
    Call after pipeline completes.
    """
    try:
        from langsmith import Client

        client = Client()

        # Log shortlist rate as a metric
        shortlisted    = len(result.get("shortlisted", []))
        rejected       = result.get("rejected_count", 0)
        total          = shortlisted + rejected
        shortlist_rate = round(shortlisted / max(total, 1) * 100, 1)

        client.create_feedback(
            run_id   = run_id,
            key      = "shortlist_rate_pct",
            score    = shortlist_rate / 100,
            comment  = f"Shortlisted {shortlisted}/{total} candidates",
        )

        logger.info(
            "LangSmith feedback logged — run_id=%s shortlist_rate=%.1f%%",
            run_id, shortlist_rate,
        )

    except Exception as exc:
        # Never let observability failures crash the pipeline
        logger.warning("LangSmith feedback failed (non-fatal): %s", exc)


def get_langsmith_run_url(run_id: str, project: str) -> str | None:
    """Return the LangSmith UI URL for a given run."""
    try:
        return f"https://smith.langchain.com/projects/{project}/runs/{run_id}"
    except Exception:
        return None