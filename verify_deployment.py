"""部署验证示例 - 快速验证"""

import asyncio

from src.core.config import get_settings
from src.core.logging_config import setup_logging
from src.core.llm.client import get_llm_client


async def verify_deployment():
    """验证部署环境"""
    print("=" * 60)
    print("部署验证")
    print("=" * 60)

    # 1. 验证配置
    print("\n1. 验证配置...")
    settings = get_settings()
    print(f"   [OK] 模型: {settings.DEEPSEEK_MODEL}")
    print(f"   [OK] 超时: {settings.DEEPSEEK_TIMEOUT}s")
    print(f"   [OK] 日志: {settings.LOG_FILE}")

    # 2. 验证日志系统
    print("\n2. 验证日志系统...")
    setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)
    print(f"   [OK] 日志已配置")

    # 3. 验证 API 连接
    print("\n3. 验证 API 连接...")
    try:
        client = get_llm_client()
        response = await client.generate("你好，请回复'OK'")
        print(f"   [OK] API 连接正常")
        print(f"   响应: {response[:50]}...")
    except Exception as e:
        print(f"   [FAIL] API 连接失败: {e}")
        return False

    # 4. 验证输入验证
    print("\n4. 验证输入验证...")
    from src.core.validation import validate_idea, validate_novel_type

    try:
        validate_idea("一个测试创意")
        validate_novel_type("玄幻")
        print(f"   [OK] 输入验证正常")
    except Exception as e:
        print(f"   [FAIL] 输入验证失败: {e}")
        return False

    # 5. 验证 JSON 解析
    print("\n5. 验证 JSON 解析...")
    from src.core.json_utils import safe_json_parse

    test_json = '{"name": "test", "value": 123}'
    result = safe_json_parse(test_json)
    if result and result.get("name") == "test":
        print(f"   [OK] JSON 解析正常")
    else:
        print(f"   [FAIL] JSON 解析失败")
        return False

    print("\n" + "=" * 60)
    print("[SUCCESS] 部署验证通过！")
    print("=" * 60)
    return True


async def main():
    """主函数"""
    success = await verify_deployment()
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
