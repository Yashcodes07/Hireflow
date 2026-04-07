"""
mcp/task_manager_mcp.py
══════════════════════════════════════════════════════════════════
Task Manager MCP — Track hiring pipeline tasks

Responsibilities:
  - Create tasks for each hiring stage transition
  - Mark tasks complete when agents finish
  - Track overdue tasks
  - Generate task summary for HR dashboard

Stores tasks in AlloyDB via crud, with in-memory fallback.
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

logger = logging.getLogger("task_manager_mcp")


class TaskStatus(str, Enum):
    PENDING    = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE   = "complete"
    OVERDUE    = "overdue"


class TaskPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ── In-memory task store (fallback) ──────────────────────────────────────────
_tasks: dict[str, dict] = {}


# ── Core task operations ──────────────────────────────────────────────────────

async def create_task(
    job_id      : str,
    title       : str,
    description : str,
    assigned_to : str = "hr@company.com",
    priority    : TaskPriority = TaskPriority.MEDIUM,
    due_hours   : int = 24,
    metadata    : dict = None,
) -> dict:
    """Create a new hiring pipeline task."""
    task_id  = str(uuid.uuid4())[:8]
    due_at   = datetime.now(timezone.utc) + timedelta(hours=due_hours)

    task = {
        "task_id"    : task_id,
        "job_id"     : job_id,
        "title"      : title,
        "description": description,
        "assigned_to": assigned_to,
        "priority"   : priority,
        "status"     : TaskStatus.PENDING,
        "due_at"     : due_at.isoformat(),
        "created_at" : datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "metadata"   : metadata or {},
    }

    _tasks[task_id] = task
    logger.info("Task created: [%s] %s → %s", task_id, title, assigned_to)
    return task


async def complete_task(task_id: str, notes: str = "") -> bool:
    """Mark a task as complete."""
    if task_id in _tasks:
        _tasks[task_id]["status"]       = TaskStatus.COMPLETE
        _tasks[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
        _tasks[task_id]["notes"]        = notes
        logger.info("Task completed: %s", task_id)
        return True
    logger.warning("Task not found: %s", task_id)
    return False


async def get_tasks_for_job(job_id: str) -> list[dict]:
    """Get all tasks for a specific job."""
    return [t for t in _tasks.values() if t["job_id"] == job_id]


async def get_pending_tasks(job_id: str) -> list[dict]:
    """Get all pending tasks for a job."""
    return [
        t for t in _tasks.values()
        if t["job_id"] == job_id and t["status"] == TaskStatus.PENDING
    ]


async def get_task_summary(job_id: str) -> dict:
    """Get task completion summary for a job."""
    all_tasks  = await get_tasks_for_job(job_id)
    complete   = [t for t in all_tasks if t["status"] == TaskStatus.COMPLETE]
    pending    = [t for t in all_tasks if t["status"] == TaskStatus.PENDING]

    now = datetime.now(timezone.utc)
    overdue = []
    for t in pending:
        try:
            due = datetime.fromisoformat(t["due_at"])
            if due < now:
                overdue.append(t)
        except Exception:
            pass

    return {
        "job_id"         : job_id,
        "total_tasks"    : len(all_tasks),
        "complete"       : len(complete),
        "pending"        : len(pending),
        "overdue"        : len(overdue),
        "completion_pct" : round(len(complete) / max(len(all_tasks), 1) * 100, 1),
        "overdue_tasks"  : [t["title"] for t in overdue],
    }


# ── Pipeline-specific task creators ──────────────────────────────────────────

async def create_screening_tasks(job_id: str, candidate_count: int) -> list[dict]:
    """Create tasks for the screening stage."""
    tasks = []
    tasks.append(await create_task(
        job_id      = job_id,
        title       = f"Review AI screening results for {candidate_count} candidates",
        description = "Review scores and reasoning from the AI screener. Approve or override shortlist.",
        priority    = TaskPriority.HIGH,
        due_hours   = 4,
        metadata    = {"stage": "screening", "candidate_count": candidate_count},
    ))
    return tasks


async def create_interview_tasks(
    job_id         : str,
    candidate_name : str,
    candidate_email: str,
    slot_date      : str,
) -> dict:
    """Create task for interview follow-up."""
    return await create_task(
        job_id      = job_id,
        title       = f"Collect feedback — {candidate_name}",
        description = f"Get interview feedback from panel for {candidate_name} ({candidate_email}). Interview on {slot_date}.",
        priority    = TaskPriority.HIGH,
        due_hours   = 48,
        metadata    = {
            "stage"          : "interviewing",
            "candidate_email": candidate_email,
            "interview_date" : slot_date,
        },
    )


async def create_offer_tasks(
    job_id         : str,
    candidate_name : str,
    candidate_email: str,
) -> dict:
    """Create task for offer follow-up."""
    return await create_task(
        job_id      = job_id,
        title       = f"Follow up on offer — {candidate_name}",
        description = f"Confirm {candidate_name} ({candidate_email}) has received and reviewed the offer letter. Collect acceptance/rejection.",
        priority    = TaskPriority.HIGH,
        due_hours   = 72,
        metadata    = {
            "stage"          : "offer",
            "candidate_email": candidate_email,
        },
    )


async def create_report_task(job_id: str) -> dict:
    """Create task to review the hiring report."""
    return await create_task(
        job_id      = job_id,
        title       = "Review hiring pipeline report",
        description = "Review the AI-generated hiring summary report. Share with leadership if needed.",
        priority    = TaskPriority.MEDIUM,
        due_hours   = 24,
        metadata    = {"stage": "report"},
    )