"""连续性编辑 Sub-Agent"""

import json
import time

import structlog
from src.core.llm.client import get_llm_client
from src.core.json_utils import safe_json_parse
from src.core.agents.journal_recorder import get_journal_recorder

logger = structlog.get_logger(__name__)

CONTINUITY_EDITOR_PROMPT = """你是一位小说的连续性编辑（Continuity Editor），
负责审查新写的章节是否与已有设定一致。

## 新章节内容
{chapter_content}

## 已有的关键设定记录
{kg_summary}

## 审查规则
1. 区分「真实矛盾」和「合理剧情转折」
   - 角色 A 在第 5 章死了，第 10 章突然说话 → 真矛盾
   - 角色 B 一直是好人，第 15 章突然背叛 → 剧情转折，不是矛盾
2. 区分「设定违反」和「设定扩展」
   - 主角不会飞，但新章节飞了 → 设定违反
   - 之前没提主角会隐身，突然会了 → 设定扩展

## 输出格式（严格 JSON）
{{
  "verdict": "pass|warn|block",
  "issues": [
    {{
      "type": "contradiction|expansion|twist",
      "severity": "critical|minor|info",
      "description": "具体描述",
      "entity": "相关实体名",
      "suggestion": "建议修复方式",
      "kg_update_needed": true,
      "kg_update_detail": "图谱更新内容描述"
    }}
  ],
  "summary": "整体审查结论（1-2句话）"
}}
"""


class ContinuityEditorAgent:
    """连续性编辑 Sub-Agent：审查生成内容与已有设定的一致性"""

    def __init__(self, task_id: str | None = None, novel_id: int | None = None):
        self.task_id = task_id
        self.novel_id = novel_id

    async def review(self, chapter_content: str, kg_summary: str) -> dict:
        """审查新章节内容的一致性"""
        logger.info("continuity_editor_review_start", content_len=len(chapter_content))

        # 创建日志条目（依赖注入的记录器；未注入时跳过日志）
        journal = None
        recorder = get_journal_recorder()
        if self.task_id and recorder is not None:
            journal = await recorder.create_entry(
                task_id=self.task_id,
                agent_name="continuity_editor",
                novel_id=self.novel_id,
                input_summary={
                    "content_length": len(chapter_content),
                    "kg_summary_length": len(kg_summary or ""),
                },
            )
        start_time = time.monotonic()

        prompt = CONTINUITY_EDITOR_PROMPT.format(
            chapter_content=chapter_content,
            kg_summary=kg_summary or "无已有的关键设定记录。",
        )

        client = get_llm_client()
        default_report = {
            "verdict": "pass",
            "issues": [],
            "summary": "未能成功生成审查结论，默认通过。"
        }

        try:
            # 使用 flash 模型，且 use_flash=True
            raw = await client.generate(prompt, use_flash=True, max_tokens=2000)
            logger.info("continuity_editor_raw_response", raw_len=len(raw))

            # 尝试使用 safe_json_parse
            result = safe_json_parse(raw, fallback=None)
            if result is None:
                # 手动 fallback 提取
                start = raw.find('{')
                end = raw.rfind('}')
                if start != -1 and end != -1:
                    try:
                        result = json.loads(raw[start:end+1])
                    except Exception as e:
                        logger.warning("continuity_editor_fallback_json_parse_failed", error=str(e))

            if isinstance(result, dict):
                # 检查并补全必需的键
                if "verdict" not in result:
                    result["verdict"] = "pass"
                if "issues" not in result or not isinstance(result["issues"], list):
                    result["issues"] = []
                if "summary" not in result:
                    result["summary"] = ""
                logger.info(
                    "continuity_editor_review_success",
                    verdict=result["verdict"],
                    issues_count=len(result["issues"]),
                )

                # 更新日志
                if journal:
                    await recorder.complete_entry(
                        entry_id=journal.id,
                        status="success",
                        output_summary={
                            "verdict": result["verdict"],
                            "issues_count": len(result["issues"]),
                            "summary": result["summary"],
                        },
                        duration_ms=int((time.monotonic() - start_time) * 1000),
                        continuity_score={
                            "pass": 90, "warn": 60, "block": 30,
                        }.get(result["verdict"], 50),
                    )
                return result

            logger.warning("continuity_editor_invalid_response_format", raw=raw)

            if journal:
                await recorder.complete_entry(
                    entry_id=journal.id, status="failed",
                    error_message="Invalid response format",
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
            return default_report

        except Exception as e:
            logger.error("continuity_editor_review_failed", error=str(e), exc_info=True)
            if journal:
                await recorder.complete_entry(
                    entry_id=journal.id, status="failed",
                    error_message=str(e),
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
            return default_report
