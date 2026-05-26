"""大纲↔正文双向同步服务"""

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, select, update

from src.api.models.db_models import Chapter, Outline, OutlineSyncSuggestion
from src.core.database import get_db_session
from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

IMPACT_ANALYSIS_PROMPT = """你是小说编辑助手。以下是大纲的修改内容和已生成的章节列表。
请分析哪些章节受到大纲修改的影响，需要修订。

## 大纲修改
层级: {level}
旧内容: {old_content}
新内容: {new_content}

## 已生成章节
{chapters_summary}

## 输出要求
输出 JSON 数组，每项包含:
- affected_chapter: 受影响章节号(int)
- impact_type: 影响类型(plot_conflict/character_inconsistency/
  setting_contradiction/pacing_shift)
- severity: 严重度(high/medium/low)
- suggestion: 建议修改方向(string)

只输出 JSON 数组，无其他文字。如果没有章节受影响，输出空数组 []。"""

DEVIATION_DETECT_PROMPT = """你是小说编辑助手。对比章节正文与章纲要求，评估偏离程度。

## 章纲要求
{outline_content}

## 章节正文（前2000字）
{chapter_content}

## 输出要求
输出 JSON:
{{"deviation_score": 0.0到1.0的浮点数, "deviation_summary": "偏离摘要描述"}}

评分标准:
- 0.0-0.2: 完全符合大纲
- 0.2-0.3: 轻微偏离，可接受
- 0.3-0.6: 显著偏离，需关注
- 0.6-1.0: 严重偏离，需修订

只输出 JSON。"""


