# CHANGE-034 Story Bible 与三层知识图谱前端

## 概述
新增故事圣经（Story Bible）功能，提供世界观规则、角色卡、阵营关系、伏笔清单等结构化设定管理；前端全面重构，包括 Create、Home、NovelDetail、ChapterEdit、RelationGraph 页面大改版；知识图谱前端升级为三层可视化。

## 变更文件

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
| `src/core/llm/prompts.py` | 修改 | 新增 CHAPTER_PLANNING_PROMPT，章节规划单独 Prompt |
| `frontend/src/views/Create.vue` | 修改 | 创作流程 UI 重构，步骤引导优化 |
| `frontend/src/views/Home.vue` | 修改 | 首页重构，小说卡片展示优化 |
| `frontend/src/views/NovelDetail.vue` | 修改 | 小说工作台大改版，集成 Story Bible 入口 |
| `frontend/src/views/ChapterEdit.vue` | 修改 | 章节编辑器重构，支持 AI 辅助修改 |
| `frontend/src/views/RelationGraph.vue` | 修改 | 三层知识图谱可视化（人物/事件/世界分层展示） |
| `frontend/src/components/VolumeList.vue` | 修改 | 卷列表组件优化 |
| `frontend/src/style.css` | 修改 | 全局样式扩充 |
| `alembic/versions/1f4a7c9d2b35_add_story_bibles_table.py` | 新增 | story_bibles 表迁移 |
| `tests/unit/test_change035_story_bible_and_three_layer.py` | 新增 | Story Bible API 和三层图谱测试 |

## 核心实现

### Story Bible 数据结构
```python
worldview_rules: str       # 世界观规则文本
character_cards: list[dict] # 角色卡列表
faction_relations: str     # 阵营关系
location_settings: str     # 地点设定
prop_settings: str         # 道具设定
foreshadowing_list: list[dict] # 伏笔清单
hard_settings: str         # 硬性设定（不可违反）
```

### 三层知识图谱
- 人物层：角色节点 + 人物关系边
- 事件层：剧情事件节点 + 因果关系边
- 世界层：地点/势力/道具节点 + 归属关系边

## 关联 Commits
- `81363a1` feat: refresh creation and novel workspace UI
- `0a83522` fix: include writing style in novel summaries
- `0fd4f2a` feat: add story bible and layered graph
