"""Career system generation and progression services."""

from typing import Any

from sqlalchemy import select

from src.api.models.db_models import CareerSystem, CharacterCareer
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
