"""User and session database models for authentication.

These are defined in the core layer so that security/authentication logic
in src/core/security/ does not need to depend on the API layer directly.

Note: This file defines its own Base (AuthBase) rather than re-using the
main API Base to avoid "Table 'users' is already defined" errors when both
core/auth_models and api/models/db_models are imported.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class AuthBase(DeclarativeBase):
    pass


UTC = timezone.utc


class User(AuthBase):
    """用户"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserSession(AuthBase):
    """用户会话"""

    __tablename__ = "user_sessions"

    session_token: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
