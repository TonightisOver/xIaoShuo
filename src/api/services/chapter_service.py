"""章节管理服务"""

import difflib
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update

from src.api.models.db_models import Chapter, ChapterVersion
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class ChapterService:
    """章节（Chapter）的 CRUD 及版本管理"""

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
        """创建章节版本快照，同时更新 Chapter.content 和 Chapter.word_count。"""
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
        """将指定版本内容写回 Chapter.content，并创建 source=rollback 的新版本。"""
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
        from src.api.services.volume_service import get_volume_service
        svc = get_volume_service()
        volumes = await svc.list_volumes(novel_id)
        fixed = 0
        async with get_db_session() as session:
            for vol in volumes:
                ch_start = vol.get("chapter_start")
                ch_end = vol.get("chapter_end")
                vol_num = vol.get("volume_number")
                if ch_start is None or ch_end is None or vol_num is None:
                    continue
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


_chapter_service: ChapterService | None = None


def get_chapter_service() -> ChapterService:
    global _chapter_service
    if _chapter_service is None:
        _chapter_service = ChapterService()
    return _chapter_service
