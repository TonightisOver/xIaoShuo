"""路由模块"""

from .conversations import router as conversations_router
from .health import router as health_router
from .novels import router as novels_router
from .projects import router as projects_router
from .ws import router as ws_router

__all__ = ["novels_router", "health_router", "projects_router", "ws_router", "conversations_router"]
