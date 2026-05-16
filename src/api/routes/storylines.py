"""故事线/人物弧光/场景 API 路由"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.services.storyline_service import get_storyline_service

router = APIRouter(prefix="/api/v1/projects", tags=["storylines"])


class StorylineRequest(BaseModel):
    name: str
    type: str = "main"
    description: str | None = None
    key_events: list[dict] = Field(default_factory=list)
    status: str = "active"


class CharacterArcRequest(BaseModel):
    character_id: int
    arc_type: str = "growth"
    description: str | None = None
    stages: list[dict] = Field(default_factory=list)


class SceneRequest(BaseModel):
    name: str
    location: str | None = None
    description: str | None = None
    appearances: list[dict] = Field(default_factory=list)


class LinkCharacterRequest(BaseModel):
    character_id: int
    role_in_line: str | None = None


# --- Storylines ---

@router.get("/{novel_id}/storylines")
async def list_storylines(novel_id: str):
    service = get_storyline_service()
    return await service.list_storylines(novel_id)


@router.post("/{novel_id}/storylines", status_code=201)
async def create_storyline(novel_id: str, request: StorylineRequest):
    service = get_storyline_service()
    sl_id = await service.create_storyline(novel_id, **request.model_dump())
    return {"id": sl_id, "status": "created"}


@router.put("/{novel_id}/storylines/{sl_id}")
async def update_storyline(novel_id: str, sl_id: int, request: StorylineRequest):
    service = get_storyline_service()
    updated = await service.update_storyline(sl_id, **request.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Storyline not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/storylines/{sl_id}")
async def delete_storyline(novel_id: str, sl_id: int):
    service = get_storyline_service()
    deleted = await service.delete_storyline(sl_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Storyline not found")
    return {"status": "deleted"}


@router.post("/{novel_id}/storylines/{sl_id}/characters")
async def link_character_to_storyline(novel_id: str, sl_id: int, request: LinkCharacterRequest):
    service = get_storyline_service()
    await service.add_character_to_storyline(sl_id, request.character_id, request.role_in_line)
    return {"status": "linked"}


# --- Character Arcs ---

@router.get("/{novel_id}/character-arcs")
async def list_character_arcs(novel_id: str):
    service = get_storyline_service()
    return await service.list_character_arcs(novel_id)


@router.post("/{novel_id}/character-arcs", status_code=201)
async def create_character_arc(novel_id: str, request: CharacterArcRequest):
    service = get_storyline_service()
    arc_id = await service.create_character_arc(novel_id, **request.model_dump())
    return {"id": arc_id, "status": "created"}


@router.put("/{novel_id}/character-arcs/{arc_id}")
async def update_character_arc(novel_id: str, arc_id: int, request: CharacterArcRequest):
    service = get_storyline_service()
    updated = await service.update_character_arc(arc_id, **request.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Character arc not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/character-arcs/{arc_id}")
async def delete_character_arc(novel_id: str, arc_id: int):
    service = get_storyline_service()
    deleted = await service.delete_character_arc(arc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character arc not found")
    return {"status": "deleted"}


# --- Scenes ---

@router.get("/{novel_id}/scenes")
async def list_scenes(novel_id: str):
    service = get_storyline_service()
    return await service.list_scenes(novel_id)


@router.post("/{novel_id}/scenes", status_code=201)
async def create_scene(novel_id: str, request: SceneRequest):
    service = get_storyline_service()
    scene_id = await service.create_scene(novel_id, **request.model_dump())
    return {"id": scene_id, "status": "created"}


@router.put("/{novel_id}/scenes/{scene_id}")
async def update_scene(novel_id: str, scene_id: int, request: SceneRequest):
    service = get_storyline_service()
    updated = await service.update_scene(scene_id, **request.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/scenes/{scene_id}")
async def delete_scene(novel_id: str, scene_id: int):
    service = get_storyline_service()
    deleted = await service.delete_scene(scene_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "deleted"}


# --- Relations ---

@router.get("/{novel_id}/relations")
async def get_relations(novel_id: str):
    service = get_storyline_service()
    return await service.get_relations(novel_id)


@router.post("/{novel_id}/storylines/from-conversation/{conv_id}")
async def generate_storylines_from_conversation(novel_id: str, conv_id: int):
    service = get_storyline_service()
    try:
        created = await service.generate_from_conversation(novel_id, conv_id)
        return {"status": "generated", "storylines": created, "count": len(created)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{novel_id}/storylines/generate-ai")
async def generate_storylines_ai(novel_id: str):
    service = get_storyline_service()
    created = await service.generate_storylines_ai(novel_id)
    return {"status": "generated", "storylines": created, "count": len(created)}


@router.post("/{novel_id}/character-arcs/generate-ai")
async def generate_arcs_ai(novel_id: str):
    service = get_storyline_service()
    created = await service.generate_arcs_ai(novel_id)
    return {"status": "generated", "arcs": created, "count": len(created)}


@router.post("/{novel_id}/scenes/generate-ai")
async def generate_scenes_ai(novel_id: str):
    service = get_storyline_service()
    created = await service.generate_scenes_ai(novel_id)
    return {"status": "generated", "scenes": created, "count": len(created)}
