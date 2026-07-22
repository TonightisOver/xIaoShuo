"""世界观/力量体系管理服务"""

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from src.api.models.db_models import PowerSystem, WorldSetting
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class WorldService:

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
            from src.core.creative_control.control_service import (
                assert_generation_write_allowed_in_session,
            )

            await assert_generation_write_allowed_in_session(
                session, novel_id, "world", novel_id
            )
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
            from src.core.creative_control.control_service import (
                assert_generation_write_allowed_in_session,
                has_generation_fence,
            )

            await assert_generation_write_allowed_in_session(
                session, novel_id, "power_system", name
            )
            if has_generation_fence():
                existing = (
                    await session.execute(
                        select(PowerSystem)
                        .where(
                            PowerSystem.novel_id == novel_id,
                            PowerSystem.name == name,
                        )
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    existing.description = description
                    existing.levels = levels or []
                    existing.updated_at = datetime.now(UTC)
                    return existing.id
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


_world_service: WorldService | None = None


def get_world_service() -> WorldService:
    global _world_service
    if _world_service is None:
        _world_service = WorldService()
    return _world_service
