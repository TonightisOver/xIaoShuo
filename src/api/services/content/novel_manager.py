"""小说项目管理服务"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.models.db_models import (
    Novel,
    Task,
)
from src.api.services.content.chapter_service import get_chapter_service
from src.api.services.content.world_service import get_world_service
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class NovelManager:

    async def create_novel(self, idea: str, novel_type: str, target_words: int,
                           title: str | None = None,
                           writing_style: str = "现代白话",
                           custom_style_description: str | None = None,
                           writing_style_prompt: str | None = None,
                           owner_id: int | None = None) -> str:
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
                owner_id=owner_id,
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
                           limit: int = 20, offset: int = 0,
                           owner_id: int | None = None):
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
            if owner_id is not None:
                query = query.where(Novel.owner_id == owner_id)

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
            if owner_id is not None:
                query = query.where(Novel.owner_id == owner_id)
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

    # --- Chapter Versions (delegated to ChapterService) ---

    async def create_chapter_version(self, novel_id: str, chapter_number: int,
                                      content: str, source: str = "manual",
                                      rewrite_instruction: str | None = None,
                                      quality_score: float | None = None,
                                      model_name: str | None = None,
                                      prompt_summary: str | None = None,
                                      diff_from_previous: str | None = None,
                                      kg_conflicts: dict | None = None,
                                      user_notes: str | None = None,
                                      is_active: bool = False) -> int:
        """创建章节版本快照，代理到 ChapterService。"""
        return await get_chapter_service().create_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            content=content,
            source=source,
            rewrite_instruction=rewrite_instruction,
            quality_score=quality_score,
            model_name=model_name,
            prompt_summary=prompt_summary,
            diff_from_previous=diff_from_previous,
            kg_conflicts=kg_conflicts,
            user_notes=user_notes,
            is_active=is_active,
        )

    async def list_chapter_versions(self, novel_id: str,
                                     chapter_number: int) -> list[dict]:
        """返回版本列表（不含 content），代理到 ChapterService。"""
        return await get_chapter_service().list_chapter_versions(
            novel_id=novel_id, chapter_number=chapter_number
        )

    async def get_chapter_version(self, novel_id: str, chapter_number: int,
                                   version_number: int) -> dict | None:
        """返回单个版本完整内容，代理到 ChapterService。"""
        return await get_chapter_service().get_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            version_number=version_number,
        )

    async def rollback_chapter_version(self, novel_id: str, chapter_number: int,
                                        version_number: int) -> int | None:
        """将指定版本内容写回 Chapter.content，并创建 source=rollback 的新版本。"""
        target = await self.get_chapter_version(novel_id, chapter_number, version_number)
        if not target:
            return None
        return await self.create_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            content=target["content"] or "",
            source="rollback",
            rewrite_instruction=f"回滚自版本 {version_number}",
        )

    async def activate_chapter_version(self, novel_id: str, chapter_number: int,
                                        version_number: int) -> bool | None:
        """将指定版本设为活跃版本，代理到 ChapterService。"""
        return await get_chapter_service().activate_chapter_version(
            novel_id=novel_id,
            chapter_number=chapter_number,
            version_number=version_number,
        )

    async def compare_chapter_versions(self, novel_id: str, chapter_number: int,
                                        v1: int, v2: int) -> dict | None:
        """对比两个版本，代理到 ChapterService。"""
        return await get_chapter_service().compare_chapter_versions(
            novel_id=novel_id,
            chapter_number=chapter_number,
            v1=v1,
            v2=v2,
        )

    async def fix_volume_numbers(self, novel_id: str) -> int:
        """根据卷的 chapter_start/chapter_end 为章节补充 volume_number。"""
        return await get_chapter_service().fix_volume_numbers(novel_id)

    # --- Power Systems (delegated to WorldService) ---

    async def list_power_systems(self, novel_id: str) -> list[dict]:
        """返回力量体系列表，代理到 WorldService。"""
        return await get_world_service().list_power_systems(novel_id)

    async def create_power_system(self, novel_id: str, name: str,
                                   description: str | None = None,
                                   levels: list | None = None) -> int:
        """创建力量体系，代理到 WorldService。"""
        return await get_world_service().create_power_system(
            novel_id=novel_id,
            name=name,
            description=description,
            levels=levels,
        )

    async def update_power_system(self, novel_id: str, ps_id: int, **kwargs) -> bool:
        """更新力量体系，代理到 WorldService（带 novel_id ownership 校验）。"""
        return await get_world_service().update_power_system(
            novel_id=novel_id, ps_id=ps_id, **kwargs
        )

    async def delete_power_system(self, novel_id: str, ps_id: int) -> bool:
        """删除力量体系，代理到 WorldService（带 novel_id ownership 校验）。"""
        return await get_world_service().delete_power_system(
            novel_id=novel_id, ps_id=ps_id
        )

    # --- Backward Compatibility Delegations ---

    async def get_chapter(self, novel_id: str, chapter_number: int) -> dict | None:
        """获取章节，代理到 ChapterService。"""
        return await get_chapter_service().get_chapter(novel_id, chapter_number)

    async def update_state_delta(self, novel_id: str, chapter_number: int,
                                state_delta: dict) -> bool:
        """更新章节结构化状态增量，代理到 ChapterService。"""
        return await get_chapter_service().update_state_delta(
            novel_id=novel_id, chapter_number=chapter_number, state_delta=state_delta
        )

    async def update_quality_status(self, novel_id: str, chapter_number: int,
                                     status: str) -> bool:
        """更新章节质量门禁状态，代理到 ChapterService。"""
        return await get_chapter_service().update_quality_status(
            novel_id=novel_id, chapter_number=chapter_number, status=status
        )

    async def get_chapter_tail(self, novel_id: str, limit: int = 1) -> list[dict]:
        """获取最后的章节，代理到 ChapterService。"""
        return await get_chapter_service().get_chapter_tail(novel_id, limit)

    async def list_chapters(self, novel_id: str) -> list[dict]:
        """获取章节列表，代理到 ChapterService。"""
        return await get_chapter_service().list_chapters(novel_id)

    async def get_world_setting(self, novel_id: str) -> dict | None:
        """获取世界设定，代理到 WorldService。"""
        return await get_world_service().get_world_setting(novel_id)

    async def upsert_world_setting(self, novel_id: str, **kwargs) -> None:
        """更新/插入世界设定，代理到 WorldService。"""
        await get_world_service().upsert_world_setting(novel_id, **kwargs)

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
            "owner_id": novel.owner_id,
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
            "owner_id": novel.owner_id,
        }


_novel_manager: NovelManager | None = None


def get_novel_manager() -> NovelManager:
    global _novel_manager
    if _novel_manager is None:
        _novel_manager = NovelManager()
    return _novel_manager
