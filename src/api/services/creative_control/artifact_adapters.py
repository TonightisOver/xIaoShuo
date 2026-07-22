"""创作控制元数据与真实业务产物之间的适配层。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.api.models.db_models import (
    ChapterBlueprint,
    Character,
    Outline,
    WorldSetting,
)
from src.api.services.content.blueprint_service import BlueprintService
from src.api.services.content.character_service import get_character_service
from src.api.services.content.novel_manager import get_novel_manager
from src.api.services.content.outline_service import get_outline_service
from src.api.services.content.world_service import get_world_service
from src.core.database import get_db_session


class ArtifactAdapterRegistry:
    """按产物类型列举、读取和更新真实业务数据。"""

    _SUPPORTED = {
        "novel",
        "world",
        "character",
        "master_outline",
        "volume_outline",
        "blueprint",
        "chapter",
        "chapter_version",
        "quality",
        "final",
    }

    def _validate(self, artifact_type: str) -> None:
        if artifact_type not in self._SUPPORTED:
            raise ValueError(f"unsupported artifact type: {artifact_type}")

    async def list_artifacts(
        self, novel_id: str, artifact_type: str
    ) -> list[dict[str, str]]:
        self._validate(artifact_type)
        if artifact_type == "novel":
            novel = await get_novel_manager().get_novel(novel_id)
            return (
                [{"artifact_id": novel_id, "label": novel.get("title") or "项目"}]
                if novel
                else []
            )
        if artifact_type == "world":
            world = await get_world_service().get_world_setting(novel_id)
            return (
                [{"artifact_id": novel_id, "label": "世界观"}] if world else []
            )
        if artifact_type == "character":
            rows = await get_character_service().list_characters(novel_id)
            return [
                {"artifact_id": str(row["id"]), "label": row.get("name") or "角色"}
                for row in rows
            ]
        if artifact_type == "master_outline":
            row = await get_outline_service().get_master_outline(novel_id)
            return (
                [{"artifact_id": str(row["id"]), "label": "全书总纲"}]
                if row
                else []
            )
        if artifact_type == "volume_outline":
            rows = await get_outline_service().get_volume_outlines(novel_id)
            return [
                {
                    "artifact_id": str(row["volume_number"]),
                    "label": f"第{row['volume_number']}卷",
                }
                for row in rows
            ]
        if artifact_type == "blueprint":
            async with get_db_session() as session:
                rows = (
                    await session.execute(
                        select(ChapterBlueprint)
                        .where(
                            ChapterBlueprint.novel_id == novel_id,
                            ChapterBlueprint.is_active.is_(True),
                        )
                        .order_by(ChapterBlueprint.chapter_number)
                    )
                ).scalars().all()
            return [
                {
                    "artifact_id": str(row.chapter_number),
                    "label": f"第{row.chapter_number}章蓝图",
                }
                for row in rows
            ]
        rows = await get_novel_manager().list_chapters(novel_id)
        return [
            {
                "artifact_id": str(row["chapter"]),
                "label": row.get("title") or f"第{row['chapter']}章",
            }
            for row in rows
        ]

    async def load(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
    ) -> dict[str, Any] | str:
        self._validate(artifact_type)
        if artifact_type == "novel":
            value = await get_novel_manager().get_novel(novel_id)
        elif artifact_type == "world":
            value = await get_world_service().get_world_setting(novel_id)
        elif artifact_type == "character":
            rows = await get_character_service().list_characters(novel_id)
            value = next(
                (row for row in rows if str(row["id"]) == artifact_id), None
            )
        elif artifact_type == "master_outline":
            row = await get_outline_service().get_master_outline(novel_id)
            value = row.get("content") if row and str(row["id"]) == artifact_id else None
        elif artifact_type == "volume_outline":
            rows = await get_outline_service().get_volume_outlines(novel_id)
            row = next(
                (
                    item
                    for item in rows
                    if str(item["volume_number"]) == artifact_id
                ),
                None,
            )
            value = row.get("content") if row else None
        elif artifact_type == "blueprint":
            value = await BlueprintService().get_blueprint(
                novel_id, int(artifact_id)
            )
        else:
            value = await get_novel_manager().get_chapter(
                novel_id, int(artifact_id)
            )
            if value and artifact_type in {"chapter", "chapter_version", "final"}:
                value = value.get("content") or ""
        if value is None:
            raise ValueError(
                f"artifact not found: {artifact_type}/{artifact_id}"
            )
        return value

    async def save(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        content: dict[str, Any] | str,
    ) -> None:
        self._validate(artifact_type)
        if not isinstance(content, dict):
            raise ValueError(f"{artifact_type} requires structured content")
        if artifact_type == "world":
            await get_world_service().upsert_world_setting(novel_id, **content)
            return
        if artifact_type == "character":
            if not await get_character_service().update_character(
                novel_id, int(artifact_id), **content
            ):
                raise ValueError(f"artifact not found: character/{artifact_id}")
            return
        if artifact_type == "master_outline":
            await get_outline_service().upsert_master_outline(novel_id, content)
            return
        if artifact_type == "volume_outline":
            await get_outline_service().upsert_volume_outline(
                novel_id, int(artifact_id), content
            )
            return
        if artifact_type == "blueprint":
            await BlueprintService().update_blueprint(
                novel_id, int(artifact_id), content
            )
            return
        raise ValueError(f"unsupported writable artifact type: {artifact_type}")

    async def save_in_session(
        self,
        session,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        content: dict[str, Any] | str,
    ) -> None:
        """在调用方事务内更新真实产物，供原子编辑/回退使用。"""
        self._validate(artifact_type)
        if not isinstance(content, dict):
            raise ValueError(f"{artifact_type} requires structured content")

        if artifact_type == "world":
            row = (
                await session.execute(
                    select(WorldSetting)
                    .where(WorldSetting.novel_id == novel_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"artifact not found: world/{artifact_id}")
            fields = {"background", "geography", "culture", "rules", "extra"}
        elif artifact_type == "character":
            row = (
                await session.execute(
                    select(Character)
                    .where(
                        Character.novel_id == novel_id,
                        Character.id == int(artifact_id),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"artifact not found: character/{artifact_id}")
            fields = {
                "name", "role", "description", "personality", "abilities",
                "background_story", "extra",
            }
        elif artifact_type in {"master_outline", "volume_outline"}:
            conditions = [Outline.novel_id == novel_id]
            if artifact_type == "master_outline":
                conditions.extend([Outline.level == "master", Outline.id == int(artifact_id)])
            else:
                conditions.extend([
                    Outline.level == "volume",
                    Outline.volume_number == int(artifact_id),
                ])
            row = (
                await session.execute(
                    select(Outline).where(*conditions).with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"artifact not found: {artifact_type}/{artifact_id}")
            row.content = content
            return
        elif artifact_type == "blueprint":
            row = (
                await session.execute(
                    select(ChapterBlueprint)
                    .where(
                        ChapterBlueprint.novel_id == novel_id,
                        ChapterBlueprint.chapter_number == int(artifact_id),
                        ChapterBlueprint.is_active.is_(True),
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                raise ValueError(f"artifact not found: blueprint/{artifact_id}")
            fields = {
                "chapter_type", "plot_goal", "hook_design",
                "foreshadow_actions", "cliffhanger", "pacing_target",
                "key_characters", "word_target",
            }
        else:
            raise ValueError(f"unsupported writable artifact type: {artifact_type}")

        for field in fields:
            if field in content:
                setattr(row, field, content[field])
