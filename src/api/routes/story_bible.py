"""故事圣经 (Novel Bible) API 路由"""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from src.api.models.db_models import Novel, StoryBible
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/projects/{novel_id}/story-bible",
    tags=["story-bible"],
)


# --- Request/Response Models ---

class StoryBibleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    novel_id: str
    worldview_rules: str = ""
    character_cards: list[dict] = []
    faction_relations: str = ""
    location_settings: str = ""
    prop_settings: str = ""
    foreshadowing_list: list[dict] = []
    hard_settings: str = ""
    timeline_events: list[dict] = []
    unresolved_hooks: list[dict] = []
    main_goals: list[dict] = []
    banned_elements: list[dict] = []


class StoryBibleUpdate(BaseModel):
    worldview_rules: str | None = None
    character_cards: list[dict] | None = None
    faction_relations: str | None = None
    location_settings: str | None = None
    prop_settings: str | None = None
    foreshadowing_list: list[dict] | None = None
    hard_settings: str | None = None
    timeline_events: list[dict] | None = None
    unresolved_hooks: list[dict] | None = None
    main_goals: list[dict] | None = None
    banned_elements: list[dict] | None = None


# --- Endpoints ---

@router.get("", response_model=StoryBibleResponse)
async def get_story_bible(novel_id: str):
    """获取小说的故事圣经。如果不存在，则自动初始化一条空记录。"""
    async with get_db_session() as session:
        # Check if novel exists first
        novel_result = await session.execute(
            select(Novel).where(Novel.novel_id == novel_id)
        )
        novel = novel_result.scalar_one_or_none()
        if not novel:
            raise HTTPException(status_code=404, detail="Novel project not found")

        # Query story bible
        bible_result = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        bible = bible_result.scalar_one_or_none()

        if not bible:
            logger.info("Initializing new StoryBible", novel_id=novel_id)
            bible = StoryBible(
                novel_id=novel_id,
                worldview_rules="",
                character_cards=[],
                faction_relations="",
                location_settings="",
                prop_settings="",
                foreshadowing_list=[],
                hard_settings="",
                timeline_events=[],
                unresolved_hooks=[],
                main_goals=[],
                banned_elements=[],
            )
            session.add(bible)
            # Commit will be handled by the context manager get_db_session
            await session.flush()

        return bible


@router.put("", response_model=StoryBibleResponse)
async def update_story_bible(novel_id: str, body: StoryBibleUpdate):
    """更新小说的故事圣经设定"""
    async with get_db_session() as session:
        # Query story bible
        bible_result = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        bible = bible_result.scalar_one_or_none()

        if not bible:
            # Try to initialize if missing
            novel_result = await session.execute(
                select(Novel).where(Novel.novel_id == novel_id)
            )
            novel = novel_result.scalar_one_or_none()
            if not novel:
                raise HTTPException(status_code=404, detail="Novel project not found")

            bible = StoryBible(
                novel_id=novel_id,
                worldview_rules="",
                character_cards=[],
                faction_relations="",
                location_settings="",
                prop_settings="",
                foreshadowing_list=[],
                hard_settings="",
                timeline_events=[],
                unresolved_hooks=[],
                main_goals=[],
                banned_elements=[],
            )
            session.add(bible)

        # Apply updates
        if body.worldview_rules is not None:
            bible.worldview_rules = body.worldview_rules
        if body.character_cards is not None:
            bible.character_cards = body.character_cards
        if body.faction_relations is not None:
            bible.faction_relations = body.faction_relations
        if body.location_settings is not None:
            bible.location_settings = body.location_settings
        if body.prop_settings is not None:
            bible.prop_settings = body.prop_settings
        if body.foreshadowing_list is not None:
            bible.foreshadowing_list = body.foreshadowing_list
        if body.hard_settings is not None:
            bible.hard_settings = body.hard_settings
        if getattr(body, "timeline_events", None) is not None:
            bible.timeline_events = body.timeline_events
        if getattr(body, "unresolved_hooks", None) is not None:
            bible.unresolved_hooks = body.unresolved_hooks
        if getattr(body, "main_goals", None) is not None:
            bible.main_goals = body.main_goals
        if getattr(body, "banned_elements", None) is not None:
            bible.banned_elements = body.banned_elements

        session.add(bible)
        return bible
