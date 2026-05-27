"""故事线/人物弧光/场景管理服务"""

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import (
    CharacterArc,
    Scene,
    Storyline,
    StorylineCharacter,
)
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class StorylineService:

    # --- Storylines ---

    async def list_storylines(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Storyline).where(Storyline.novel_id == novel_id)
            )
            return [{"id": s.id, "name": s.name, "type": s.type,
                     "description": s.description, "key_events": s.key_events,
                     "status": s.status} for s in result.scalars().all()]

    async def create_storyline(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            sl = Storyline(novel_id=novel_id, **kwargs,
                           updated_at=datetime.now(UTC))
            session.add(sl)
            await session.flush()
            return sl.id

    async def update_storyline(self, sl_id: int, novel_id: str, **kwargs) -> bool:
        async with get_db_session() as session:
            query = select(Storyline).where(
                Storyline.id == sl_id, Storyline.novel_id == novel_id
            )
            result = await session.execute(query)
            sl = result.scalar_one_or_none()
            if not sl:
                return False
            for k, v in kwargs.items():
                if hasattr(sl, k) and v is not None:
                    setattr(sl, k, v)
            sl.updated_at = datetime.now(UTC)
        return True

    async def delete_storyline(self, sl_id: int, novel_id: str) -> bool:
        async with get_db_session() as session:
            query = select(Storyline).where(
                Storyline.id == sl_id, Storyline.novel_id == novel_id
            )
            result = await session.execute(query)
            sl = result.scalar_one_or_none()
            if not sl:
                return False
            await session.delete(sl)
        return True

    # --- Character Arcs ---

    async def list_character_arcs(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(CharacterArc).where(CharacterArc.novel_id == novel_id)
            )
            return [{"id": a.id, "character_id": a.character_id,
                     "arc_type": a.arc_type, "description": a.description,
                     "stages": a.stages} for a in result.scalars().all()]

    async def create_character_arc(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            arc = CharacterArc(novel_id=novel_id, **kwargs,
                               updated_at=datetime.now(UTC))
            session.add(arc)
            await session.flush()
            return arc.id

    async def update_character_arc(self, arc_id: int, novel_id: str, **kwargs) -> bool:
        async with get_db_session() as session:
            query = select(CharacterArc).where(
                CharacterArc.id == arc_id, CharacterArc.novel_id == novel_id
            )
            result = await session.execute(query)
            arc = result.scalar_one_or_none()
            if not arc:
                return False
            for k, v in kwargs.items():
                if hasattr(arc, k) and v is not None:
                    setattr(arc, k, v)
            arc.updated_at = datetime.now(UTC)
        return True

    async def delete_character_arc(self, arc_id: int, novel_id: str) -> bool:
        async with get_db_session() as session:
            query = select(CharacterArc).where(
                CharacterArc.id == arc_id, CharacterArc.novel_id == novel_id
            )
            result = await session.execute(query)
            arc = result.scalar_one_or_none()
            if not arc:
                return False
            await session.delete(arc)
        return True

    # --- Scenes ---

    async def list_scenes(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Scene).where(Scene.novel_id == novel_id)
            )
            return [{"id": s.id, "name": s.name, "location": s.location,
                     "description": s.description, "appearances": s.appearances}
                    for s in result.scalars().all()]

    async def create_scene(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            scene = Scene(novel_id=novel_id, **kwargs,
                          updated_at=datetime.now(UTC))
            session.add(scene)
            await session.flush()
            return scene.id

    async def update_scene(self, scene_id: int, novel_id: str, **kwargs) -> bool:
        async with get_db_session() as session:
            query = select(Scene).where(
                Scene.id == scene_id, Scene.novel_id == novel_id
            )
            result = await session.execute(query)
            scene = result.scalar_one_or_none()
            if not scene:
                return False
            for k, v in kwargs.items():
                if hasattr(scene, k) and v is not None:
                    setattr(scene, k, v)
            scene.updated_at = datetime.now(UTC)
        return True

    async def delete_scene(self, scene_id: int, novel_id: str) -> bool:
        async with get_db_session() as session:
            query = select(Scene).where(
                Scene.id == scene_id, Scene.novel_id == novel_id
            )
            result = await session.execute(query)
            scene = result.scalar_one_or_none()
            if not scene:
                return False
            await session.delete(scene)
        return True

    # --- Relations ---

    async def add_character_to_storyline(self, storyline_id: int,
                                         character_id: int, novel_id: str,
                                         role: str | None = None) -> None:
        async with get_db_session() as session:
            sl = await session.get(Storyline, storyline_id)
            if not sl or sl.novel_id != novel_id:
                raise ValueError("故事线不存在或不属于该小说")
            sc = StorylineCharacter(
                storyline_id=storyline_id,
                character_id=character_id,
                role_in_line=role,
            )
            session.add(sc)

    async def get_relations(self, novel_id: str) -> dict[str, Any]:
        storylines = await self.list_storylines(novel_id)
        arcs = await self.list_character_arcs(novel_id)
        scenes = await self.list_scenes(novel_id)

        # Get storyline-character links filtered by novel via JOIN
        async with get_db_session() as session:
            result = await session.execute(
                select(StorylineCharacter)
                .join(Storyline, StorylineCharacter.storyline_id == Storyline.id)
                .where(Storyline.novel_id == novel_id)
            )
            links = [{"storyline_id": sc.storyline_id, "character_id": sc.character_id,
                      "role_in_line": sc.role_in_line} for sc in result.scalars().all()]

        return {
            "storylines": storylines,
            "character_arcs": arcs,
            "scenes": scenes,
            "storyline_character_links": links,
        }


_storyline_service: StorylineService | None = None


def get_storyline_service() -> StorylineService:
    global _storyline_service
    if _storyline_service is None:
        _storyline_service = StorylineService()
    return _storyline_service
