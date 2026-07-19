"""FakeLLMClient：按调用序号返回各 node 期望结构的响应，不触外网。

匹配策略：各 node 执行顺序固定（idea_expansion→world_building→character_design
→outline_generation→chapter_generation），用调用序号取响应最稳，避免 prompt 关键词
跨节点重叠（如"世界观"同时出现在 world/character/outline 的 prompt 里）。
"""

from __future__ import annotations


class FakeLLMClient:
    """get_llm_client() 的 fake 替身。

    generate() 按调用序号返回预设响应；stream_generate() 一次性 yield 整段。
    端到端流水线测试不验证流式切片与具体字数，只验证 stage 流转/结构填充。
    """

    # 按调用顺序的响应：[idea_expansion, world_building, character_design, outline, chapter]
    RESPONSES: list[str] = [
        # 0 idea_expansion：返回扩展创意文本（非 JSON）
        "一个关于修仙者从凡人成长为仙尊的故事，含奇遇、宗门历练、渡劫化神等元素，主角坚毅重情。",
        # 1 world_building：返回世界观 JSON
        '{"background":"九州大陆，灵气充沛","geography":"东荒西漠南林北雪","culture":"宗门林立，散修无数","rules":"练气筑基金丹元婴化神"}',
        # 2 character_design：返回人物 JSON（列表）
        '[{"name":"林凡","role":"主角","description":"天赋异禀的少年，身世成谜","personality":"坚毅重情","background":"村中孤儿"},{"name":"苏清雪","role":"女主","description":"青云宗大师姐","personality":"冷静聪慧","background":"宗门世家"}]',
        # 3 outline_generation：返回大纲 JSON（volumes 含 chapters，跨卷全局编号由 node 重排）
        '{"outline":{"premise":"林凡拜入青云宗","rising":"历练成长结交伙伴","climax":"渡劫化神","ending":"飞升上界"},"volumes":[{"volume_number":1,"title":"初入江湖","summary":"拜师修炼初露锋芒","chapters":[{"chapter":1,"title":"家乡变故","plot":"村庄遭邪派袭击，林凡幸存","words":5000},{"chapter":2,"title":"拜入门派","plot":"随师入门，初识苏清雪","words":5000}]}]}',
        # 4 chapter_generation：返回章节正文
        "林凡站在青云山脚下，仰望着云雾缭绕的山门，这一刻他等了整整十年。师尊在前引路，山风猎猎作响，他踏出第一步，身后的村庄烟火渐远。门派巍峨，青石阶上千人仰望。他暗暗发誓：终有一日，他要站到这山巅之上，俯瞰九州。苏清雪从山门走出，一袭白衣，目光在他身上停留片刻。这是他们的初遇，也是命运齿轮转动的起点。（正文约五百字，本章完）",
    ]

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._idx = 0

    async def generate(self, prompt: str, temperature=None, max_tokens=None, use_flash=False) -> str:
        self.calls.append(prompt)
        idx = self._idx
        self._idx += 1
        if idx < len(self.RESPONSES):
            return self.RESPONSES[idx]
        return "fake-default-response"

    async def stream_generate(self, prompt: str, temperature=None, max_tokens=None, use_flash=False):
        resp = await self.generate(prompt, temperature, max_tokens, use_flash)
        yield resp
