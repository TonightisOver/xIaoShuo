"""AI 生成服务 — 故事线/力量体系/人物弧光/场景的 LLM 编排"""

import structlog

logger = structlog.get_logger(__name__)


class AIGenerationService:

    async def generate_from_conversation(
        self, novel_id: str, conv_id: int,
    ) -> list[dict]:
        """从对话中提取故事线"""
        from src.api.services.conversation_service import get_conversation_service
        from src.api.services.storyline_service import get_storyline_service
        from src.core.llm.client import get_llm_client
        from src.core.llm.helpers import generate_and_parse_json

        conv_service = get_conversation_service()
        conv = await conv_service.get_conversation(conv_id, novel_id)
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
        storylines_data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=[]
        )

        if not isinstance(storylines_data, list):
            storylines_data = []

        sl_service = get_storyline_service()
        created: list[dict] = []
        for sl in storylines_data:
            if isinstance(sl, dict) and sl.get("name"):
                sl_id = await sl_service.create_storyline(
                    novel_id,
                    name=sl.get("name", ""),
                    type=sl.get("type", "main"),
                    description=sl.get("description", ""),
                    key_events=sl.get("key_events", []),
                )
                created.append({"id": sl_id, **sl})

        return created

    async def generate_storylines_ai(self, novel_id: str) -> list[dict]:
        """基于已有设定 LLM 自动生成故事线"""
        from src.api.services.novel_manager import get_novel_manager
        from src.api.services.storyline_service import get_storyline_service
        from src.core.llm.client import get_llm_client
        from src.core.llm.helpers import generate_and_parse_json

        manager = get_novel_manager()
        novel = await manager.get_novel(novel_id)
        if not novel:
            raise ValueError("小说不存在")
        world = await manager.get_world_setting(novel_id)
        characters = await manager.list_characters(novel_id)

        idea_part = (novel.get('idea') or '')[:200]
        context = f"小说类型：{novel.get('novel_type', '')}\n创意：{idea_part}\n"
        if world and world.get("background"):
            context += f"世界观：{world['background'][:200]}\n"
        if characters:
            context += f"人物：{', '.join(c['name'] for c in characters[:5])}\n"

        prompt = f"""基于以下小说设定，生成 2-4 条故事线（主线+副线+暗线）。

{context}

输出 JSON 数组：
[{{"name": "线索名称", "type": "main|sub|hidden", "description": "描述", "key_events": [{{"chapter": 1, "event": "事件"}}]}}]

只输出 JSON。"""

        client = get_llm_client()
        data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=[]
        )
        if not isinstance(data, list):
            data = []

        sl_service = get_storyline_service()
        created: list[dict] = []
        for sl in data:
            if isinstance(sl, dict) and sl.get("name"):
                sl_id = await sl_service.create_storyline(
                    novel_id, name=sl["name"],
                    type=sl.get("type", "main"),
                    description=sl.get("description", ""),
                    key_events=sl.get("key_events", []),
                )
                created.append({"id": sl_id, **sl})
        return created

    async def generate_power_systems_ai(self, novel_id: str) -> list[dict]:
        """基于世界观+小说类型 LLM 自动生成力量/等级体系"""
        from src.api.services.novel_manager import get_novel_manager
        from src.core.llm.client import get_llm_client
        from src.core.llm.helpers import generate_and_parse_json

        manager = get_novel_manager()
        novel = await manager.get_novel(novel_id)
        if not novel:
            raise ValueError("小说不存在")
        world = await manager.get_world_setting(novel_id)

        idea_part = (novel.get('idea') or '')[:300]
        context_parts = [
            f"小说类型：{novel.get('novel_type', '')}",
            f"创意：{idea_part}",
        ]
        if world:
            if world.get("background"):
                context_parts.append(f"世界背景：{world['background'][:300]}")
            if world.get("rules"):
                context_parts.append(f"世界规则：{world['rules'][:300]}")

        prompt = f"""基于以下小说设定，设计完整的力量/等级体系。

{chr(10).join(context_parts)}

要求：
- 设计1-3个力量体系（如修仙境界、魔法等级、科技树等）
- 每个体系包含完整的等级序列（5-10级）
- 每级描述核心能力和突破条件

输出 JSON 数组：
[{{"name": "体系名称", "description": "体系概述", "levels": [{{"name": "等级名", "description": "核心能力", "breakthrough": "突破条件"}}]}}]

只输出 JSON。"""

        client = get_llm_client()
        data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=[]
        )
        if not isinstance(data, list):
            data = []

        created: list[dict] = []
        for ps_data in data:
            if isinstance(ps_data, dict) and ps_data.get("name"):
                ps_id = await manager.create_power_system(
                    novel_id,
                    name=ps_data.get("name", ""),
                    description=ps_data.get("description", ""),
                    levels=ps_data.get("levels", []),
                )
                created.append({"id": ps_id, **ps_data})

        return created

    async def generate_arcs_ai(self, novel_id: str) -> list[dict]:
        """基于已有人物+大纲+世界观+故事线 LLM 自动生成人物弧光"""
        from src.api.services.novel_manager import get_novel_manager
        from src.api.services.outline_service import get_outline_service
        from src.api.services.storyline_service import get_storyline_service
        from src.core.llm.client import get_llm_client
        from src.core.llm.helpers import generate_and_parse_json

        manager = get_novel_manager()
        characters = await manager.list_characters(novel_id)
        if not characters:
            return []

        novel = await manager.get_novel(novel_id)
        world = await manager.get_world_setting(novel_id)
        sl_service = get_storyline_service()
        try:
            storylines = await sl_service.list_storylines(novel_id)
        except Exception:
            logger.warning(
                "storyline_context_unavailable_for_arc_generation",
                novel_id=novel_id,
                exc_info=True,
            )
            storylines = []

        # Build rich context
        context_parts: list[str] = []
        if isinstance(novel, dict):
            context_parts.append(f"小说类型：{novel.get('novel_type', '')}")
            context_parts.append(f"核心创意：{(novel.get('idea') or '')[:500]}")
        if isinstance(world, dict):
            if world.get("background"):
                context_parts.append(f"世界背景：{world['background'][:300]}")
            if world.get("rules"):
                context_parts.append(f"世界规则：{world['rules'][:200]}")
        if storylines:
            sl_text = "\n".join(
                f"- [{sl['type']}] {sl['name']}: {(sl.get('description') or '')[:100]}"
                for sl in storylines[:5]
            )
            context_parts.append(f"已有故事线：\n{sl_text}")

        # Try to get outline for chapter structure context
        try:
            outline_svc = get_outline_service()
            master = await outline_svc.get_master_outline(novel_id)
            if master and master.get("content"):
                mc = master["content"]
                if mc.get("premise"):
                    context_parts.append(f"故事前提：{mc['premise'][:200]}")
                if mc.get("main_conflict"):
                    context_parts.append(f"主要冲突：{mc['main_conflict'][:200]}")
        except Exception:
            pass

        char_info = "\n".join(
            f"- {c['name']}({c.get('role', '未知')}): "
            f"{(c.get('description') or '')[:100]}"
            for c in characters[:10]
        )

        prompt = f"""你是人物弧光设计师。基于以下小说的完整设定，为每个主要角色设计人物弧光（成长轨迹）。

=== 小说设定 ===
{chr(10).join(context_parts)}

=== 人物 ===
{char_info}

要求：
- 每个弧光必须与小说的核心冲突、故事前提、已有故事线紧密关联
- 弧光有清晰的起点、转变过程和终点
- 人物弧光之间应有呼应（互补或对立）
- 章节范围应合理分布，避免所有弧光集中在同一段

输出 JSON 数组：
[{{"character_id": 1, "arc_type": "growth|fall|transformation|flat", "description": "弧光描述（需点明与该小说的具体关联）", "stages": [{{"chapter_range": [1, 10], "state": "状态", "trigger": "触发事件"}}]}}]

只输出 JSON。"""

        client = get_llm_client()
        data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=[]
        )
        if not isinstance(data, list):
            data = []

        created: list[dict] = []
        char_by_id = {c["id"]: c for c in characters}
        char_by_name = {c["name"]: c for c in characters}
        for arc in data:
            if not isinstance(arc, dict):
                continue
            # Prefer explicit character_id from LLM, then index-based fallback
            char_id = arc.get("character_id")
            if char_id and char_id in char_by_id:
                actual_char = char_by_id[char_id]
            else:
                # Try name matching
                char_name = arc.get("character_name") or arc.get("name")
                if char_name and char_name in char_by_name:
                    actual_char = char_by_name[char_name]
                elif data.index(arc) < len(characters):
                    actual_char = characters[data.index(arc)]
                else:
                    continue
            actual_char_id = actual_char["id"]
            arc_id = await sl_service.create_character_arc(
                novel_id, character_id=actual_char_id,
                arc_type=arc.get("arc_type", "growth"),
                description=arc.get("description", ""),
                stages=arc.get("stages", [])
            )
            arc_data = {
                k: v for k, v in arc.items()
                if k not in ("character_id", "character_name", "name")
            }
            created.append({"id": arc_id, "character_id": actual_char_id, **arc_data})
        return created

    async def generate_scenes_ai(self, novel_id: str) -> list[dict]:
        """基于世界观+大纲 LLM 自动生成场景"""
        from src.api.services.novel_manager import get_novel_manager
        from src.api.services.storyline_service import get_storyline_service
        from src.core.llm.client import get_llm_client
        from src.core.llm.helpers import generate_and_parse_json

        manager = get_novel_manager()
        world = await manager.get_world_setting(novel_id)

        context = ""
        if world:
            if world.get("geography"):
                context += f"地理：{world['geography'][:200]}\n"
            if world.get("background"):
                context += f"背景：{world['background'][:200]}\n"

        prompt = f"""基于以下世界观设定，生成 3-6 个重要场景/地点。

{context or '暂无世界观，请生成通用场景'}

输出 JSON 数组：
[{{"name": "场景名称", "location": "地理位置", "description": "描述", "appearances": [{{"chapter": 1, "event": "发生的事件"}}]}}]

只输出 JSON。"""

        client = get_llm_client()
        data = await generate_and_parse_json(
            client, prompt, max_tokens=2000, fallback=[]
        )
        if not isinstance(data, list):
            data = []

        sl_service = get_storyline_service()
        created: list[dict] = []
        for sc in data:
            if isinstance(sc, dict) and sc.get("name"):
                sc_id = await sl_service.create_scene(
                    novel_id, name=sc["name"],
                    location=sc.get("location", ""),
                    description=sc.get("description", ""),
                    appearances=sc.get("appearances", []),
                )
                created.append({"id": sc_id, **sc})
        return created


_ai_generation_service: AIGenerationService | None = None


def get_ai_generation_service() -> AIGenerationService:
    global _ai_generation_service
    if _ai_generation_service is None:
        _ai_generation_service = AIGenerationService()
    return _ai_generation_service
