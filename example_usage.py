"""小说生成平台使用示例"""

import asyncio
from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState
from src.core.logging_config import setup_logging
from src.core.config import get_settings


async def generate_novel(
    idea: str,
    novel_type: str = "玄幻",
    target_words: int = 100000,
    project_id: str = "novel-001",
) -> NovelState:
    """生成小说

    Args:
        idea: 小说创意
        novel_type: 小说类型（玄幻/武侠/仙侠/都市/历史/科幻/游戏/军事/悬疑/灵异/同人/轻小说/其他）
        target_words: 目标字数（10,000 - 10,000,000）
        project_id: 项目 ID

    Returns:
        最终状态，包含生成的章节
    """
    # 清除配置缓存，重新加载环境变量
    from src.core.config import get_settings
    get_settings.cache_clear()

    # 设置日志
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)

    print("=" * 60)
    print("AI 中文小说生成平台")
    print("=" * 60)
    print(f"\n项目 ID: {project_id}")
    print(f"创意: {idea}")
    print(f"类型: {novel_type}")
    print(f"目标字数: {target_words:,}")
    print("\n开始生成...\n")

    # 创建工作流图
    graph = create_novel_graph()

    # 初始化状态
    initial_state: NovelState = {
        "project_id": project_id,
        "idea": idea,
        "novel_type": novel_type,
        "target_words": target_words,
        "current_stage": "start",
        "chapters": [],
        "errors": [],
    }

    # 执行工作流（需要提供 thread_id 用于状态持久化）
    config = {"configurable": {"thread_id": project_id}}
    result = await graph.ainvoke(initial_state, config=config)

    # 显示结果
    print("\n" + "=" * 60)
    print("生成完成！")
    print("=" * 60)
    print(f"\n当前阶段: {result['current_stage']}")
    print(f"生成章节数: {len(result['chapters'])}")

    if result.get("errors"):
        print(f"\n遇到的错误: {len(result['errors'])} 个")
        for i, error in enumerate(result["errors"], 1):
            print(f"  {i}. {error[:100]}...")

    # 显示章节信息
    if result["chapters"]:
        print("\n章节列表:")
        for i, chapter in enumerate(result["chapters"], 1):
            title = chapter.get("title", f"第{i}章")
            content_length = len(chapter.get("content", ""))
            print(f"  {i}. {title} ({content_length:,} 字)")

    # 显示世界观（如果有）
    if result.get("world"):
        world = result["world"]
        print(f"\n世界观:")
        print(f"  名称: {world.get('name', 'N/A')}")
        print(f"  背景: {world.get('background', 'N/A')[:100]}...")

    # 显示人物（如果有）
    if result.get("characters"):
        print(f"\n主要人物: {len(result['characters'])} 个")
        for char in result["characters"][:3]:  # 只显示前 3 个
            print(f"  - {char.get('name', 'N/A')}: {char.get('role', 'N/A')}")

    print("\n" + "=" * 60)

    return result


async def main():
    """主函数 - 运行示例"""

    # 示例 1: 玄幻小说
    result = await generate_novel(
        idea="一个现代程序员穿越到修仙世界，用编程思维修炼",
        novel_type="玄幻",
        target_words=100000,
        project_id="novel-example-001",
    )

    # 保存结果到文件（可选）
    if result["chapters"]:
        output_file = f"output_{result['project_id']}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"项目: {result['project_id']}\n")
            f.write(f"创意: {result['idea'][:100]}...\n")
            f.write(f"类型: {result['novel_type']}\n")
            f.write(f"目标字数: {result['target_words']:,}\n")
            f.write("\n" + "=" * 60 + "\n\n")

            for i, chapter in enumerate(result["chapters"], 1):
                f.write(f"\n\n第 {i} 章: {chapter.get('title', f'第{i}章')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(chapter.get("content", ""))

        print(f"\n小说已保存到: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
