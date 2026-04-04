"""
routes/hire.py — All API routes for the HR Hiring Gateway.

Endpoints:
  POST /auth/token  → get JWT
  POST /hire        → main pipeline trigger (auth required)
  GET  /health      → Cloud Run health check (no auth)
  GET  /jobs/{job_id}/status → poll a running job
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

# ✅ CORRECT
from auth import (
    create_access_token,
    get_current_user,
    require_role,
    TokenData,
)
from models import (
    HireRequest,
    HireResponse,
    TokenResponse,
    ErrorResponse,
    TokenRequest,
)
from pipeline.langgraph_trigger import run_hiring_pipeline
from config import get_settings

router = APIRouter()
settings = get_settings()


# ── Health check ──────────────────────────────────────────────────────────────

@router.get(
    "/health",
    tags=["ops"],
    summary="Cloud Run liveness / readiness probe",
)
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


# ── Auth ──────────────────────────────────────────────────────────────────────

@router.post(
    "/auth/token",
    response_model=TokenResponse,
    tags=["auth"],
    summary="Exchange username + password for a JWT bearer token",
)
async def login(body: TokenRequest):
    """
    Stub: replace with real user-lookup + bcrypt verify.
    For now, accepts any non-empty credentials in dev mode.
    """
    if not body.username or not body.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username and password are required",
        )

    # ─── TODO: verify against AlloyDB users table ───
    # user = await db.fetch_user(body.username)
    # if not user or not verify_password(body.password, user.hashed_password):
    #     raise HTTPException(401, "Invalid credentials")

    token, expires_in = create_access_token(subject=body.username, role="hr_user")
    return TokenResponse(access_token=token, expires_in=expires_in)


# ── Core hiring pipeline ──────────────────────────────────────────────────────

@router.post(
    "/hire",
    response_model=HireResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        403: {"model": ErrorResponse, "description": "Insufficient role"},
        502: {"model": ErrorResponse, "description": "Agent pipeline error"},
    },
    tags=["hiring"],
    summary="Submit job description + resumes → run full hiring pipeline",
)
async def submit_hire_request(
    body: HireRequest,
    request: Request,
    # Auth: HR users and admins only
    user: TokenData = Depends(require_role(["hr_user", "hr_manager", "admin"])),
):
    """
    Main endpoint consumed by the HR frontend.

    Flow:
    1. FastAPI validates `body` against HireRequest schema
    2. Auth dependency verifies JWT / API key + role
    3. Pipeline is triggered asynchronously via LangGraph Manager Agent
    4. Returns structured JSON: shortlist, interview slots, offer links, report
    """
    request_id: str = getattr(request.state, "request_id", "no-id")

    try:
        result = await run_hiring_pipeline(body, request_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Pipeline error: {exc}",
        )

    return result


# ── Status polling (optional) ─────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}/status",
    tags=["hiring"],
    summary="Poll the current stage of a running job",
)
async def job_status(
    job_id: str,
    user: TokenData = Depends(get_current_user),
):
    """
    Thin wrapper — delegates to the agent's state store (AlloyDB).
    Replace stub with a real DB query.
    """
    # TODO: query AlloyDB HiringState for job_id
    return {
        "job_id": job_id,
        "stage":  "screening",
        "message": "Stub — connect to AlloyDB",
    }
