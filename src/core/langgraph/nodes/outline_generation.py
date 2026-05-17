"""大纲生成节点"""

import json
import logging

from src.core.json_utils import safe_json_parse
from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import OUTLINE_GENERATION_PROMPT
from src.core.validation import get_style_instruction

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
        style_instruction = get_style_instruction(state.get("writing_style", ""), state.get("writing_style_prompt", ""))
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"
        response = await client.generate(prompt, max_tokens=4000)

        # 使用改进的 JSON 解析
        fallback_data = {
            "outline": {
                "opening": "主角在家乡遭遇变故，被师父救下",
                "development": "拜入门派，开始修炼，逐渐成长",
                "climax": "邪派来袭，主角挺身而出",
                "ending": "主角战胜邪派，成为一代强者",
            },
            "volumes": [
                {
                    "volume_number": 1,
                    "title": "初入江湖",
                    "summary": "主角遭遇变故，拜入门派开始修炼",
                    "chapters": [
                        {"chapter": 1, "title": "家乡变故", "plot": "主角的家乡遭到邪派袭击", "words": 5000},
                        {"chapter": 2, "title": "拜入门派", "plot": "跟随师父来到门派", "words": 5000},
                    ],
                },
            ],
        }

        result = safe_json_parse(
            response, fallback=fallback_data, extract_partial=True
        )

        outline = result.get("outline", {})
        volumes = result.get("volumes", [])

        # 从 volumes 中提取 chapter_outlines（兼容旧格式）
        chapter_outlines = result.get("chapter_outlines", [])
        if not chapter_outlines and volumes:
            for vol in volumes:
                for ch in vol.get("chapters", []):
                    ch["volume_number"] = vol.get("volume_number", 1)
                    chapter_outlines.append(ch)

        return {
            **state,
            "outline": outline,
            "volumes": volumes,
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

        volumes = [
            {
                "volume_number": 1,
                "title": "初入江湖",
                "summary": "主角遭遇变故，拜入门派",
                "chapters": [
                    {"chapter": 1, "title": "家乡变故", "plot": "邪派袭击", "words": 5000, "volume_number": 1},
                    {"chapter": 2, "title": "拜入门派", "plot": "开始修炼", "words": 5000, "volume_number": 1},
                    {"chapter": 3, "title": "初露锋芒", "plot": "门派比武", "words": 5000, "volume_number": 1},
                ],
            },
        ]

        chapter_outlines = []
        for vol in volumes:
            chapter_outlines.extend(vol["chapters"])

        return {
            **state,
            "outline": outline,
            "volumes": volumes,
            "chapter_outlines": chapter_outlines,
            "current_stage": "outline_generation_completed",
            "errors": state["errors"] + [f"outline_generation API failed: {str(e)}"],
        }
