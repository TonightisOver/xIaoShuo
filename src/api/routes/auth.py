"""Authentication API routes."""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.models.db_models import User
from src.core.database import get_db_session
from src.core.security.auth import get_current_user
from src.core.security.users import (
    create_session,
    delete_session,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class AuthResponse(BaseModel):
    session_token: str
    username: str
    user_id: int


class UserResponse(BaseModel):
    id: int
    username: str


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: AuthRequest):
    """Register a new user and return a session token."""
    async with get_db_session() as session:
        # Check if username exists
        result = await session.execute(
            select(User).where(User.username == req.username)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )

        # Create user（若 username 匹配 ADMIN_USERNAME 环境变量，标记为 admin）
        import os
        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        is_admin = bool(admin_username) and req.username == admin_username
        hashed = hash_password(req.password)
        new_user = User(username=req.username, hashed_password=hashed, is_admin=is_admin)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        user_id = new_user.id

    # Create session token
    token = await create_session(user_id)
    return AuthResponse(session_token=token, username=req.username, user_id=user_id)


@router.post("/login", response_model=AuthResponse)
async def login(req: AuthRequest):
    """Login a user and return a session token."""
    async with get_db_session() as session:
        result = await session.execute(
            select(User).where(User.username == req.username)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect username or password",
            )

        user_id = user.id

    token = await create_session(user_id)
    return AuthResponse(session_token=token, username=req.username, user_id=user_id)


@router.post("/logout")
async def logout(
    authorization: str | None = Header(default=None),
    x_session_token: str | None = Header(default=None),
):
    """Log out a user by invalidating their session token."""
    supplied_token = x_session_token
    if supplied_token is None and authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            supplied_token = token

    if supplied_token:
        await delete_session(supplied_token)
    return {"status": "success"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile info."""
    return UserResponse(id=current_user.id, username=current_user.username)
