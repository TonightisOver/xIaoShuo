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
    conv = await service.get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.post("/{novel_id}/conversations/{conv_id}/messages")
async def send_message(novel_id: str, conv_id: int, request: SendMessageRequest):
    service = get_conversation_service()
    try:
        response = await service.send_message(conv_id, request.content)
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
        result = await service.conclude_conversation(conv_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
