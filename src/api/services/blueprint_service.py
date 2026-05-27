"""章节蓝图服务 — 生成、查询、更新结构化蓝图"""

import json

import structlog
from sqlalchemy import select, update

from src.api.models.db_models import (
    ChapterBlueprint,
)
from src.api.services.knowledge_graph_service import KnowledgeGraphService
from src.api.services.novel_context_service import NovelContextBuilder
from src.core.database import get_db_session
from src.core.llm.client import get_llm_client
from src.core.llm.helpers import generate_and_parse_json
from src.core.llm.prompts import BLUEPRINT_GENERATION_PROMPT

logger = structlog.get_logger(__name__)

_context_builder = NovelContextBuilder()

BLUEPRINT_FIELDS = [
    "chapter_type",
    "plot_goal",
    "hook_design",
    "foreshadow_actions",
    "cliffhanger",
    "pacing_target",
    "key_characters",
    "word_target",
]


class BlueprintService:
    """章节蓝图的生成、查询与更新"""

    async def generate_blueprint(
        self,
        novel_id: str,
        chapter_number: int,
        chapter_outline: dict,
        volume_context: str = "",
    ) -> dict:
        """调用 LLM 生成结构化蓝图并持久化到 DB。"""
        logger.info(
            "generating_blueprint",
            novel_id=novel_id,
            chapter_number=chapter_number,
        )

        context = await self._build_context(novel_id, chapter_number, chapter_outline)

        prompt = BLUEPRINT_GENERATION_PROMPT.format(
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            previous_chapter=context["previous_chapter"],
            story_bible=context["story_bible"],
            kg_context=context["kg_context"],
            volume_context=volume_context or context.get("volume_context", ""),
        )

        client = get_llm_client()
        blueprint_data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=None
        )
        if blueprint_data is None:
            logger.error(
                "blueprint_json_parse_failed",
                novel_id=novel_id,
                chapter_number=chapter_number,
            )
            blueprint_data = self._default_blueprint(chapter_outline)

        async with get_db_session() as session:
            await session.execute(
                update(ChapterBlueprint)
                .where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.chapter_number == chapter_number,
                    ChapterBlueprint.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )

            new_bp = ChapterBlueprint(
                novel_id=novel_id,
                chapter_number=chapter_number,
                chapter_type=blueprint_data.get("chapter_type", "main_advance"),
                plot_goal=blueprint_data.get("plot_goal", ""),
                hook_design=blueprint_data.get("hook_design", ""),
                foreshadow_actions=blueprint_data.get("foreshadow_actions"),
                cliffhanger=blueprint_data.get("cliffhanger", ""),
                pacing_target=blueprint_data.get("pacing_target", "medium"),
                key_characters=blueprint_data.get("key_characters"),
                word_target=blueprint_data.get("word_target", 3000),
                rewrite_actions=None,
                is_active=True,
            )
            session.add(new_bp)

        logger.info(
            "blueprint_generated",
            novel_id=novel_id,
            chapter_number=chapter_number,
            chapter_type=blueprint_data.get("chapter_type"),
        )
        return blueprint_data

    async def get_blueprint(self, novel_id: str, chapter_number: int) -> dict | None:
        """获取当前活跃蓝图"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.chapter_number == chapter_number,
                    ChapterBlueprint.is_active == True,  # noqa: E712
                )
            )
            bp = result.scalar_one_or_none()
            if bp is None:
                return None
            return self._model_to_dict(bp)

    async def update_blueprint(
        self, novel_id: str, chapter_number: int, updates: dict
    ) -> dict:
        """用户手动编辑蓝图字段"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.chapter_number == chapter_number,
                    ChapterBlueprint.is_active == True,  # noqa: E712
                )
            )
            bp = result.scalar_one_or_none()
            if bp is None:
                raise ValueError(
                    f"No active blueprint for novel={novel_id} chapter={chapter_number}"
                )

            for field, value in updates.items():
                if field in BLUEPRINT_FIELDS and hasattr(bp, field):
                    setattr(bp, field, value)

        logger.info(
            "blueprint_updated",
            novel_id=novel_id,
            chapter_number=chapter_number,
            updated_fields=list(updates.keys()),
        )
        return self._model_to_dict(bp)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _build_context(
        self, novel_id: str, chapter_number: int, chapter_outline: dict
    ) -> dict:
        """从 DB 读取蓝图生成所需的上下文"""
        async with get_db_session() as session:
            bp_ctx = await _context_builder.build_blueprint_context(
                session, novel_id, chapter_number, chapter_outline
            )

        ctx: dict = {
            "previous_chapter": bp_ctx.previous_chapter,
            "story_bible": bp_ctx.story_bible,
            "kg_context": "",
            "volume_context": bp_ctx.volume_context,
        }

        # KG 上下文
        try:
            kg_service = KnowledgeGraphService()
            ctx["kg_context"] = await kg_service.retrieve_context(
                novel_id, chapter_outline
            )
        except Exception as e:
            logger.warning("kg_context_retrieval_failed", error=str(e))

        return ctx

    @staticmethod
    def _model_to_dict(bp: ChapterBlueprint) -> dict:
        return {
            "chapter_type": bp.chapter_type,
            "plot_goal": bp.plot_goal,
            "hook_design": bp.hook_design,
            "foreshadow_actions": bp.foreshadow_actions,
            "cliffhanger": bp.cliffhanger,
            "pacing_target": bp.pacing_target,
            "key_characters": bp.key_characters,
            "word_target": bp.word_target,
            "rewrite_actions": bp.rewrite_actions,
            "is_active": bp.is_active,
        }

    @staticmethod
    def _default_blueprint(chapter_outline: dict) -> dict:
        return {
            "chapter_type": "main_advance",
            "plot_goal": chapter_outline.get("plot", ""),
            "hook_design": "",
            "foreshadow_actions": [],
            "cliffhanger": "",
            "pacing_target": "medium",
            "key_characters": chapter_outline.get("key_characters", []),
            "word_target": 3000,
        }
