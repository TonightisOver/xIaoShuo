"""Career system generation and progression services."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select

from src.api.models.db_models import (
    CareerSystem,
    Character,
    CharacterCareer,
)
from src.core.database import get_db_session
from src.core.llm.helpers import generate_and_parse_json


def _normalize_career(
    raw: dict[str, Any], category: str | None = None
) -> dict[str, Any]:
    stages = raw.get("stages") or []
    if not isinstance(stages, list):
        stages = []

    max_stage = raw.get("max_stage")
    if not isinstance(max_stage, int):
        max_stage = len(stages) if stages else None

    attribute_bonuses = raw.get("attribute_bonuses") or {}
    if not isinstance(attribute_bonuses, dict):
        attribute_bonuses = {}

    return {
        "name": raw.get("name", ""),
        "category": raw.get("category") or category or "sub",
        "description": raw.get("description", ""),
        "stages": stages,
        "max_stage": max_stage,
        "requirements": raw.get("requirements", ""),
        "special_abilities": raw.get("special_abilities", ""),
        "worldview_rules": raw.get("worldview_rules", ""),
        "attribute_bonuses": attribute_bonuses,
    }


def _flatten_career_data(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        careers: list[dict[str, Any]] = []
        for item in data.get("main_careers", []):
            if isinstance(item, dict):
                careers.append(_normalize_career(item, "main"))
        for item in data.get("sub_careers", []):
            if isinstance(item, dict):
                careers.append(_normalize_career(item, "sub"))
        if careers:
            return careers
        data = data.get("careers", [])

    if not isinstance(data, list):
        return []

    careers = []
    for item in data:
        if isinstance(item, dict) and item.get("name"):
            careers.append(_normalize_career(item))
    return careers


async def generate_career_system(
    client: Any,
    project_context: dict[str, Any],
    main_count: int = 2,
    sub_count: int = 6,
) -> list[dict[str, Any]]:
    """Generate a main/sub career system from project worldview context."""
    world_context = project_context.get("world_context", "")
    prompt = f"""你是网络小说职业体系设定师。
请基于以下项目和世界观上下文，生成完整的职业+等级阶段体系。

=== 项目上下文 ===
标题：{project_context.get("title", "")}
类型：{project_context.get("novel_type", "")}
核心创意：{project_context.get("idea", "")}

=== 世界观上下文 ===
{world_context or "暂无明确世界观，请根据题材生成自洽设定。"}

要求：
- 生成 {main_count} 个主职业和 {sub_count} 个副职业。
- 每个职业必须有 stages。
- stages 格式为 {{"level": 1, "name": "阶段名", "description": "能力变化"}}。
- 每个职业包含 max_stage、requirements、special_abilities、worldview_rules。
- attribute_bonuses 使用 JSON 对象，例如 {{"strength": "+10%", "spirit": "+5%"}}。
- 主职业推动战斗/成长主线，副职业服务生产、社交、探索或世界机制。
- 所有规则必须贴合上面的世界观上下文。

输出 JSON：
{{
  "main_careers": [
    {{
      "name": "职业名",
      "category": "main",
      "description": "职业概述",
      "stages": [{{"level": 1, "name": "阶段名", "description": "阶段描述"}}],
      "max_stage": 5,
      "requirements": "入门或晋升要求",
      "special_abilities": "核心能力",
      "worldview_rules": "世界观规则约束",
      "attribute_bonuses": {{"strength": "+10%"}}
    }}
  ],
  "sub_careers": [
    {{
      "name": "职业名",
      "category": "sub",
      "description": "职业概述",
      "stages": [{{"level": 1, "name": "阶段名", "description": "阶段描述"}}],
      "max_stage": 5,
      "requirements": "入门或晋升要求",
      "special_abilities": "核心能力",
      "worldview_rules": "世界观规则约束",
      "attribute_bonuses": {{"crafting": "+10%"}}
    }}
  ]
}}

