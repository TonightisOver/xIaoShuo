"""创作产物本体、版本、控制状态和审计日志的原子写入。"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from src.api.models.db_models import (
    ArtifactVersion,
    Chapter,
    ChapterVersion,
    OperationLog,
)
from src.api.services.creative_control.artifact_adapters import (
    ArtifactAdapterRegistry,
)
from src.core.creative_control.control_service import CreativeControlService
from src.core.database import get_db_session
from src.core.exceptions import StaleChapterVersionError


@dataclass(frozen=True)
class ArtifactWriteResult:
    control_version: int
    artifact_version: int


class CreativeArtifactWriteService:
    def __init__(self) -> None:
        self._controls = CreativeControlService()
        self._adapters = ArtifactAdapterRegistry()

    async def edit_artifact(
        self,
        *,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        content: dict[str, Any] | str,
        expected_control_version: int,
        expected_active_version: int | None,
        operator_id: int | None,
    ) -> ArtifactWriteResult:
        async with get_db_session() as session:
            control = await self._controls.assert_writable_in_session(
                session,
                novel_id,
                artifact_type,
                artifact_id,
                expected_control_version,
            )
            if control is None:
                raise ValueError("artifact control not found")

            if artifact_type in {
                "world", "character", "master_outline", "volume_outline", "blueprint",
            }:
                if not isinstance(content, dict):
                    raise ValueError(f"{artifact_type} requires structured content")
                await self._adapters.save_in_session(
                    session, novel_id, artifact_type, artifact_id, content
                )
                artifact_version = await self._snapshot_in_session(
                    session,
                    novel_id,
                    artifact_type,
                    artifact_id,
                    content,
                    operator_id,
                )
            elif artifact_type in {"chapter", "chapter_version"}:
                if expected_active_version is None:
                    raise ValueError("正文编辑必须提供 expected_active_version")
                if not isinstance(content, str):
                    raise ValueError("正文编辑内容必须是字符串")
                artifact_version = await self._edit_chapter_in_session(
                    session,
                    novel_id,
                    int(artifact_id),
                    content,
                    expected_active_version,
                )
            else:
                raise ValueError(f"unsupported writable artifact type: {artifact_type}")

            control_version = await self._controls._apply_in_session(
                session,
                control,
                to_status="edited",
                action="edit",
                expected_version=expected_control_version,
                operator_id=operator_id,
            )
            return ArtifactWriteResult(control_version, artifact_version)

    async def rollback_artifact(
        self,
        *,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        target_version: int,
        expected_control_version: int,
        expected_active_version: int | None,
        operator_id: int | None,
    ) -> ArtifactWriteResult:
        async with get_db_session() as session:
            control = await self._controls.assert_writable_in_session(
                session,
                novel_id,
                artifact_type,
                artifact_id,
                expected_control_version,
            )
            if control is None:
                raise ValueError("artifact control not found")

            if artifact_type in {
                "world", "character", "master_outline", "volume_outline", "blueprint",
            }:
                versions = list((
                    await session.execute(
                        select(ArtifactVersion)
                        .where(
                            ArtifactVersion.novel_id == novel_id,
                            ArtifactVersion.artifact_type == artifact_type,
                            ArtifactVersion.artifact_id == artifact_id,
                        )
                        .with_for_update()
                    )
                ).scalars().all())
                target = next(
                    (item for item in versions if item.version_number == target_version),
                    None,
                )
                if target is None:
                    raise ValueError(f"version not found: {target_version}")
                await self._adapters.save_in_session(
                    session,
                    novel_id,
                    artifact_type,
                    artifact_id,
                    target.content_snapshot,
                )
                for item in versions:
                    item.is_active = False
                await session.flush()
                target.is_active = True
            elif artifact_type in {"chapter", "chapter_version"}:
                if expected_active_version is None:
                    raise ValueError("正文回退必须提供 expected_active_version")
                await self._activate_chapter_in_session(
                    session,
                    novel_id,
                    int(artifact_id),
                    target_version,
                    expected_active_version,
                )
            else:
                raise ValueError(f"unsupported rollback artifact type: {artifact_type}")

            control.version += 1
            control.control_status = "edited"
            control.updated_at = datetime.now(UTC)
            session.add(OperationLog(
                novel_id=novel_id,
                artifact_type=artifact_type,
                artifact_id=artifact_id,
                action="rollback",
                from_version=expected_control_version,
                to_version=control.version,
                operator_id=operator_id,
            ))
            return ArtifactWriteResult(control.version, target_version)

    async def _snapshot_in_session(
        self,
        session,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        content: dict[str, Any],
        operator_id: int | None,
    ) -> int:
        result = await session.execute(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.novel_id == novel_id,
                ArtifactVersion.artifact_type == artifact_type,
                ArtifactVersion.artifact_id == artifact_id,
            )
            .with_for_update()
        )
        versions = list(result.scalars().all())
        next_version = max((item.version_number for item in versions), default=0) + 1
        for item in versions:
            item.is_active = False
        session.add(ArtifactVersion(
            novel_id=novel_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            version_number=next_version,
            content_snapshot=content,
            source="manual",
            operator_id=operator_id,
            is_active=True,
        ))
        return next_version

    async def _edit_chapter_in_session(
        self,
        session,
        novel_id: str,
        chapter_number: int,
        content: str,
        expected_active_version: int,
    ) -> int:
        chapter = (
            await session.execute(
                select(Chapter)
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if chapter is None:
            raise ValueError("Chapter not found")
        versions = list((
            await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .with_for_update()
            )
        ).scalars().all())
        active = next((item.version_number for item in versions if item.is_active), None)
        if active != expected_active_version:
            raise StaleChapterVersionError(
                novel_id, chapter_number, expected_active_version, active
            )
        next_version = max((item.version_number for item in versions), default=0) + 1
        for item in versions:
            item.is_active = False
        session.add(ChapterVersion(
            novel_id=novel_id,
            chapter_number=chapter_number,
            version_number=next_version,
            content=content,
            word_count=len(content),
            source="manual",
            is_active=True,
            created_at=datetime.now(UTC),
        ))
        chapter.content = content
        chapter.word_count = len(content)
        chapter.quality_status = "unverified"
        chapter.updated_at = datetime.now(UTC)
        return next_version

    async def _activate_chapter_in_session(
        self,
        session,
        novel_id: str,
        chapter_number: int,
        selected_version: int,
        expected_active_version: int,
    ) -> None:
        chapter = (
            await session.execute(
                select(Chapter)
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if chapter is None:
            raise ValueError("Chapter not found")
        versions = list((
            await session.execute(
                select(ChapterVersion)
                .where(
                    ChapterVersion.novel_id == novel_id,
                    ChapterVersion.chapter_number == chapter_number,
                )
                .with_for_update()
            )
        ).scalars().all())
        active = next((item.version_number for item in versions if item.is_active), None)
        if active != expected_active_version:
            raise StaleChapterVersionError(
                novel_id, chapter_number, expected_active_version, active
            )
        target = next(
            (item for item in versions if item.version_number == selected_version), None
        )
        if target is None:
            raise ValueError(f"version not found: {selected_version}")
        for item in versions:
            item.is_active = False
        await session.flush()
        target.is_active = True
        chapter.content = target.content or ""
        chapter.word_count = target.word_count
        chapter.quality_status = "unverified"
        chapter.updated_at = datetime.now(UTC)
