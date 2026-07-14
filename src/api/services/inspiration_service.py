"""In-memory inspiration wizard service.

灵感向导：多步 LLM 对话把模糊念头发展成可写的小说方案。

process_step 使用结构化输出（reply + suggestions）：LLM 每步除了回复文字，
还返回针对下一步的**具体候选建议**（如 title 步直接给 3 个候选标题），
前端渲染为可点选卡片。经 generate_and_validate 校验 + 失败重试，
LLM 不可用时降级到静态建议（服务永不 500）。
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from src.api.services.novel_manager import get_novel_manager
from src.core.langgraph.node_utils import generate_and_validate
from src.core.llm.client import get_llm_client

# 标准小说类型表（与前端 novelTypes 一致）
NOVEL_GENRES = [
    "玄幻", "仙侠", "都市", "科幻", "历史", "武侠",
    "言情", "悬疑", "军事", "游戏", "竞技", "灵异", "同人",
]


class InspirationStepReply(BaseModel):
    """process_step 的 LLM 结构化输出。"""

    reply: str = ""
    suggestions: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class InspirationWizard:
    steps = ["idea", "title", "description", "theme", "genre", "confirm"]
    session_ttl = timedelta(hours=24)
    max_sessions = 100

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def start_session(self) -> dict[str, Any]:
        self._cleanup_sessions()
        self._enforce_session_limit()
        session_id = f"inspiration-{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        self._sessions[session_id] = {
            "session_id": session_id,
            "current_step": "idea",
            "collected": {},
            "outline": None,
            "created_at": now,
            "updated_at": now,
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
            "options": self._static_suggestions("idea"),
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

        # genre / confirm 的候选是固定表，无需 LLM 生成建议；
        # 其余步骤让 LLM 返回结构化 {reply, suggestions}（具体候选）
        if next_step in ("genre", None):
            ai_reply = await self._plain_reply(session["collected"], step, next_step)
            options = self._static_suggestions(next_step or "confirm")
        else:
            typed = await generate_and_validate(
                get_llm_client(),
                self._build_structured_prompt(session["collected"], step, next_step),
                InspirationStepReply,
                f"inspiration_step_{step}",
                fallback=None,
                temperature=0.8,
                max_tokens=900,
                use_flash=True,
            )
            if typed is not None and typed.reply.strip():
                ai_reply = typed.reply.strip()
                options = [s.strip() for s in typed.suggestions if s.strip()][:4]
                if not options:
                    options = self._static_suggestions(next_step)
            else:
                # LLM 失败降级：通用回复 + 静态建议，服务不中断
                ai_reply = self._fallback_reply(step, next_step)
                options = self._static_suggestions(next_step)

        if next_step is not None:
            session["current_step"] = next_step

        return {
            "session_id": session_id,
            "step": step,
            "ai_reply": ai_reply,
            "next_step": next_step,
            "options": options,
            "collected": deepcopy(session["collected"]),
        }

    async def generate_outline(self, session_id: str) -> dict[str, Any]:
        """从 session 生成大纲（兼容旧调用，session 过期会 KeyError）。"""
        session = self._get_session(session_id)
        return await self.generate_outline_from_collected(
            session["collected"], session_id=session_id,
        )

    async def generate_outline_from_collected(
        self, collected: dict[str, str], session_id: str | None = None,
    ) -> dict[str, Any]:
        """无状态生成大纲：直接用前端传来的 collected 数据，不依赖 session。

        彻底解决容器重启/-session 过期导致 /generate 404 的问题。
        """
        prompt = self._build_outline_prompt(collected)
        outline = await get_llm_client().generate(
            prompt,
            temperature=0.6,
            max_tokens=2500,
        )
        # 若有 session，顺便缓存 outline（非关键）
        if session_id and session_id in self._sessions:
            self._sessions[session_id]["outline"] = outline
            self._sessions[session_id]["updated_at"] = datetime.now(UTC).isoformat()
        return {
            "outline": outline,
            "collected": deepcopy(collected),
        }

    async def create_project(
        self, session_id: str, target_words: int = 100000,
        owner_id: int | None = None,
    ) -> dict[str, Any]:
        """从 session 创建项目（兼容旧调用）。"""
        session = self._get_session(session_id)
        return await self.create_project_from_collected(
            session["collected"], target_words=target_words,
            owner_id=owner_id, outline=session.get("outline"),
        )

    async def create_project_from_collected(
        self, collected: dict[str, str], target_words: int = 100000,
        owner_id: int | None = None, outline: str | None = None,
    ) -> dict[str, Any]:
        """无状态创建项目：直接用前端传来的 collected 数据，不依赖 session。"""
        idea = self._project_idea(collected, outline)
        novel_type = collected.get("genre") or "未分类"
        title = collected.get("title")

        novel_id = await get_novel_manager().create_novel(
            idea=idea,
            novel_type=novel_type,
            target_words=target_words,
            title=title,
            owner_id=owner_id,
        )
        return {
            "novel_id": novel_id,
            "status": "draft",
            "title": title,
            "novel_type": novel_type,
        }

    def clear(self) -> None:
        self._sessions.clear()

    def _get_session(self, session_id: str) -> dict[str, Any]:
        self._cleanup_sessions()
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError("Inspiration session not found")
        return session

    def _cleanup_sessions(self) -> None:
        now = datetime.now(UTC)
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - self._parse_time(session.get("created_at")) >= self.session_ttl
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def _enforce_session_limit(self) -> None:
        while len(self._sessions) >= self.max_sessions:
            oldest_id = min(
                self._sessions,
                key=lambda session_id: self._parse_time(
                    self._sessions[session_id].get("created_at")
                ),
            )
            self._sessions.pop(oldest_id, None)

    def _parse_time(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            parsed = datetime.fromisoformat(value)
        else:
            return datetime.min.replace(tzinfo=UTC)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _next_step(self, step: str) -> str | None:
        index = self.steps.index(step)
        if index + 1 >= len(self.steps):
            return None
        return self.steps[index + 1]

    # ── prompt 构建 ──────────────────────────────────────────────

    # 每个"下一步"对应的具体建议要求：让 LLM 给可直接点选的候选，而非抽象指导
    _NEXT_STEP_SUGGESTION_SPEC = {
        "title": "3-4 个可直接采用的**具体候选书名**（结合创意内容起名，风格各异：有的短促有冲击力、有的带悬念）",
        "description": "3 个可直接采用的**一句话故事梗概候选**（各自侧重不同：主角欲望、最大阻碍、世界独特规则）",
        "theme": "4 个**贴合这个故事的主题词**（如'成长与代价'，要与已收集的创意/标题/简介呼应，不要泛泛而谈）",
        "confirm": "无需建议",
    }

    def _build_structured_prompt(
        self,
        collected: dict[str, str],
        step: str,
        next_step: str,
    ) -> str:
        context = self._format_context(collected)
        suggestion_spec = self._NEXT_STEP_SUGGESTION_SPEC.get(next_step, "3 个具体候选")
        return f"""你是小说灵感向导，正在帮助用户从零构思一部中文网络小说。

