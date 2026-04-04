"""
pipeline/langgraph_trigger.py
Sends the validated HireRequest to the LangGraph Manager Agent
and waits for the structured HireResponse.

Replace the HTTP call with a direct LangGraph .ainvoke() if
the agent runs in the same process.
"""

from __future__ import annotations
import httpx
import logging
from uuid import uuid4

from config import get_settings
from models import HireRequest, HireResponse, HiringStage, CandidateResult, CandidateStatus

logger = logging.getLogger("pipeline")
settings = get_settings()


async def run_hiring_pipeline(request: HireRequest, request_id: str) -> HireResponse:
    """
    Trigger the LangGraph Manager Agent and return structured results.

    In production, swap the HTTP call for:
        from agents.manager import manager_graph
        result = await manager_graph.ainvoke(state)
    """
    payload = {
        "job_id":          request.job_id,
        "job_title":       request.job_title,
        "job_description": request.job_description,
        "required_skills": request.required_skills,
        "resumes":         [r.model_dump() for r in request.resumes],
        "max_shortlist":   request.max_shortlist,
        "notify_emails":   request.notify_emails,
        "run_id":          request_id,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.AGENT_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{settings.LANGGRAPH_ENDPOINT}/run",
                json=payload,
                headers={"X-Request-ID": request_id},
            )
            resp.raise_for_status()
            data = resp.json()

        return HireResponse(
            job_id          = data["job_id"],
            stage           = HiringStage(data.get("stage", "screening")),
            shortlisted     = [CandidateResult(**c) for c in data.get("shortlisted", [])],
            rejected_count  = data.get("rejected_count", 0),
            report_url      = data.get("report_url"),
            audit_log_id    = data.get("audit_log_id"),
            pipeline_run_id = data.get("run_id", request_id),
        )

    except httpx.HTTPStatusError as exc:
        logger.error("Agent returned error: %s", exc.response.text)
        raise

    except httpx.RequestError as exc:
        logger.error("Could not reach agent: %s", exc)
        raise
