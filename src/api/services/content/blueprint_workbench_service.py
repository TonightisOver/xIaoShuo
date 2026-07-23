"""章节蓝图工作台聚合服务。

职责：
- list_chapter_summaries：以 chapter 级 Outline 为主轴合并四源（Outline/ChapterBlueprint/
  Chapter/Volume），按 chapter_number 去重，服务端分页（page_size 上限 100），返回统一摘要
  含 control_status/locked/quality_status。能发现「未生成蓝图」的章节。
- get_workspace：单章详情聚合（blueprint+control+versions+outline+previous_state_delta+
  chapter_summary+quality_status+available_characters），单事务，子查询失败降级 null。
- get_options：蓝图字段枚举（取自 blueprint_enums，无 DB）。

不直接修改 ArtifactControl/版本表，全部经现有 service 读取。
设计依据：docs/superpowers/specs/2026-07-22-chapter-blueprint-workbench-design.md
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import (
    ArtifactControl,
    Chapter,
    ChapterBlueprint,
    Outline,
    Volume,
)
from src.api.services.content.blueprint_service import BlueprintService
from src.api.services.content.character_service import get_character_service
from src.core.creative_control.artifact_version_store import ArtifactVersionStore
from src.core.creative_control.blueprint_enums import BLUEPRINT_FIELD_OPTIONS
from src.core.creative_control.control_service import CreativeControlService
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 50
_BLUEPRINT_BATCH_LIMIT = 50


class BlueprintWorkbenchService:
    """章节蓝图工作台聚合查询入口。"""

    # ----------------------------------------------------- 章节摘要列表

    async def list_chapter_summaries(
        self,
        novel_id: str,
        *,
        volume_number: int | None = None,
        status: str | None = None,
        search: str | None = None,
        chapter_start: int | None = None,
        chapter_end: int | None = None,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), _MAX_PAGE_SIZE)

        outlines = await self._load_chapter_outlines(novel_id, volume_number)
        blueprints = await self._load_active_blueprints(novel_id)
        chapters = await self._load_chapters(novel_id)
        volumes = await self._load_volumes(novel_id)
        controls = await self._load_blueprint_controls(novel_id)
        generating = await self._load_generating_chapters(novel_id)

        # 合并章号集合（Outline 为主轴，Blueprint/Chapter/Volume 补齐）
        chapter_set: set[int] = {o.chapter_number for o in outlines}
        chapter_set.update(blueprints.keys())
        chapter_set.update(chapters.keys())
        for v in volumes:
            if v.chapter_start and v.chapter_end:
                chapter_set.update(range(v.chapter_start, v.chapter_end + 1))

        # volume 推导：Outline 无 volume_number 时按 Volume 范围
        vol_map: dict[int, int] = {}
        for v in volumes:
            if v.chapter_start and v.chapter_end:
                for c in range(v.chapter_start, v.chapter_end + 1):
                    vol_map[c] = v.volume_number

        all_items: list[dict[str, Any]] = []
        for c in sorted(chapter_set):
            if chapter_start is not None and c < chapter_start:
                continue
            if chapter_end is not None and c > chapter_end:
                continue
            outline = next((o for o in outlines if o.chapter_number == c), None)
            bp = blueprints.get(c)
            ch = chapters.get(c)
            ctrl = controls.get(c)
            vol = (getattr(outline, "volume_number", None) if outline else None) or vol_map.get(c)

            if volume_number is not None and vol != volume_number:
                continue

            title = None
            if ch is not None and getattr(ch, "title", None):
                title = ch.title
            elif outline is not None:
                content = getattr(outline, "content", None) or {}
                title = content.get("title") if isinstance(content, dict) else None

            if search:
                query = search.strip().casefold()
                title_matches = title is not None and query in title.casefold()
                chapter_matches = query in str(c)
                if not title_matches and not chapter_matches:
                    continue

            has_blueprint = bp is not None
            control_status = self._derive_status(
                ctrl, has_blueprint, c in generating
            )
            if status and control_status != status:
                continue

            all_items.append({
                "chapter_number": c,
                "volume_number": vol,
                "title": title,
                "has_outline": outline is not None,
                "has_blueprint": has_blueprint,
                "has_chapter": ch is not None,
                "blueprint_version": getattr(bp, "version_number", None) if bp else None,
                "control_status": control_status,
                "control_version": getattr(ctrl, "version", None) if ctrl else None,
                "locked": bool(getattr(ctrl, "locked", False)) if ctrl else False,
                "quality_status": getattr(ch, "quality_status", None) if ch else None,
                "updated_at": getattr(bp, "updated_at", None) if bp else None,
            })

        total = len(all_items)
        offset = (page - 1) * page_size
        page_items = all_items[offset:offset + page_size]

        status_counts: dict[str, int] = {}
        for it in all_items:
            status_counts[it["control_status"]] = status_counts.get(it["control_status"], 0) + 1

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "status_counts": status_counts,
        }

    @staticmethod
    def _derive_status(ctrl: Any | None, has_blueprint: bool, generating: bool) -> str:
        """章节摘要状态推导（映射提示词 8 态 + not_generated 派生态）。

        ctrl is None 表示该章尚未进入控制台流程：
        - 正在生成中 → generating
        - 无蓝图 → not_generated
        - 有蓝图但未纳入控制流 → draft（视作草稿态，待纳入控制台）
        """
        if ctrl is None:
            if generating:
                return "generating"
            return "not_generated" if not has_blueprint else "draft"
        cs = getattr(ctrl, "control_status", None)
        if generating or cs == "generating":
            return "generating"
        if cs == "failed":
            return "failed"
        if getattr(ctrl, "locked", False) or cs == "locked":
            return "locked"
        if cs == "approved":
            return "confirmed"
        if cs == "stale":
            return "stale"
        if cs == "edited":
            return "edited"
        if cs == "generated":
            return "generated"
        if cs == "draft":
            return "draft" if has_blueprint else "not_generated"
        return "draft" if has_blueprint else "not_generated"

    # ----------------------------------------------------- 单章 workspace

    async def get_workspace(self, novel_id: str, chapter_number: int) -> dict[str, Any]:
        workspace: dict[str, Any] = {
            "blueprint": None,
            "control": None,
            "versions": [],
            "outline": None,
            "previous_state_delta": None,
            "chapter_summary": None,
            "quality_status": None,
            "available_characters": [],
        }
        async with get_db_session() as session:
            try:
                workspace["blueprint"] = await self._get_blueprint_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001 - 子查询降级
                logger.warning("workspace_blueprint_failed", error=str(exc))
            try:
                workspace["control"] = await self._get_control_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_control_failed", error=str(exc))
            try:
                workspace["versions"] = await self._get_versions_list(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_versions_failed", error=str(exc))
            try:
                workspace["outline"] = await self._get_chapter_outline_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_outline_failed", error=str(exc))
            try:
                workspace["previous_state_delta"] = await self._get_previous_state_delta(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_prev_delta_failed", error=str(exc))
            try:
                chapter_summary = await self._get_chapter_summary(novel_id, chapter_number)
                workspace["chapter_summary"] = chapter_summary
                workspace["quality_status"] = chapter_summary.get("quality_status") if chapter_summary else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_chapter_failed", error=str(exc))
            try:
                workspace["available_characters"] = await self._get_available_characters(novel_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_characters_failed", error=str(exc))
        return workspace

    def get_options(self) -> dict[str, list[str]]:
        return BLUEPRINT_FIELD_OPTIONS

    # ----------------------------------------------------- 子查询（可 mock）

    async def _get_blueprint_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        return await BlueprintService().get_blueprint(novel_id, chapter_number)

    async def _get_control_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        return await CreativeControlService().get(
            novel_id, "blueprint", str(chapter_number)
        )

    async def _get_versions_list(self, novel_id: str, chapter_number: int) -> list[dict]:
        return await ArtifactVersionStore().list_versions(
            novel_id, "blueprint", str(chapter_number)
        )

    async def _get_chapter_outline_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(
                    Outline.novel_id == novel_id,
                    Outline.level == "chapter",
                    Outline.chapter_number == chapter_number,
                )
            )
            o = result.scalar_one_or_none()
            if o is None:
                return None
            return {"id": o.id, "volume_number": o.volume_number,
                    "chapter_number": o.chapter_number, "content": o.content, "status": o.status}

    async def _get_previous_state_delta(self, novel_id: str, chapter_number: int) -> dict | None:
        if chapter_number <= 1:
            return None
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter.state_delta).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            row = result.first()
            return row.state_delta if row else None

    async def _get_chapter_summary(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            c = result.scalar_one_or_none()
            if c is None:
                return None
            return {"status": c.status, "word_count": c.word_count,
                    "quality_status": c.quality_status, "title": c.title}

    async def _get_available_characters(self, novel_id: str) -> list[dict]:
        rows = await get_character_service().list_characters(novel_id)
        return [{"id": r["id"], "name": r["name"], "role": r.get("role")} for r in rows]

    # ----------------------------------------------------- 批量加载（可 mock）

    async def _load_chapter_outlines(self, novel_id: str, volume_number: int | None = None) -> list[Any]:
        async with get_db_session() as session:
            query = select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "chapter",
            )
            if volume_number is not None:
                query = query.where(Outline.volume_number == volume_number)
            query = query.order_by(Outline.chapter_number)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def _load_active_blueprints(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.is_active.is_(True),
                )
            )
            return {b.chapter_number: b for b in result.scalars().all()}

    async def _load_chapters(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.novel_id == novel_id)
            )
            latest: dict[int, Any] = {}
            for c in result.scalars().all():
                prev = latest.get(c.chapter_number)
                if prev is None or c.id > prev.id:
                    latest[c.chapter_number] = c
            return latest

    async def _load_volumes(self, novel_id: str) -> list[Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume).where(Volume.novel_id == novel_id)
            )
            return list(result.scalars().all())

    async def _load_blueprint_controls(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                )
            )
            return {int(r.artifact_id): r for r in result.scalars().all() if r.artifact_id is not None}

    async def _load_generating_chapters(self, novel_id: str) -> set[int]:
        """返回 control_status=generating 的章号。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    ArtifactControl.control_status == "generating",
                )
            )
            return {int(r) for r in result.scalars().all() if r is not None}
