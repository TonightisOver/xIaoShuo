"""Book import service for TXT novel analysis."""

from __future__ import annotations

import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.api.services.novel_manager import get_novel_manager
from src.core.llm.helpers import generate_and_parse_json

CHAPTER_PATTERN = re.compile(r"(?im)(第.{1,5}章[^\n\r]*|Chapter\s+\d+[^\n\r]*)")


class BookImportService:
    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}

    def upload_and_parse(self, file_path_or_text: str) -> list[dict[str, Any]]:
        text = self._read_text(file_path_or_text)
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            raise ValueError("TXT content cannot be empty")

        matches = list(CHAPTER_PATTERN.finditer(text))
        if not matches:
            return [{"index": 1, "title": "全文", "content": text}]

        chapters: list[dict[str, Any]] = []
        prefix = text[: matches[0].start()].strip()
        if prefix:
            chapters.append({"index": 1, "title": "序章", "content": prefix})

        start_index = len(chapters) + 1
        for offset, match in enumerate(matches):
            index = start_index + offset
            next_match = matches[offset + 1] if offset + 1 < len(matches) else None
            end = next_match.start() if next_match else len(text)
            title = match.group(0).strip()
            content = text[match.end():end].strip()
            chapters.append({"index": index, "title": title, "content": content})

        return chapters

    async def analyze_novel(
        self,
        client: Any,
        chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        samples = self._build_chapter_samples(chapters)
        fallback = {
            "title": "拆书导入项目",
            "genre": "拆书导入",
            "summary": "",
            "characters": [],
            "worldview": {"background": "", "rules": "", "geography": ""},
            "foreshadows": [],
            "writing_style": {
                "narrative_perspective": "",
                "language_features": "",
                "pacing_preference": "",
            },
        }
        prompt = f"""你是资深中文网络小说拆书分析师。
请分析以下小说章节样本，提取可复用的项目设定。

章节样本：
{samples}

请只输出 JSON，格式如下：
{{
  "title": "作品标题或项目标题",
  "genre": "类型",
  "summary": "整体故事概述",
  "characters": [
    {{"name": "姓名", "personality": "性格", "background": "背景"}}
  ],
  "worldview": {{
    "background": "世界背景",
    "rules": "运行规则",
    "geography": "地理/势力/重要地点"
  }},
  "foreshadows": [
    {{"name": "伏笔名", "description": "内容", "chapter": 1, "status": "active"}}
  ],
  "writing_style": {{
    "narrative_perspective": "叙事视角",
    "language_features": "语言特点",
    "pacing_preference": "节奏偏好"
  }}
}}"""

        data = await generate_and_parse_json(
            client,
            prompt,
            max_tokens=4000,
            temperature=0.3,
            fallback=fallback,
        )
        if not isinstance(data, dict):
            data = fallback
        return self._normalize_analysis(data, chapters)

    async def create_project_from_analysis(
        self,
        novel_id: str,
        analysis_data: dict[str, Any],
    ) -> dict[str, Any]:
        manager = get_novel_manager()
        title = analysis_data.get("title") or novel_id
        novel_type = analysis_data.get("genre") or "拆书导入"
        style = analysis_data.get("writing_style") or {}
        style_prompt = self._format_writing_style(style)
        idea = self._format_project_idea(analysis_data)

        created_novel_id = await manager.create_novel(
            idea=idea,
            novel_type=novel_type,
            target_words=100000,
            title=title,
            writing_style="拆书风格",
            custom_style_description=style_prompt,
            writing_style_prompt=style_prompt,
        )

        worldview = analysis_data.get("worldview") or {}
        await manager.upsert_world_setting(
            created_novel_id,
            background=worldview.get("background", ""),
            rules=worldview.get("rules", ""),
            geography=worldview.get("geography", ""),
            extra={"foreshadows": analysis_data.get("foreshadows", [])},
        )

        created_characters = []
        for character in analysis_data.get("characters", []):
            if not isinstance(character, dict) or not character.get("name"):
                continue
            char_id = await manager.create_character(
                created_novel_id,
                name=character.get("name", ""),
                role=character.get("role", "主要角色"),
                personality=character.get("personality", ""),
                background_story=character.get("background", ""),
                description=character.get("description", ""),
            )
            created_characters.append({"id": char_id, "name": character["name"]})

        return {
            "novel_id": created_novel_id,
            "status": "draft",
            "title": title,
            "novel_type": novel_type,
            "characters_created": created_characters,
        }

    def create_task(self, chapters: list[dict[str, Any]]) -> str:
        task_id = f"book-import-{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "chapters": deepcopy(chapters),
            "chapter_count": len(chapters),
            "analysis": None,
            "project": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        return task_id

    async def run_analysis(self, task_id: str, client: Any) -> None:
        task = self._get_task(task_id)
        self._set_task(task_id, status="analyzing", error=None)
        try:
            analysis = await self.analyze_novel(client, task["chapters"])
            self._set_task(task_id, status="completed", analysis=analysis)
        except Exception as exc:
            self._set_task(task_id, status="failed", error=str(exc))

    def get_status(self, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "chapter_count": task["chapter_count"],
            "analysis": deepcopy(task["analysis"]),
            "project": deepcopy(task["project"]),
            "error": task["error"],
            "created_at": task["created_at"],
            "updated_at": task["updated_at"],
        }

    async def apply_task(self, task_id: str) -> dict[str, Any]:
        task = self._get_task(task_id)
        if task["status"] == "applied" and task["project"]:
            return deepcopy(task["project"])
        if task["status"] != "completed" or not task["analysis"]:
            raise ValueError("Book import analysis is not completed")

        project = await self.create_project_from_analysis(task_id, task["analysis"])
        self._set_task(task_id, status="applied", project=project)
        return deepcopy(project)

    def clear(self) -> None:
        self._tasks.clear()

    def _get_task(self, task_id: str) -> dict[str, Any]:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError("Book import task not found")
        return task

    def _set_task(self, task_id: str, **updates: Any) -> None:
        task = self._get_task(task_id)
        task.update(updates)
        task["updated_at"] = datetime.now(UTC).isoformat()

    def _read_text(self, file_path_or_text: str) -> str:
        if os.path.exists(file_path_or_text):
            raw = Path(file_path_or_text).read_bytes()
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return raw.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="ignore")
        return file_path_or_text

    def _build_chapter_samples(self, chapters: list[dict[str, Any]]) -> str:
        selected = chapters[:6]
        if len(chapters) > 8:
            selected += chapters[-2:]
        parts = []
        for chapter in selected:
            content = chapter.get("content", "")
            parts.append(
                f"## {chapter.get('title', '')}\n{content[:2500]}"
            )
        return "\n\n".join(parts)

    def _normalize_analysis(
        self,
        data: dict[str, Any],
        chapters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        worldview = data.get("worldview")
        if not isinstance(worldview, dict):
            worldview = {}
        style = data.get("writing_style")
        if not isinstance(style, dict):
            style = {}
        characters = data.get("characters")
        if not isinstance(characters, list):
            characters = []
        foreshadows = data.get("foreshadows")
        if not isinstance(foreshadows, list):
            foreshadows = []

        return {
            "title": data.get("title") or "拆书导入项目",
            "genre": data.get("genre") or "拆书导入",
            "summary": data.get("summary") or "",
            "chapter_count": len(chapters),
            "characters": characters,
            "worldview": {
                "background": worldview.get("background", ""),
                "rules": worldview.get("rules", ""),
                "geography": worldview.get("geography", ""),
            },
            "foreshadows": foreshadows,
            "writing_style": {
                "narrative_perspective": style.get("narrative_perspective", ""),
                "language_features": style.get("language_features", ""),
                "pacing_preference": style.get("pacing_preference", ""),
            },
        }

    def _format_writing_style(self, style: dict[str, Any]) -> str:
        return "\n".join(
            part for part in [
                f"叙事视角：{style.get('narrative_perspective', '')}",
                f"语言特点：{style.get('language_features', '')}",
                f"节奏偏好：{style.get('pacing_preference', '')}",
            ]
            if part.strip("：")
        )

    def _format_project_idea(self, analysis: dict[str, Any]) -> str:
        worldview = analysis.get("worldview") or {}
        return "\n\n".join(
            [
                f"拆书概述：{analysis.get('summary', '')}",
                f"世界背景：{worldview.get('background', '')}",
                f"世界规则：{worldview.get('rules', '')}",
                f"地理设定：{worldview.get('geography', '')}",
                f"伏笔列表：{analysis.get('foreshadows', [])}",
            ]
        )


_book_import_service: BookImportService | None = None


def get_book_import_service() -> BookImportService:
    global _book_import_service
    if _book_import_service is None:
        _book_import_service = BookImportService()
    return _book_import_service
