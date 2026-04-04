"""
auth.py — Dual-mode authentication: JWT bearer tokens + static API keys.

Usage (in routes):
    user = Depends(get_current_user)          # accepts either method
    user = Depends(require_jwt)               # JWT only
    user = Depends(require_api_key)           # API key only
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel

from config import get_settings, Settings

# ── Security schemes ──────────────────────────────────────────────────────────
bearer_scheme  = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# ── Token payload ─────────────────────────────────────────────────────────────
class TokenData(BaseModel):
    sub: str                    # user id / service name
    role: str = "hr_user"
    exp: Optional[datetime] = None


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str = "hr_user",
    settings: Settings = None,
) -> tuple[str, int]:
    """Return (encoded_jwt, expires_in_seconds)."""
    if settings is None:
        settings = get_settings()

    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, settings.JWT_EXPIRE_MINUTES * 60


def decode_access_token(token: str, settings: Settings) -> TokenData:
    """Decode & validate JWT. Raises HTTPException on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return TokenData(
            sub=payload["sub"],
            role=payload.get("role", "hr_user"),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Dependency functions ───────────────────────────────────────────────────────

def require_jwt(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> TokenData:
    """Validates Bearer JWT. Inject with Depends(require_jwt)."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials, settings)


def require_api_key(
    api_key: str = Security(api_key_scheme),
    settings: Settings = Depends(get_settings),
) -> TokenData:
    """Validates X-API-Key header. Inject with Depends(require_api_key)."""
    if not api_key or api_key not in settings.VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return TokenData(sub="api-key-client", role="service")


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_scheme),
    settings: Settings = Depends(get_settings),
) -> TokenData:
    """
    Accepts either Bearer JWT **or** X-API-Key.
    JWT is checked first; falls back to API key.
    Raises 401 if neither is valid.
    """
    # ① Try JWT
    if credentials and credentials.credentials:
        try:
            return decode_access_token(credentials.credentials, settings)
        except HTTPException:
            pass  # fall through to API key

    # ② Try API key
    if api_key and api_key in settings.VALID_API_KEYS:
        return TokenData(sub="api-key-client", role="service")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide Bearer token or X-API-Key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(allowed_roles: list[str]):
    """
    Role-based access control decorator factory.
    Usage:  Depends(require_role(["admin", "hr_manager"]))
    """
    def _checker(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not allowed. Required: {allowed_roles}",
            )
        return user
    return _checker
