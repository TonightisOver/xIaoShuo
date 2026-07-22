"""角色管理服务"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from src.api.models.db_models import Character
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class CharacterService:

    async def list_characters(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Character).where(Character.novel_id == novel_id)
            )
            return [{"id": c.id, "name": c.name, "role": c.role,
                     "description": c.description, "personality": c.personality,
                     "abilities": c.abilities, "background_story": c.background_story,
                     "extra": c.extra, "updated_at": c.updated_at}
                    for c in result.scalars().all()]

    async def create_character(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            from src.core.creative_control.control_service import (
                assert_generation_write_allowed_in_session,
                has_generation_fence,
            )

            await assert_generation_write_allowed_in_session(
                session, novel_id, "character", str(kwargs.get("name") or "new")
            )
            if has_generation_fence() and kwargs.get("name"):
                existing = (
                    await session.execute(
                        select(Character)
                        .where(
                            Character.novel_id == novel_id,
                            Character.name == kwargs["name"],
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    for key, value in kwargs.items():
                        if hasattr(existing, key) and value is not None:
                            setattr(existing, key, value)
                    existing.updated_at = datetime.now(UTC)
                    return existing.id
            char = Character(novel_id=novel_id, **kwargs,
                             updated_at=datetime.now(UTC))
            session.add(char)
            await session.flush()
            return char.id

    async def get_character_by_name(self, novel_id: str, name: str) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Character).where(
                    Character.novel_id == novel_id,
                    Character.name == name,
                )
            )
            char = result.scalar_one_or_none()
            if not char:
                return None
            return {"id": char.id, "name": char.name, "role": char.role,
                    "description": char.description, "personality": char.personality,
                    "abilities": char.abilities, "background_story": char.background_story}

    async def update_character(self, novel_id: str, char_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            from src.core.creative_control.control_service import (
                assert_generation_write_allowed_in_session,
            )

            await assert_generation_write_allowed_in_session(
                session, novel_id, "character", str(char_id)
            )
            result = await session.execute(
                select(Character).where(
                    Character.id == char_id,
                    Character.novel_id == novel_id,
                )
            )
            char = result.scalar_one_or_none()
            if not char:
                return False
            for k, v in kwargs.items():
                if hasattr(char, k) and v is not None:
                    setattr(char, k, v)
            char.updated_at = datetime.now(UTC)
        return True

    async def delete_character(self, novel_id: str, char_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Character).where(
                    Character.id == char_id,
                    Character.novel_id == novel_id,
                )
            )
            char = result.scalar_one_or_none()
            if not char:
                return False
            await session.delete(char)
        return True


_character_service: CharacterService | None = None


def get_character_service() -> CharacterService:
    global _character_service
    if _character_service is None:
        _character_service = CharacterService()
    return _character_service
