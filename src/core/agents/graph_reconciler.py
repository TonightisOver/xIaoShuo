"""图谱协调者 Sub-Agent"""

import json
import structlog
from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

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

## 你的任务
请输出以下更新列表（必须是严格 JSON 格式）：
{{
  "entities_to_upsert": [
    {{
      "name": "实体名称",
      "type": "character|location|organization|item|event|foreshadowing",
      "aliases": ["别名"],
      "attributes": {{ "status": "alive", ... }}
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
  ]
}}

## 规则限制
1. 仅输出合法的 JSON，不要包含 explanations，不要有 markdown 语法块（除了标准的 json 以外），不要有任何前导或后随的文字。
2. 每一个被允许写入的实体，必须出现在 `entities_to_upsert` 中。如果有实体状态改变，可以在 `entity_status_updates` 或 `entities_to_upsert` 中提供。
3. 任何在 Continuity Report 中被明确判定为「严重矛盾（block/critical contradiction）」的新实体或关系，应当被**丢弃/过滤**（不要放入输出的任何列表中）。
4. any 被判定为「合理转折」或「设定扩展」的信息（如角色死亡、关系改变），应当体现在 `entity_status_updates` 或 `triples_to_add` 中，确保图谱能演化。
5. 伏笔回收的实体应当在 `foreshadowing_resolutions` 中指定。
"""


class GraphReconcilerAgent:
    """图谱协调 Sub-Agent：智能解决冲突并更新知识图谱"""

    async def reconcile(
        self,
        continuity_report: dict,
        extracted_entities: str,
        existing_entities: str,
    ) -> dict:
        """根据审查报告、抽取结果和已有上下文，智能产出图谱更新决策"""
        logger.info("graph_reconciler_reconciling")

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
                },
            )
            logger.info(
                "graph_reconciler_completed",
                upsert_count=len(result.get("entities_to_upsert", [])),
                triples_count=len(result.get("triples_to_add", [])),
                updates_count=len(result.get("entity_status_updates", [])),
                resolutions_count=len(result.get("foreshadowing_resolutions", [])),
            )
            return result
        except Exception as e:
            logger.warning("graph_reconciler_failed", error=str(e))
            # 发生异常时，默认不进行任何更新
            return {
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
            }
