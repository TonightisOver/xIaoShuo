"""改写闭环服务 — 自动迭代评估+改写直到质量达标"""

import structlog
from sqlalchemy import select

from src.api.models.db_models import Character, Novel, WorldSetting
from src.api.services.novel_manager import get_novel_manager
from src.api.services.quality_action_service import QualityActionService
from src.core.context import NovelContextBuilder
from src.core.database import get_db_session
from src.core.quality import QUALITY_DIMENSIONS
from src.core.quality.evaluator import evaluate_chapter_quality

logger = structlog.get_logger(__name__)


async def _evaluate_chapter_quality_for_novel(
    novel_id: str, chapter_number: int, content: str
) -> dict:
    """从 DB 获取小说上下文后调用公共质量评估，返回 scores dict。

    Returns:
        {"advancement": 0.8, "conflict": 0.7, ..., "overall": 0.75}
    """
    novel_type = ""
    idea = ""
    world_setting = ""
    characters = ""

    async with get_db_session() as session:
        novel_res = await session.execute(
            select(Novel).where(Novel.novel_id == novel_id)
        )
        novel = novel_res.scalar_one_or_none()
        if novel:
            novel_type = novel.novel_type or ""
            idea = novel.idea or ""

        ws_res = await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        ws = ws_res.scalar_one_or_none()
        if ws:
            parts = []
            if ws.background:
                parts.append(ws.background)
            if ws.rules:
                parts.append(ws.rules)
            world_setting = "\n".join(parts)

        chars_res = await session.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        chars = chars_res.scalars().all()
        if chars:
            char_list = [
                f"- {c.name}（{c.role or '未知'}）：{c.description or ''}"
                for c in chars
            ]
            characters = "\n".join(char_list)

    result = await evaluate_chapter_quality(
        chapter_content=content,
        chapter_number=chapter_number,
        novel_type=novel_type or "网络小说",
        idea=idea or "暂无核心创意描述",
        world_setting=world_setting or "未设定",
        characters=characters or "未设定",
    )
    return result.to_scores_dict()


class RewriteLoopService:
    """自动改善闭环：评估 -> 改写 -> 再评估，直到达标或达到最大迭代次数"""

    async def auto_improve_chapter(
        self,
        novel_id: str,
        chapter_number: int,
        max_iterations: int = 3,
        target_score: float = 0.6,
        dimensions: list[str] | None = None,
    ) -> dict:
        """自动改善闭环。

        循环:
        1. 获取当前章节内容
        2. 调用质量评估获取分数
        3. 检查是否达标（所有目标维度 >= target_score）
        4. 如果达标或达到 max_iterations，停止
        5. 生成改写动作
        6. 执行批量改写
        7. 创建新版本
        8. 记录本轮结果
        9. 回到步骤 2

        Returns:
            {
                "iterations_done": int,
                "final_scores": dict,
                "reached_target": bool,
                "improvement_history": [...]
            }
        """
        from src.core.llm.chapter_rewriter import batch_targeted_rewrite

        target_dims = dimensions or QUALITY_DIMENSIONS
        manager = get_novel_manager()
        action_service = QualityActionService()

        rewrite_context: dict | None = None

        improvement_history: list[dict] = []
        final_scores: dict = {}

        logger.info(
            "auto_improve_start",
            novel_id=novel_id,
            chapter_number=chapter_number,
            max_iterations=max_iterations,
            target_score=target_score,
            dimensions=target_dims,
        )

        for iteration in range(1, max_iterations + 1):
            # 1. 获取当前章节内容
            chapter = await manager.get_chapter(novel_id, chapter_number)
            if not chapter or not chapter.get("content"):
                raise ValueError("章节内容为空，无法进行改善")
            current_content = chapter["content"]

            # 2. 质量评估
            scores = await _evaluate_chapter_quality_for_novel(
                novel_id, chapter_number, current_content
            )
            scores_before = dict(scores)

            # 3. 检查是否达标
            all_pass = all(
                scores.get(dim, 0) >= target_score for dim in target_dims
            )
            if all_pass:
                logger.info(
                    "auto_improve_target_reached",
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    iteration=iteration,
                )
                final_scores = scores
                break

            # 5. 生成改写动作（仅针对目标维度中低分的）
            filtered_scores = {
                k: v for k, v in scores.items()
                if k in target_dims or k == "overall"
            }
            actions = action_service.generate_rewrite_actions(
                filtered_scores, threshold=target_score
            )

            if not actions:
                logger.info(
                    "auto_improve_no_actions",
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    iteration=iteration,
                )
                final_scores = scores
                break

            # 6. 执行批量改写（懒加载上下文，仅在首次需要时构建）
            if rewrite_context is None:
                async with get_db_session() as session:
                    ctx = await NovelContextBuilder().build_rewrite_context(
                        session, novel_id, chapter_number
                    )
                rewrite_context = {
                    "world_setting": ctx.world_setting,
                    "chapter_outline": ctx.chapter_outline,
                    "prev_chapter_summary": ctx.prev_chapter_summary,
                    "next_chapter_summary": ctx.next_chapter_summary,
                    "characters": ctx.characters,
                    "story_bible": ctx.story_bible,
                    "writing_style": ctx.writing_style,
                }

            new_content = await batch_targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=current_content,
                actions=actions,
                context=rewrite_context,
            )

            # 7. 创建新版本
            action_types = [a.get("action_type", "") for a in actions]
            new_version = await manager.create_chapter_version(
                novel_id=novel_id,
                chapter_number=chapter_number,
                content=new_content,
                source="ai_rewrite",
                rewrite_instruction=(
                    f"auto_improve_iter{iteration}:"
                    f" {','.join(action_types)}"
                ),
                is_active=True,
            )

            # 8. 评估改写后的分数
            scores_after = await _evaluate_chapter_quality_for_novel(
                novel_id, chapter_number, new_content
            )
            final_scores = scores_after

            improvement_history.append({
                "iteration": iteration,
                "scores_before": scores_before,
                "scores_after": scores_after,
                "actions_taken": action_types,
                "new_version_number": new_version,
                "word_count": len(new_content),
            })

            logger.info(
                "auto_improve_iteration_done",
                novel_id=novel_id,
                chapter_number=chapter_number,
                iteration=iteration,
                overall_before=scores_before.get("overall"),
                overall_after=scores_after.get("overall"),
            )

            # 检查改写后是否达标
            all_pass_after = all(
                scores_after.get(dim, 0) >= target_score for dim in target_dims
            )
            if all_pass_after:
                logger.info(
                    "auto_improve_target_reached_after_rewrite",
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    iteration=iteration,
                )
                break

        reached_target = all(
            final_scores.get(dim, 0) >= target_score for dim in target_dims
        )

        logger.info(
            "auto_improve_done",
            novel_id=novel_id,
            chapter_number=chapter_number,
            iterations_done=len(improvement_history),
            reached_target=reached_target,
            final_overall=final_scores.get("overall"),
        )

        return {
            "iterations_done": len(improvement_history),
            "final_scores": final_scores,
            "reached_target": reached_target,
            "improvement_history": improvement_history,
        }
