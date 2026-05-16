"""测试 API 连接"""

import asyncio
from src.core.config import get_settings
from src.core.llm.client import get_llm_client


async def test_api():
    """测试 API 连接"""
    # 清除配置缓存，重新加载环境变量
    get_settings.cache_clear()

    settings = get_settings()
    print(f"API Key (last 4): ...{settings.DEEPSEEK_API_KEY[-4:]}")
    print(f"Model: {settings.DEEPSEEK_MODEL}")
    print(f"Base URL: {settings.DEEPSEEK_BASE_URL}")

    print("\n测试 API 调用...")
    client = get_llm_client()

    try:
        response = await client.generate("你好，请回复'OK'")
        print(f"[OK] API 调用成功！")
        print(f"响应: {response}")
    except Exception as e:
        print(f"[FAIL] API 调用失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_api())
