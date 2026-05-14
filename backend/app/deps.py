from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .database import db_conn

security = HTTPBearer(auto_error=False)


def get_db() -> Generator:
    with db_conn() as conn:
        yield conn


def require_admin(
    creds: HTTPAuthorizationCredentials | None = Security(security),
) -> None:
    expected = get_settings().admin_password
    if not expected:
        return
    token = creds.credentials if creds and creds.scheme.lower() == "bearer" else None
    if token != expected:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid admin token. Send Authorization: Bearer <WEMO_ADMIN_PASSWORD> for all /api routes except GET /api/health.",
        )
