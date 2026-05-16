"""健康检查路由"""

from datetime import datetime

from fastapi import APIRouter

from src.api.models.responses import HealthResponse

router = APIRouter(prefix="/api/v1", tags=["health"])


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
    )
