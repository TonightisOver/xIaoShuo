"""Inspiration mode API routes."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.services.inspiration_service import get_inspiration_wizard
from src.core.security.auth import get_current_user
from src.core.auth_models import User

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/inspiration", tags=["inspiration"])


class InspirationStepRequest(BaseModel):
    step: str = Field(..., min_length=1)
    user_input: str = Field(..., min_length=1)


class InspirationCreateRequest(BaseModel):
    target_words: int = Field(default=100000, ge=10000, le=10000000)


@router.post("/start")
async def start_inspiration_session():
    wizard = get_inspiration_wizard()
    return wizard.start_session()


@router.post("/{session_id}/step")
async def process_inspiration_step(
    session_id: str,
    request: InspirationStepRequest,
):
    wizard = get_inspiration_wizard()
    try:
        return await wizard.process_step(
            session_id=session_id,
            step=request.step,
            user_input=request.user_input,
        )
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
async def generate_inspiration_outline(session_id: str):
    wizard = get_inspiration_wizard()
    try:
        return await wizard.generate_outline(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Inspiration session not found")
    except Exception as exc:
        logger.error(
            "inspiration_outline_failed",
            session_id=session_id,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Failed to generate outline")


@router.post("/{session_id}/create")
async def create_inspiration_project(
    session_id: str,
    request: InspirationCreateRequest | None = None,
    current_user: User = Depends(get_current_user),
):
    wizard = get_inspiration_wizard()
    target_words = request.target_words if request else 100000
    try:
        return await wizard.create_project(
            session_id, target_words=target_words, owner_id=current_user.id,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Inspiration session not found")
    except Exception as exc:
        logger.error("inspiration_create_failed", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create project")
