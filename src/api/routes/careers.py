"""Career system API routes."""

from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.models.db_models import (
    CareerSystem,
    Character,
    CharacterCareer,
    Novel,
)
from src.api.services.career_service import generate_career_system
from src.core.database import get_db_session
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["careers"])


class CareerGenerateRequest(BaseModel):
    main_count: int = Field(default=2, ge=1, le=5)
    sub_count: int = Field(default=6, ge=0, le=12)


class CareerUpdateRequest(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    stages: list[dict] | None = None
    max_stage: int | None = None
    requirements: str | None = None
    special_abilities: str | None = None
    worldview_rules: str | None = None
    attribute_bonuses: dict[str, Any] | None = None


class AssignCareerRequest(BaseModel):
    career_id: int
    current_stage: int = Field(default=1, ge=1)


def _career_to_dict(career: CareerSystem) -> dict[str, Any]:
    return {
        "id": career.id,
        "novel_id": career.novel_id,
        "name": career.name,
        "category": career.category,
        "description": career.description,
        "stages": career.stages,
        "max_stage": career.max_stage,
        "requirements": career.requirements,
        "special_abilities": career.special_abilities,
        "worldview_rules": career.worldview_rules,
        "attribute_bonuses": career.attribute_bonuses,
        "updated_at": career.updated_at,
    }


async def _get_project_context(novel_id: str) -> dict[str, Any] | None:
    async with get_db_session() as session:
        result = await session.execute(
            select(Novel)
            .options(selectinload(Novel.world_setting))
            .where(Novel.novel_id == novel_id)
        )
        novel = result.scalar_one_or_none()
        if not novel:
            return None
        world = novel.world_setting
        world_parts = []
        if world:
            if world.background:
                world_parts.append(f"背景：{world.background}")
            if world.geography:
                world_parts.append(f"地理：{world.geography}")
            if world.culture:
                world_parts.append(f"文化：{world.culture}")
            if world.rules:
                world_parts.append(f"规则：{world.rules}")
        return {
            "novel_id": novel.novel_id,
            "title": novel.title,
            "idea": novel.idea,
            "novel_type": novel.novel_type,
            "world_context": "\n".join(world_parts),
        }


@router.post("/{novel_id}/careers/generate", status_code=201)
async def generate_careers(
    novel_id: str, request: CareerGenerateRequest | None = None
):
    request = request or CareerGenerateRequest()
    project_context = await _get_project_context(novel_id)
    if not project_context:
        raise HTTPException(status_code=404, detail="Novel not found")

    try:
        careers = await generate_career_system(
            get_llm_client(),
            project_context,
            main_count=request.main_count,
            sub_count=request.sub_count,
        )
    except Exception as e:
        logger.error("career_generation_failed", novel_id=novel_id, error=str(e))
        raise HTTPException(status_code=500, detail="Career generation failed")

    created = []
    async with get_db_session() as session:
        for data in careers:
            if not data.get("name"):
                continue
            career = CareerSystem(
                novel_id=novel_id,
                name=data["name"],
                category=data.get("category", "sub"),
                description=data.get("description"),
                stages=data.get("stages") or [],
                max_stage=data.get("max_stage"),
                requirements=data.get("requirements"),
                special_abilities=data.get("special_abilities"),
                worldview_rules=data.get("worldview_rules"),
                attribute_bonuses=data.get("attribute_bonuses") or {},
                updated_at=datetime.now(UTC),
            )
            session.add(career)
            await session.flush()
            created.append(_career_to_dict(career))

    return created


@router.get("/{novel_id}/careers")
async def list_careers(novel_id: str):
    async with get_db_session() as session:
        novel_result = await session.execute(
            select(Novel.novel_id).where(Novel.novel_id == novel_id)
        )
        if not novel_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Novel not found")

        result = await session.execute(
            select(CareerSystem)
            .where(CareerSystem.novel_id == novel_id)
            .order_by(CareerSystem.category, CareerSystem.id)
        )
        return [_career_to_dict(career) for career in result.scalars().all()]


@router.put("/{novel_id}/careers/{career_id}")
async def update_career(
    novel_id: str, career_id: int, request: CareerUpdateRequest
):
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    async with get_db_session() as session:
        result = await session.execute(
            select(CareerSystem).where(
                CareerSystem.id == career_id,
                CareerSystem.novel_id == novel_id,
            )
        )
        career = result.scalar_one_or_none()
        if not career:
            raise HTTPException(status_code=404, detail="Career not found")

        for key, value in updates.items():
            setattr(career, key, value)
        career.updated_at = datetime.now(UTC)
        await session.flush()
        return {"status": "updated"}


@router.post("/{novel_id}/characters/{char_id}/careers", status_code=201)
async def assign_character_career(
    novel_id: str, char_id: int, request: AssignCareerRequest
):
    async with get_db_session() as session:
        char_result = await session.execute(
            select(Character).where(
                Character.id == char_id,
                Character.novel_id == novel_id,
            )
        )
        character = char_result.scalar_one_or_none()
        if not character:
            raise HTTPException(status_code=404, detail="Character not found")

        career_result = await session.execute(
            select(CareerSystem).where(
                CareerSystem.id == request.career_id,
                CareerSystem.novel_id == novel_id,
            )
        )
        career = career_result.scalar_one_or_none()
        if not career:
            raise HTTPException(status_code=404, detail="Career not found")
        if career.max_stage is not None and request.current_stage > career.max_stage:
            raise HTTPException(
                status_code=400, detail="current_stage exceeds max_stage"
            )

        existing_result = await session.execute(
            select(CharacterCareer).where(
                CharacterCareer.character_id == char_id,
                CharacterCareer.career_id == request.career_id,
            )
        )
        character_career = existing_result.scalar_one_or_none()
        if character_career:
            character_career.current_stage = request.current_stage
            character_career.updated_at = datetime.now(UTC)
            status = "updated"
        else:
            character_career = CharacterCareer(
                character_id=char_id,
                career_id=request.career_id,
                current_stage=request.current_stage,
                updated_at=datetime.now(UTC),
            )
            session.add(character_career)
            status = "created"

        await session.flush()
        return {
            "id": character_career.id,
            "character_id": char_id,
            "career_id": request.career_id,
            "current_stage": character_career.current_stage,
            "status": status,
        }
