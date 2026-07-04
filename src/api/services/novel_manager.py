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
