"""大纲生成节点"""

import json
import logging

from src.core.json_utils import safe_json_parse, validate_json_structure
from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import OUTLINE_GENERATION_PROMPT

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """大纲生成节点

    生成总体大纲和章节大纲。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        client = get_llm_client()
        prompt = OUTLINE_GENERATION_PROMPT.format(
            idea=state["idea"],
            world_setting=json.dumps(state["world_setting"], ensure_ascii=False),
            characters=json.dumps(state["characters"], ensure_ascii=False),
            target_words=state["target_words"],
        )

        logger.info(f"Generating outline for project {state['project_id']}")
        response = await client.generate(prompt, max_tokens=4000)

        # 使用改进的 JSON 解析
        fallback_data = {
            "outline": {
                "opening": "主角在家乡遭遇变故，被师父救下",
                "development": "拜入门派，开始修炼，逐渐成长",
                "climax": "邪派来袭，主角挺身而出",
                "ending": "主角战胜邪派，成为一代强者",
            },
            "chapter_outlines": [
                {
                    "chapter": 1,
                    "title": "家乡变故",
                    "plot": "主角的家乡遭到邪派袭击，师父出现相救",
                    "words": 5000,
                },
                {
                    "chapter": 2,
                    "title": "拜入门派",
                    "plot": "主角跟随师父来到门派，开始修炼之路",
                    "words": 5000,
                },
            ],
        }

        result = safe_json_parse(
            response, fallback=fallback_data, extract_partial=True
        )

        # 验证 JSON 结构
        if not validate_json_structure(
            result, ["outline", "chapter_outlines"], "outline_generation"
        ):
            logger.warning("Invalid outline_generation structure, using fallback")
            result = fallback_data

        outline = result.get("outline", {})
        chapter_outlines = result.get("chapter_outlines", [])

        return {
            **state,
            "outline": outline,
            "chapter_outlines": chapter_outlines,
            "current_stage": "outline_generation_completed",
        }

    except Exception as e:
        logger.error(f"Outline generation failed, using fallback: {e}")
        outline = {
            "opening": "主角在家乡遭遇变故，被师父救下",
            "development": "拜入门派，开始修炼，逐渐成长",
            "climax": "邪派来袭，主角挺身而出",
            "ending": "主角战胜邪派，成为一代强者",
        }

        chapter_outlines = [
            {
                "chapter": 1,
                "title": "家乡变故",
                "plot": "主角的家乡遭到邪派袭击，师父出现相救",
                "words": 5000,
            },
            {
                "chapter": 2,
                "title": "拜入门派",
                "plot": "主角跟随师父来到门派，开始修炼之路",
                "words": 5000,
            },
            {
                "chapter": 3,
                "title": "初露锋芒",
                "plot": "主角在门派比武中展现天赋",
                "words": 5000,
            },
        ]

        return {
            **state,
            "outline": outline,
            "chapter_outlines": chapter_outlines,
            "current_stage": "outline_generation_completed",
            "errors": state["errors"] + [f"outline_generation API failed: {str(e)}"],
        }
