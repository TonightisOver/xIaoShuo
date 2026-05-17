# xIaoShuo 全面功能 Review v2

## 审查目标

验证 CHANGE-001 到 CHANGE-022 的所有功能是否正确实现、前后端正确连通、无代码缺陷。

## 审查方式

1. **静态代码分析**：检查路由→服务→模型的调用链是否完整
2. **前后端一致性**：前端调用的 API 是否在后端注册
3. **数据模型完整性**：DB 模型字段是否与迁移一致
4. **代码质量**：ruff lint + mypy 类型检查

## 审查范围

### 后端文件

```
src/api/main.py                          — 路由注册
src/api/routes/__init__.py               — 路由导出
src/api/routes/novels.py                 — 旧版任务 API
src/api/routes/projects.py               — 项目管理 + 子资源 CRUD
src/api/routes/conversations.py          — 对话 + 确认 + 生成大纲
src/api/routes/outlines.py               — 大纲 CRUD + 生成
src/api/routes/storylines.py             — 故事线/弧光/场景 + AI 生成
src/api/routes/style.py                  — 文风生成
src/api/routes/ws.py                     — WebSocket
src/api/routes/health.py                 — 健康检查

src/api/services/task_manager.py         — 任务管理
src/api/services/novel_manager.py        — 小说项目管理
src/api/services/novel_generator.py      — 生成器（全量/按卷/按章）
src/api/services/conversation_service.py — 对话服务
src/api/services/outline_service.py      — 大纲服务
src/api/services/storyline_service.py    — 故事线服务
src/api/services/progress_event_bus.py   — 事件总线

src/api/models/db_models.py              — 所有 SQLAlchemy 模型
src/api/models/requests.py               — 请求模型
src/api/models/responses.py              — 响应模型

src/core/database.py                     — 数据库连接
src/core/config.py                       — 配置
src/core/validation.py                   — 验证 + 文风常量
src/core/langgraph/state.py              — LangGraph 状态
src/core/langgraph/graph.py              — 工作流图
src/core/langgraph/nodes/*.py            — 5 个节点
src/core/llm/client.py                   — LLM 客户端
src/core/llm/prompts.py                  — Prompt 模板
```

### 前端文件

```
frontend/src/main.js
frontend/src/App.vue
frontend/src/router/index.js
frontend/src/style.css
frontend/src/views/Home.vue
frontend/src/views/Create.vue
frontend/src/views/NovelDetail.vue
frontend/src/views/TaskDetail.vue
frontend/src/views/WorldEdit.vue
frontend/src/views/Characters.vue
frontend/src/views/ChapterEdit.vue
frontend/src/views/Conversation.vue
frontend/src/views/OutlineEditor.vue
frontend/src/views/StorylineManager.vue
frontend/src/views/RelationGraph.vue
frontend/src/components/VolumeList.vue
frontend/src/components/ChapterRangeDialog.vue
frontend/src/components/ProgressBar.vue
frontend/src/components/StageIndicator.vue
frontend/src/components/TaskCard.vue
frontend/src/composables/useWebSocket.js
```

### 配置文件

```
Dockerfile
docker-compose.yml
nginx.conf
pyproject.toml
alembic.ini
alembic/env.py
alembic/versions/*.py
```

## 检查清单

### 1. 路由→服务调用链完整性

对每个路由文件，检查：
- [ ] 每个 `@router.xxx` 装饰器对应的函数是否调用了正确的服务方法
- [ ] 服务方法是否在对应的 service 类中实现
- [ ] 服务方法调用的 DB 模型字段是否存在

重点检查：
```
conversations.py:
  - confirm_message() → conversation_service.confirm_message()
  - generate-outline → conversation_service.generate_outline_from_conv()
  - apply-suggestion → novel_manager.upsert_world_setting / create_character

storylines.py:
  - generate-ai → storyline_service.generate_storylines_ai()
  - character-arcs/generate-ai → storyline_service.generate_arcs_ai()
  - scenes/generate-ai → storyline_service.generate_scenes_ai()
  - from-conversation → storyline_service.generate_from_conversation()

projects.py:
  - DELETE /chapters/{num} → novel_manager.delete_chapter()
  - POST /generate-volume → novel_generator.generate_volume_background()
  - POST /generate-chapters → novel_generator.generate_chapters_background()
```

### 2. 数据模型完整性

检查 `db_models.py` 中所有模型的字段是否与 alembic 迁移一致：
- [ ] Novel: novel_id, title, idea, novel_type, target_words, writing_style, custom_style_description, writing_style_prompt, status, created_at, updated_at, completed_at
- [ ] Task: task_id, novel_id, status, idea, novel_type, target_words, ...
- [ ] WorldSetting: novel_id, background, geography, culture, rules, extra
- [ ] Character: novel_id, name, role, description, personality, abilities, background_story, extra
- [ ] Chapter: novel_id, volume_number, chapter_number, title, content, word_count, status
- [ ] Volume: novel_id, volume_number, title, summary, outline, status, chapter_start, chapter_end
- [ ] Conversation: novel_id, topic, status, created_at, concluded_at
- [ ] Message: conversation_id, role, content, confirmed_as, created_at
- [ ] Outline: novel_id, level, volume_number, chapter_number, content, status
- [ ] Storyline: novel_id, name, type, description, key_events, status
- [ ] CharacterArc: novel_id, character_id, arc_type, description, stages
- [ ] Scene (scenes_table): novel_id, name, location, description, appearances
- [ ] StorylineCharacter: storyline_id, character_id, role_in_line

### 3. 前端→后端 API 调用一致性

对每个前端 `.vue` 文件中的 `fetch()` 调用，检查：
- [ ] URL 路径是否与后端路由匹配
- [ ] HTTP 方法是否正确（GET/POST/PUT/DELETE）
- [ ] 请求体字段是否与后端 Pydantic 模型匹配
- [ ] 响应字段是否被正确使用

### 4. 前端路由完整性

检查 `router/index.js` 中的路由是否都有对应的 `.vue` 文件：
```
/                          → Home.vue
/create                    → Create.vue
/task/:id                  → TaskDetail.vue
/novels/:id                → NovelDetail.vue
/novels/:id/world          → WorldEdit.vue
/novels/:id/characters     → Characters.vue
/novels/:id/chapters/:num  → ChapterEdit.vue
/novels/:id/conversations/:convId → Conversation.vue
/novels/:id/outlines       → OutlineEditor.vue
/novels/:id/storylines     → StorylineManager.vue
/novels/:id/graph          → RelationGraph.vue
```

### 5. LangGraph 工作流完整性

- [ ] state.py 字段与各节点使用的字段一致
- [ ] graph.py 节点注册与 nodes/ 目录文件一致
- [ ] 各节点 import 的 get_style_instruction 函数存在
- [ ] novel_generator.py 的 initial_state 包含所有必要字段

### 6. 代码质量

```bash
# Lint
poetry run ruff check src/ --select E,W,F,I

# Type check
poetry run mypy src/ --ignore-missing-imports

# Tests
poetry run pytest tests/ -v
```

## 输出格式

请输出 HTML 报告，包含：
1. 总体通过率
2. 每个检查项的结果（✅/❌/⚠️）
3. 发现的问题列表（按 P0/P1/P2 分级）
4. 修复建议
