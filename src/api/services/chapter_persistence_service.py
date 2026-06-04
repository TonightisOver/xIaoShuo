"""章节持久化服务

负责将生成结果（LangGraph pipeline / 长篇生成）写入数据库。
从 novel_generator.py 中提取，保持接口稳定。
"""

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def persist_langgraph_result(
    novel_id: str, result: dict[str, Any], *, manager=None
) -> None:
    """Persist LangGraph result into novel sub-tables.

    Handles: world_setting, characters, volumes, chapters, version records.

    Args:
        novel_id: Novel ID
        result: LangGraph pipeline result dict
        manager: Optional novel_manager instance (for testability)
    """
    from sqlalchemy import delete

    from src.api.models.db_models import Chapter
    from src.core.database import get_db_session

    if manager is None:
        from src.api.services.novel_manager import get_novel_manager
        manager = get_novel_manager()

    try:
        # World setting
        ws = result.get("world_setting")
        if ws and isinstance(ws, dict):
            await manager.upsert_world_setting(
                novel_id,
                background=ws.get("background") or ws.get("世界背景"),
                geography=ws.get("geography") or ws.get("地理环境"),
                culture=ws.get("culture") or ws.get("文化体系"),
                rules=ws.get("rules") or ws.get("世界规则"),
                extra={
                    k: v
                    for k, v in ws.items()
                    if k
                    not in (
                        "background", "geography", "culture", "rules",
                        "世界背景", "地理环境", "文化体系", "世界规则",
                    )
                },
            )

        # Characters (upsert: update existing by name, insert new)
        characters = result.get("characters", [])
        for char in characters:
            if isinstance(char, dict) and char.get("name"):
                char_data = dict(
                    name=char.get("name", ""),
                    role=char.get("role") or char.get("角色"),
                    description=char.get("description") or char.get("描述"),
                    personality=char.get("personality") or char.get("性格"),
                    abilities=char.get("abilities") or char.get("能力"),
                    background_story=char.get("background_story") or char.get("背景"),
                )
                existing = await manager.get_character_by_name(novel_id, char_data["name"])
                if existing:
                    await manager.update_character(novel_id, existing["id"], **char_data)
                else:
                    await manager.create_character(novel_id, **char_data)

        # Volumes
        volumes = result.get("volumes", [])
        for vol in volumes:
            if isinstance(vol, dict):
                vol_chapters = vol.get("chapters", [])
                ch_start = vol_chapters[0].get("chapter", 1) if vol_chapters else None
                ch_end = vol_chapters[-1].get("chapter", 1) if vol_chapters else None
                await manager.create_volume(
                    novel_id,
                    volume_number=vol.get("volume_number", 1),
                    title=vol.get("title"),
                    summary=vol.get("summary"),
                    outline=vol,
                    chapter_start=ch_start,
                    chapter_end=ch_end,
                )

        # Chapters
        chapters = result.get("chapters", [])
        async with get_db_session() as session:
            for ch in chapters:
                if isinstance(ch, dict):
                    ch_num = ch.get("chapter", 0)
                    if hasattr(Chapter, "__table__"):
                        await session.execute(
                            delete(Chapter).where(
                                Chapter.novel_id == novel_id,
                                Chapter.chapter_number == ch_num,
                            )
                        )
                    chapter = Chapter(
                        novel_id=novel_id,
                        volume_number=ch.get("volume_number"),
                        chapter_number=ch_num,
                        title=ch.get("title", ""),
                        content=ch.get("content", ""),
                        word_count=ch.get("word_count", 0),
                        status="generated",
                        updated_at=datetime.now(UTC),
                    )
                    session.add(chapter)

        # 补充可能遗漏的 volume_number
        await manager.fix_volume_numbers(novel_id)

        # Auto-create version records for generated chapters
        for ch in chapters:
            if isinstance(ch, dict) and ch.get("content"):
                try:
                    await manager.create_chapter_version(
                        novel_id=novel_id,
                        chapter_number=ch.get("chapter", 0),
                        content=ch.get("content", ""),
                        source="generation",
                        model_name="deepseek",
                        is_active=True,
                    )
                except (ValueError, Exception):
                    pass

        # Update novel status
        await manager.update_novel(novel_id, status="completed")

        logger.info("persist_results_completed", novel_id=novel_id)

    except Exception as e:
        logger.error("persist_results_failed", novel_id=novel_id, error=str(e))
        from src.core.exceptions import PersistenceError

        raise PersistenceError(
            f"Failed to persist langgraph result for {novel_id}: {e}"
        ) from e


