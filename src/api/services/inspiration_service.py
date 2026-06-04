"""In-memory inspiration wizard service."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from src.api.services.novel_manager import get_novel_manager
from src.core.llm.client import get_llm_client


class InspirationWizard:
    steps = ["idea", "title", "description", "theme", "genre", "confirm"]

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def start_session(self) -> dict[str, Any]:
        session_id = f"inspiration-{uuid.uuid4().hex}"
        self._sessions[session_id] = {
            "session_id": session_id,
            "current_step": "idea",
            "collected": {},
            "outline": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        welcome = (
            "欢迎进入灵感模式。先告诉我一个朦胧的念头、场景、人物或冲突，"
            "我们会一步步把它发展成可写的小说方案。"
        )
        return {
            "session_id": session_id,
            "step": "idea",
            "ai_reply": welcome,
            "next_step": "idea",
            "options": self._suggestions_for_step("idea"),
            "collected": {},
        }

    async def process_step(
        self,
        session_id: str,
        step: str,
        user_input: str,
    ) -> dict[str, Any]:
        session = self._get_session(session_id)
        if step not in self.steps:
            raise ValueError(f"Invalid step: {step}")
        if step != session["current_step"]:
            raise ValueError(
                f"Expected step {session['current_step']}, got {step}"
            )
        if not user_input.strip():
            raise ValueError("user_input cannot be empty")

        session["collected"][step] = user_input.strip()
        session["updated_at"] = datetime.now(UTC).isoformat()

        next_step = self._next_step(step)
        prompt = self._build_step_prompt(session["collected"], step, next_step)
        ai_reply = await get_llm_client().generate(
            prompt,
            temperature=0.7,
            max_tokens=900,
            use_flash=True,
        )

        if next_step is not None:
            session["current_step"] = next_step

        return {
            "session_id": session_id,
            "step": step,
            "ai_reply": ai_reply,
            "next_step": next_step,
            "options": self._suggestions_for_step(next_step or "confirm"),
            "collected": deepcopy(session["collected"]),
        }

    async def generate_outline(self, session_id: str) -> dict[str, Any]:
        session = self._get_session(session_id)
        prompt = self._build_outline_prompt(session["collected"])
        outline = await get_llm_client().generate(
            prompt,
            temperature=0.6,
            max_tokens=2500,
        )
        session["outline"] = outline
        session["updated_at"] = datetime.now(UTC).isoformat()
        return {
            "session_id": session_id,
            "outline": outline,
            "collected": deepcopy(session["collected"]),
        }

    async def create_project(self, session_id: str) -> dict[str, Any]:
        session = self._get_session(session_id)
        collected = session["collected"]
        idea = self._project_idea(collected, session.get("outline"))
        novel_type = collected.get("genre") or "未分类"
        title = collected.get("title")

        novel_id = await get_novel_manager().create_novel(
            idea=idea,
            novel_type=novel_type,
            target_words=100000,
            title=title,
        )
        session["novel_id"] = novel_id
        session["updated_at"] = datetime.now(UTC).isoformat()
        return {
            "session_id": session_id,
            "novel_id": novel_id,
            "status": "draft",
            "title": title,
            "novel_type": novel_type,
        }

    def clear(self) -> None:
        self._sessions.clear()

    def _get_session(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("Inspiration session not found")
        return session

    def _next_step(self, step: str) -> str | None:
        index = self.steps.index(step)
        if index + 1 >= len(self.steps):
            return None
        return self.steps[index + 1]

    def _build_step_prompt(
        self,
        collected: dict[str, str],
        step: str,
        next_step: str | None,
    ) -> str:
        context = self._format_context(collected)
        next_instruction = (
            f"下一步要引导用户填写：{next_step}。"
            if next_step
            else "用户已确认方案，请总结这个小说创意并提示可以生成大纲。"
        )
        return f"""你是小说灵感向导，正在帮助用户从零构思一部中文网络小说。

已收集上下文：
{context}

用户刚刚完成步骤：{step}
{next_instruction}

请用中文回复：
1. 简短认可并提炼用户输入中的创作价值；
2. 结合所有已收集上下文提出下一步问题；
3. 不要编造已经确定的内容，不要输出 JSON。"""

    def _build_outline_prompt(self, collected: dict[str, str]) -> str:
        return f"""你是资深中文网络小说策划。
请根据以下灵感模式收集的信息生成一份可执行小说大纲。

已收集上下文：
{self._format_context(collected)}

请输出：
1. 核心卖点
2. 主角与关键角色
3. 世界观/背景
4. 主线冲突
5. 三幕式剧情推进
6. 前 10 章章节大纲
7. 可持续扩展的伏笔与爽点设计"""

    def _format_context(self, collected: dict[str, str]) -> str:
        if not collected:
            return "暂无"
        labels = {
            "idea": "初始想法",
            "title": "标题",
            "description": "简介",
            "theme": "主题",
            "genre": "类型",
            "confirm": "确认意见",
        }
        return "\n".join(
            f"- {labels.get(step, step)}：{value}"
            for step, value in collected.items()
        )

    def _project_idea(self, collected: dict[str, str], outline: str | None) -> str:
        parts = [self._format_context(collected)]
        if outline:
            parts.append(f"生成大纲：\n{outline}")
        return "\n\n".join(parts)

    def _suggestions_for_step(self, step: str) -> list[str]:
        suggestions = {
            "idea": [
                "一个普通人发现世界运行规则有漏洞",
                "末日后幸存者重建秩序",
                "主角继承一座会成长的城市",
                "被误判为反派的人试图改写命运",
            ],
            "title": ["短促有冲击力", "带主角身份", "突出核心设定", "保留悬念"],
            "description": [
                "主角是谁，他想要什么",
                "最大的阻碍是什么",
                "世界有什么独特规则",
                "故事开局的引爆事件",
            ],
            "theme": ["成长与代价", "秩序与自由", "命运与选择", "复仇与救赎"],
            "genre": ["玄幻", "都市", "科幻", "悬疑", "历史"],
            "confirm": ["生成大纲", "创建项目", "继续调整标题", "继续调整类型"],
        }
        return suggestions[step]


_inspiration_wizard: InspirationWizard | None = None


def get_inspiration_wizard() -> InspirationWizard:
    global _inspiration_wizard
    if _inspiration_wizard is None:
        _inspiration_wizard = InspirationWizard()
    return _inspiration_wizard
