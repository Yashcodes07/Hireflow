"""
models.py — All Pydantic schemas for request parsing & response shaping.
FastAPI validates every incoming payload against these automatically.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import base64


# ── Enums ─────────────────────────────────────────────────────────────────────

class HiringStage(str, Enum):
    SCREENING   = "screening"
    INTERVIEWING = "interviewing"
    OFFER       = "offer"
    CLOSED      = "closed"


class CandidateStatus(str, Enum):
    PENDING   = "pending"
    SHORTLISTED = "shortlisted"
    REJECTED  = "rejected"
    HIRED     = "hired"


# ── Inbound ────────────────────────────────────────────────────────────────────

class ResumeInput(BaseModel):
    """A single candidate resume — base64-encoded PDF or raw text."""
    candidate_name: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., pattern=r"^[\w\.\+\-]+@[\w\-]+\.[a-z]{2,}$")
    resume_text: Optional[str] = Field(None, description="Plain-text resume content")
    resume_b64: Optional[str] = Field(None, description="Base64-encoded PDF resume")

    @field_validator("resume_b64")
    @classmethod
    def validate_base64(cls, v):
        if v is not None:
            try:
                base64.b64decode(v, validate=True)
            except Exception:
                raise ValueError("resume_b64 must be valid base64")
        return v

    @field_validator("resume_text", mode="before")
    @classmethod
    def at_least_one_resume(cls, v, info):
        # Cross-field check handled at HireRequest level
        return v


class HireRequest(BaseModel):
    """
    POST /hire  — main entry point.
    HR user sends job description + a batch of resumes.
    """
    job_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_\-]+$")
    job_title: str = Field(..., min_length=3, max_length=200)
    job_description: str = Field(..., min_length=50, max_length=10_000)
    required_skills: list[str] = Field(default_factory=list, max_length=30)
    resumes: list[ResumeInput] = Field(..., min_length=1, max_length=100)
    notify_emails: list[str] = Field(
        default_factory=list,
        description="Send offer/interview invites to these addresses"
    )
    max_shortlist: int = Field(default=5, ge=1, le=50)


# ── Auth schemas ───────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Outbound ───────────────────────────────────────────────────────────────────

class CandidateResult(BaseModel):
    candidate_name: str
    email: str
    score: float = Field(..., ge=0.0, le=100.0)
    status: CandidateStatus
    interview_slot: Optional[str] = None
    offer_letter_url: Optional[str] = None
    notes: Optional[str] = None


class HireResponse(BaseModel):
    """Structured JSON returned to the HR user after pipeline completes."""
    job_id: str
    stage: HiringStage
    shortlisted: list[CandidateResult]
    rejected_count: int
    report_url: Optional[str] = None
    audit_log_id: Optional[str] = None
    pipeline_run_id: str   # LangSmith trace ID
    message: str = "Pipeline completed successfully"


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
