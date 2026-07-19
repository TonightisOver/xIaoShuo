"""Admin and user authentication dependency for protected API routes."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import Depends, Header, HTTPException, WebSocket, status

from src.core.auth_models import User
from src.core.config import get_settings
from src.core.security.users import get_or_create_dev_user, get_session_user


def get_admin_token() -> str:
    # 从 Settings 读取（pydantic 已加载 .env），而非 os.getenv（后者读不到 .env）
    token = get_settings().ADMIN_TOKEN.strip()
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
        # 开发期自动登录：DEV_AUTO_LOGIN 开启时无 token 直接返回 dev 用户
        if get_settings().DEV_AUTO_LOGIN:
            return await get_or_create_dev_user()
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


async def require_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前登录用户是 admin（is_admin=True）。

    用于 LLM 配置等敏感操作：普通用户 403，admin 用户允许。
    与 require_admin（ADMIN_TOKEN）互补——require_admin 给运维脚本，
    require_admin_user 给前端登录的 admin 用户。
    """
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user



async def get_websocket_user(websocket: WebSocket) -> User | None:
    """从 Sec-WebSocket-Protocol 子协议中取 session token 认证。

    浏览器 WebSocket API 无法发送自定义 Header，改用子协议传 token：
        new WebSocket(url, ['xiaoshuo', token])
    后端只接受 ['xiaoshuo', token] 形态，校验 token 返回 User；
    无效或缺失返回 None（由路由 close 4401）。不回显 token。
    """
    raw = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [item.strip() for item in raw.split(",") if item.strip()]
    if len(protocols) == 2 and protocols[0] == "xiaoshuo":
        return await get_session_user(protocols[1])
    if get_settings().DEV_AUTO_LOGIN:
        return await get_or_create_dev_user()
    return None
