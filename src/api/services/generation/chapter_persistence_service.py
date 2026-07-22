"""章节持久化服务

负责将生成结果（LangGraph pipeline / 长篇生成）写入数据库。
从 novel_generator.py 中提取，保持接口稳定。
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from src.core.creative_control.contracts import (
    ARTIFACT_TYPES,
    ASSISTED_REVIEW_STAGES,
    stage_of,
)

logger = structlog.get_logger(__name__)


async def _record_artifact_generated(
    novel_id: str,
    artifact_type: str,
    artifact_id: str,
    *,
    generation_meta: dict | None = None,
) -> None:
    """生成路径落库后回写 Creative Control 元数据（best-effort，不破坏生成）。

    按 Novel.creation_mode 决定 awaiting_review：
    - auto：不置标记（连续生成 = 现状）
    - assisted：关键阶段（1/4/7/9）置 awaiting_review
    - manual：所有阶段置 awaiting_review
    任何异常被 CreativeControlService.record_generated 内部吞掉，此处不再 try。
    """
    if artifact_type not in ARTIFACT_TYPES:
        return
    try:
        from src.api.services.content.novel_manager import get_novel_manager
        from src.core.creative_control.control_service import CreativeControlService

        novel = await get_novel_manager().get_novel(novel_id)
        mode = (novel or {}).get("creation_mode", "auto")
        awaiting = False
        if mode == "manual":
            awaiting = True
        elif mode == "assisted":
            awaiting = stage_of(artifact_type) in ASSISTED_REVIEW_STAGES
        await CreativeControlService().record_generated(
            novel_id, artifact_type, artifact_id,
            generation_meta=generation_meta, awaiting_review=awaiting,
        )
    except Exception:  # noqa: BLE001 - 插桩绝不破坏生成
        logger.warning(
            "creative_control_instrumentation_failed",
            novel_id=novel_id, artifact_type=artifact_type,
            artifact_id=artifact_id,
        )


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
    from sqlalchemy import select

    from src.api.models.db_models import Chapter
    from src.core.creative_control.control_service import (
        CreativeControlService,
        current_generation_task_id,
    )
    from src.core.database import get_db_session
    from src.core.exceptions import LeaseLost

    if manager is None:
        from src.api.services.content.novel_manager import get_novel_manager
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
            await _record_artifact_generated(
                novel_id, "world", novel_id,
                generation_meta={"source": "generation"},
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
                from src.api.services.content.character_service import (
                    get_character_service,
                )
                char_svc = get_character_service()
                existing = await char_svc.get_character_by_name(novel_id, char_data["name"])
                if existing:
                    char_id = existing["id"]
                    await char_svc.update_character(novel_id, existing["id"], **char_data)
                else:
                    char_id = await char_svc.create_character(
                        novel_id, **char_data
                    )
                await _record_artifact_generated(
                    novel_id, "character", str(char_id),
                    generation_meta={"source": "generation"},
                )

        # Volumes
        from src.api.services.content.volume_service import get_volume_service
        volume_svc = get_volume_service()
        volumes = result.get("volumes", [])
        for vol in volumes:
            if isinstance(vol, dict):
                vol_chapters = vol.get("chapters", [])
                ch_start = vol_chapters[0].get("chapter", 1) if vol_chapters else None
                ch_end = vol_chapters[-1].get("chapter", 1) if vol_chapters else None
                await volume_svc.create_volume(
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
                    await CreativeControlService().assert_generation_allowed_in_session(
                        session, novel_id, "chapter", str(ch_num)
                    )
                    existing = None
                    if hasattr(Chapter, "__table__"):
                        existing = (
                            await session.execute(
                                select(Chapter)
                                .where(
                                    Chapter.novel_id == novel_id,
                                    Chapter.chapter_number == ch_num,
                                )
                                .with_for_update()
                            )
                        ).scalar_one_or_none()
                    if existing is not None:
                        existing.volume_number = ch.get("volume_number")
                        existing.title = ch.get("title", "")
                        existing.content = ch.get("content", "")
                        existing.word_count = ch.get("word_count", 0)
                        existing.status = "generated"
                        existing.updated_at = datetime.now(UTC)
                    else:
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
                    generation_task_id = current_generation_task_id()
                    chapter_number = ch.get("chapter", 0)
                    await manager.create_chapter_version(
                        novel_id=novel_id,
                        chapter_number=chapter_number,
                        content=ch.get("content", ""),
                        source="generation",
                        model_name="deepseek",
                        is_active=True,
                        idempotency_key=(
                            f"{generation_task_id}:langgraph:{chapter_number}:active"
                            if generation_task_id
                            else None
                        ),
                    )
                    # Creative Control 插桩：记录章节/版本已生成（best-effort，不破坏生成）
                    ch_num = str(ch.get("chapter", 0))
                    await _record_artifact_generated(
                        novel_id, "chapter", ch_num,
                        generation_meta={"source": "generation", "model": "deepseek"},
                    )
                    await _record_artifact_generated(
                        novel_id, "chapter_version", ch_num,
                        generation_meta={"source": "generation", "model": "deepseek"},
                    )
                except LeaseLost:
                    raise
                except Exception:
                    logger.warning(
                        "chapter_version_persistence_failed",
                        novel_id=novel_id,
                        chapter_number=ch.get("chapter", 0),
                        exc_info=True,
                    )

        # Update novel status
        await manager.update_novel(novel_id, status="completed")

        logger.info("persist_results_completed", novel_id=novel_id)

    except LeaseLost:
        raise
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
    from sqlalchemy import select

    from src.api.models.db_models import Chapter
    from src.core.creative_control.control_service import CreativeControlService
    from src.core.database import get_db_session

    async with get_db_session() as session:
        for ch in chapters:
            await CreativeControlService().assert_generation_allowed_in_session(
                session,
                novel_id,
                "chapter",
                str(ch["chapter"]),
            )
            # upsert：同 novel_id+chapter_number 已存在则 UPDATE，避免唯一约束冲突
            existing = (
                await session.execute(
                    select(Chapter).where(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number == ch["chapter"],
                    )
                )
            ).scalar_one_or_none()
            fields = dict(
                volume_number=volume_number or ch.get("volume_number"),
                title=ch["title"],
                content=ch["content"],
                word_count=ch["word_count"],
                chapter_type=ch.get("chapter_type"),
                status=status,
                state_delta=ch.get("state_delta"),
                quality_status=ch.get("quality_status"),
            )
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
            else:
                session.add(Chapter(novel_id=novel_id, chapter_number=ch["chapter"], **fields))


async def record_chapter_artifacts(
    novel_id: str,
    chapters: list[dict[str, Any]],
) -> None:
    """对成功生成的章节创建版本记录 + 反向更新 StoryBible。

    提取自 persist_chapters_with_replace，供逐章路径（GVC）与批量路径复用，
    统一"生成后留痕"语义。任一章节的版本/StoryBible 失败不阻断整体。
    """
    from src.api.services.content.novel_manager import get_novel_manager

    manager = get_novel_manager()
    successful_chapters = [
        ch for ch in chapters if ch.get("content") and ch.get("word_count", 0) > 0
    ]

    # 版本记录
    for ch in successful_chapters:
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
        try:
            from src.api.services.content.story_bible_service import (
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
    from src.api.services.content.novel_manager import get_novel_manager
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

    # 版本记录 + StoryBible 反向更新（复用统一函数）
    await record_chapter_artifacts(novel_id, successful_chapters)


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
                version.quality_scores = quality_scores
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
