"""演示日志功能的示例脚本"""

import asyncio

from src.core.config import get_settings
from src.core.llm.client import get_llm_client
from src.core.logging_config import setup_logging


async def main():
    """主函数"""
    # 初始化日志
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)

    print(f"日志已配置，输出到: {settings.LOG_FILE}")
    print("=" * 60)

    # 测试 API 调用（会记录到日志）
    try:
        client = get_llm_client()
        result = await client.generate("你好，请用一句话介绍你自己")
        print(f"API 调用成功，响应长度: {len(result)} 字符")
        print(f"响应内容: {result[:100]}...")
    except Exception as e:
        print(f"API 调用失败: {e}")

    print("=" * 60)
    print(f"请查看日志文件: {settings.LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
