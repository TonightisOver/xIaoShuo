"""创作对话 API 路由"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.services.conversation_service import get_conversation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=100)


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


@router.post("/{novel_id}/conversations", status_code=201)
async def create_conversation(novel_id: str, request: CreateConversationRequest):
    service = get_conversation_service()
    conv_id = await service.create_conversation(novel_id, request.topic)
    return {"id": conv_id, "status": "active"}


@router.get("/{novel_id}/conversations")
async def list_conversations(novel_id: str):
    service = get_conversation_service()
    return await service.list_conversations(novel_id)


@router.get("/{novel_id}/conversations/{conv_id}")
async def get_conversation(novel_id: str, conv_id: int):
    service = get_conversation_service()
    conv = await service.get_conversation(conv_id, novel_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/{novel_id}/conversations/{conv_id}/messages")
async def send_message(novel_id: str, conv_id: int, request: SendMessageRequest):
    service = get_conversation_service()
    try:
        response = await service.send_message(conv_id, request.content, novel_id)
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate response")


@router.post("/{novel_id}/conversations/{conv_id}/conclude")
async def conclude_conversation(novel_id: str, conv_id: int):
    service = get_conversation_service()
    try:
        result = await service.conclude_conversation(conv_id, novel_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class ApplySuggestionRequest(BaseModel):
    suggestion_type: str = Field(..., description="world|character|plot")
    content: str = Field(..., min_length=1)


@router.post("/{novel_id}/conversations/{conv_id}/apply-suggestion")
async def apply_suggestion(novel_id: str, conv_id: int, request: ApplySuggestionRequest):
    from src.api.services.novel_manager import get_novel_manager

    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if request.suggestion_type == "world":
        world = await manager.get_world_setting(novel_id)
        existing_bg = (world.get("background") or "") if world else ""
        existing_rules = (world.get("rules") or "") if world else ""
        # Append to background if it looks like world-building, otherwise to rules
        if any(kw in request.content for kw in ["世界", "大陆", "环境", "地理", "背景"]):
            new_bg = f"{existing_bg}\n{request.content}".strip() if existing_bg else request.content
            await manager.upsert_world_setting(novel_id, background=new_bg)
            return {"status": "applied", "target": "world_settings.background", "content": new_bg[:100]}
        else:
            new_rules = f"{existing_rules}\n{request.content}".strip() if existing_rules else request.content
            await manager.upsert_world_setting(novel_id, rules=new_rules)
            return {"status": "applied", "target": "world_settings.rules", "content": new_rules[:100]}

    elif request.suggestion_type == "character":
        # Try to extract name from content (first few chars before colon or dash)
        content = request.content
        name = content[:20].split("：")[0].split(":")[0].split("—")[0].split("-")[0].strip()
        if len(name) > 10:
            name = name[:10]
        description = content[len(name):].lstrip("：:-— ") if len(content) > len(name) else content
        from src.api.services.character_service import get_character_service
        char_id = await get_character_service().create_character(
            novel_id, name=name or "新角色",
            description=description or content
        )
        return {"status": "applied", "target": "characters", "id": char_id, "name": name}

    else:
        return {"status": "noted", "message": "情节建议已记录，请手动应用到大纲"}


class ConfirmMessageRequest(BaseModel):
    confirm_as: str = Field(..., description="world|character|storyline|outline")


@router.post("/{novel_id}/conversations/{conv_id}/messages/{msg_id}/confirm")
async def confirm_message(novel_id: str, conv_id: int, msg_id: int, request: ConfirmMessageRequest):
    service = get_conversation_service()
    try:
        result = await service.confirm_message(conv_id, msg_id, request.confirm_as, novel_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{novel_id}/conversations/{conv_id}/generate-outline")
async def generate_outline_from_conversation(novel_id: str, conv_id: int):
    service = get_conversation_service()
    try:
        result = await service.generate_outline_from_conv(novel_id, conv_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")
