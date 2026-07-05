"""User authentication security helper functions."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, UTC

from sqlalchemy import select

from src.api.models.db_models import User, UserSession
from src.core.database import get_db_session

# PBKDF2 password hashing parameters
SALT_SIZE = 16
ITERATIONS = 100000
HASH_NAME = "sha256"


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2."""
    salt = secrets.token_bytes(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        salt,
        ITERATIONS,
    )
    return f"{salt.hex()}${key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its PBKDF2 hash."""
    try:
        salt_hex, key_hex = hashed_password.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac(
            HASH_NAME,
            password.encode("utf-8"),
            salt,
            ITERATIONS,
        )
        return secrets.compare_digest(actual_key, expected_key)
    except Exception:
        return False


async def create_session(user_id: int, expires_in_days: int = 7) -> str:
    """Create a new database-backed user session and return token."""
    token = secrets.token_hex(32)
    expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

    async with get_db_session() as session:
        db_session = UserSession(
            session_token=token,
            user_id=user_id,
            expires_at=expires_at,
        )
        session.add(db_session)
        await session.commit()
    return token


async def get_session_user(token: str) -> User | None:
    """Retrieve User if session token is valid and not expired."""
    async with get_db_session() as session:
        result = await session.execute(
            select(UserSession).where(UserSession.session_token == token)
        )
        db_session = result.scalar_one_or_none()
        if not db_session:
            return None

        # Handle timezone-aware or naive datetime comparison
        now_dt = datetime.now(UTC)
        expires_at = db_session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now_dt:
            # Session expired, remove from database
            await session.delete(db_session)
            await session.commit()
            return None

        user_result = await session.execute(
            select(User).where(User.id == db_session.user_id)
        )
        return user_result.scalar_one_or_none()


async def delete_session(token: str) -> None:
    """Delete a user session from the database (logout)."""
    async with get_db_session() as session:
        result = await session.execute(
            select(UserSession).where(UserSession.session_token == token)
        )
        db_session = result.scalar_one_or_none()
        if db_session:
            await session.delete(db_session)
            await session.commit()
