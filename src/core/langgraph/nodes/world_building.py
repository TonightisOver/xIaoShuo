"""世界观构建节点"""

import logging

from src.core.json_utils import validate_json_structure
from src.core.langgraph.node_utils import generate_and_validate
from src.core.langgraph.schemas import WorldSetting
from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import WORLD_BUILDING_PROMPT
from src.core.validation import get_style_instruction

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """世界观构建节点

    构建小说的世界观、背景设定、规则体系。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        client = get_llm_client()
        prompt = WORLD_BUILDING_PROMPT.format(
            idea=state["idea"],
            novel_type=state["novel_type"],
        )

        logger.info(f"Building world for project {state['project_id']}")
        style_instruction = get_style_instruction(state.get("writing_style", ""), state.get("writing_style_prompt", ""))
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"

        # fallback 仍用 dict 形式（与原 state 兼容）
        fallback_world_setting = {
            "background": f"这是一个{state['novel_type']}世界，拥有独特的力量体系。",
            "rules": "修炼分为炼气、筑基、金丹、元婴等境界。",
            "geography": "世界分为东、西、南、北四大域，中央为圣地。",
            "culture": "修仙门派林立，凡人王朝并存。",
        }
        fallback_model = WorldSetting.model_validate(fallback_world_setting)

        # generate_and_validate：LLM 调用 + 解析 + Pydantic 校验 + 失败重试一次
        typed = await generate_and_validate(
            client, prompt, WorldSetting, "world_building", fallback=fallback_model,
        )
        # 转回 dict 写入 state（state 字段类型是 dict）
        world_setting = typed.model_dump() if typed else fallback_world_setting

        # 兜底：确保 4 个必需 key 都存在
        required_keys = ["background", "rules", "geography", "culture"]
        if not validate_json_structure(world_setting, required_keys, "world_setting"):
            logger.warning("Invalid world_setting structure, using fallback")
            world_setting = fallback_world_setting

        return {
            **state,
            "world_setting": world_setting,
            "current_stage": "world_building_completed",
        }

    except Exception as e:
        logger.error(f"World building failed, using fallback: {e}")
        world_setting = {
            "background": f"这是一个{state['novel_type']}世界，拥有独特的力量体系。",
            "rules": "修炼分为炼气、筑基、金丹、元婴等境界。",
            "geography": "世界分为东、西、南、北四大域，中央为圣地。",
            "culture": "修仙门派林立，凡人王朝并存。",
        }

        return {
            **state,
            "world_setting": world_setting,
            "current_stage": "world_building_completed",
            "errors": state["errors"] + [f"world_building API failed: {str(e)}"],
        }
