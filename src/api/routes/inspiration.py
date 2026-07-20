"""Inspiration mode API routes."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.services.content.inspiration_service import get_inspiration_wizard
from src.core.auth_models import User
from src.core.security.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/inspiration", tags=["inspiration"])


class InspirationStepRequest(BaseModel):
    step: str = Field(..., min_length=1)
    user_input: str = Field(..., min_length=1)


class InspirationCreateRequest(BaseModel):
    target_words: int = Field(default=100000, ge=10000, le=10000000)


class InspirationGenerateRequest(BaseModel):
    """无状态生成大纲：前端直接传 collected 数据，不依赖 session。"""
    collected: dict[str, str] = Field(default_factory=dict)


class InspirationCreateCollectedRequest(BaseModel):
    """无状态创建项目：前端直接传 collected + target_words，不依赖 session。"""
    collected: dict[str, str] = Field(default_factory=dict)
    target_words: int = Field(default=100000, ge=10000, le=10000000)
    outline: str | None = None


@router.post("/start")
async def start_inspiration_session(current_user: User = Depends(get_current_user)):
    wizard = get_inspiration_wizard()
    return wizard.start_session(owner_id=current_user.id)


@router.post("/{session_id}/step")
async def process_inspiration_step(
    session_id: str,
    request: InspirationStepRequest,
    current_user: User = Depends(get_current_user),
):
    wizard = get_inspiration_wizard()
    try:
        return await wizard.process_step(
            session_id=session_id,
            step=request.step,
            user_input=request.user_input,
            owner_id=current_user.id,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Inspiration session not accessible")
    except KeyError:
        raise HTTPException(status_code=404, detail="Inspiration session not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("inspiration_step_failed", session_id=session_id, error=str(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to process inspiration step",
        )


@router.post("/{session_id}/generate")
async def generate_inspiration_outline(
    session_id: str,
    request: InspirationGenerateRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    """生成大纲。无状态：优先用请求体的 collected，回退 session（兼容旧前端）。"""
    wizard = get_inspiration_wizard()
    try:
        if request and request.collected:
            # 无状态：前端传 collected，不依赖 session（容器重启也不丢）
            return await wizard.generate_outline_from_collected(
                request.collected, session_id=session_id,
            )
        # 回退：从 session 取（旧前端兼容）
        return await wizard.generate_outline(session_id, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Inspiration session not accessible")
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Inspiration session not found（请刷新页面重新开始，或在前端传 collected 数据）",
        )
    except Exception as exc:
        logger.error("inspiration_outline_failed", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to generate outline")


@router.post("/{session_id}/create")
async def create_inspiration_project(
    session_id: str,
    request: InspirationCreateCollectedRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    """创建项目。无状态：优先用请求体的 collected，回退 session（兼容旧前端）。"""
    wizard = get_inspiration_wizard()
    try:
        if request and request.collected:
            # 无状态：前端传 collected + target_words + outline
            return await wizard.create_project_from_collected(
                request.collected,
                target_words=request.target_words,
                owner_id=current_user.id,
                outline=request.outline,
            )
        # 回退：从 session 取（旧前端兼容）
        return await wizard.create_project(
            session_id, owner_id=current_user.id,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Inspiration session not accessible")
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Inspiration session not found（请刷新页面重新开始，或在前端传 collected 数据）",
        )
    except Exception as exc:
        logger.error("inspiration_create_failed", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create project")
