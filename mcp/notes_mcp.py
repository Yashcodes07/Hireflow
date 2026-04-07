"""
mcp/notes_mcp.py
══════════════════════════════════════════════════════════════════
Notes MCP — Cloud Firestore document store

Responsibilities:
  - Store offer letter drafts
  - Store interview feedback notes
  - Store pipeline decisions as structured documents
  - Retrieve notes by job_id / candidate email

Uses Google Cloud Firestore via Application Default Credentials.
Falls back to in-memory dict if Firestore not configured.
"""

from __future__ import annotations
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Any

logger = logging.getLogger("notes_mcp")

# ── In-memory fallback store ──────────────────────────────────────────────────
_memory_store: dict[str, dict] = {}


# ── Firestore client ──────────────────────────────────────────────────────────

def _get_firestore():
    try:
        from google.cloud import firestore
        return firestore.AsyncClient()
    except Exception as exc:
        logger.warning("Firestore not available — using memory store: %s", exc)
        return None


# ── Core operations ───────────────────────────────────────────────────────────

async def save_note(
    collection : str,
    doc_id     : str,
    data       : dict,
) -> bool:
    """Save a document to Firestore or memory store."""
    data["saved_at"] = datetime.now(timezone.utc).isoformat()

    db = _get_firestore()
    if db:
        try:
            await db.collection(collection).document(doc_id).set(data)
            logger.info("Firestore saved: %s/%s", collection, doc_id)
            return True
        except Exception as exc:
            logger.warning("Firestore save failed: %s", exc)

    # Memory fallback
    key = f"{collection}/{doc_id}"
    _memory_store[key] = data
    logger.info("Memory store saved: %s", key)
    return True


async def get_note(collection: str, doc_id: str) -> Optional[dict]:
    """Retrieve a document from Firestore or memory store."""
    db = _get_firestore()
    if db:
        try:
            doc = await db.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as exc:
            logger.warning("Firestore get failed: %s", exc)

    key = f"{collection}/{doc_id}"
    return _memory_store.get(key)


async def list_notes(collection: str, job_id: str) -> list[dict]:
    """List all documents in a collection filtered by job_id."""
    db = _get_firestore()
    if db:
        try:
            docs = await db.collection(collection).where("job_id", "==", job_id).get()
            return [d.to_dict() for d in docs]
        except Exception as exc:
            logger.warning("Firestore list failed: %s", exc)

    # Memory fallback
    prefix = f"{collection}/"
    return [
        v for k, v in _memory_store.items()
        if k.startswith(prefix) and v.get("job_id") == job_id
    ]


# ── Domain-specific helpers ───────────────────────────────────────────────────

async def save_offer_draft(
    job_id        : str,
    candidate_email: str,
    offer_text    : str,
    salary_inr    : float | None = None,
    start_date    : str | None   = None,
) -> bool:
    """Save an offer letter draft to Notes MCP."""
    doc_id = f"{job_id}_{candidate_email.replace('@', '_').replace('.', '_')}"
    return await save_note(
        collection = "offer_drafts",
        doc_id     = doc_id,
        data       = {
            "job_id"         : job_id,
            "candidate_email": candidate_email,
            "offer_text"     : offer_text,
            "salary_inr"     : salary_inr,
            "start_date"     : start_date,
            "status"         : "draft",
        },
    )


async def save_interview_feedback(
    job_id          : str,
    candidate_email : str,
    feedback_text   : str,
    feedback_score  : float | None = None,
    interviewer     : str | None   = None,
) -> bool:
    """Save post-interview feedback."""
    doc_id = f"{job_id}_{candidate_email.replace('@', '_').replace('.', '_')}_feedback"
    return await save_note(
        collection = "interview_feedback",
        doc_id     = doc_id,
        data       = {
            "job_id"         : job_id,
            "candidate_email": candidate_email,
            "feedback_text"  : feedback_text,
            "feedback_score" : feedback_score,
            "interviewer"    : interviewer,
        },
    )


async def save_pipeline_snapshot(job_id: str, run_id: str, state: dict) -> bool:
    """Save the full pipeline state as a snapshot for audit purposes."""
    doc_id = f"{job_id}_{run_id}"
    # Remove large fields before storing
    snapshot = {
        k: v for k, v in state.items()
        if k not in ("candidates",)
    }
    return await save_note(
        collection = "pipeline_snapshots",
        doc_id     = doc_id,
        data       = {"job_id": job_id, "run_id": run_id, **snapshot},
    )


async def get_offer_draft(job_id: str, candidate_email: str) -> Optional[dict]:
    doc_id = f"{job_id}_{candidate_email.replace('@', '_').replace('.', '_')}"
    return await get_note("offer_drafts", doc_id)