已收集上下文：
{context}

用户刚刚完成步骤：{step}（{self._step_label(step)}）
下一步要引导用户填写：{next_step}（{self._step_label(next_step)}）

请输出严格 JSON（不要 markdown 代码块，不要多余文字）：
{{
  "reply": "你的回复：1)简短认可并提炼用户输入的创作亮点（1-2句）；2)自然引出下一步的问题（1句）。总共不超过 80 字，口吻亲切专业。",
  "suggestions": [{suggestion_spec}]
}}

要求：
- suggestions 必须是**具体可点选采用的内容**，不是抽象写作指导
- 紧扣已收集的上下文，不要脱离用户的创意
- 不要编造用户没说过的设定"""

    async def _plain_reply(
        self, collected: dict[str, str], step: str, next_step: str | None,
    ) -> str:
        """genre/confirm 步骤：候选固定，只需 LLM 生成过渡回复文字。"""
        context = self._format_context(collected)
        next_instruction = (
            f"下一步请用户从标准类型中选择小说类型（genre）。"
            if next_step == "genre"
            else "用户已完成全部信息收集，请总结这个小说方案的亮点（2-3句），并提示可以生成大纲或直接创建项目。"
        )
        prompt = f"""你是小说灵感向导。

已收集上下文：
{context}

用户刚刚完成步骤：{step}（{self._step_label(step)}）
{next_instruction}

请用中文回复（不超过 100 字，不要 JSON，不要列表符号）。"""
        try:
            reply = await get_llm_client().generate(
                prompt, temperature=0.7, max_tokens=300, use_flash=True,
            )
            return reply.strip() or self._fallback_reply(step, next_step)
        except Exception:
            return self._fallback_reply(step, next_step)

    def _step_label(self, step: str | None) -> str:
        labels = {
            "idea": "初始想法", "title": "标题", "description": "简介",
            "theme": "主题", "genre": "类型", "confirm": "确认",
        }
        return labels.get(step or "", step or "")

    def _fallback_reply(self, step: str, next_step: str | None) -> str:
        """LLM 不可用时的降级回复。"""
        if next_step is None:
            return "信息已收集完整！可以生成大纲预览，或直接创建项目开始创作。"
        return (
            f"已记录你的{self._step_label(step)}。"
            f"接下来聊聊{self._step_label(next_step)}——可以参考下面的建议，也可以自由输入。"
        )

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

    def _static_suggestions(self, step: str) -> list[str]:
        """静态建议：genre/confirm 的固定候选，及 LLM 失败时其他步骤的降级建议。"""
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
            "genre": NOVEL_GENRES,
            "confirm": ["生成大纲", "创建项目", "继续调整标题", "继续调整类型"],
        }
        return suggestions[step]

    # 兼容旧测试/调用方
    def _suggestions_for_step(self, step: str) -> list[str]:
        return self._static_suggestions(step)


_inspiration_wizard: InspirationWizard | None = None


def get_inspiration_wizard() -> InspirationWizard:
    global _inspiration_wizard
    if _inspiration_wizard is None:
        _inspiration_wizard = InspirationWizard()
    return _inspiration_wizard
