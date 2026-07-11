"""知识图谱 LLM Prompt 常量。

从 knowledge_graph_service.py 提取，便于统一管理与版本化。
"""

KG_EXTRACTION_PROMPT = """你是一个小说知识抽取专家。请从以下章节文本中抽取实体和关系。

## 已知实体（避免重复创建）
{existing_entities_json}

## 章节文本
{chapter_text}

## 输出格式（严格 JSON）
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "character|location|organization|item|event|foreshadowing",
      "aliases": ["别名1"],
      "attributes": {{"status": "alive"}}
    }}
  ],
  "triples": [
    {{
      "subject": "实体名称A",
      "predicate": "关系谓词",
      "object": "实体名称B",
      "confidence": 0.9
    }}
  ]
}}

## 抽取规则
1. 人物实体必须包含 status 属性（alive/dead/missing/unknown）
2. 伏笔实体必须包含 foreshadowing_status 属性（planted/resolved/hanging）
3. 关系谓词使用中文，保持简洁（2-4字）
4. 如果实体已在"已知实体"中存在，使用相同名称，不要创建新实体
5. confidence < 0.5 的关系不要输出
"""

CONSISTENCY_CHECK_PROMPT = """\
你是一个小说一致性检查专家。请检查新章节内容是否与已有设定矛盾。

## 新章节内容（节选）
{chapter_text}

## 新抽取的关系
{new_triples}

## 历史设定上下文
{history_context}

## 输出格式（严格 JSON 数组）
[
  {{
    "severity": "error|warning",
    "type": "冲突类型",
    "message": "具体描述",
    "entity": "相关实体名"
  }}
]

如果没有冲突，返回空数组 []。
"""
