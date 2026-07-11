"""图谱协调者 Sub-Agent"""

import json
import time

import structlog
from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client
from src.core.agents.journal_recorder import get_journal_recorder

logger = structlog.get_logger(__name__)

GRAPH_RECONCILER_PROMPT = """你是一个小说知识图谱协调专家（Graph Reconciler Sub-Agent）。
你的任务是根据「连续性编辑审查报告（Continuity Report）」、「本章抽取的新实体和关系（Raw Extracted Entities & Triples）」以及「已有实体上下文（Existing Entities Context）」，智能地决定需要对知识图谱做哪些更新。

你的目标是：
1. **防止图谱污染**：如果本章新抽取的数据与已有设定存在「真实矛盾」（例如，死人复活、不合理的地点跳跃等被 Continuity Report 拦截的问题），应该跳过或不合并这些无效数据。
2. **支持合理剧情转折**：如果 Continuity Report 指出是「合理转折/变化」（例如，好人变坏、阵营改变、角色位置转移），应当更新图谱（在 entity_status_updates 或 triples_to_add 中体现最新的状态或关系），不要将其作为矛盾丢弃。
3. **伏笔回收**：如果章节中回收了某项伏笔，应当在 `foreshadowing_resolutions` 中将该伏笔实体的 status 更新为 `resolved`。
4. **正常实体/关系合并**：对于没有冲突的全新实体和关系，应该将其加入更新列表中。

## 输入数据

### 1. 连续性编辑审查报告 (Continuity Report)
{continuity_report}

### 2. 本章新抽取的实体和关系 (Raw Extracted)
{extracted_entities}

### 3. 已有的实体与关系上下文 (Existing Entities)
{existing_entities}

## 三阶段分级原则

你需要对每个待写入实体进行分级判定：

### Stage 1 — block（严格拦截）
- 被 Continuity Report 标记为 `verdict=block` 的严重矛盾实体
- 违背核心世界观设定的实体（例如角色死亡后复活无剧情说明）
- 将这些实体放入 `blocked_entities` 列表，并给出 `reason`

### Stage 2 — pass（自动合并）
- 无任何矛盾的常规实体/关系
- `_needs_review=False`，可直接写入图谱
- 放入 `entities_to_upsert` / `triples_to_add` / `entity_status_updates`

### Stage 3 — escalate（需要人工确认）
- 被 Continuity Report 标记为 `verdict=warn` 的潜在问题实体
- 非严重但有不确定性，建议标注 `_needs_review=True`
- 放入 `entities_to_upsert` 但附带 `_needs_review=True` 标记
- 不立即写入实体状态（status 保持 pending_review）

## 你的输出（严格 JSON 格式）
{{
  "entities_to_upsert": [
    {{
      "name": "实体名称",
      "type": "character|location|organization|item|event|foreshadowing",
      "aliases": ["别名"],
      "attributes": {{ "status": "alive", ... }},
      "_needs_review": false
    }}
  ],
  "triples_to_add": [
    {{
      "subject": "实体名称A",
      "predicate": "关系谓词",
      "object": "实体名称B",
      "confidence": 0.9,
      "metadata": {{}}
    }}
  ],
  "entity_status_updates": [
    {{
      "name": "实体名称",
      "attributes": {{ "status": "dead", "location": "天玄城" }}
    }}
  ],
  "foreshadowing_resolutions": [
    {{
      "name": "伏笔实体名称",
      "attributes": {{ "foreshadowing_status": "resolved" }}
    }}
  ],
  "blocked_entities": [
    {{
      "name": "被拦截实体名称",
      "reason": "被拦截原因描述"
    }}
  ]
}}

## 规则限制
1. 仅输出合法的 JSON，不要包含 explanations，不要有 markdown 语法块，不要有任何前导或后随的文字。
2. `blocked_entities` 必须列出所有因 block/warn 被拦截的实体名称和原因。
3. `_needs_review=true` 的实体在 `entity_status_updates` 中不立即写入状态，等待人工确认。
4. `_needs_review=false` 的实体在 `entity_status_updates` 中正常写入最新状态。
5. 任何被明确判定为「严重矛盾（block/critical contradiction）」的实体，只入 `blocked_entities`，不写入任何 merge 列表。
6. 伏笔回收的实体应当在 `foreshadowing_resolutions` 中指定。
"""


class GraphReconcilerAgent:
    """图谱协调 Sub-Agent：智能解决冲突并更新知识图谱"""

    def __init__(self, task_id: str | None = None, novel_id: int | None = None):
        self.task_id = task_id
        self.novel_id = novel_id

    async def reconcile(
        self,
        continuity_report: dict,
        extracted_entities: str,
        existing_entities: str,
    ) -> dict:
        """根据审查报告、抽取结果和已有上下文，智能产出图谱更新决策"""
        logger.info("graph_reconciler_reconciling")

        # 创建日志条目（依赖注入的记录器；未注入时跳过日志）
        journal = None
        recorder = get_journal_recorder()
        if self.task_id and recorder is not None:
            journal = await recorder.create_entry(
                task_id=self.task_id,
                agent_name="graph_reconciler",
                novel_id=self.novel_id,
                input_summary={
                    "continuity_verdict": continuity_report.get("verdict")
                        if isinstance(continuity_report, dict) else None,
                    "extracted_length": len(extracted_entities or ""),
                },
            )
        start_time = time.monotonic()

        # 格式化报告以安全渲染 JSON 或字典
        if isinstance(continuity_report, dict):
            report_str = json.dumps(continuity_report, ensure_ascii=False)
        elif continuity_report is None:
            report_str = "{}"
        else:
            report_str = str(continuity_report)

        prompt = GRAPH_RECONCILER_PROMPT.format(
            continuity_report=report_str,
            extracted_entities=extracted_entities or "{}",
            existing_entities=existing_entities or "无",
        )

        client = get_llm_client()
        try:
            # 必须使用 use_flash=True 生成，以快速、低成本响应
            raw = await client.generate(prompt, use_flash=True, temperature=0.1)
            result = safe_json_parse(
                raw,
                fallback={
                    "entities_to_upsert": [],
                    "triples_to_add": [],
                    "entity_status_updates": [],
                    "foreshadowing_resolutions": [],
                    "blocked_entities": [],
                },
            )
            # 确保 blocked_entities 字段存在
            if "blocked_entities" not in result:
                result["blocked_entities"] = []

            # 统计
            upsert_count = len(result.get("entities_to_upsert", []))
            blocked_count = len(result.get("blocked_entities", []))
            triples_count = len(result.get("triples_to_add", []))
            updates_count = len(result.get("entity_status_updates", []))
            resolutions_count = len(result.get("foreshadowing_resolutions", []))

            logger.info(
                "graph_reconciler_completed",
                upsert_count=upsert_count,
                triples_count=triples_count,
                updates_count=updates_count,
                resolutions_count=resolutions_count,
                blocked_count=blocked_count,
            )

            # 更新日志
            if journal:
                await recorder.complete_entry(
                    entry_id=journal.id,
                    status="success",
                    output_summary={
                        "upsert_count": upsert_count,
                        "triples_count": triples_count,
                        "updates_count": updates_count,
                        "resolutions_count": resolutions_count,
                        "blocked_count": blocked_count,
                    },
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                    conflict_count=blocked_count,
                    blocked_entity_count=blocked_count,
                )
            return result
        except Exception as e:
            logger.warning("graph_reconciler_failed", error=str(e))
            if journal:
                await recorder.complete_entry(
                    entry_id=journal.id, status="failed",
                    error_message=str(e),
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                )
            # 发生异常时，默认不进行任何更新
            return {
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [],
            }
