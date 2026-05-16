"""故事线/人物弧光/场景管理服务"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from src.api.models.db_models import (
    CharacterArc, Scene, Storyline, StorylineCharacter,
)
from src.core.database import get_db_session

logger = logging.getLogger(__name__)


class StorylineService:

    # --- Storylines ---

    async def list_storylines(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Storyline).where(Storyline.novel_id == novel_id)
            )
            return [{"id": s.id, "name": s.name, "type": s.type,
                     "description": s.description, "key_events": s.key_events,
                     "status": s.status} for s in result.scalars().all()]

    async def create_storyline(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            sl = Storyline(novel_id=novel_id, **kwargs,
                           updated_at=datetime.now(timezone.utc))
            session.add(sl)
            await session.flush()
            return sl.id

    async def update_storyline(self, sl_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(Storyline).where(Storyline.id == sl_id))
            sl = result.scalar_one_or_none()
            if not sl:
                return False
            for k, v in kwargs.items():
                if hasattr(sl, k) and v is not None:
                    setattr(sl, k, v)
            sl.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_storyline(self, sl_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(Storyline).where(Storyline.id == sl_id))
            sl = result.scalar_one_or_none()
            if not sl:
                return False
            await session.delete(sl)
        return True

    # --- Character Arcs ---

    async def list_character_arcs(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(CharacterArc).where(CharacterArc.novel_id == novel_id)
            )
            return [{"id": a.id, "character_id": a.character_id,
                     "arc_type": a.arc_type, "description": a.description,
                     "stages": a.stages} for a in result.scalars().all()]

    async def create_character_arc(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            arc = CharacterArc(novel_id=novel_id, **kwargs,
                               updated_at=datetime.now(timezone.utc))
            session.add(arc)
            await session.flush()
            return arc.id

    async def update_character_arc(self, arc_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(CharacterArc).where(CharacterArc.id == arc_id))
            arc = result.scalar_one_or_none()
            if not arc:
                return False
            for k, v in kwargs.items():
                if hasattr(arc, k) and v is not None:
                    setattr(arc, k, v)
            arc.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_character_arc(self, arc_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(CharacterArc).where(CharacterArc.id == arc_id))
            arc = result.scalar_one_or_none()
            if not arc:
                return False
            await session.delete(arc)
        return True

    # --- Scenes ---

    async def list_scenes(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Scene).where(Scene.novel_id == novel_id)
            )
            return [{"id": s.id, "name": s.name, "location": s.location,
                     "description": s.description, "appearances": s.appearances}
                    for s in result.scalars().all()]

    async def create_scene(self, novel_id: str, **kwargs) -> int:
        async with get_db_session() as session:
            scene = Scene(novel_id=novel_id, **kwargs,
                          updated_at=datetime.now(timezone.utc))
            session.add(scene)
            await session.flush()
            return scene.id

    async def update_scene(self, scene_id: int, **kwargs) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(Scene).where(Scene.id == scene_id))
            scene = result.scalar_one_or_none()
            if not scene:
                return False
            for k, v in kwargs.items():
                if hasattr(scene, k) and v is not None:
                    setattr(scene, k, v)
            scene.updated_at = datetime.now(timezone.utc)
        return True

    async def delete_scene(self, scene_id: int) -> bool:
        async with get_db_session() as session:
            result = await session.execute(select(Scene).where(Scene.id == scene_id))
            scene = result.scalar_one_or_none()
            if not scene:
                return False
            await session.delete(scene)
        return True

    # --- Relations ---

    async def add_character_to_storyline(self, storyline_id: int,
                                         character_id: int, role: str | None = None) -> None:
        async with get_db_session() as session:
            sc = StorylineCharacter(
                storyline_id=storyline_id,
                character_id=character_id,
                role_in_line=role,
            )
            session.add(sc)

    async def get_relations(self, novel_id: str) -> dict[str, Any]:
        storylines = await self.list_storylines(novel_id)
        arcs = await self.list_character_arcs(novel_id)
        scenes = await self.list_scenes(novel_id)

        # Get storyline-character links
        async with get_db_session() as session:
            result = await session.execute(select(StorylineCharacter))
            links = [{"storyline_id": sc.storyline_id, "character_id": sc.character_id,
                      "role_in_line": sc.role_in_line} for sc in result.scalars().all()]

        sl_ids = {s["id"] for s in storylines}
        links = [l for l in links if l["storyline_id"] in sl_ids]

        return {
            "storylines": storylines,
            "character_arcs": arcs,
            "scenes": scenes,
            "storyline_character_links": links,
        }

    async def generate_from_conversation(self, novel_id: str, conv_id: int) -> list[dict]:
        """从对话中提取故事线"""
        from src.api.services.conversation_service import get_conversation_service
        from src.core.llm.client import get_llm_client
        from src.core.json_utils import safe_json_parse

        conv_service = get_conversation_service()
        conv = await conv_service.get_conversation(conv_id)
        if not conv:
            raise ValueError("对话不存在")

        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else 'AI'}：{m['content']}"
            for m in conv.get("messages", [])
        )

        prompt = f"""分析以下创作对话，提取故事线结构。

对话内容：
{conv_text[:3000]}

请提取出故事线，输出 JSON 数组：
[{{"name": "线索名称", "type": "main|sub|hidden", "description": "描述", "key_events": [{{"chapter": 1, "event": "事件描述"}}]}}]

只输出 JSON。"""

        client = get_llm_client()
        response = await client.generate(prompt, max_tokens=2000)
        storylines_data = safe_json_parse(response, fallback=[], extract_partial=True)

        if not isinstance(storylines_data, list):
            storylines_data = []

        created = []
        for sl in storylines_data:
            if isinstance(sl, dict) and sl.get("name"):
                sl_id = await self.create_storyline(
                    novel_id,
                    name=sl.get("name", ""),
                    type=sl.get("type", "main"),
                    description=sl.get("description", ""),
                    key_events=sl.get("key_events", []),
                )
                created.append({"id": sl_id, **sl})

        return created


_storyline_service: StorylineService | None = None


def get_storyline_service() -> StorylineService:
    global _storyline_service
    if _storyline_service is None:
        _storyline_service = StorylineService()
    return _storyline_service
