"""Admin and user authentication dependency for protected API routes."""

from __future__ import annotations

import os
from secrets import compare_digest

from fastapi import Header, HTTPException, status

from src.api.models.db_models import User
from src.core.security.users import get_session_user


def get_admin_token() -> str:
    token = os.getenv("ADMIN_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ADMIN_TOKEN must be set")
    return token


def validate_admin_token() -> None:
    get_admin_token()


async def require_admin(
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None),
) -> None:
    expected_token = get_admin_token()
    supplied_token = x_admin_token
    if supplied_token is None and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            supplied_token = token

    if supplied_token is None or not compare_digest(supplied_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token required",
        )


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
) -> User:
    """FastAPI dependency to retrieve the currently logged in user."""
    supplied_token = x_session_token
    if supplied_token is None and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            supplied_token = token

    if not supplied_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token required",
        )

    user = await get_session_user(supplied_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return user

