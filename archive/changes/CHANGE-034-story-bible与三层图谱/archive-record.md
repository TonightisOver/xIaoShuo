# CHANGE-034 归档记录

- 原名称：story-bible与三层图谱
- 状态：archived-completed
- 时间范围：2026-05-27
- 原路径：`.harness/changes/CHANGE-034-story-bible与三层图谱`
- 归档路径：`archive/changes/CHANGE-034-story-bible与三层图谱`
- 关联提交：
  - 413f7f0 2026-05-27 feat(CHANGE-050): 工程质量修复 — 层级边界修正与前端测试体系

## 目标

新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识图谱前端升级为三层可视化。

## 主要设计决定

新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识图谱前端升级为三层可视化。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/routes/story_bible.py` | 新增 | Story Bible CRUD API，前缀 `/api/v1/projects/{novel_id}/story-bible` |
| `src/api/routes/__init__.py` | 修改 | 注册 story_bible 路由 |
| `src/api/models/db_models.py` | 修改 | 新增 StoryBible 模型（worldview_rules/character_cards/foreshadowing_list 等字段） |
| `src/api/models/responses.py` | 修改 | 新增 StoryBibleResponse |
| `src/api/main.py` | 修改 | 挂载 story_bible 路由 |
| `src/api/services/knowledge_graph_service.py` | 修改 | 三层图谱数据聚合（人物层/事件层/世界层） |
| `src/api/services/novel_manager.py` | 修改 | 小说详情接口返回 story_bible 关联数据 |
| `src/core/llm/chapter_generator.py` | 修改 | 章节生成引入 story_bible 上下文 |
| `src/core/llm/client.py` | 修改 | 重试逻辑增加 openai.APIConnectionError 识别（预置） |

## 涉及模块

- `alembic/versions/1f4a7c9d2b35_add_story_bibles_table.py`
- `frontend/src/components/VolumeList.vue`
- `frontend/src/style.css`
- `frontend/src/views/ChapterEdit.vue`
- `frontend/src/views/Create.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/RelationGraph.vue`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/models/responses.py`
- `src/api/routes/__init__.py`
- `src/api/routes/story_bible.py`
- `src/api/services/knowledge_graph_service.py`
- `src/api/services/novel_manager.py`
- `src/core/llm/chapter_generator.py`
- `src/core/llm/client.py`
- `src/core/llm/prompts.py`
- `tests/unit/test_change035_story_bible_and_three_layer.py`

## 实施结果

新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识图谱前端升级为三层可视化。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/routes/story_bible.py` | 新增 | Story Bible CRUD API，前缀 `/api/v1/projects/{novel_id}/story-bible` |
| `src/api/routes/__init__.py` | 修改 | 注册 story_bible 路由 |
| `src/api/models/db_models.py` | 修改 | 新增 StoryBible 模型（worldview_rules/character_cards/foreshadowing_list 等字段） |
| `src/api/models/responses.py` | 修改 | 新增 StoryBibleResponse |
| `src/api/main.py` | 修改 | 挂载 story_bible 路由 |
| `src/api/services/knowledge_graph_service.py` | 修改 | 三层图谱数据聚合（人物层/事件层/世界层） |
| `src/api/services/novel_manager.py` | 修改 | 小说详情接口返回 story_bible 关联数据 |
| `src/core/llm/chapter_generator.py` | 修改 | 章节生成引入 story_bible 上下文 |
| `src/core/llm/client.py` | 修改 | 重试逻辑增加 openai.APIConnectionError 识别（预置） |

## 测试与验证

新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识图谱前端升级为三层可视化。
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/routes/story_bible.py` | 新增 | Story Bible CRUD API，前缀 `/api/v1/projects/{novel_id}/story-bible` |
| `src/api/routes/__init__.py` | 修改 | 注册 story_bible 路由 |
| `src/api/models/db_models.py` | 修改 | 新增 StoryBible 模型（worldview_rules/character_cards/foreshadowing_list 等字段） |
| `src/api/models/responses.py` | 修改 | 新增 StoryBibleResponse |
| `src/api/main.py` | 修改 | 挂载 story_bible 路由 |
| `src/api/services/knowledge_graph_service.py` | 修改 | 三层图谱数据聚合（人物层/事件层/世界层） |
| `src/api/services/novel_manager.py` | 修改 | 小说详情接口返回 story_bible 关联数据 |
| `src/core/llm/chapter_generator.py` | 修改 | 章节生成引入 story_bible 上下文 |
| `src/core/llm/client.py` | 修改 | 重试逻辑增加 openai.APIConnectionError 识别（预置） |

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `summary.md`
