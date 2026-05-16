"""创意扩展节点"""

import logging

from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import IDEA_EXPANSION_PROMPT
from src.core.validation import ValidationError, validate_idea, get_style_instruction

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """创意扩展节点

    将用户的简单创意扩展为详细的故事概念。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    try:
        # 验证输入
        try:
            validated_idea = validate_idea(state["idea"])
        except ValidationError as e:
            logger.error(f"Input validation failed: {e}")
            return {
                **state,
                "current_stage": "idea_expansion_failed",
                "errors": state["errors"] + [f"输入验证失败: {str(e)}"],
            }

        # 调用 LLM API 生成扩展创意
        client = get_llm_client()
        prompt = IDEA_EXPANSION_PROMPT.format(
            idea=validated_idea,
            novel_type=state["novel_type"],
            target_words=state["target_words"],
        )

        logger.info(f"Expanding idea for project {state['project_id']}")
        style_instruction = get_style_instruction(state.get("writing_style", ""), state.get("writing_style_prompt", ""))
        if style_instruction:
            prompt = f"{style_instruction}\n\n{prompt}"
        expanded_idea = await client.generate(prompt)

        return {
            **state,
            "idea": expanded_idea,
            "current_stage": "idea_expansion_completed",
        }

    except Exception as e:
        # 降级到 mock 数据
        logger.error(f"Idea expansion failed, using fallback: {e}")
        original_idea = state["idea"]
        expanded_idea = (
            f"{original_idea}\n\n"
            f"【扩展后的创意】\n"
            f"这是一个关于{state['novel_type']}世界的故事。"
            f"主角将经历重重考验，最终成长为一代强者。"
            f"故事充满了冒险、友情和成长的元素。"
        )

        return {
            **state,
            "idea": expanded_idea,
            "current_stage": "idea_expansion_completed",
            "errors": state["errors"] + [f"idea_expansion API failed: {str(e)}"],
        }
