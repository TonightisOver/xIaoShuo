"""小说项目管理服务"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.models.db_models import (
    Chapter,
    ChapterVersion,
    Character,
    Novel,
    PowerSystem,
    Task,
    Volume,
    WorldSetting,
)
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


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
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
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

            task_id = None
            if novel.status == "generating":
                task_res = await session.execute(
                    select(Task.task_id)
                    .where(Task.novel_id == novel_id)
                    .order_by(Task.created_at.desc())
                    .limit(1)
                )
                task_id = task_res.scalar_one_or_none()

            data = self._novel_to_dict(novel)
            data["active_task_id"] = task_id
            return data

    async def list_novels(self, novel_type: str | None = None,
                           limit: int = 20, offset: int = 0):
        async with get_db_session() as session:
            latest_task = (
                select(
                    Task.novel_id,
                    Task.task_id,
                    func.row_number()
                    .over(
                        partition_by=Task.novel_id,
                        order_by=Task.created_at.desc(),
                    )
                    .label("rn"),
                )
                .subquery()
            )
            query = select(Novel)
            if novel_type:
                query = query.where(Novel.novel_type == novel_type)

            count_q = select(func.count()).select_from(query.subquery())
            total = (await session.execute(count_q)).scalar_one()

            query = (
                select(Novel, latest_task.c.task_id)
                .outerjoin(
                    latest_task,
                    (latest_task.c.novel_id == Novel.novel_id)
                    & (latest_task.c.rn == 1),
                )
            )
            if novel_type:
                query = query.where(Novel.novel_type == novel_type)
            query = query.order_by(Novel.updated_at.desc()).limit(limit).offset(offset)
            rows = (await session.execute(query)).all()

            summaries = []
            for n, task_id in rows:
                summary = self._novel_summary(n)
                summary["active_task_id"] = task_id if n.status == "generating" else None
                summaries.append(summary)

            return summaries, total

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
            novel.updated_at = datetime.now(UTC)
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
                ws.updated_at = datetime.now(UTC)
            else:
                ws = WorldSetting(novel_id=novel_id, **kwargs,
                                  updated_at=datetime.now(UTC))
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
                             updated_at=datetime.now(UTC))
            session.add(ps)
            await session.flush()
            return ps.id

    async def update_power_system(self, novel_id: str, ps_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(PowerSystem).where(
                    PowerSystem.id == ps_id,
                    PowerSystem.novel_id == novel_id,
                )
            )
            ps = result.scalar_one_or_none()
            if not ps:
                return False
            for k, v in kwargs.items():
                if hasattr(ps, k) and v is not None:
                    setattr(ps, k, v)
            ps.updated_at = datetime.now(UTC)
        return True

    async def delete_power_system(self, novel_id: str, ps_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(PowerSystem).where(
                    PowerSystem.id == ps_id,
                    PowerSystem.novel_id == novel_id,
                )
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

    async def list_chapters_preview(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(
                    Chapter.id,
                    Chapter.chapter_number,
                    Chapter.volume_number,
                    Chapter.title,
                    Chapter.word_count,
                    Chapter.status,
                    Chapter.chapter_type,
                    Chapter.updated_at,
                )
                .where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number)
            )
            return [
                {
                    "id": row.id,
                    "chapter_number": row.chapter_number,
                    "volume_number": row.volume_number,
                    "title": row.title,
                    "word_count": row.word_count,
                    "status": row.status,
                    "chapter_type": row.chapter_type,
                    "updated_at": row.updated_at,
                }
                for row in result.all()
            ]

    async def get_chapter_tail(
        self, novel_id: str, chapter_number: int, tail_chars: int = 500
    ) -> str:
        async with get_db_session() as session:
            result = await session.execute(
                select(func.substr(Chapter.content, -tail_chars))
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .order_by(Chapter.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none() or ""

    async def get_chapter(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number
                ).order_by(Chapter.id.desc()).limit(1)
            )
            c = result.scalar_one_or_none()
            if not c:
                return None
            return {"id": c.id, "novel_id": c.novel_id,
                    "chapter_number": c.chapter_number,
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
                ).order_by(Chapter.id.desc()).limit(1)
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
            ch.updated_at = datetime.now(UTC)
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

    async def delete_failed_chapters(self, novel_id: str, min_words: int = 100) -> int:
        """批量删除 word_count < min_words 的失败章节"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.word_count < min_words,
                )
            )
            failed = result.scalars().all()
            for ch in failed:
                await session.delete(ch)
            return len(failed)

    # --- Chapter Versions ---

    async def create_chapter_version(
        self,
        novel_id: str,
        chapter_number: int,
        content: str,
        source: str = "manual",
        rewrite_instruction: str | None = None,
        quality_score: float | None = None,
        model_name: str | None = None,
        prompt_summary: str | None = None,
        diff_from_previous: str | None = None,
        kg_conflicts: dict | None = None,
        user_notes: str | None = None,
        is_active: bool = False,
    ) -> int:
        """创建章节版本快照，同时更新 Chapter.content 和 Chapter.word_count。

        Returns:
            新版本号 version_number
        """
        async with get_db_session() as session:
            ch_res = await session.execute(
                select(Chapter)
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .with_for_update()
            )
            ch = ch_res.scalar_one_or_none()
            if not ch:
                raise ValueError("Chapter not found")

            max_ver_res = await session.execute(
                select(func.max(ChapterVersion.version_number)).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
            )
            max_ver = max_ver_res.scalar_one_or_none() or 0
            new_version = max_ver + 1

            word_count = len(content)

            version = ChapterVersion(
                novel_id=novel_id,
                chapter_number=chapter_number,
                version_number=new_version,
                content=content,
                word_count=word_count,
                source=source,
                rewrite_instruction=rewrite_instruction,
                quality_score=quality_score,
                model_name=model_name,
                prompt_summary=prompt_summary,
                diff_from_previous=diff_from_previous,
                kg_conflicts=kg_conflicts,
                user_notes=user_notes,
                is_active=is_active,
                created_at=datetime.now(UTC),
            )
            session.add(version)

            if is_active:
                await session.execute(
                    select(ChapterVersion)
                    .where(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                        ChapterVersion.version_number != new_version,
                    )
                )

            ch.content = content
            ch.word_count = word_count
            ch.updated_at = datetime.now(UTC)

            await session.flush()
            return new_version

    async def list_chapter_versions(self, novel_id: str, chapter_number: int) -> list[dict]:
        """返回版本列表（不含 content），按 version_number 降序。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .order_by(ChapterVersion.version_number.desc())
            )
            return [
                {
                    "id": v.id,
                    "version_number": v.version_number,
                    "word_count": v.word_count,
                    "source": v.source,
                    "rewrite_instruction": v.rewrite_instruction,
                    "quality_score": v.quality_score,
                    "model_name": v.model_name,
                    "is_active": v.is_active,
                    "created_at": v.created_at,
                }
                for v in result.scalars().all()
            ]

    async def get_chapter_version(
        self, novel_id: str, chapter_number: int, version_number: int
    ) -> dict | None:
        """返回单个版本完整内容。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                    ChapterVersion.version_number == version_number,
                )
            )
            v = result.scalar_one_or_none()
            if not v:
                return None
            return {
                "id": v.id,
                "version_number": v.version_number,
                "content": v.content,
                "word_count": v.word_count,
                "source": v.source,
                "rewrite_instruction": v.rewrite_instruction,
                "quality_score": v.quality_score,
                "model_name": v.model_name,
                "prompt_summary": v.prompt_summary,
                "diff_from_previous": v.diff_from_previous,
                "kg_conflicts": v.kg_conflicts,
                "user_notes": v.user_notes,
                "is_active": v.is_active,
                "created_at": v.created_at,
            }

    async def rollback_chapter_version(
        self, novel_id: str, chapter_number: int, version_number: int
    ) -> int | None:
        """将指定版本内容写回 Chapter.content，并创建 source=rollback 的新版本。

        Returns:
            新版本号，若目标版本不存在则返回 None
        """
        target = await self.get_chapter_version(novel_id, chapter_number, version_number)
        if not target:
            return None
        new_version = await self.create_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            content=target["content"] or "",
            source="rollback",
            rewrite_instruction=f"回滚自版本 {version_number}",
        )
        return new_version

    async def activate_chapter_version(
        self, novel_id: str, chapter_number: int, version_number: int
    ) -> bool | None:
        """将指定版本设为活跃版本，更新章节正文。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                    ChapterVersion.version_number == version_number,
                )
            )
            target = result.scalar_one_or_none()
            if not target:
                return None

            await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
            )
            for v in (await session.execute(
                select(ChapterVersion).where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
            )).scalars().all():
                v.is_active = (v.version_number == version_number)

            ch_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            ch = ch_res.scalar_one_or_none()
            if ch and target.content:
                ch.content = target.content
                ch.word_count = target.word_count
                ch.updated_at = datetime.now(UTC)

        return True

    async def compare_chapter_versions(
        self, novel_id: str, chapter_number: int, v1: int, v2: int
    ) -> dict | None:
        """对比两个版本，返回两者内容和基本 diff 信息。"""
        ver1 = await self.get_chapter_version(novel_id, chapter_number, v1)
        ver2 = await self.get_chapter_version(novel_id, chapter_number, v2)
        if not ver1 or not ver2:
            return None

        import difflib
        content1 = ver1["content"] or ""
        content2 = ver2["content"] or ""
        diff = list(difflib.unified_diff(
            content1.splitlines(keepends=True),
            content2.splitlines(keepends=True),
            fromfile=f"v{v1}",
            tofile=f"v{v2}",
            lineterm="",
        ))
        return {
            "v1": {"version_number": v1, "word_count": ver1["word_count"], "source": ver1["source"], "created_at": ver1["created_at"]},
            "v2": {"version_number": v2, "word_count": ver2["word_count"], "source": ver2["source"], "created_at": ver2["created_at"]},
            "diff": "\n".join(diff),
            "word_count_change": ver2["word_count"] - ver1["word_count"],
        }

    async def fix_volume_numbers(self, novel_id: str) -> int:
        """根据卷的 chapter_start/chapter_end 为章节补充 volume_number。"""
        volumes = await self.list_volumes(novel_id)
        fixed = 0
        async with get_db_session() as session:
            for vol in volumes:
                ch_start = vol.get("chapter_start")
                ch_end = vol.get("chapter_end")
                vol_num = vol.get("volume_number")
                if ch_start is None or ch_end is None or vol_num is None:
                    continue
                from sqlalchemy import update
                result = await session.execute(
                    update(Chapter)
                    .where(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number >= ch_start,
                        Chapter.chapter_number <= ch_end,
                        Chapter.volume_number.is_(None),
                    )
                    .values(volume_number=vol_num)
                )
                fixed += result.rowcount
        return fixed

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
                         updated_at=datetime.now(UTC))
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
            vol.updated_at = datetime.now(UTC)
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
            "writing_style": novel.writing_style,
            "created_at": novel.created_at,
            "updated_at": novel.updated_at,
        }


_novel_manager: NovelManager | None = None


def get_novel_manager() -> NovelManager:
    global _novel_manager
    if _novel_manager is None:
        _novel_manager = NovelManager()
    return _novel_manager
