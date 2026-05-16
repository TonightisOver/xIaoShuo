"""测试 DeepSeek API 集成的简单脚本"""

import asyncio
import json

from src.core.langgraph.state import NovelState
from src.core.langgraph.nodes import idea_expansion, world_building


async def test_idea_expansion():
    """测试创意扩展节点"""
    print("=" * 60)
    print("测试创意扩展节点")
    print("=" * 60)

    state: NovelState = {
        "project_id": "test-001",
        "idea": "一个普通少年意外获得神秘力量，踏上修仙之路",
        "novel_type": "玄幻",
        "target_words": 50000,
        "current_stage": "init",
        "errors": [],
    }

    result = await idea_expansion.node(state)

    print(f"\n原始创意: {state['idea']}")
    print(f"\n扩展后创意:\n{result['idea']}")
    print(f"\n当前阶段: {result['current_stage']}")
    print(f"错误列表: {result['errors']}")
    print("=" * 60)

    return result


async def test_world_building():
    """测试世界观构建节点"""
    print("\n" + "=" * 60)
    print("测试世界观构建节点")
    print("=" * 60)

    state: NovelState = {
        "project_id": "test-001",
        "idea": "一个普通少年意外获得神秘力量，踏上修仙之路。他将面对强大的敌人，经历生死考验，最终成长为一代强者。",
        "novel_type": "玄幻",
        "target_words": 50000,
        "current_stage": "idea_expansion_completed",
        "errors": [],
    }

    result = await world_building.node(state)

    print(f"\n世界观设定:")
    print(json.dumps(result["world_setting"], ensure_ascii=False, indent=2))
    print(f"\n当前阶段: {result['current_stage']}")
    print(f"错误列表: {result['errors']}")
    print("=" * 60)

    return result


async def main():
    """主函数"""
    print("\n开始测试 DeepSeek API 集成\n")

    try:
        # 测试创意扩展
        result1 = await test_idea_expansion()

        # 测试世界观构建
        result2 = await test_world_building()

        print("\n✅ 所有测试完成！")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
