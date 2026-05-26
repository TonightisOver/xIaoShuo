"""读者视角模拟服务"""

import asyncio
import time

import structlog
from sqlalchemy import and_, select

from src.api.models.db_models import Chapter, ReaderSimulation
from src.core.database import get_db_session
from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

READER_PERSONAS = {
    "hardcore_fan": {
        "id": "hardcore_fan",
        "name": "核心粉丝",
        "description": "追更型读者，关注剧情连贯性和人物成长",
        "prompt": (
            "你是一个狂热的网文追更读者。你从第一章就开始追这本书，"
            "对每个角色都有深厚感情。你特别在意：\n"
            "- 人物是否OOC（行为是否符合之前的性格设定）\n"
            "- 之前埋下的伏笔是否有回收\n"
            "- 情感描写是否能引起共鸣\n"
            "- 角色成长是否合理\n"
            "请以核心粉丝的视角评价这一章。"
        ),
    },
    "casual_reader": {
        "id": "casual_reader",
        "name": "路人读者",
        "description": "碎片化阅读，注重即时爽感",
        "prompt": (
            "你是一个随便翻翻的路人读者，通勤时用手机看小说。"
            "你没有太多耐心，如果开头不吸引人就会划走。你在意：\n"
            "- 开头是否能在30秒内抓住注意力\n"
            "- 节奏是否紧凑，有没有大段无聊描写\n"
            "- 看完这章是否想点下一章\n"
            "- 有没有让你想截图分享的精彩片段\n"
            "请以路人读者的视角评价这一章。"
        ),
    },
    "critic": {
        "id": "critic",
        "name": "专业评论家",
        "description": "文学性审美，关注叙事技巧",
        "prompt": (
            "你是一个专业的文学评论家，有深厚的叙事学功底。"
            "你用专业眼光审视作品，关注：\n"
            "- 叙事视角和时间线处理是否得当\n"
            "- 文笔质量（比喻、意象、节奏感）\n"
            "- 主题表达是否有深度\n"
            "- 情节结构是否完整（起承转合）\n"
            "请以专业评论家的视角评价这一章。"
        ),
    },
    "veteran_reader": {
        "id": "veteran_reader",
        "name": "网文老白",
        "description": "阅文无数，对套路敏感",
        "prompt": (
            "你是一个看了上千本网文的老白读者，什么套路都见过。"
            "你对陈词滥调免疫，但好的创新会让你眼前一亮。你关注：\n"
            "- 这个套路是否有新意，还是老生常谈\n"
            "- 爽点密度够不够，有没有让你拍大腿的情节\n"
            "- 金手指/外挂是否合理，有没有崩坏\n"
            "- 节奏是否符合网文阅读习惯（水不水）\n"
            "请以网文老白的视角评价这一章。"
        ),
    },
}

SIMULATION_PROMPT = """你正在扮演一位读者，阅读以下章节内容并给出反馈。

## 你的读者身份
{persona_prompt}

## 章节上下文
{context}

## 本章内容
{chapter_content}

## 输出要求
请输出严格的 JSON 格式反馈（不要输出其他文字）：
{{
  "engagement_score": 0.0到1.0的浮点数（你的投入程度）,
  "would_continue_reading": true或false（是否想看下一章）,
  "emotional_response": "一句话描述你的情感反应",
  "pacing_assessment": "too_slow"或"good"或"too_fast",
  "character_consistency": "consistent"或"minor_issues"或"ooc",
  "satisfaction_points": ["爽点/亮点1", "爽点/亮点2"],
  "pain_points": ["问题/不足1", "问题/不足2"],
  "overall_comment": "以你的读者身份写一段50-100字的总评"
}}"""