只输出 JSON。"""

    data = await generate_and_parse_json(
        client, prompt, max_tokens=3000, temperature=0.7, fallback={}
    )
    return _flatten_career_data(data)


async def get_career_progression(character_id: int) -> list[dict[str, Any]]:
    """Get assigned career progression for a character."""
    async with get_db_session() as session:
        result = await session.execute(
            select(CharacterCareer, CareerSystem)
            .join(CareerSystem, CharacterCareer.career_id == CareerSystem.id)
            .where(CharacterCareer.character_id == character_id)
        )
        progression = []
        for character_career, career in result.all():
            stages = career.stages or []
            current_stage_data = next(
                (
                    stage for stage in stages
                    if stage.get("level") == character_career.current_stage
                ),
                None,
            )
            progression.append({
                "id": character_career.id,
                "character_id": character_career.character_id,
                "career_id": career.id,
                "career_name": career.name,
                "category": career.category,
                "current_stage": character_career.current_stage,
                "current_stage_data": current_stage_data,
                "max_stage": career.max_stage,
                "stages": stages,
                "attribute_bonuses": career.attribute_bonuses or {},
                "updated_at": character_career.updated_at,
            })
        return progression


def _coerce_career_id(raw: Any) -> int | None:
    """Best-effort conversion of a frontend career id into a DB int id.

    The frontend may carry string pseudo-ids (e.g. 'def-xiuxian', 'ai-...') for
    LocalStorage-backed careers that have no DB row. Such ids are not numeric
    and must map to None so callers can skip them gracefully.
    """
    if isinstance(raw, bool):  # bool is a subclass of int, guard it
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if raw == "":
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _stage_index_to_level(career: CareerSystem, stage_index: Any) -> int:
    """Translate a 0-based stage array index into a 1-based current_stage level.

    The frontend dropdown uses array indices as option values, while the DB
    stores the 1-based level. When stages carry a `level` field we prefer the
    explicit value; otherwise we fall back to index+1.
    """
    default = 1
    try:
        idx = int(stage_index)
    except (TypeError, ValueError):
        return default
    stages = career.stages or []
    if 0 <= idx < len(stages):
        stage = stages[idx]
        if isinstance(stage, dict):
            level = stage.get("level")
            if isinstance(level, int) and level > 0:
                return level
        return idx + 1
    return default


def _level_to_stage_index(career: CareerSystem, level: int) -> int:
    """Translate a 1-based current_stage level into a 0-based stage array index."""
    stages = career.stages or []
    for i, stage in enumerate(stages):
        if isinstance(stage, dict) and stage.get("level") == level:
            return i
    # Fallback: assume stages are ordered and level maps to index level-1.
    if level and level > 0:
        return min(level - 1, max(len(stages) - 1, 0))
    return 0


async def upsert_careers(novel_id: str, careers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bulk upsert careers for a novel, de-duplicating by name.

    Frontend sends the full career list (including possibly string pseudo-ids
    for LocalStorage-only entries). We match existing rows by name within the
    novel; rows without a name are skipped. Returns the resulting DB rows so
    the route can hand back stable integer ids.
    """
    async with get_db_session() as session:
        existing_result = await session.execute(
            select(CareerSystem).where(CareerSystem.novel_id == novel_id)
        )
        existing_by_name: dict[str, CareerSystem] = {
            c.name: c for c in existing_result.scalars().all()
        }

        result_rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for raw in careers:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_career(raw)
            name = normalized.get("name")
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            career = existing_by_name.get(name)
            if career is None:
                career = CareerSystem(
                    novel_id=novel_id,
                    name=name,
                    category=normalized["category"],
                    description=normalized["description"],
                    stages=normalized["stages"],
                    max_stage=normalized["max_stage"],
                    requirements=normalized["requirements"],
                    special_abilities=normalized["special_abilities"],
                    worldview_rules=normalized["worldview_rules"],
                    attribute_bonuses=normalized["attribute_bonuses"],
                    updated_at=datetime.now(UTC),
                )
                session.add(career)
            else:
                career.category = normalized["category"]
                career.description = normalized["description"]
                career.stages = normalized["stages"]
                career.max_stage = normalized["max_stage"]
                career.requirements = normalized["requirements"]
                career.special_abilities = normalized["special_abilities"]
                career.worldview_rules = normalized["worldview_rules"]
                career.attribute_bonuses = normalized["attribute_bonuses"]
                career.updated_at = datetime.now(UTC)
            await session.flush()
            result_rows.append(_career_to_dict_from_service(career))

        return result_rows


