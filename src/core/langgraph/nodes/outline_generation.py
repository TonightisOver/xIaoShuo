"""大纲生成节点"""

import json
import logging

from src.core.json_utils import safe_json_parse
from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import (
    MASTER_OUTLINE_PROMPT,
    OUTLINE_GENERATION_PROMPT,
    VOLUME_OUTLINE_PROMPT,
)
from src.core.validation import get_style_instruction

logger = logging.getLogger(__name__)

# Chapter type distribution template for volume outline
CHAPTER_TYPES_TEMPLATE = """
- main_advance（主线推进）：约 {main_advance} 章
- climax（高潮章）：约 {climax} 章
- aftermath（余波章）：约 {aftermath} 章
- daily（日常章）：约 {daily} 章
- setup（铺垫章）：约 {setup} 章
- filler（注水章）：约 0 章
"""


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


async def master_outline_generation_node(state: NovelState) -> NovelState:
    """总纲生成节点（百万字长篇专用）

    生成三级大纲的第一级：总纲（卷级概述 + 主线规划 + 伏笔分布）。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        client = get_llm_client()
        volumes_count = state.get("total_volumes") or 10
        chapters_per_vol = state.get("chapters_per_volume") or 40
        words_per_chapter = state.get("target_words_per_chapter") or 3000

        prompt = MASTER_OUTLINE_PROMPT.format(
            idea=state["idea"],
            novel_type=state["novel_type"],
            target_words=state["target_words"],
            volumes=volumes_count,
            chapters_per_volume=chapters_per_vol,
            words_per_chapter=words_per_chapter,
        )

        logger.info(f"Generating master outline for project {state['project_id']}")
        style_instruction = get_style_instruction(
            state.get("writing_style", ""),
            state.get("writing_style_prompt", ""),
        )
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"

        response = await client.generate(prompt, max_tokens=6000)

        # Fallback data for parsing failure
        fallback_volumes = []
        for i in range(1, volumes_count + 1):
            fallback_volumes.append({
                "volume_number": i,
                "title": f"第{i}卷",
                "summary": f"本卷主要情节发展",
                "chapter_types": {
                    "main_advance": int(chapters_per_vol * 0.45),
                    "climax": int(chapters_per_vol * 0.12),
                    "aftermath": int(chapters_per_vol * 0.08),
                    "daily": int(chapters_per_vol * 0.15),
                    "setup": int(chapters_per_vol * 0.15),
                    "filler": 0,
                },
                "key_events": [],
                "foreshadows_planted": [],
                "foreshadows_resolved": [],
            })

        fallback_data = {
            "title": state.get("idea", "")[:20],
            "synopsis": state["idea"],
            "main_conflict": "待展开",
            "main_theme": "待确定",
            "volumes": fallback_volumes,
            "foreshadow_plan": [],
            "character_plan": [],
        }

        result = safe_json_parse(
            response, fallback=fallback_data, extract_partial=True
        )

        return {
            **state,
            "master_outline": result,
            "volumes": result.get("volumes", []),
            "outline": {
                "opening": result.get("synopsis", ""),
                "development": result.get("main_conflict", ""),
                "climax": result.get("main_theme", ""),
                "ending": "",
            },
            "current_stage": "master_outline_completed",
        }

    except Exception as e:
        logger.error(f"Master outline generation failed: {e}")
        return {
            **state,
            "master_outline": {
                "title": state.get("idea", "")[:20],
                "synopsis": state["idea"],
                "volumes": [],
            },
            "volumes": [],
            "current_stage": "master_outline_completed",
            "errors": state.get("errors", []) + [f"master_outline failed: {str(e)}"],
        }


async def volume_outline_generation_node(state: NovelState) -> NovelState:
    """卷纲细化节点（百万字长篇专用）

    生成三级大纲的第二级：卷纲（逐卷细化，注入总纲 + 前序卷摘要）。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        client = get_llm_client()
        current_volume = state.get("current_volume_number") or 1
        chapters_per_vol = state.get("chapters_per_volume") or 40
        words_per_chapter = state.get("target_words_per_chapter") or 3000
        master_outline = state.get("master_outline") or {}

        # Get volume info from master outline
        volumes = master_outline.get("volumes", [])
        current_vol_info = next(
            (v for v in volumes if v.get("volume_number") == current_volume),
            {"title": f"第{current_volume}卷", "summary": "待生成"}
        )

        # Build previous volumes summary
        prev_volumes_summary = "这是第一卷，无前序卷摘要。"
        if current_volume > 1:
            prev_parts = []
            for v in volumes:
                if v.get("volume_number", 0) < current_volume:
                    prev_parts.append(
                        f"- 第{v.get('volume_number')}卷《{v.get('title', '')}》：{v.get('summary', '')}"
                    )
            if prev_parts:
                prev_volumes_summary = "\n".join(prev_parts)

        # Build chapter types requirement string
        chapter_types = current_vol_info.get("chapter_types", {})
        chapter_types_str = CHAPTER_TYPES_TEMPLATE.format(
            main_advance=chapter_types.get("main_advance", int(chapters_per_vol * 0.45)),
            climax=chapter_types.get("climax", int(chapters_per_vol * 0.12)),
            aftermath=chapter_types.get("aftermath", int(chapters_per_vol * 0.08)),
            daily=chapter_types.get("daily", int(chapters_per_vol * 0.15)),
            setup=chapter_types.get("setup", int(chapters_per_vol * 0.15)),
        )

        prompt = VOLUME_OUTLINE_PROMPT.format(
            master_outline=json.dumps(
                {k: v for k, v in master_outline.items() if k != "volumes"},
                ensure_ascii=False,
            ),
            volume_number=current_volume,
            volume_summary=current_vol_info.get("summary", ""),
            previous_volumes_summary=prev_volumes_summary,
            chapters_count=chapters_per_vol,
            words_per_chapter=words_per_chapter,
            chapter_types=chapter_types_str,
        )

        logger.info(
            f"Generating volume outline for volume {current_volume}, "
            f"project {state['project_id']}"
        )
        style_instruction = get_style_instruction(
            state.get("writing_style", ""),
            state.get("writing_style_prompt", ""),
        )
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"

        response = await client.generate(prompt, max_tokens=6000)

        # Fallback chapters
        fallback_chapters = []
        for i in range(1, chapters_per_vol + 1):
            ch_type = "main_advance" if i % 3 != 0 else "daily"
            fallback_chapters.append({
                "chapter": i,
                "title": f"第{i}章",
                "chapter_type": ch_type,
                "plot": f"第{current_volume}卷第{i}章情节",
                "key_characters": [],
                "foreshadows_planted": [],
                "foreshadows_resolved": [],
                "turning_point": "",
                "emotional_arc": "平静->推进",
            })

        fallback_data = {
            "volume_number": current_volume,
            "title": current_vol_info.get("title", f"第{current_volume}卷"),
            "chapters": fallback_chapters,
        }

        result = safe_json_parse(
            response, fallback=fallback_data, extract_partial=True
        )

        chapters = result.get("chapters", fallback_chapters)

        # Add volume_number to each chapter for tracking
        for ch in chapters:
            ch["volume_number"] = current_volume

        return {
            **state,
            "chapter_outlines": chapters,
            "volumes": [
                v for v in state.get("volumes", [])
                if v.get("volume_number") != current_volume
            ] + [{
                "volume_number": current_volume,
                "title": result.get("title", current_vol_info.get("title", "")),
                "summary": current_vol_info.get("summary", ""),
                "chapters": chapters,
                "chapter_start": chapters[0].get("chapter", 1) if chapters else 1,
                "chapter_end": chapters[-1].get("chapter", chapters_per_vol) if chapters else chapters_per_vol,
            }],
            "current_stage": "volume_outline_completed",
        }

    except Exception as e:
        logger.error(f"Volume outline generation failed: {e}")
        current_volume = state.get("current_volume_number") or 1
        chapters_per_vol = state.get("chapters_per_volume") or 40

        fallback_chapters = []
        for i in range(1, chapters_per_vol + 1):
            fallback_chapters.append({
                "chapter": i,
                "title": f"第{i}章",
                "chapter_type": "main_advance",
                "plot": f"情节待展开",
                "key_characters": [],
                "volume_number": current_volume,
            })

        return {
            **state,
            "chapter_outlines": fallback_chapters,
            "current_stage": "volume_outline_completed",
            "errors": state.get("errors", []) + [f"volume_outline failed: {str(e)}"],
        }
