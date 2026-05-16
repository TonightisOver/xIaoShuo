"""大纲服务 - 三级大纲管理"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, and_

from src.api.models.db_models import Outline
from src.core.database import get_db_session
from src.core.llm.client import get_llm_client
from src.core.json_utils import safe_json_parse

logger = logging.getLogger(__name__)

GENERATE_VOLUMES_PROMPT = """你是小说大纲师。基于以下总纲，将故事拆分为若干卷。

总纲：{master_outline}
目标字数：{target_words}
小说类型：{novel_type}

要求：
- 根据字数合理分卷（10万字2-3卷，30万字5-8卷，50万字+8-15卷）
- 每卷有独立的阶段性目标和小高潮
- 前后卷情节连贯
- 每卷包含5-10章

输出 JSON 数组：
[{{"volume_number": 1, "title": "卷标题", "summary": "概要", "goal": "阶段目标", "climax": "本卷高潮", "chapters": [{{"chapter": 1, "title": "章标题", "summary": "章概要"}}]}}]

只输出 JSON。"""

GENERATE_CHAPTERS_PROMPT = """你是小说大纲师。基于以下卷纲，为每章生成详细的章纲。

卷纲：{volume_outline}
世界观：{world_setting}
人物：{characters}

每章要求：
- 包含具体场景（地点、出场人物、事件）
- 标注转折点和情感节奏
- 字数目标

输出 JSON 数组：
[{{"chapter": 1, "title": "章标题", "scenes": [{{"location": "地点", "characters": ["人物"], "event": "事件"}}], "turning_point": "转折", "emotional_beat": "情感节奏", "word_target": 5000}}]

只输出 JSON。"""

FROM_CONVERSATION_PROMPT = """分析以下创作对话，提取并整理为结构化的小说总纲。

对话内容：
{conversation_text}

已有设定：
{context}

输出 JSON 格式的总纲：
{{"premise": "核心前提", "main_conflict": "主要冲突", "plot_arcs": [{{"name": "线名", "description": "描述", "stages": ["起", "承", "转", "合"]}}], "ending": "结局走向", "themes": ["主题1", "主题2"]}}

