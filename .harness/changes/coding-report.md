# 编码报告：CHANGE-041 故事圣经约束系统

> 日期：2026-05-22

## 变更摘要

实现了 StoryBible 精准约束注入、生成后反向更新、冲突检测三大核心功能。

## 完成任务

### Task 1: StoryBible 数据模型扩展
- `src/api/models/db_models.py` — 新增 4 个 JSON 字段：timeline_events, unresolved_hooks, main_goals, banned_elements
- `alembic/versions/20260522_extend_story_bibles_fields.py` — 新增迁移文件

### Task 2: StoryBible API 路由更新
- `src/api/routes/story_bible.py` — StoryBibleResponse/StoryBibleUpdate 增加 4 个字段，初始化和更新逻辑同步更新

### Task 3: 精准约束抽取服务
- `src/api/services/story_bible_service.py` (新增) — `extract_relevant_constraints()` 方法
  - 只抽取本章出场人物的 character_cards
  - 只抽取相关伏笔
  - 只取最近 5 章时间线事件
  - 过滤已解决悬念和已完成目标
  - 全局约束始终包含

### Task 4: 章节生成器约束注入替换
- `src/core/llm/chapter_generator.py` — 替换全量注入为 `extract_relevant_constraints()` 调用

### Task 5: 生成后反向更新 StoryBible 服务
- `src/api/services/story_bible_service.py` — `update_bible_after_generation()` 方法
  - LLM 分析章节内容提取新事件、新悬念、已回收悬念、人物更新、目标进展
  - Merge 到 StoryBible 各字段

### Task 6: StoryBible 冲突检测集成
- `src/api/services/story_bible_service.py` — `detect_bible_conflicts()` 方法
  - 规则检测：伏笔遗忘（超过 10 章未回收）
  - LLM 检测：人物性格漂移、时间线冲突、设定矛盾
- `src/core/langgraph/nodes/quality_check.py` — 在知识图谱检查后集成 StoryBible 冲突检测

### Task 7: 反向更新集成到生成流程
- `src/api/services/novel_generator.py` — 在章节持久化和版本创建后调用 `update_bible_after_generation()`

## 测试结果

- `tests/unit/test_change041_story_bible.py` — 23 tests PASSED
- `tests/unit/test_change040_volume_and_graph.py` — 18 tests PASSED (回归验证)

## 文件变更清单

| 文件 | 变更类型 | 行数变化 |
|------|----------|----------|
| src/api/models/db_models.py | 修改 | +4 |
| alembic/versions/20260522_extend_story_bibles_fields.py | 新增 | +32 |
| src/api/routes/story_bible.py | 修改 | +20 |
| src/api/services/story_bible_service.py | 新增 | ~300 |
| src/core/llm/chapter_generator.py | 修改 | -20/+10 |
| src/core/langgraph/nodes/quality_check.py | 修改 | +15 |
| src/api/services/novel_generator.py | 修改 | +12 |
| tests/unit/test_change041_story_bible.py | 新增 | ~230 |
