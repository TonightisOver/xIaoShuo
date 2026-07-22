"""Volume management service"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from src.api.models.db_models import Volume
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class VolumeService:
    """卷管理服务"""

    async def list_volumes(self, novel_id: str) -> list[dict]:
        """获取小说所有卷"""
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
        """获取单卷详情"""
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
        """创建新卷"""
        async with get_db_session() as session:
            from src.core.creative_control.control_service import (
                assert_generation_write_allowed_in_session,
                has_generation_fence,
            )

            await assert_generation_write_allowed_in_session(
                session, novel_id, "volume_outline", str(volume_number)
            )
            if has_generation_fence():
                existing = (
                    await session.execute(
                        select(Volume)
                        .where(
                            Volume.novel_id == novel_id,
                            Volume.volume_number == volume_number,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.title = title
                    existing.summary = summary
                    existing.outline = outline
                    existing.chapter_start = chapter_start
                    existing.chapter_end = chapter_end
                    existing.updated_at = datetime.now(UTC)
                    return existing.id
            vol = Volume(novel_id=novel_id, volume_number=volume_number,
                         title=title, summary=summary, outline=outline,
                         chapter_start=chapter_start, chapter_end=chapter_end,
                         updated_at=datetime.now(UTC))
            session.add(vol)
            await session.flush()
            return vol.id

    async def update_volume(self, novel_id: str, volume_number: int, **kwargs) -> bool:
        """更新卷信息"""
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


_volume_service: VolumeService | None = None


def get_volume_service() -> VolumeService:
    """获取 VolumeService 全局单例"""
    global _volume_service
    if _volume_service is None:
        _volume_service = VolumeService()
    return _volume_service