只输出 JSON。"""


class OutlineService:

    async def get_master_outline(self, novel_id: str) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(
                    Outline.novel_id == novel_id,
                    Outline.level == "master"
                )
            )
            outline = result.scalar_one_or_none()
            if not outline:
                return None
            return {"id": outline.id, "content": outline.content,
                    "status": outline.status, "updated_at": outline.updated_at}

    async def upsert_master_outline(self, novel_id: str, content: dict) -> None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(
                    Outline.novel_id == novel_id,
                    Outline.level == "master"
                )
            )
            outline = result.scalar_one_or_none()
            if outline:
                outline.content = content
                outline.updated_at = datetime.now(timezone.utc)
            else:
                outline = Outline(
                    novel_id=novel_id, level="master",
                    content=content, status="draft",
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(outline)

    async def get_volume_outlines(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(
                    Outline.novel_id == novel_id,
                    Outline.level == "volume"
                ).order_by(Outline.volume_number)
            )
            return [{"id": o.id, "volume_number": o.volume_number,
                     "content": o.content, "status": o.status}
                    for o in result.scalars().all()]

    async def get_chapter_outlines(self, novel_id: str, volume_number: int | None = None) -> list[dict]:
        async with get_db_session() as session:
            query = select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "chapter"
            )
            if volume_number is not None:
                query = query.where(Outline.volume_number == volume_number)
            query = query.order_by(Outline.chapter_number)
            result = await session.execute(query)
            return [{"id": o.id, "volume_number": o.volume_number,
                     "chapter_number": o.chapter_number,
                     "content": o.content, "status": o.status}
                    for o in result.scalars().all()]

    async def upsert_volume_outline(self, novel_id: str, volume_number: int, content: dict) -> None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(and_(
                    Outline.novel_id == novel_id,
                    Outline.level == "volume",
                    Outline.volume_number == volume_number
                ))
            )
            outline = result.scalar_one_or_none()
            if outline:
                outline.content = content
                outline.updated_at = datetime.now(timezone.utc)
            else:
                outline = Outline(
                    novel_id=novel_id, level="volume",
                    volume_number=volume_number, content=content,
                    status="draft", updated_at=datetime.now(timezone.utc)
                )
                session.add(outline)

    async def upsert_chapter_outline(self, novel_id: str, volume_number: int,
                                     chapter_number: int, content: dict) -> None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(and_(
                    Outline.novel_id == novel_id,
                    Outline.level == "chapter",
                    Outline.chapter_number == chapter_number
                ))
            )
            outline = result.scalar_one_or_none()
            if outline:
                outline.content = content
                outline.updated_at = datetime.now(timezone.utc)
            else:
                outline = Outline(
                    novel_id=novel_id, level="chapter",
                    volume_number=volume_number,
                    chapter_number=chapter_number, content=content,
                    status="draft", updated_at=datetime.now(timezone.utc)
                )
                session.add(outline)

    async def get_outline_tree(self, novel_id: str) -> dict:
        master = await self.get_master_outline(novel_id)
        volumes = await self.get_volume_outlines(novel_id)
        chapters = await self.get_chapter_outlines(novel_id)

        # Group chapters by volume
        vol_chapters: dict[int, list] = {}
        for ch in chapters:
            vn = ch.get("volume_number") or 0
            vol_chapters.setdefault(vn, []).append(ch)

        for vol in volumes:
            vol["chapters"] = vol_chapters.get(vol["volume_number"], [])

        return {
            "master": master,
            "volumes": volumes,
            "unassigned_chapters": vol_chapters.get(0, []),
        }

    # --- LLM Generation ---

    async def generate_volume_outlines(self, novel_id: str,
                                       novel_type: str, target_words: int) -> list[dict]:
        master = await self.get_master_outline(novel_id)
        if not master:
            raise ValueError("总纲不存在，请先创建总纲")

        client = get_llm_client()
        prompt = GENERATE_VOLUMES_PROMPT.format(
            master_outline=str(master["content"]),
            target_words=target_words,
            novel_type=novel_type,
        )
        response = await client.generate(prompt, max_tokens=4000)
        volumes = safe_json_parse(response, fallback=[], extract_partial=True)

        if not isinstance(volumes, list):
            volumes = []

        # Save to DB
        for vol in volumes:
            vol_num = vol.get("volume_number", 1)
            await self.upsert_volume_outline(novel_id, vol_num, vol)

        return volumes

    async def generate_chapter_outlines(self, novel_id: str, volume_number: int) -> list[dict]:
        vol_outlines = await self.get_volume_outlines(novel_id)
        vol = next((v for v in vol_outlines if v["volume_number"] == volume_number), None)
        if not vol:
            raise ValueError(f"卷{volume_number}大纲不存在")

        from src.api.services.novel_manager import get_novel_manager
        manager = get_novel_manager()
        world = await manager.get_world_setting(novel_id)
        characters = await manager.list_characters(novel_id)

        client = get_llm_client()
        prompt = GENERATE_CHAPTERS_PROMPT.format(
            volume_outline=str(vol["content"]),
            world_setting=str(world) if world else "暂无",
            characters=str([c["name"] + "(" + (c.get("role") or "") + ")" for c in characters[:10]]),
        )
        response = await client.generate(prompt, max_tokens=4000)
        chapters = safe_json_parse(response, fallback=[], extract_partial=True)

        if not isinstance(chapters, list):
            chapters = []

        for ch in chapters:
            ch_num = ch.get("chapter", 0)
            if ch_num:
                await self.upsert_chapter_outline(novel_id, volume_number, ch_num, ch)

        return chapters

    async def generate_master_from_conversation(self, novel_id: str, conv_id: int) -> dict:
        from src.api.services.conversation_service import get_conversation_service
        from src.api.services.novel_manager import get_novel_manager

        conv_service = get_conversation_service()
        conv = await conv_service.get_conversation(conv_id)
        if not conv:
            raise ValueError("对话不存在")

        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else 'AI'}：{m['content']}"
            for m in conv.get("messages", [])
        )

        manager = get_novel_manager()
        world = await manager.get_world_setting(novel_id)
        characters = await manager.list_characters(novel_id)

        context = ""
        if world and world.get("background"):
            context += f"世界观：{world['background'][:200]}\n"
        if characters:
            context += f"人物：{', '.join(c['name'] for c in characters[:5])}"

        client = get_llm_client()
        prompt = FROM_CONVERSATION_PROMPT.format(
            conversation_text=conv_text[:3000],
            context=context or "暂无",
        )
        response = await client.generate(prompt, max_tokens=2000)
        master_content = safe_json_parse(response, fallback={
            "premise": "待完善",
            "main_conflict": "待完善",
            "plot_arcs": [],
            "ending": "待完善",
            "themes": [],
        }, extract_partial=True)

        await self.upsert_master_outline(novel_id, master_content)
        return master_content


_outline_service: OutlineService | None = None


def get_outline_service() -> OutlineService:
    global _outline_service
    if _outline_service is None:
        _outline_service = OutlineService()
    return _outline_service
