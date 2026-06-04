"""LLM 配置管理路由 — CRUD + token 统计"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from src.api.models.db_models import LLMConfig
from src.core.database import get_db_session
from src.core.llm.token_tracker import get_token_tracker
from src.core.security.auth import require_admin

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/llm",
    tags=["llm"],
    dependencies=[Depends(require_admin)],
)


# ---------------------------------------------------------------------------
# Pydantic 模型
# ---------------------------------------------------------------------------


class LLMConfigCreate(BaseModel):
    """创建 LLM 配置请求体"""

    name: str = Field(..., max_length=100)
    base_url: str = Field(..., max_length=500)
    api_key: str = Field(..., max_length=500)
    model_flash: str = Field(..., max_length=100)
    model_pro: str = Field(..., max_length=100)


class LLMConfigUpdate(BaseModel):
    """更新 LLM 配置请求体（所有字段可选）"""

    name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    model_flash: str | None = Field(None, max_length=100)
    model_pro: str | None = Field(None, max_length=100)


class LLMConfigResponse(BaseModel):
    """LLM 配置响应（api_key 脱敏）"""

    id: int
    name: str
    base_url: str
    api_key: str  # 脱敏后的值
    model_flash: str
    model_pro: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _mask_api_key(api_key: str) -> str:
    """脱敏 api_key，仅保留末4位。"""
    if len(api_key) >= 4:
        return "****" + api_key[-4:]
    return "****"


def _to_response(config: LLMConfig) -> LLMConfigResponse:
    return LLMConfigResponse(
        id=config.id,
        name=config.name,
        base_url=config.base_url,
        api_key=_mask_api_key(config.api_key),
        model_flash=config.model_flash,
        model_pro=config.model_pro,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _reload_active_llm_client(config: LLMConfig) -> None:
    """Refresh the process-wide LLM client after the active config changes."""
    import src.core.llm.client as llm_module
    from src.core.llm.client import LLMClient

    llm_module._client = LLMClient(llm_config=config)
    logger.info(
        "llm_client_reloaded_from_config",
        config_id=config.id,
        name=config.name,
    )


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=list[LLMConfigResponse])
async def list_configs() -> list[LLMConfigResponse]:
    """列出所有 LLM 配置（api_key 脱敏）。"""
    async with get_db_session() as session:
        result = await session.execute(select(LLMConfig).order_by(LLMConfig.id))
        configs = result.scalars().all()
    return [_to_response(c) for c in configs]


@router.post("/configs", response_model=LLMConfigResponse, status_code=201)
async def create_config(body: LLMConfigCreate) -> LLMConfigResponse:
    """创建新 LLM 配置。"""
    async with get_db_session() as session:
        config = LLMConfig(
            name=body.name,
            base_url=body.base_url,
            api_key=body.api_key,
            model_flash=body.model_flash,
            model_pro=body.model_pro,
            is_active=False,
        )
        session.add(config)
        await session.flush()
        await session.refresh(config)
        return _to_response(config)


@router.put("/configs/{config_id}", response_model=LLMConfigResponse)
async def update_config(config_id: int, body: LLMConfigUpdate) -> LLMConfigResponse:
    """更新 LLM 配置（部分字段可选）。"""
    reload_config: LLMConfig | None = None
    async with get_db_session() as session:
        result = await session.execute(
            select(LLMConfig).where(LLMConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise HTTPException(status_code=404, detail="配置不存在")

        if body.name is not None:
            config.name = body.name
        if body.base_url is not None:
            config.base_url = body.base_url
        if body.api_key is not None:
            config.api_key = body.api_key
        if body.model_flash is not None:
            config.model_flash = body.model_flash
        if body.model_pro is not None:
            config.model_pro = body.model_pro

        await session.flush()
        await session.refresh(config)
        if config.is_active:
            reload_config = config
        response = _to_response(config)
    if reload_config:
        _reload_active_llm_client(reload_config)
    return response


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(config_id: int) -> None:
    """删除 LLM 配置。若为激活配置则拒绝删除（返回 400）。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(LLMConfig).where(LLMConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise HTTPException(status_code=404, detail="配置不存在")
        if config.is_active:
            raise HTTPException(
                status_code=400, detail="无法删除当前激活的配置，请先激活其他配置"
            )
        await session.delete(config)


@router.post("/configs/{config_id}/activate", response_model=LLMConfigResponse)
async def activate_config(config_id: int) -> LLMConfigResponse:
    """激活指定配置，同时将其他配置设为非激活（事务保证）。"""
    reload_config: LLMConfig | None = None
    async with get_db_session() as session:
        result = await session.execute(
            select(LLMConfig).where(LLMConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise HTTPException(status_code=404, detail="配置不存在")

        # 将所有配置设为非激活
        await session.execute(
            update(LLMConfig).values(is_active=False)
        )
        # 激活目标配置
        config.is_active = True

        await session.flush()
        await session.refresh(config)
        reload_config = config
        response = _to_response(config)
    if reload_config:
        _reload_active_llm_client(reload_config)
    return response


@router.get("/token-stats")
async def get_token_stats() -> dict[str, Any]:
    """返回 token 用量统计数据。"""
    return get_token_tracker().get_stats()