async def persist_generated_chapters(
    novel_id: str,
    chapters: list[dict[str, Any]],
    volume_number: int | None = None,
    *,
    status: str = "generated",
) -> None:
    """Persist a list of generated chapters to the DB.

    Used by generate_volume_background and _generate_volume_chapters.
    """
    from src.api.models.db_models import Chapter
    from src.core.database import get_db_session

    async with get_db_session() as session:
        for ch in chapters:
            chapter = Chapter(
                novel_id=novel_id,
                volume_number=volume_number or ch.get("volume_number"),
                chapter_number=ch["chapter"],
                title=ch["title"],
                content=ch["content"],
                word_count=ch["word_count"],
                chapter_type=ch.get("chapter_type"),
                status=status,
            )
            session.add(chapter)


async def persist_chapters_with_replace(
    novel_id: str,
    chapters: list[dict[str, Any]],
    volumes: list[dict[str, Any]],
    *,
    status: str = "regenerated",
) -> None:
    """Delete existing chapters and persist new ones.

    Used by generate_chapters_background.
    Also creates version records and updates StoryBible.
    """
    from sqlalchemy import delete

    from src.api.models.db_models import Chapter
    from src.api.services.novel_manager import get_novel_manager
    from src.core.database import get_db_session

    manager = get_novel_manager()

    def _find_volume_number(ch_num: int) -> int | None:
        for vol in volumes:
            outline = vol.get("outline") or {}
            for ch in outline.get("chapters", []):
                if ch.get("chapter") == ch_num:
                    return vol.get("volume_number")
        for vol in volumes:
            ch_start = vol.get("chapter_start")
            ch_end = vol.get("chapter_end")
            if ch_start is not None and ch_end is not None:
                if ch_start <= ch_num <= ch_end:
                    return vol.get("volume_number")
        return None

    successful_chapters = [
        ch for ch in chapters if ch.get("content") and ch.get("word_count", 0) > 0
    ]

    async with get_db_session() as session:
        for ch in successful_chapters:
            await session.execute(
                delete(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == ch["chapter"],
                )
            )
            chapter = Chapter(
                novel_id=novel_id,
                chapter_number=ch["chapter"],
                volume_number=_find_volume_number(ch["chapter"]),
                title=ch["title"],
                content=ch["content"],
                word_count=ch["word_count"],
                status=status,
            )
            session.add(chapter)

    # 补充可能遗漏的 volume_number
    await manager.fix_volume_numbers(novel_id)

    # Auto-create version records
    for ch in successful_chapters:
        if ch.get("content"):
            try:
                await manager.create_chapter_version(
                    novel_id=novel_id,
                    chapter_number=ch["chapter"],
                    content=ch["content"],
                    source="generation",
                    model_name="deepseek",
                    is_active=True,
                )
            except (ValueError, Exception):
                pass

    # 反向更新 StoryBible
    for ch in successful_chapters:
        if ch.get("content"):
            try:
                from src.api.services.story_bible_service import (
                    update_bible_after_generation,
                )

                await update_bible_after_generation(
                    novel_id=novel_id,
                    chapter_number=ch["chapter"],
                    chapter_content=ch["content"],
                    chapter_outline=ch,
                )
            except Exception as e:
                logger.warning(
                    "story_bible_update_failed chapter=%s: %s", ch.get("chapter"), e
                )


async def persist_quality_to_version(
    novel_id: str,
    chapter_number: int,
    quality_scores: dict,
    consistency_warnings: list,
) -> None:
    """将质量评分回写到章节的活跃版本记录"""
    try:
        from sqlalchemy import and_, select

        from src.api.models.db_models import ChapterVersion
        from src.core.database import get_db_session

        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterVersion).where(
                    and_(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                        ChapterVersion.is_active.is_(True),
                    )
                )
            )
            version = result.scalar_one_or_none()
            if version:
                version.quality_score = quality_scores.get("overall")
                version.kg_conflicts = consistency_warnings or None
                await session.commit()
                logger.info(
                    "persisted_quality_score",
                    quality_score=version.quality_score,
                    chapter=chapter_number,
                    version=version.version_number,
                )
    except Exception as e:
        logger.warning("persist_quality_score_failed", error=str(e))