class ReaderSimulationService:

    async def run_simulation(
        self,
        novel_id: str,
        chapter_number: int,
        personas: list[str] | None = None,
    ) -> int:
        """触发读者模拟，返回 simulation_id"""
        if not personas:
            personas = list(READER_PERSONAS.keys())

        valid_personas = [
            p for p in personas if p in READER_PERSONAS
        ]
        if not valid_personas:
            valid_personas = list(READER_PERSONAS.keys())

        async with get_db_session() as session:
            sim = ReaderSimulation(
                novel_id=novel_id,
                chapter_number=chapter_number,
                personas_used=valid_personas,
                results=[],
                status="pending",
            )
            session.add(sim)
            await session.flush()
            sim_id = sim.id

        return sim_id

    async def execute_simulation(self, simulation_id: int):
        """执行模拟（由 BackgroundTasks 调用）"""
        start = time.time()

        async with get_db_session() as session:
            result = await session.execute(
                select(ReaderSimulation).where(
                    ReaderSimulation.id == simulation_id
                )
            )
            sim = result.scalar_one_or_none()
            if not sim:
                return
            sim.status = "running"

        try:
            async with get_db_session() as session:
                context = await self._build_context(
                    session, sim.novel_id, sim.chapter_number
                )

            if not context:
                async with get_db_session() as session:
                    result = await session.execute(
                        select(ReaderSimulation).where(
                            ReaderSimulation.id == simulation_id
                        )
                    )
                    sim = result.scalar_one_or_none()
                    if sim:
                        sim.status = "failed"
                        sim.results = [
                            {"error": "Chapter not found or empty"}
                        ]
                return

            tasks = [
                self._simulate_single_persona(
                    READER_PERSONAS[pid], context
                )
                for pid in sim.personas_used
            ]
            results = await asyncio.gather(
                *tasks, return_exceptions=True
            )

            final_results = []
            for pid, res in zip(sim.personas_used, results):
                if isinstance(res, Exception):
                    logger.warning(
                        "persona_simulation_failed",
                        persona=pid,
                        error=str(res),
                    )
                    final_results.append({
                        "persona_id": pid,
                        "persona_name": READER_PERSONAS[pid]["name"],
                        "error": str(res),
                    })
                else:
                    res["persona_id"] = pid
                    res["persona_name"] = READER_PERSONAS[pid]["name"]
                    final_results.append(res)

            duration = int((time.time() - start) * 1000)

            async with get_db_session() as session:
                result = await session.execute(
                    select(ReaderSimulation).where(
                        ReaderSimulation.id == simulation_id
                    )
                )
                sim = result.scalar_one_or_none()
                if sim:
                    sim.results = final_results
                    sim.status = "completed"
                    sim.duration_ms = duration

        except Exception as e:
            logger.error(
                "simulation_execution_failed", error=str(e)
            )
            async with get_db_session() as session:
                result = await session.execute(
                    select(ReaderSimulation).where(
                        ReaderSimulation.id == simulation_id
                    )
                )
                sim = result.scalar_one_or_none()
                if sim:
                    sim.status = "failed"
                    sim.duration_ms = int(
                        (time.time() - start) * 1000
                    )

    async def _build_context(
        self, session, novel_id: str, chapter_number: int
    ) -> dict | None:
        result = await session.execute(
            select(Chapter).where(
                and_(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
        )
        chapter = result.scalar_one_or_none()
        if not chapter or not chapter.content:
            return None

        content = chapter.content
        if len(content) > 10000:
            content = content[:8000] + "\n...\n" + content[-2000:]

        prev_summary = ""
        if chapter_number > 1:
            prev_result = await session.execute(
                select(Chapter).where(
                    and_(
                        Chapter.novel_id == novel_id,
                        Chapter.chapter_number
                        == chapter_number - 1,
                    )
                )
            )
            prev_ch = prev_result.scalar_one_or_none()
            if prev_ch and prev_ch.content:
                prev_summary = (
                    f"前一章摘要：{prev_ch.content[:500]}..."
                )

        context_text = ""
        if prev_summary:
            context_text = prev_summary
        if chapter.title:
            context_text += f"\n本章标题：{chapter.title}"

        return {
            "chapter_content": content,
            "context": context_text or "（无额外上下文）",
        }

    async def _simulate_single_persona(
        self, persona: dict, context: dict
    ) -> dict:
        prompt = SIMULATION_PROMPT.format(
            persona_prompt=persona["prompt"],
            context=context["context"],
            chapter_content=context["chapter_content"],
        )

        llm = get_llm_client()
        response = await asyncio.wait_for(
            llm.generate(prompt, temperature=0.7),
            timeout=30,
        )

        data = safe_json_parse(response, {})
        if not data or "engagement_score" not in data:
            raise ValueError(
                f"Invalid LLM response for {persona['id']}"
            )
        return data

    async def get_simulation(
        self, simulation_id: int
    ) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(ReaderSimulation).where(
                    ReaderSimulation.id == simulation_id
                )
            )
            sim = result.scalar_one_or_none()
            if not sim:
                return None
            return {
                "id": sim.id,
                "novel_id": sim.novel_id,
                "chapter_number": sim.chapter_number,
                "personas_used": sim.personas_used,
                "results": sim.results,
                "summary": sim.summary,
                "status": sim.status,
                "duration_ms": sim.duration_ms,
                "created_at": (
                    sim.created_at.isoformat()
                    if sim.created_at
                    else None
                ),
            }

    async def list_simulations(
        self, novel_id: str, chapter_number: int
    ) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ReaderSimulation)
                .where(
                    and_(
                        ReaderSimulation.novel_id == novel_id,
                        ReaderSimulation.chapter_number
                        == chapter_number,
                    )
                )
                .order_by(ReaderSimulation.created_at.desc())
                .limit(20)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id,
                    "chapter_number": r.chapter_number,
                    "personas_used": r.personas_used,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "created_at": (
                        r.created_at.isoformat()
                        if r.created_at
                        else None
                    ),
                }
                for r in rows
            ]


_reader_simulation_service: ReaderSimulationService | None = None


def get_reader_simulation_service() -> ReaderSimulationService:
    global _reader_simulation_service
    if _reader_simulation_service is None:
        _reader_simulation_service = ReaderSimulationService()
    return _reader_simulation_service
