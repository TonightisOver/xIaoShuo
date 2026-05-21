"""健康检查路由"""

from datetime import datetime

from fastapi import APIRouter

from src.api.models.responses import HealthResponse
from src.core.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["health"])

_PLACEHOLDER_KEYS = {
    "",
    "dummy_key_for_compilation",
    "your-api-key-here",
    "your_api_key_here",
    "sk-placeholder",
}


def _is_api_key_configured() -> bool:
    """Return True if the configured API key is not a known placeholder."""
    settings = get_settings()
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    return bool(key) and key.lower() not in _PLACEHOLDER_KEYS


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """健康检查

    Returns:
        健康状态
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(),
        api_key_configured=_is_api_key_configured(),
    )
