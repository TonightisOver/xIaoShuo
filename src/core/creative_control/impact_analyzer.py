"""ImpactAnalyzer —— 依赖图驱动的下游影响分析。

职责：
- analyze：给定上游产物(novel_id, artifact_type, artifact_id)，递归收集下游类型，
  按各下游产物的 ArtifactControl 行分流：
    * locked 或 control_status in {approved, locked} -> to_mark_stale（已确认/锁定，仅标记过期）
    * 其余（含无 control 行的历史产物）-> regenerable（可自动重生成）

细化规则（按 artifact_type）：
- character：图下游 master_outline；另查角色出场章（_load_character_chapters）补 chapter
- volume_outline：图下游 blueprint/chapter 仅限该卷章号范围（_load_volume_chapter_range）
- blueprint：下游为该章 chapter + 后续章（_load_subsequent_chapters，仅 stale-only 不重生成）
- chapter：无下游（改正文只产新版本 + unverified，不级联）

泛型上游（novel/world/master_outline）的下游 id 无法由单个上游 id 反推，因此直接
按下游类型查 ArtifactControl 行（同 novel 下该 type 全部行）作为下游条目。

所有 DB 查询走 get_db_session；细化查询拆为可 mock 的私有 async 方法以利测试。

设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.api.models.db_models import ArtifactControl, Chapter, ChapterBlueprint, Volume
from src.core.creative_control.contracts import DEPENDENCY_GRAPH
from src.core.database import get_db_session

# 已确认/锁定：上游变更时仅标记过期，不自动重生成（与 control_service.mark_stale 对齐）。
_PROTECTED_STATUSES: frozenset[str] = frozenset({"approved", "locked"})


class ImpactAnalyzer:
    """依赖图驱动的下游影响分析器。"""

    async def analyze(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
    ) -> dict[str, Any]:
        upstream = {"artifact_type": artifact_type, "artifact_id": artifact_id}

        # chapter 无下游：改正文只产新版本 + unverified，不级联。
        if artifact_type == "chapter" or not DEPENDENCY_GRAPH.get(artifact_type):
            return {
                "upstream": upstream,
                "direct_downstream": [],
                "full_downstream": [],
                "regenerable": [],
                "to_mark_stale": [],
            }

        direct_types = set(DEPENDENCY_GRAPH.get(artifact_type, []))
        full_types = self._collect_full_downstream(artifact_type)

        # 展开下游条目：list[(artifact_type, artifact_id, is_stale_only)]。
        down_items = await self._resolve_downstream_items(
            novel_id, artifact_type, artifact_id, full_types
        )

        # 查相关 ArtifactControl 行（按 type 一次 in_ 查询）。
        types = {t for t, _, _ in down_items}
        control_by_key: dict[tuple[str, str], ArtifactControl] = {}
        if types:
            async with get_db_session() as session:
                result = await session.execute(
                    select(ArtifactControl).where(
                        ArtifactControl.novel_id == novel_id,
                        ArtifactControl.artifact_type.in_(types),
                    )
                )
                for row in result.scalars().all():
                    control_by_key[(row.artifact_type, row.artifact_id)] = row

        direct_downstream: list[dict[str, Any]] = []
        full_downstream: list[dict[str, Any]] = []
        regenerable: list[dict[str, Any]] = []
        to_mark_stale: list[dict[str, Any]] = []

        for atype, aid, stale_only in down_items:
            row = control_by_key.get((atype, aid))
            item = self._item_dict(atype, aid, row)
            full_downstream.append(item)
            if atype in direct_types:
                direct_downstream.append(item)

            if stale_only or self._is_protected(row):
                to_mark_stale.append(item)
            else:
                regenerable.append(item)

        return {
            "upstream": upstream,
            "direct_downstream": direct_downstream,
            "full_downstream": full_downstream,
            "regenerable": regenerable,
            "to_mark_stale": to_mark_stale,
        }

    # --------------------------------------------------------------- 类型收集

    @staticmethod
    def _collect_full_downstream(artifact_type: str) -> list[str]:
        """按依赖图 BFS 递归收集所有下游类型（去重，保序）。"""
        seen: list[str] = []
        seen_set: set[str] = set()
        queue = list(DEPENDENCY_GRAPH.get(artifact_type, []))
        while queue:
            t = queue.pop(0)
            if t in seen_set:
                continue
            seen_set.add(t)
            seen.append(t)
            queue.extend(DEPENDENCY_GRAPH.get(t, []))
        return seen

    # ----------------------------------------------------------- 下游条目解析

    async def _resolve_downstream_items(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        full_types: list[str],
    ) -> list[tuple[str, str, bool]]:
        """把下游类型展开成具体 (artifact_type, artifact_id, is_stale_only) 条目。

        泛型上游（novel/world/master_outline）无法由上游 id 反推具体下游 id，
        故改为查 ArtifactControl 行展开（_load_controlled_artifacts）。
        """
        if artifact_type == "character":
            return await self._resolve_character_items(novel_id, artifact_id, full_types)
        if artifact_type == "volume_outline":
            return await self._resolve_volume_items(novel_id, artifact_id, full_types)
        if artifact_type == "blueprint":
            return await self._resolve_blueprint_items(novel_id, artifact_id)
        # 泛型：按下游类型查所有 control 行展开。
        return await self._resolve_generic_items(novel_id, full_types)

    async def _resolve_generic_items(
        self, novel_id: str, full_types: list[str]
    ) -> list[tuple[str, str, bool]]:
        """泛型下游：按下游类型查 ArtifactControl 行作为条目（id 来自行）。"""
        items: list[tuple[str, str, bool]] = []
        if not full_types:
            return items
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type.in_(full_types),
                )
            )
            rows = result.scalars().all()
        for row in rows:
            items.append((row.artifact_type, row.artifact_id, False))
        return items

    async def _resolve_character_items(
        self, novel_id: str, character_id: str, full_types: list[str]
    ) -> list[tuple[str, str, bool]]:
        """character：图下游 master_outline 等用 control 行展开 + 角色出场章 chapter。"""
        items: list[tuple[str, str, bool]] = []
        # 非章类型走 control 行展开。
        non_chapter_types = [t for t in full_types if t != "chapter"]
        if non_chapter_types:
            items.extend(await self._resolve_generic_items(novel_id, non_chapter_types))
        # 角色出场章。
        chapters = await self._load_character_chapters(novel_id, character_id)
        for _, cid in chapters:
            items.append(("chapter", cid, False))
        return items

    async def _resolve_volume_items(
        self, novel_id: str, volume_artifact_id: str, full_types: list[str]
    ) -> list[tuple[str, str, bool]]:
        """volume_outline：blueprint/chapter 仅限该卷章号范围；其余类型按 control 行展开。"""
        items: list[tuple[str, str, bool]] = []
        volume_number = _to_int(volume_artifact_id)
        chapter_start, chapter_end = await self._load_volume_chapter_range(
            novel_id, volume_number or 0
        )
        scoped_types = [t for t in full_types if t in ("blueprint", "chapter")]
        other_types = [t for t in full_types if t not in ("blueprint", "chapter")]
        if other_types:
            items.extend(await self._resolve_generic_items(novel_id, other_types))
        if not scoped_types or chapter_start is None or chapter_end is None:
            return items
        # 范围内该 type 的 control 行作为条目。
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type.in_(scoped_types),
                )
            )
            rows = result.scalars().all()
        for row in rows:
            cn = _to_int(row.artifact_id)
            if cn is not None and chapter_start <= cn <= chapter_end:
                items.append((row.artifact_type, row.artifact_id, False))
        return items

    async def _resolve_blueprint_items(
        self, novel_id: str, blueprint_artifact_id: str
    ) -> list[tuple[str, str, bool]]:
        """blueprint：该章 chapter + 后续章（后续章 stale-only，不 regenerable）。"""
        chapter_number = _to_int(blueprint_artifact_id)
        items: list[tuple[str, str, bool]] = []
        if chapter_number is not None:
            items.append(("chapter", str(chapter_number), False))
        subsequent = await self._load_subsequent_chapters(novel_id, chapter_number or 0)
        for cn in subsequent:
            items.append(("chapter", str(cn), True))  # stale-only
        return items

    # ----------------------------------------------------- 可 mock 的私有查询

    async def _load_character_chapters(
        self, novel_id: str, character_id: str
    ) -> list[tuple[str, str]]:
        """查 character 出场章：ChapterBlueprint.key_characters 含该角色名的 active 蓝图。

        Returns:
            [("chapter", chapter_number_str), ...]
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint.chapter_number).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.is_active.is_(True),
                    ChapterBlueprint.key_characters.contains([character_id]),
                )
            )
            rows = result.scalars().all()
        return [("chapter", str(cn)) for cn in rows]

    async def _load_volume_chapter_range(
        self, novel_id: str, volume_number: int
    ) -> tuple[int | None, int | None]:
        """查该卷的 chapter_start / chapter_end。不存在返回 (None, None)。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume.chapter_start, Volume.chapter_end).where(
                    Volume.novel_id == novel_id,
                    Volume.volume_number == volume_number,
                )
            )
            row = result.first()
        if row is None:
            return None, None
        return row.chapter_start, row.chapter_end

    async def _load_subsequent_chapters(
        self, novel_id: str, chapter_number: int
    ) -> list[int]:
        """查严格大于 chapter_number 的所有章号（后续连续性检查范围）。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter.chapter_number).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number > chapter_number,
                )
            )
            return list(result.scalars().all())

    # --------------------------------------------------------------- 辅助

    @staticmethod
    def _item_dict(
        artifact_type: str, artifact_id: str, row: ArtifactControl | None
    ) -> dict[str, Any]:
        return {
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "control_status": row.control_status if row is not None else None,
            "locked": bool(row.locked) if row is not None else False,
        }

    @staticmethod
    def _is_protected(row: ArtifactControl | None) -> bool:
        """locked 或 control_status in {approved, locked} -> to_mark_stale。无行 -> regenerable。"""
        if row is None:
            return False
        return bool(row.locked) or row.control_status in _PROTECTED_STATUSES


def _to_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
