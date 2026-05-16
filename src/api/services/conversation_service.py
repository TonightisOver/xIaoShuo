"""创作对话服务"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.models.db_models import Conversation, Message
from src.api.services.novel_manager import get_novel_manager
from src.core.database import get_db_session
from src.core.llm.client import get_llm_client

logger = logging.getLogger(__name__)

CONVERSATION_SYSTEM_PROMPT = """你是一位资深小说创作顾问。当前正在协助用户创作一部{novel_type}小说。

已有设定：
{context}

讨论主题：{topic}

请基于以上设定，与用户讨论并提供专业建议。回复简洁有针对性，每次回复不超过 300 字。如果需要用户做选择，列出 2-4 个选项。"""

CONCLUDE_PROMPT = """请分析以下创作对话，提取可以应用到小说设定中的结论。

对话内容：
{conversation_text}

请以 JSON 格式输出建议列表：
[{{"type": "world|character|plot", "content": "具体建议内容"}}]

只输出 JSON，不要其他说明。"""


class ConversationService:

    async def create_conversation(self, novel_id: str, topic: str) -> int:
        async with get_db_session() as session:
            conv = Conversation(
                novel_id=novel_id,
                topic=topic,
                status="active",
                created_at=datetime.now(timezone.utc),
            )
            session.add(conv)
            await session.flush()
            return conv.id

    async def list_conversations(self, novel_id: str) -> list[dict]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Conversation)
                .where(Conversation.novel_id == novel_id)
                .order_by(Conversation.created_at.desc())
            )
            return [{"id": c.id, "topic": c.topic, "status": c.status,
                     "created_at": c.created_at, "concluded_at": c.concluded_at}
                    for c in result.scalars().all()]

    async def get_conversation(self, conv_id: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == conv_id)
            )
            conv = result.scalar_one_or_none()
            if not conv:
                return None
            return {
                "id": conv.id,
                "novel_id": conv.novel_id,
                "topic": conv.topic,
                "status": conv.status,
                "created_at": conv.created_at,
                "messages": [
                    {"id": m.id, "role": m.role, "content": m.content,
                     "created_at": m.created_at}
                    for m in conv.messages
                ],
            }

    async def send_message(self, conv_id: int, content: str) -> dict:
        async with get_db_session() as session:
            # Save user message
            user_msg = Message(
                conversation_id=conv_id,
                role="user",
                content=content,
                created_at=datetime.now(timezone.utc),
            )
            session.add(user_msg)
            await session.flush()

        # Get conversation with messages for context
        conv_data = await self.get_conversation(conv_id)
        if not conv_data:
            raise ValueError("Conversation not found")

        # Build prompt with novel context
        novel_manager = get_novel_manager()
        novel = await novel_manager.get_novel(conv_data["novel_id"])
        world = await novel_manager.get_world_setting(conv_data["novel_id"])
        characters = await novel_manager.list_characters(conv_data["novel_id"])

        context_parts = []
        if world:
            world_parts = []
            if world.get("background"):
                world_parts.append(f"背景：{world['background'][:300]}")
            if world.get("rules"):
                world_parts.append(f"规则：{world['rules'][:200]}")
            if world.get("culture"):
                world_parts.append(f"文化：{world['culture'][:200]}")
            if world.get("geography"):
                world_parts.append(f"地理：{world['geography'][:200]}")
            if world_parts:
                context_parts.append("世界观：\n" + "\n".join(world_parts))
        if characters:
            for char in characters[:5]:
                char_info = f"- {char['name']}（{char.get('role', '未知')}）"
                if char.get("description"):
                    char_info += f"：{char['description'][:100]}"
                if char.get("personality"):
                    char_info += f"，性格：{char['personality'][:50]}"
                context_parts.append(char_info)
            if context_parts and characters:
                context_parts.insert(len(context_parts) - len(characters), "人物设定：")

        system_prompt = CONVERSATION_SYSTEM_PROMPT.format(
            novel_type=novel.get("novel_type", ""),
            context="\n".join(context_parts) or "暂无设定",
            topic=conv_data["topic"],
        )

        # Build messages for LLM (last 20 turns)
        history = conv_data["messages"][-20:]
        messages_text = system_prompt + "\n\n"
        for msg in history:
            role_label = "用户" if msg["role"] == "user" else "助手"
            messages_text += f"{role_label}：{msg['content']}\n\n"

        # Call LLM
        client = get_llm_client()
        ai_response = await client.generate(messages_text)

        # Save AI response
        async with get_db_session() as session:
            ai_msg = Message(
                conversation_id=conv_id,
                role="assistant",
                content=ai_response,
                created_at=datetime.now(timezone.utc),
            )
            session.add(ai_msg)
            await session.flush()
            return {"id": ai_msg.id, "role": "assistant",
                    "content": ai_response, "created_at": ai_msg.created_at}

    async def conclude_conversation(self, conv_id: int) -> dict:
        conv_data = await self.get_conversation(conv_id)
        if not conv_data:
            raise ValueError("Conversation not found")

        # Build conversation text
        conv_text = "\n".join(
            f"{'用户' if m['role'] == 'user' else 'AI'}：{m['content']}"
            for m in conv_data["messages"]
        )

        # Ask LLM to extract suggestions
        prompt = CONCLUDE_PROMPT.format(conversation_text=conv_text[:3000])
        client = get_llm_client()
        response = await client.generate(prompt)

        # Parse suggestions
        from src.core.json_utils import safe_json_parse
        suggestions = safe_json_parse(response, fallback=[], extract_partial=True)
        if not isinstance(suggestions, list):
            suggestions = []

        # Mark conversation as concluded
        async with get_db_session() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == conv_id)
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.status = "concluded"
                conv.concluded_at = datetime.now(timezone.utc)

        return {"status": "concluded", "suggestions": suggestions}


_conversation_service: ConversationService | None = None


def get_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
