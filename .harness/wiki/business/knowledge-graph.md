# 知识图谱系统

## 概述

故事知识图谱是从已生成章节中自动抽取的结构化记忆系统，用于提升长篇小说生成的连贯性、可控性和可维护性。

与 Storyline/Character/WorldSetting 系统互补：
- **Storyline 等** = 用户/AI 规划的"计划设定"
- **知识图谱** = 从实际生成文本中抽取的"事实记忆"

## 核心能力

### 1. 自动抽取

章节生成后，LLM 自动从文本中抽取：
- **实体**: 人物、地点、组织、道具、事件、伏笔
- **三元组**: 实体间关系（如"张三 → 师徒 → 李四"）

### 2. 上下文检索

生成新章节前，系统自动：
1. 从章节大纲提取关键词
2. 匹配已有实体
3. 查询相关三元组、悬挂伏笔、最近事件
4. 格式化为 prompt 片段注入生成请求

### 3. 一致性检查

生成后自动检查：
- **规则检查**（零成本）: 死亡角色复活、互斥关系矛盾
- **LLM 语义检查**（仅在规则发现疑似问题时触发）

### 4. 时空与状态追踪（活态记忆）

为防止长文写作中角色“吃设定”或“吃状态”（例如前文受伤、后文瞬间痊愈），系统引入了按章节追踪的实体活态历史：
- **状态继承与覆盖**: 在章节抽取 Merge 实体时，自动加载该实体在此章节之前的最新历史状态快照作为基底，并与本章 LLM 抽取的最新属性叠加（覆盖或新增），保存为本章节的全新快照并向前推演实体当前状态。
- **时序演进关系去重**: 人物间恩怨关系随剧情发展多次更新时（如好感度由 10 变为 30），检索时自动按章节降序排列并利用内存 Set 判定，仅向 Prompt 注入最新的演化关系，排除老旧干扰。

## 数据模型

| 表 | 说明 |
|----|------|
| `knowledge_entities` | 实体（UUID PK, novel_id, entity_type, name, aliases, attributes, first/last_chapter） |
| `knowledge_entity_states` | 实体章节历史状态快照表（UUID PK, novel_id, entity_id, chapter_number, attributes, created_at） |
| `knowledge_triples` | 三元组（UUID PK, subject_id, predicate, object_id, chapter_number, confidence, status） |
| `knowledge_extraction_logs` | 抽取日志（novel_id + chapter_number 唯一） |

## API 端点

前缀: `/api/v1/projects/{novel_id}/knowledge-graph`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/entities` | 查询实体列表 |
| GET/POST/PUT/DELETE | `/entities/{id}` | 实体 CRUD |
| GET | `/entities/{id}/history` | 查询单个实体的时序状态轨迹快照 |
| GET | `/triples` | 查询三元组 |
| POST/PUT/DELETE | `/triples/{id}` | 三元组 CRUD |
| POST | `/extract/{chapter_number}` | 手动触发单章抽取 |
| POST | `/extract-all` | 全量重新抽取 |
| GET | `/visualization` | 可视化数据（nodes + edges） |
| POST | `/consistency-check/{chapter_number}` | 手动一致性检查 |

## LangGraph 集成

不修改图结构，在现有节点内部调用：
- `chapter_generation` 节点: 生成前检索上下文，生成后抽取
- `quality_check` 节点: 一致性检查作为质量评分维度

## Feature Flag

`KNOWLEDGE_GRAPH_ENABLED=true`（环境变量可关闭）

关闭时所有图谱操作优雅跳过，不影响核心生成流程。

## 前端

`RelationGraph.vue` 页面包含两个 Tab：
- **故事结构**: 原有树形图（storylines/arcs/scenes）
- **知识图谱**: D3 力导向图（entities + triples 网络）
