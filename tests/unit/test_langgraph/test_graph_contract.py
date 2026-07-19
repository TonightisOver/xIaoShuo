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
