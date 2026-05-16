"""人物设计节点"""

import json
import logging

from src.core.json_utils import safe_json_parse, validate_json_structure
from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import CHARACTER_DESIGN_PROMPT
from src.core.validation import WRITING_STYLES

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """人物设计节点

    设计主要人物和人物关系。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        client = get_llm_client()
        prompt = CHARACTER_DESIGN_PROMPT.format(
            idea=state["idea"],
            world_setting=json.dumps(state["world_setting"], ensure_ascii=False),
        )

        logger.info(f"Designing characters for project {state['project_id']}")
        style_instruction = WRITING_STYLES.get(state.get("writing_style", ""), "")
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"
        response = await client.generate(prompt)

        # 使用改进的 JSON 解析
        fallback_data = {
            "characters": [
                {
                    "name": "张三",
                    "role": "主角",
                    "personality": "坚韧不拔，重情重义",
                    "background": "出身平凡，机缘巧合踏上修仙之路",
                    "goal": "成为强者，保护家人",
                    "ability": "未知天赋",
                },
                {
                    "name": "李四",
                    "role": "配角",
                    "personality": "严厉但关爱弟子",
                    "background": "某大派长老",
                    "goal": "培养弟子",
                    "ability": "高深修为",
                },
            ],
            "relationships": {
                "张三-李四": "师徒关系",
            },
        }

        result = safe_json_parse(
            response, fallback=fallback_data, extract_partial=True
        )

        # 验证 JSON 结构
        if not validate_json_structure(
            result, ["characters", "relationships"], "character_design"
        ):
            logger.warning("Invalid character_design structure, using fallback")
            result = fallback_data

        characters = result.get("characters", [])
        relationships = result.get("relationships", {})

        return {
            **state,
            "characters": characters,
            "relationships": relationships,
            "current_stage": "character_design_completed",
        }

    except Exception as e:
        logger.error(f"Character design failed, using fallback: {e}")
        characters = [
            {
                "name": "张三",
                "role": "主角",
                "personality": "坚韧不拔，重情重义",
                "background": "出身平凡，机缘巧合踏上修仙之路",
                "goal": "成为强者，保护家人",
                "ability": "未知天赋",
            },
            {
                "name": "李四",
                "role": "配角",
                "personality": "严厉但关爱弟子",
                "background": "某大派长老",
                "goal": "培养弟子",
                "ability": "高深修为",
            },
            {
                "name": "王五",
                "role": "反派",
                "personality": "阴险狡诈",
                "background": "邪派高手",
                "goal": "称霸武林",
                "ability": "邪功",
            },
        ]

        relationships = {
            "张三-李四": "师徒关系",
            "张三-王五": "敌对关系",
        }

        return {
            **state,
            "characters": characters,
            "relationships": relationships,
            "current_stage": "character_design_completed",
            "errors": state["errors"] + [f"character_design API failed: {str(e)}"],
        }
