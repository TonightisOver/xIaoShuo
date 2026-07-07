"""记忆策展人 Sub-Agent"""

import json
import structlog
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

MEMORY_CURATOR_PROMPT = """你是一位资深的小说编辑助理，负责为即将写作的章节准备「记忆备忘录」。

## 即将创作的章节大纲
{chapter_outline}

## 从知识图谱中检索到的原始数据
{raw_kg_data}

## 从故事圣经中检索到的约束
{story_bible_constraints}

## 你的任务
请将以上信息整理为一份分级的「记忆备忘录」，格式如下：

### 🔴 硬约束（违反将导致严重剧情矛盾，绝不能违背）
- 只列出与本章直接相关的、被Story Bible明确禁止违反的设定
- 如：某角色已经死亡、某地点已被摧毁、某技能有明确限制

### 🟡 推荐遵循（保持一致性的建议，但如果剧情转折需要可以突破）
- 角色当前位置和状态
- 近几章建立的人物关系
- 正在进行的剧情线

### 🟢 灵感素材（可自由参考，不构成约束）
- 悬挂伏笔提示（可以考虑在本章回收）
- 配角信息
- 世界观细节补充

### ⚠️ 需要注意的潜在冲突点
- 如果本章大纲的方向与某些已有设定有张力，指出来并建议如何平滑过渡

请注意：你的目标是帮助创作者写出更好的故事，而不是限制他的创造力。
备忘录总长度控制在 800 字以内。
"""


class MemoryCuratorAgent:
    """记忆策展 Sub-Agent：智能整理 KG 上下文"""

    async def curate(
        self,
        chapter_outline: dict,
        raw_kg_context: str,
        story_bible_context: str,
    ) -> str:
        """生成分级记忆备忘录"""
        if not raw_kg_context and not story_bible_context:
            return "无历史设定。"

        logger.info(
            "memory_curator_curating",
            chapter=chapter_outline.get("chapter", 0),
        )

        prompt = MEMORY_CURATOR_PROMPT.format(
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            raw_kg_data=raw_kg_context or "无",
            story_bible_constraints=story_bible_context or "无",
        )
        
        client = get_llm_client()
        try:
            # 用 flash 模型降低成本（策展任务不需要最强模型）
            memo = await client.generate(prompt, use_flash=True, max_tokens=1500)
            logger.info("memory_curator_completed", chapter=chapter_outline.get("chapter", 0))
            return memo
        except Exception as e:
            logger.warning("memory_curator_failed", error=str(e))
            # Fallback to appending raw contexts directly
            return f"{story_bible_context}\n\n{raw_kg_context}"