class OutlineSyncService:

    async def analyze_impact(
        self,
        novel_id: str,
        level: str,
        volume_number: int | None,
        chapter_number: int | None,
        old_content: dict,
        new_content: dict,
    ) -> list[dict]:
        async with get_db_session() as session:
            query = (
                select(Chapter)
                .where(Chapter.novel_id == novel_id)
                .where(Chapter.status != "draft")
                .where(Chapter.content.isnot(None))
                .order_by(Chapter.chapter_number)
            )
            if level == "volume" and volume_number is not None:
                query = query.where(Chapter.volume_number == volume_number)
            elif level == "chapter" and chapter_number is not None:
                query = query.where(
                    Chapter.chapter_number == chapter_number
                )

            result = await session.execute(query)
            chapters = result.scalars().all()

            if not chapters:
                return []

            chapters_summary = "\n".join(
                f"- 第{ch.chapter_number}章「{ch.title or ''}」"
                f"({ch.word_count}字)"
                for ch in chapters
            )

            prompt = IMPACT_ANALYSIS_PROMPT.format(
                level=level,
                old_content=str(old_content)[:2000],
                new_content=str(new_content)[:2000],
                chapters_summary=chapters_summary,
            )

            try:
                llm = get_llm_client()
                response = await asyncio.wait_for(
                    llm.generate(prompt, temperature=0.3),
                    timeout=30,
                )
                suggestions_data = safe_json_parse(response, [])
            except (TimeoutError, Exception) as e:
                logger.warning("impact_analysis_failed", error=str(e))
                return []

            if not isinstance(suggestions_data, list):
                return []

            await session.execute(
                update(OutlineSyncSuggestion)
                .where(
                    and_(
                        OutlineSyncSuggestion.novel_id == novel_id,
                        OutlineSyncSuggestion.source_level == level,
                        OutlineSyncSuggestion.status == "pending",
                    )
                )
                .values(status="expired")
            )

            created = []
            for item in suggestions_data[:20]:
                if not isinstance(item, dict):
                    continue
                sug = OutlineSyncSuggestion(
                    novel_id=novel_id,
                    source_level=level,
                    source_volume=volume_number,
                    source_chapter=chapter_number,
                    affected_chapter=item.get("affected_chapter", 0),
                    impact_type=item.get("impact_type", "plot_conflict"),
                    severity=item.get("severity", "medium"),
                    suggestion=item.get("suggestion", ""),
                    status="pending",
                )
                session.add(sug)
                created.append(item)

        return created

    async def get_suggestions(
        self,
        novel_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        async with get_db_session() as session:
            query = (
                select(OutlineSyncSuggestion)
                .where(OutlineSyncSuggestion.novel_id == novel_id)
                .order_by(OutlineSyncSuggestion.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if status:
                query = query.where(
                    OutlineSyncSuggestion.status == status
                )
            result = await session.execute(query)
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "affected_chapter": r.affected_chapter,
                    "impact_type": r.impact_type,
                    "severity": r.severity,
                    "suggestion": r.suggestion,
                    "status": r.status,
                    "source_level": r.source_level,
                    "created_at": r.created_at.isoformat()
                    if r.created_at else None,
                }
                for r in rows
            ]

    async def accept_suggestion(self, suggestion_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(OutlineSyncSuggestion).where(
                    OutlineSyncSuggestion.id == suggestion_id
                )
            )
            sug = result.scalar_one_or_none()
            if not sug or sug.status != "pending":
                return False

            sug.status = "accepted"
            sug.resolved_at = datetime.now(UTC)

            await session.execute(
                update(Chapter)
                .where(
                    and_(
                        Chapter.novel_id == sug.novel_id,
                        Chapter.chapter_number == sug.affected_chapter,
                    )
                )
                .values(status="needs_revision")
            )
            return True

    async def reject_suggestion(self, suggestion_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(
                select(OutlineSyncSuggestion).where(
                    OutlineSyncSuggestion.id == suggestion_id
                )
            )
            sug = result.scalar_one_or_none()
            if not sug or sug.status != "pending":
                return False
            sug.status = "rejected"
            sug.resolved_at = datetime.now(UTC)
            return True

    async def batch_action(
        self, ids: list[int], action: str
    ) -> int:
        count = 0
        for sid in ids:
            if action == "accept":
                ok = await self.accept_suggestion(sid)
            else:
                ok = await self.reject_suggestion(sid)
            if ok:
                count += 1
        return count

    async def detect_deviation(
        self, novel_id: str, chapter_number: int
    ) -> dict:
        async with get_db_session() as session:
            ch_result = await session.execute(
                select(Chapter).where(
                    and_(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number == chapter_number,
                    )
                )
            )
            chapter = ch_result.scalar_one_or_none()
            if not chapter or not chapter.content:
                return {"error": "Chapter not found or empty"}

            outline_result = await session.execute(
                select(Outline).where(
                    and_(
                        Outline.novel_id == novel_id,
                        Outline.level == "chapter",
                        Outline.chapter_number == chapter_number,
                    )
                )
            )
            outline = outline_result.scalar_one_or_none()
            if not outline:
                return {"error": "Chapter outline not found"}

            prompt = DEVIATION_DETECT_PROMPT.format(
                outline_content=str(outline.content)[:1500],
                chapter_content=chapter.content[:2000],
            )

            try:
                llm = get_llm_client()
                response = await asyncio.wait_for(
                    llm.generate(prompt, temperature=0.2),
                    timeout=30,
                )
                data = safe_json_parse(response, {})
            except (TimeoutError, Exception) as e:
                logger.warning("deviation_detect_failed", error=str(e))
                data = {"deviation_score": 0.0, "deviation_summary": ""}

            score = float(data.get("deviation_score", 0.0))
            summary = data.get("deviation_summary", "")

            if score < 0.3:
                outline.status = "completed"
                outline.deviation_summary = None
            else:
                outline.status = "deviated"
                outline.deviation_summary = summary

        return {
            "outline_status": outline.status,
            "deviation_score": score,
            "deviation_summary": summary,
        }

    async def get_sync_status(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline)
                .where(
                    and_(
                        Outline.novel_id == novel_id,
                        Outline.level == "chapter",
                    )
                )
                .order_by(Outline.chapter_number)
            )
            outlines = result.scalars().all()
            return [
                {
                    "chapter_number": o.chapter_number,
                    "outline_status": o.status,
                    "deviation_summary": o.deviation_summary,
                }
                for o in outlines
            ]


_outline_sync_service: OutlineSyncService | None = None


def get_outline_sync_service() -> OutlineSyncService:
    global _outline_sync_service
    if _outline_sync_service is None:
        _outline_sync_service = OutlineSyncService()
    return _outline_sync_service
