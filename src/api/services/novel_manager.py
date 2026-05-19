"""小说项目管理服务"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.models.db_models import (
    Chapter,
    Character,
    Novel,
    PowerSystem,
    Volume,
    WorldSetting,
)
from src.core.database import get_db_session

logger = logging.getLogger(__name__)


class NovelManager:

    async def create_novel(self, idea: str, novel_type: str, target_words: int,
                           title: str | None = None,
                           writing_style: str = "现代白话",
                           custom_style_description: str | None = None,
                           writing_style_prompt: str | None = None) -> str:
        novel_id = f"novel-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
        async with get_db_session() as session:
            novel = Novel(
                novel_id=novel_id,
                title=title or idea[:50],
                idea=idea,
                novel_type=novel_type,
                target_words=target_words,
                writing_style=writing_style,
                custom_style_description=custom_style_description,
                writing_style_prompt=writing_style_prompt,
                status="draft",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(novel)
        logger.info(f"Created novel {novel_id}")
        return novel_id

    async def get_novel(self, novel_id: str) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Novel)
                .options(
                    selectinload(Novel.world_setting),
                    selectinload(Novel.characters),
                    selectinload(Novel.power_systems),
                )
                .where(Novel.novel_id == novel_id)
            )
            novel = result.scalar_one_or_none()
            if not novel:
                return None
            return self._novel_to_dict(novel)

    async def list_novels(self, novel_type: str | None = None,
                          limit: int = 20, offset: int = 0):
        # No N+1 issue here: _novel_summary() only accesses scalar columns on Novel
        # itself and does not traverse any relationship, so no lazy-load is triggered.
        async with get_db_session() as session:
            query = select(Novel)
            if novel_type:
                query = query.where(Novel.novel_type == novel_type)

            count_q = select(func.count()).select_from(query.subquery())
            total = (await session.execute(count_q)).scalar_one()

            query = query.order_by(Novel.updated_at.desc()).limit(limit).offset(offset)
            novels = (await session.execute(query)).scalars().all()

            return [self._novel_summary(n) for n in novels], total

    async def update_novel(self, novel_id: str, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Novel).where(Novel.novel_id == novel_id)
            )
            novel = result.scalar_one_or_none()
            if not novel:
                return False
            for key, value in kwargs.items():
                if hasattr(novel, key) and value is not None:
                    setattr(novel, key, value)
            novel.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_novel(self, novel_id: str) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Novel).where(Novel.novel_id == novel_id)
            )
            novel = result.scalar_one_or_none()
            if not novel:
                return False
            await session.delete(novel)
        return True

    # --- World Setting ---

    async def get_world_setting(self, novel_id: str) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(WorldSetting).where(WorldSetting.novel_id == novel_id)
            )
            ws = result.scalar_one_or_none()
            if not ws:
                return None
            return {
                "novel_id": ws.novel_id,
                "background": ws.background,
                "geography": ws.geography,
                "culture": ws.culture,
                "rules": ws.rules,
                "extra": ws.extra,
                "updated_at": ws.updated_at,
            }

    async def upsert_world_setting(self, novel_id: str, **kwargs) -> None:
        async with get_db_session() as session:
            result = await session.execute(
                select(WorldSetting).where(WorldSetting.novel_id == novel_id)
            )
            ws = result.scalar_one_or_none()
            if ws:
                for k, v in kwargs.items():
                    if hasattr(ws, k):
                        setattr(ws, k, v)
                ws.updated_at = datetime.now(timezone.utc)
            else:
                ws = WorldSetting(novel_id=novel_id, **kwargs,
                                  updated_at=datetime.now(timezone.utc))
                session.add(ws)

    # --- Power Systems ---

    async def list_power_systems(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(PowerSystem).where(PowerSystem.novel_id == novel_id)
            )
            return [{"id": p.id, "name": p.name, "description": p.description,
                     "levels": p.levels, "updated_at": p.updated_at}
                    for p in result.scalars().all()]

    async def create_power_system(self, novel_id: str, name: str,
                                  description: str | None = None,
                                  levels: list | None = None) -> int:
        async with get_db_session() as session:
            ps = PowerSystem(novel_id=novel_id, name=name,
                             description=description, levels=levels or [],
                             updated_at=datetime.now(timezone.utc))
            session.add(ps)
            await session.flush()
            return ps.id

    async def update_power_system(self, ps_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(PowerSystem).where(PowerSystem.id == ps_id)
            )
            ps = result.scalar_one_or_none()
            if not ps:
                return False
            for k, v in kwargs.items():
                if hasattr(ps, k) and v is not None:
                    setattr(ps, k, v)
            ps.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_power_system(self, ps_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(PowerSystem).where(PowerSystem.id == ps_id)
            )
            ps = result.scalar_one_or_none()
            if not ps:
                return False
            await session.delete(ps)
        return True

    # --- Characters ---

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
            char = Character(novel_id=novel_id, **kwargs,
                             updated_at=datetime.now(timezone.utc))
            session.add(char)
            await session.flush()
            return char.id

    async def update_character(self, char_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Character).where(Character.id == char_id)
            )
            char = result.scalar_one_or_none()
            if not char:
                return False
            for k, v in kwargs.items():
                if hasattr(char, k) and v is not None:
                    setattr(char, k, v)
            char.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_character(self, char_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Character).where(Character.id == char_id)
            )
            char = result.scalar_one_or_none()
            if not char:
                return False
            await session.delete(char)
        return True

    # --- Chapters ---

    async def list_chapters(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number)
            )
            return [{"id": c.id, "chapter_number": c.chapter_number,
                     "volume_number": c.volume_number,
                     "title": c.title, "content": c.content,
                     "word_count": c.word_count, "status": c.status,
                     "updated_at": c.updated_at}
                    for c in result.scalars().all()]

    async def get_chapter(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            c = result.scalar_one_or_none()
            if not c:
                return None
            return {"id": c.id, "chapter_number": c.chapter_number,
                    "volume_number": c.volume_number,
                    "title": c.title, "content": c.content,
                    "word_count": c.word_count, "status": c.status,
                    "updated_at": c.updated_at}

    async def update_chapter(self, novel_id: str, chapter_number: int,
                             **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            for k, v in kwargs.items():
                if hasattr(ch, k) and v is not None:
                    setattr(ch, k, v)
            if "content" in kwargs and kwargs["content"]:
                ch.word_count = len(kwargs["content"])
            ch.status = "edited"
            ch.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_chapter(self, novel_id: str, chapter_number: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                )
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            await session.delete(ch)
        return True

    # --- Volumes ---

    async def list_volumes(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume).where(Volume.novel_id == novel_id)
                .order_by(Volume.volume_number)
            )
            return [{"id": v.id, "volume_number": v.volume_number,
                     "title": v.title, "summary": v.summary,
                     "outline": v.outline, "status": v.status,
                     "chapter_start": v.chapter_start, "chapter_end": v.chapter_end,
                     "updated_at": v.updated_at}
                    for v in result.scalars().all()]

    async def get_volume(self, novel_id: str, volume_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume).where(
                    Volume.novel_id == novel_id,
                    Volume.volume_number == volume_number
                )
            )
            v = result.scalar_one_or_none()
            if not v:
                return None
            return {"id": v.id, "volume_number": v.volume_number,
                    "title": v.title, "summary": v.summary,
                    "outline": v.outline, "status": v.status,
                    "chapter_start": v.chapter_start, "chapter_end": v.chapter_end,
                    "updated_at": v.updated_at}

    async def create_volume(self, novel_id: str, volume_number: int,
                            title: str | None = None, summary: str | None = None,
                            outline: dict | None = None,
                            chapter_start: int | None = None,
                            chapter_end: int | None = None) -> int:
        async with get_db_session() as session:
            vol = Volume(novel_id=novel_id, volume_number=volume_number,
                         title=title, summary=summary, outline=outline,
                         chapter_start=chapter_start, chapter_end=chapter_end,
                         updated_at=datetime.now(timezone.utc))
            session.add(vol)
            await session.flush()
            return vol.id

    async def update_volume(self, novel_id: str, volume_number: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume).where(
                    Volume.novel_id == novel_id,
                    Volume.volume_number == volume_number
                )
            )
            vol = result.scalar_one_or_none()
            if not vol:
                return False
            for k, v in kwargs.items():
                if hasattr(vol, k) and v is not None:
                    setattr(vol, k, v)
            vol.updated_at = datetime.now(timezone.utc)
        return True

    # --- Helpers ---

    def _novel_to_dict(self, novel: Novel) -> dict:
        return {
            "novel_id": novel.novel_id,
            "title": novel.title,
            "idea": novel.idea,
            "novel_type": novel.novel_type,
            "target_words": novel.target_words,
            "writing_style": novel.writing_style,
            "custom_style_description": novel.custom_style_description,
            "writing_style_prompt": novel.writing_style_prompt,
            "status": novel.status,
            "created_at": novel.created_at,
            "updated_at": novel.updated_at,
            "completed_at": novel.completed_at,
            "world_setting": bool(novel.world_setting),
            "characters_count": len(novel.characters),
            "power_systems_count": len(novel.power_systems),
        }

    def _novel_summary(self, novel: Novel) -> dict:
        return {
            "novel_id": novel.novel_id,
            "title": novel.title,
            "novel_type": novel.novel_type,
            "status": novel.status,
            "target_words": novel.target_words,
            "created_at": novel.created_at,
            "updated_at": novel.updated_at,
        }


_novel_manager: NovelManager | None = None


def get_novel_manager() -> NovelManager:
    global _novel_manager
    if _novel_manager is None:
        _novel_manager = NovelManager()
    return _novel_manager
