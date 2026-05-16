"""API 服务启动脚本"""

import uvicorn

from src.core.config import get_settings

if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
        log_level=settings.LOG_LEVEL.lower(),
    )