def _career_to_dict_from_service(career: CareerSystem) -> dict[str, Any]:
    return {
        "id": career.id,
        "novel_id": career.novel_id,
        "name": career.name,
        "category": career.category,
        "description": career.description,
        "stages": career.stages,
        "max_stage": career.max_stage,
        "requirements": career.requirements,
        "special_abilities": career.special_abilities,
        "worldview_rules": career.worldview_rules,
        "attribute_bonuses": career.attribute_bonuses,
        "updated_at": career.updated_at,
    }


async def list_character_career_assignments(novel_id: str) -> list[dict[str, Any]]:
    """Return character-career assignments for a novel using frontend contract.

    Output shape: [{ character_id, career_id, stage_index }]. stage_index is a
    0-based index into the career's stages array, derived from the stored
    1-based current_stage level.
    """
    async with get_db_session() as session:
        result = await session.execute(
            select(CharacterCareer, CareerSystem)
            .join(CareerSystem, CharacterCareer.career_id == CareerSystem.id)
            .join(Character, CharacterCareer.character_id == Character.id)
            .where(Character.novel_id == novel_id)
        )
        assignments: list[dict[str, Any]] = []
        for character_career, career in result.all():
            assignments.append({
                "character_id": character_career.character_id,
                "career_id": career.id,
                "stage_index": _level_to_stage_index(career, character_career.current_stage),
            })
        return assignments


async def save_character_career_assignment(
    novel_id: str,
    character_id: int,
    career_id: Any,
    stage_index: Any,
) -> dict[str, Any]:
    """Upsert (or clear) a character-career assignment.

    Frontend contract: body { character_id, career_id, stage_index }. When
    career_id is empty/non-numeric the assignment is cleared (idempotent).
    stage_index is a 0-based array index translated to a 1-based level.
    """
    career_int_id = _coerce_career_id(career_id)

    async with get_db_session() as session:
        char_result = await session.execute(
            select(Character).where(
                Character.id == character_id,
                Character.novel_id == novel_id,
            )
        )
        if not char_result.scalar_one_or_none():
            return {"status": "skipped", "reason": "character_not_found"}

        # Clear assignment when no valid career id is provided.
        if career_int_id is None:
            await session.execute(
                delete(CharacterCareer).where(
                    CharacterCareer.character_id == character_id
                )
            )
            await session.flush()
            return {
                "character_id": character_id,
                "career_id": None,
                "stage_index": stage_index,
                "status": "cleared",
            }

        career_result = await session.execute(
            select(CareerSystem).where(
                CareerSystem.id == career_int_id,
                CareerSystem.novel_id == novel_id,
            )
        )
        career = career_result.scalar_one_or_none()
        if career is None:
            return {"status": "skipped", "reason": "career_not_found"}

        current_stage = _stage_index_to_level(career, stage_index)
        if career.max_stage is not None and current_stage > career.max_stage:
            current_stage = career.max_stage

        existing_result = await session.execute(
            select(CharacterCareer).where(
                CharacterCareer.character_id == character_id,
                CharacterCareer.career_id == career_int_id,
            )
        )
        character_career = existing_result.scalar_one_or_none()
        if character_career:
            character_career.current_stage = current_stage
            character_career.updated_at = datetime.now(UTC)
            status = "updated"
        else:
            character_career = CharacterCareer(
                character_id=character_id,
                career_id=career_int_id,
                current_stage=current_stage,
                updated_at=datetime.now(UTC),
            )
            session.add(character_career)
            status = "created"

        await session.flush()
        return {
            "id": character_career.id,
            "character_id": character_id,
            "career_id": career_int_id,
            "stage_index": stage_index,
            "current_stage": character_career.current_stage,
            "status": status,
        }


async def delete_career(novel_id: str, career_id: Any) -> bool:
    """Delete a career by id. Returns True if a row was removed.

    Non-numeric ids (frontend pseudo-ids) resolve to None and are treated as
    no-ops so the endpoint stays idempotent.
    """
    int_id = _coerce_career_id(career_id)
    if int_id is None:
        return False
    async with get_db_session() as session:
        result = await session.execute(
            select(CareerSystem).where(
                CareerSystem.id == int_id,
                CareerSystem.novel_id == novel_id,
            )
        )
        career = result.scalar_one_or_none()
        if career is None:
            return False
        await session.delete(career)
        await session.flush()
        return True
