"""生成流水线契约测试：mock LLM，验证 LangGraph 短篇流程的 stage 流转。

覆盖回归点：create_novel_graph 的节点编排、各 stage 标记、最终进入 human_review。
不依赖外网，秒级完成，纳入 make verify。
"""

import pytest

from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState


def _initial_state() -> NovelState:
    return {
        "project_id": "contract-test",
        "novel_type": "玄幻",
        "target_words": 100000,
        "idea": "一个少年的修仙之路",
        "world_setting": None,
        "characters": [],
        "relationships": {},
        "outline": None,
        "chapter_outlines": [],
        "chapters": [],
        "current_stage": "init",
        "approval_status": "pending",
        "revision_requests": [],
        "quality_scores": {},
        "errors": [],
    }


@pytest.mark.asyncio
async def test_short_form_flow_reaches_human_review(fake_llm):
    """短篇流程应顺序走完 idea→world→character→outline→chapter→quality，到达 human_review。"""
    graph = create_novel_graph()
    config = {"configurable": {"thread_id": "contract-thread"}}

    final_state = await graph.ainvoke(_initial_state(), config=config)

    assert final_state["current_stage"] in ("human_review", "completed", "approved"), (
        f"stage 应到达 human_review/completed/approved，实际 {final_state['current_stage']}"
    )
    # 五个 node 至少各调过一次 LLM（quality_check 触发 L2 评审会再调，故 >=5）
    assert len(fake_llm.calls) >= 5, f"LLM 应被调用≥5次，实际 {len(fake_llm.calls)}"
    # outline 被填充（fake 返回了可解析 JSON）
    assert final_state.get("outline") is not None, "outline 应被填充"
    # 章节生成产物（chapter_generation 跑完会产出 chapters）
    assert len(final_state.get("chapters", [])) >= 1, "应至少生成 1 章"


@pytest.mark.asyncio
async def test_quality_gate_marks_unverified_when_low_score(fake_llm):
    """L2 评审走 fallback（fake 返回非 JSON）→ 低分 → 不标 verified。

    覆盖回归点：gate 永不伪造合格分，低分章节必须 unverified/consistency_blocked/failed。
    """
    from src.core.quality.gate import GatePersistCallbacks, run_quality_gate

    persisted: dict = {}

    async def _persist_scores(novel_id, chapter_number, scores, warnings):
        persisted["scores"] = scores

    async def _update_status(novel_id, chapter_number, status):
        persisted["status"] = status

    async def _update_delta(novel_id, chapter_number, delta):
        persisted["delta"] = delta

    callbacks = GatePersistCallbacks(
        update_state_delta=_update_delta,
        update_quality_status=_update_status,
        persist_quality_scores=_persist_scores,
    )

    result = await run_quality_gate(
        novel_id="gate-test",
        chapter_number=1,
        chapter_result={
            "chapter_number": 1,
            "title": "测试章节",
            "content": "林凡站在青云山脚下，仰望着云雾缭绕的山门。这一刻他等了十年。" * 20,
            "word_count": 400,
        },
        chapter_outline={"chapter": 1, "title": "测试", "plot": "测试情节", "words": 5000},
        novel_type="玄幻",
        idea="一个少年的修仙之路",
        world_setting="九州大陆",
        characters="林凡",
        persist_callbacks=callbacks,
    )

    assert result.quality_status != "verified", (
        f"fake LLM 返回非 JSON 应走低分路径，不得 verified，实际 {result.quality_status}"
    )
    assert result.quality_status in ("unverified", "consistency_blocked", "failed"), (
        f"quality_status 应为非通过状态，实际 {result.quality_status}"
    )
    # 评分被持久化（不丢失）
    assert "scores" in persisted, "质量评分应被持久化回调记录"

