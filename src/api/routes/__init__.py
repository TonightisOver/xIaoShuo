"""路由模块"""

from .conversations import router as conversations_router
from .export import router as export_router
from .health import router as health_router
from .knowledge_graph import router as knowledge_graph_router
from .llm_config import router as llm_config_router
from .novels import router as novels_router
from .novels import tasks_router
from .outline_sync import router as outline_sync_router
from .outlines import router as outlines_router
from .projects import router as projects_router
from .reader_simulation import router as reader_simulation_router
from .story_bible import router as story_bible_router
from .storylines import router as storylines_router
from .style import router as style_router
from .ws import router as ws_router

__all__ = [
    "novels_router", "tasks_router", "health_router", "projects_router", "ws_router",
    "conversations_router", "style_router", "outlines_router",
    "storylines_router", "knowledge_graph_router", "story_bible_router",
    "export_router", "outline_sync_router", "reader_simulation_router",
    "llm_config_router",
]

