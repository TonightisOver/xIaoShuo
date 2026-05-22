# 需求文档：故事圣经 Story Bible + 章节生成约束系统

> 版本：v1.0 · 日期：2026-05-22

---

## 需求概述

为每个小说项目维护一个结构化故事圣经（Story Bible），在章节生成前精准抽取相关约束注入 prompt，生成后自动反向更新故事圣经，并在质量评估阶段检测人物性格漂移、时间线冲突、设定矛盾、伏笔遗忘等问题。

## 背景与动机

当前系统已有基础 StoryBible 模型（worldview_rules, character_cards, faction_relations, location_settings, prop_settings, foreshadowing_list, hard_settings），章节生成前会全量注入 StoryBible 内容到 prompt。但存在以下不足：

1. **字段不完整**：缺少时间线事件、未回收悬念、主线目标、禁用设定细化等维度
2. **约束注入粗放**：当前全量注入所有 StoryBible 内容，token 浪费且噪声大
3. **无反向更新**：生成章节后不会自动更新 StoryBible，导致圣经数据逐渐过时
4. **冲突检测不足**：质量评估仅依赖知识图谱一致性检查，缺少基于 StoryBible 的专项冲突检测

## 功能范围

### 功能 1: StoryBible 模型扩展

**目标**：扩展 story_bibles 表，增加 4 个新字段

| 字段 | 类型 | 说明 |
|------|------|------|
| timeline_events | JSON | 已发生事件时间线，格式 `[{chapter, event, characters, timestamp_in_story}]` |
| unresolved_hooks | JSON | 未回收悬念，格式 `[{hook_id, description, planted_chapter, related_characters, status}]` |
| main_goals | JSON | 主线目标，格式 `[{goal_id, description, owner, status, progress}]` |
| banned_elements | JSON | 禁用设定细化，格式 `[{element, reason, scope}]` |

**约束**：
- 需要新增 Alembic 迁移文件
- 需要更新 ORM 模型 `StoryBible` 类
- 需要更新 API 路由的 Request/Response 模型
- 向后兼容：新字段默认为空列表

### 功能 2: 精准约束注入

**目标**：生成前根据当前章节的卷号、出场人物、场景，从 StoryBible 中精准抽取相关约束

**当前行为**（`chapter_generator.py` 第86-123行）：全量注入 worldview_rules, character_cards, faction_relations, location_settings, prop_settings, foreshadowing_list, hard_settings

**目标行为**：
1. 解析当前 chapter_outline 中的出场人物列表和场景地点
2. 从 character_cards 中只抽取本章出场人物的卡片
3. 从 foreshadowing_list 中只抽取与本章人物/场景相关的伏笔
4. 从 timeline_events 中只抽取最近 N 章的事件（上下文窗口）
5. 从 unresolved_hooks 中抽取所有 status=hanging 的悬念
6. 始终注入 worldview_rules、hard_settings、banned_elements（全局约束）
7. 从 main_goals 中抽取 status=active 的目标

**技术方案**：新增 `src/api/services/story_bible_service.py`，提供 `extract_relevant_constraints(bible, chapter_outline, current_chapter_num)` 方法

### 功能 3: 生成后反向更新 StoryBible

**目标**：章节生成完成后，用 LLM 分析新章节内容，自动更新 StoryBible

**触发时机**：在 LangGraph 流程中，quality_check 节点之后（或作为 quality_check 的一部分）

**更新逻辑**：
1. 调用 LLM 分析新章节，提取：新出现的人物信息、新地点、新事件、新伏笔、已回收的伏笔、主线目标进展
2. 将提取结果 merge 到 StoryBible 对应字段
3. 更新 timeline_events（追加本章事件）
4. 更新 unresolved_hooks（标记已回收的悬念，追加新悬念）
5. 更新 main_goals 进展

**技术方案**：新增 `src/core/langgraph/nodes/story_bible_update.py` 节点，或在 `novel_generator.py` 的章节持久化后调用独立服务

### 功能 4: StoryBible 冲突检测

**目标**：在质量评估阶段，对比新章节与 StoryBible 约束，检测 4 类问题

**检测维度**：
1. **人物性格漂移**：对比章节中人物行为与 character_cards 中的性格描述
2. **时间线冲突**：对比章节事件与 timeline_events 中已记录的事件顺序
3. **设定矛盾**：对比章节内容与 worldview_rules + hard_settings + banned_elements
4. **伏笔遗忘**：检查 unresolved_hooks 中 planted_chapter 距当前章节超过 N 章（可配置，默认10章）的悬念

**技术方案**：增强 `quality_check.py` 节点，在现有 8 维评分之外，增加 StoryBible 冲突检测调用，将冲突结果写入 `consistency_warnings`

## 涉及模块

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `src/api/models/db_models.py` | 修改 | StoryBible 类增加 4 个字段 |
| `alembic/versions/xxx_extend_story_bibles.py` | 新增 | 迁移文件 |
| `src/api/routes/story_bible.py` | 修改 | 更新 Request/Response 模型 |
| `src/api/services/story_bible_service.py` | 新增 | 约束抽取 + 反向更新逻辑 |
| `src/core/llm/chapter_generator.py` | 修改 | 替换全量注入为精准约束注入 |
| `src/core/langgraph/nodes/quality_check.py` | 修改 | 增加 StoryBible 冲突检测 |
| `src/core/langgraph/graph.py` | 可能修改 | 如需新增节点则修改流程图 |

## 技术约束

- Python 3.11 + FastAPI + SQLAlchemy async
- LLM 调用使用现有 `get_llm_client()` + DeepSeek API
- 不引入新外部依赖
- 新字段使用 JSON 类型，保持 PostgreSQL 兼容
- LLM prompt 需控制 token 消耗，避免过长上下文

## 验收标准

- [ ] story_bibles 表新增 timeline_events, unresolved_hooks, main_goals, banned_elements 字段
- [ ] API GET/PUT 端点支持新字段的读写
- [ ] 章节生成前根据出场人物和场景精准抽取约束（非全量注入）
- [ ] 章节生成后自动提取新信息并更新 StoryBible
- [ ] 质量评估阶段检测人物性格漂移并输出警告
- [ ] 质量评估阶段检测时间线冲突并输出警告
- [ ] 质量评估阶段检测设定矛盾并输出警告
- [ ] 质量评估阶段检测伏笔遗忘（超过 10 章未回收）并输出提醒
- [ ] 所有新增代码有对应单元测试
- [ ] Alembic 迁移可正常执行 upgrade/downgrade
