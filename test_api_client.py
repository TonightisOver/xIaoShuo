"""测试 API 端点"""

import asyncio

import httpx


async def test_api():
    """测试 API 端点"""
    base_url = "http://localhost:8000"

    async with httpx.AsyncClient() as client:
        # 测试根路径
        print("测试根路径...")
        response = await client.get(f"{base_url}/")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}\n")

        # 测试健康检查
        print("测试健康检查...")
        response = await client.get(f"{base_url}/api/v1/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}\n")

        # 测试创建小说任务
        print("测试创建小说任务...")
        response = await client.post(
            f"{base_url}/api/v1/novels",
            json={
                "idea": "一个测试创意：程序员穿越修仙世界",
                "novel_type": "玄幻",
                "target_words": 50000,
            },
        )
        print(f"状态码: {response.status_code}")
        task_data = response.json()
        print(f"响应: {task_data}\n")

        if response.status_code == 202:
            task_id = task_data["task_id"]

            # 等待一下
            await asyncio.sleep(2)

            # 测试查询任务
            print(f"测试查询任务 {task_id}...")
            response = await client.get(f"{base_url}/api/v1/novels/{task_id}")
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}\n")

            # 测试列出任务
            print("测试列出任务...")
            response = await client.get(f"{base_url}/api/v1/novels")
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.json()}\n")


if __name__ == "__main__":
    asyncio.run(test_api())
