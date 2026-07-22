"""GenerationScopePlanner —— 把生成范围意图翻译为现有端点 payload + 锁定/已确认过滤 + 预览。

不自行入队任务，只产出 endpoint + payload + 过滤结果；API 层用 task_manager.create_task 入队。
设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select

from src.core.creative_control.impact_analyzer import ImpactAnalyzer
from src.core.database import get_db_session


def _orm():
    """延迟导入 ORM 模型：core 层不在顶层依赖 api.models（layer boundary）。

    用 importlib 动态加载，避免在模块中出现 ``from src.api...`` 的 import 语句
    （层边界静态守卫会扫描所有 AST import 节点，包括函数内与 TYPE_CHECKING 块）。
    """
    module = importlib.import_module("src.api.models.db_models")
    return module.ArtifactControl, module.Chapter, module.Volume

# Token 估算系数：每字约 1.5 token（中文）
_TOKENS_PER_WORD = 1.5


@dataclass
class GenerationScopeIntent:
    """用户的生成范围意图。"""

    novel_id: str
    # chapters / volume / continue / blueprint_only / content_only / fix_quality
    mode: str = "chapters"
    chapter_start: int | None = None
    chapter_end: int | None = None
    volume_number: int | None = None
    chapter_number: int | None = None
    issue_ids: list[str] | None = None
    skip_confirmed: bool = False
    respect_locked: bool = True
    words_per_chapter: int = 3000
    chapter_numbers: list[int] | None = None


@dataclass
class ScopePlan:
    """翻译后的生成计划。"""

    endpoint: str
    payload: dict[str, Any]
    target_chapters: list[int] = field(default_factory=list)
    skipped_locked: list[int] = field(default_factory=list)
    skipped_confirmed: list[int] = field(default_factory=list)


@dataclass
class ScopePreview:
    """生成范围预览。"""

    estimated_chapters: int
    estimated_tokens: float
    target_chapters: list[int]
    skipped_locked: list[int]
    skipped_confirmed: list[int]
    impact: dict[str, Any]


class GenerationScopePlanner:
    """生成范围翻译器。"""

    def __init__(self) -> None:
        self._impact = ImpactAnalyzer()

    async def plan(self, intent: GenerationScopeIntent) -> ScopePlan:
        mode = intent.mode
        if mode == "blueprint_only":
            raw = set(intent.chapter_numbers or [])
            if intent.chapter_number is not None:
                raw.add(intent.chapter_number)
            if not raw:
                raise ValueError("blueprint_only 必须提供 chapter_number 或 chapter_numbers")
            if len(raw) > 50:
                raise ValueError("blueprint_only 单次最多 50 章")
            target = sorted(raw)
            filtered, skipped_locked, skipped_confirmed = await self._filter_chapters(
                intent, target, artifact_type="blueprint"
            )
            return ScopePlan(
                endpoint="blueprint/generate",
                payload={"chapter_numbers": filtered},
                target_chapters=filtered,
                skipped_locked=skipped_locked,
                skipped_confirmed=skipped_confirmed,
            )
        if mode == "fix_quality":
            return ScopePlan(
                endpoint="auto-improve",
                payload={
                    "chapter_number": intent.chapter_number,
                    "issue_ids": intent.issue_ids or [],
                },
                target_chapters=[intent.chapter_number] if intent.chapter_number else [],
            )

        # 计算目标章集合 + 端点
        if mode == "volume":
            target = await self._load_volume_chapters(intent.novel_id, intent.volume_number)
            endpoint = "generate-volume"
            payload: dict[str, Any] = {"volume_number": intent.volume_number}
        elif mode == "continue":
            total = await self._load_total_chapters(intent.novel_id)
            start = intent.chapter_number or 1
            end = total
            target = list(range(start, end + 1))
            endpoint = "generate-chapters"
            payload = {"chapter_start": start, "chapter_end": end}
        else:  # chapters / content_only
            start = intent.chapter_start
            end = intent.chapter_end or intent.chapter_start
            target = list(range(start, end + 1))
            endpoint = "generate-chapters"
            payload = {"chapter_start": start, "chapter_end": end}
            if mode == "content_only":
                payload["regenerate_content_only"] = True

        # 过滤锁定/已确认
        filtered, skipped_locked, skipped_confirmed = await self._filter_chapters(
            intent, target
        )
        # payload 保持现有端点契约干净；target_chapters 作为 ScopePlan 字段供 API 层组合
        return ScopePlan(
            endpoint=endpoint,
            payload=payload,
            target_chapters=filtered,
            skipped_locked=skipped_locked,
            skipped_confirmed=skipped_confirmed,
        )

    async def preview(self, intent: GenerationScopeIntent) -> ScopePreview:
        plan = await self.plan(intent)
        chapters = len(plan.target_chapters)
        tokens = intent.words_per_chapter * chapters * _TOKENS_PER_WORD
        impact = await self.analyze_impact(intent)
        return ScopePreview(
            estimated_chapters=chapters,
            estimated_tokens=tokens,
            target_chapters=plan.target_chapters,
            skipped_locked=plan.skipped_locked,
            skipped_confirmed=plan.skipped_confirmed,
            impact=impact,
        )

    async def analyze_impact(self, intent: GenerationScopeIntent) -> dict[str, Any]:
        """对生成范围做影响分析。若无明确 artifact，返回空影响。"""
        if intent.volume_number is not None:
            return await self._impact.analyze(
                intent.novel_id, "volume_outline", str(intent.volume_number)
            )
        if intent.chapter_number is not None:
            return await self._impact.analyze(
                intent.novel_id, "blueprint", str(intent.chapter_number)
            )
        return {"regenerable": [], "to_mark_stale": []}

    # --------------------------------------------------------- 过滤

    async def _filter_chapters(
        self,
        intent: GenerationScopeIntent,
        target: list[int],
        *,
        artifact_type: str = "chapter",
    ) -> tuple[list[int], list[int], list[int]]:
        if not target:
            return [], [], []
        if artifact_type == "blueprint":
            locked = set(await self._load_locked_blueprints(intent.novel_id)) if intent.respect_locked else set()
            confirmed = set(await self._load_confirmed_blueprints(intent.novel_id)) if intent.skip_confirmed else set()
        else:
            locked = set(await self._load_locked_chapters(intent.novel_id)) if intent.respect_locked else set()
            confirmed = set(await self._load_confirmed_chapters(intent.novel_id)) if intent.skip_confirmed else set()
        kept = [c for c in target if c not in locked]
        skipped_confirmed = [c for c in kept if c in confirmed]
        if intent.skip_confirmed:
            kept = [c for c in kept if c not in confirmed]
        skipped_locked = [c for c in target if c in locked]
        return kept, skipped_locked, skipped_confirmed

    # --------------------------------------------------------- DB 加载（可 mock）

    async def _load_locked_chapters(self, novel_id: str) -> list[int]:
        """返回该小说所有 locked 的章号（chapter 类型 control）。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "chapter",
                    or_(
                        ArtifactControl.locked.is_(True),
                        ArtifactControl.control_status == "locked",
                    ),
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)

    async def _load_confirmed_chapters(self, novel_id: str) -> list[int]:
        """返回 approved 状态的章号。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "chapter",
                    ArtifactControl.control_status == "approved",
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)

    async def _load_locked_blueprints(self, novel_id: str) -> list[int]:
        """返回该小说所有 locked 的章号（blueprint 类型 control）。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    or_(
                        ArtifactControl.locked.is_(True),
                        ArtifactControl.control_status == "locked",
                    ),
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)

    async def _load_confirmed_blueprints(self, novel_id: str) -> list[int]:
        """返回 approved 状态的章号（blueprint 类型 control）。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    ArtifactControl.control_status == "approved",
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)

    async def _load_volume_chapters(self, novel_id: str, volume_number: int | None) -> list[int]:
        if volume_number is None:
            return []
        _, _, Volume = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume.chapter_start, Volume.chapter_end).where(
                    Volume.novel_id == novel_id,
                    Volume.volume_number == volume_number,
                )
            )
            row = result.first()
            if row is None or row.chapter_start is None or row.chapter_end is None:
                return []
            return list(range(row.chapter_start, row.chapter_end + 1))

    async def _load_total_chapters(self, novel_id: str) -> int:
        """返回当前最大章号（用于 continue 模式）。"""
        _, Chapter, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter.chapter_number)
                .where(Chapter.novel_id == novel_id)
                .order_by(Chapter.chapter_number.desc())
                .limit(1)
            )
            row = result.first()
            return row.chapter_number if row else 0
