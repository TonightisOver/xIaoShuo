"""端到端集成测试 - 完整小说生成流程"""

import asyncio
import json
from datetime import datetime

from src.core.config import get_settings
from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState
from src.core.logging_config import setup_logging


async def test_end_to_end_novel_generation():
    """测试完整的小说生成流程"""
    print("=" * 80)
    print("端到端集成测试 - 完整小说生成流程")
    print("=" * 80)

    # 初始化日志
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)
    print(f"\n日志文件: {settings.LOG_FILE}")
    print(f"使用模型: {settings.DEEPSEEK_MODEL}")

    # 创建初始状态
    initial_state: NovelState = {
        "project_id": f"test-e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "idea": "一个普通程序员意外穿越到修仙世界，用编程思维修炼成仙",
        "novel_type": "玄幻",
        "target_words": 50000,
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

    print(f"\n项目 ID: {initial_state['project_id']}")
    print(f"创意: {initial_state['idea']}")
    print(f"类型: {initial_state['novel_type']}")
    print(f"目标字数: {initial_state['target_words']}")

    # 创建工作流
    print("\n创建 LangGraph 工作流...")
    graph = create_novel_graph()

    # 执行工作流
    print("\n开始执行工作流...\n")
    config = {"configurable": {"thread_id": initial_state["project_id"]}}

    try:
        start_time = datetime.now()
        final_state = None

        async for state in graph.astream(initial_state, config):
            for node_name, node_state in state.items():
                stage = node_state.get("current_stage", "unknown")
                errors = node_state.get("errors", [])

                print(f"[{node_name}] 阶段: {stage}")
                if errors:
                    print(f"  错误: {errors[-1]}")

                final_state = node_state

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"\n工作流执行完成，耗时: {duration:.2f} 秒")

        # 验证结果
        print("\n" + "=" * 80)
        print("验证结果")
        print("=" * 80)

        assert final_state is not None, "最终状态为空"

        # 检查各阶段完成情况
        checks = {
            "创意扩展": final_state.get("idea") != initial_state["idea"],
            "世界观构建": final_state.get("world_setting") is not None,
            "人物设计": len(final_state.get("characters", [])) > 0,
            "大纲生成": final_state.get("outline") is not None,
            "章节生成": len(final_state.get("chapters", [])) > 0,
        }

        all_passed = True
        for check_name, passed in checks.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"{check_name}: {status}")
            if not passed:
                all_passed = False

        # 显示统计信息
        print("\n统计信息:")
        print(f"  人物数量: {len(final_state.get('characters', []))}")
        print(f"  章节数量: {len(final_state.get('chapters', []))}")
        print(f"  错误数量: {len(final_state.get('errors', []))}")

        if final_state.get("errors"):
            print("\n错误列表:")
            for i, error in enumerate(final_state["errors"], 1):
                print(f"  {i}. {error}")

        # 显示生成的内容摘要
        print("\n生成内容摘要:")
        print(f"\n扩展后的创意 (前 200 字):")
        print(final_state.get("idea", "")[:200] + "...")

        if final_state.get("world_setting"):
            print(f"\n世界观背景:")
            print(final_state["world_setting"].get("background", "")[:200] + "...")

        if final_state.get("characters"):
            print(f"\n主要人物:")
            for char in final_state["characters"][:3]:
                print(f"  - {char.get('name', '未知')}: {char.get('role', '未知')}")

        if final_state.get("chapters"):
            print(f"\n第一章内容 (前 200 字):")
            first_chapter = final_state["chapters"][0]
            print(f"  标题: {first_chapter.get('title', '未知')}")
            print(f"  内容: {first_chapter.get('content', '')[:200]}...")

        print("\n" + "=" * 80)
        if all_passed:
            print("✅ 端到端测试通过！")
        else:
            print("❌ 端到端测试失败！")
        print("=" * 80)

        return all_passed

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """主函数"""
    success = await test_end_to_end_novel_generation()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
