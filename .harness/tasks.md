# 任务清单：故事圣经 Story Bible + 章节生成约束系统

> 版本：v1.0 · 日期：2026-05-22

---

## 任务总览
- 总任务数：7
- 预估复杂度：高

## 任务列表

### Task 1: StoryBible 数据模型扩展

- **目标**：为 story_bibles 表新增 4 个 JSON 字段
- **范围**：`src/api/models/db_models.py`, `alembic/versions/` (新增迁移文件)
- **修改内容**：
  1. 在 `StoryBible` 类中新增字段：
     - `timeline_events: Mapped[list[dict] | None] = mapped_column(JSON, default=list)`
     - `unresolved_hooks: Mapped[list[dict] | None] = mapped_column(JSON, default=list)`
     - `main_goals: Mapped[list[dict] | None] = mapped_column(JSON, default=list)`
     - `banned_elements: Mapped[list[dict] | None] = mapped_column(JSON, default=list)`
  2. 新增 Alembic 迁移文件 `alembic/versions/xxxx_extend_story_bibles_fields.py`，使用 `op.add_column` 添加 4 个 nullable JSON 列
- **验收标准**：
  - 迁移文件可正常执行 upgrade/downgrade
  - ORM 模型字段与数据库列一致
- **依赖**：无

### Task 2: StoryBible API 路由更新

- **目标**：更新 GET/PUT 端点支持新字段
- **范围**：`src/api/routes/story_bible.py`
- **修改内容**：
  1. `StoryBibleResponse` 增加 4 个字段（默认空列表）
  2. `StoryBibleUpdate` 增加 4 个可选字段
  3. `update_story_bible` 处理逻辑增加新字段的赋值
  4. `get_story_bible` 初始化空记录时包含新字段默认值
- **验收标准**：
  - GET 返回新字段（空列表）
  - PUT 可更新新字段
  - 向后兼容：不传新字段时不影响旧字段
- **依赖**：Task 1

### Task 3: 精准约束抽取服务

- **目标**：新建 story_bible_service，实现根据章节上下文精准抽取相关约束
- **范围**：`src/api/services/story_bible_service.py` (新增)
- **修改内容**：
  1. 实现 `extract_relevant_constraints(bible: StoryBible, chapter_outline: dict, current_chapter_num: int) -> str` 方法
  2. 逻辑：
     - 解析 chapter_outline 中的 characters 列表和 location/scene 字段
     - 从 character_cards 筛选出场人物卡片
     - 从 foreshadowing_list 筛选与出场人物相关的伏笔
     - 从 timeline_events 取最近 5 章的事件
     - 取所有 status != "resolved" 的 unresolved_hooks
     - 取所有 status = "active" 的 main_goals
     - 始终包含 worldview_rules, hard_settings, banned_elements
  3. 返回格式化的约束文本字符串（用于注入 prompt）
- **验收标准**：
  - 给定包含特定人物的 chapter_outline，只返回该人物的 character_card
  - 给定无关人物的 chapter_outline，不返回其他人物的详细卡片
  - 全局约束（worldview_rules, hard_settings）始终包含
- **依赖**：Task 1

### Task 4: 章节生成器约束注入替换

- **目标**：将 chapter_generator.py 中的全量 StoryBible 注入替换为精准约束注入
- **范围**：`src/core/llm/chapter_generator.py` (第86-123行)
- **修改内容**：
  1. 导入 `story_bible_service.extract_relevant_constraints`
  2. 查询 StoryBible 后，调用 `extract_relevant_constraints(bible, chapter_outline, chapter_num)` 获取精准约束
  3. 将返回的约束文本赋值给 `story_bible_context`
  4. 保持异常处理：服务调用失败时 fallback 到 "无历史圣经数据"
- **验收标准**：
  - 生成章节时 prompt 中只包含相关人物和约束
  - 异常时不影响章节生成流程
- **依赖**：Task 3

### Task 5: 生成后反向更新 StoryBible 服务

- **目标**：章节生成后用 LLM 分析内容并自动更新 StoryBible
- **范围**：`src/api/services/story_bible_service.py` (追加方法)
- **修改内容**：
  1. 实现 `async def update_bible_after_generation(novel_id: str, chapter_number: int, chapter_content: str, chapter_outline: dict) -> dict`
  2. 逻辑：
     - 读取当前 StoryBible
     - 构造 LLM prompt，要求从章节内容中提取：新人物信息、新地点、新事件、新伏笔、已回收伏笔、主线进展
     - 调用 `get_llm_client().generate()` 获取结构化 JSON 响应
     - 解析响应并 merge 到 StoryBible 各字段：
       - timeline_events: append 新事件
       - unresolved_hooks: 标记已回收的为 resolved，append 新悬念
       - character_cards: 更新已有人物属性或 append 新人物
       - main_goals: 更新进展
     - 写回数据库
  3. 返回更新摘要（新增了什么、更新了什么）
- **验收标准**：
  - 生成章节后 StoryBible 的 timeline_events 包含新事件
  - 已回收的伏笔 status 变为 resolved
  - LLM 调用失败时不影响主流程（仅 log warning）
- **依赖**：Task 1

### Task 6: StoryBible 冲突检测集成

- **目标**：在质量评估阶段增加基于 StoryBible 的 4 类冲突检测
- **范围**：`src/core/langgraph/nodes/quality_check.py`
- **修改内容**：
  1. 在现有知识图谱一致性检查之后，增加 StoryBible 冲突检测调用
  2. 实现（或在 story_bible_service 中实现）`async def detect_bible_conflicts(novel_id, chapter_number, chapter_content) -> list[dict]`
  3. 检测逻辑（通过 LLM prompt）：
     - 人物性格漂移：对比 character_cards 中的性格与章节行为
     - 时间线冲突：对比 timeline_events 与章节事件顺序
     - 设定矛盾：对比 worldview_rules + hard_settings + banned_elements
     - 伏笔遗忘：检查 unresolved_hooks 中 planted_chapter 距当前超过 10 章的条目
  4. 将检测结果 append 到 `consistency_warnings`
  5. 伏笔遗忘检测不需要 LLM，直接数值比较即可
- **验收标准**：
  - 当章节中人物行为与 character_cards 矛盾时，输出 severity=warning 的冲突
  - 当存在超过 10 章未回收的伏笔时，输出 severity=warning 的提醒
  - 检测失败时优雅降级，不阻断质量评估流程
- **依赖**：Task 1, Task 5

### Task 7: 反向更新集成到生成流程

- **目标**：将 StoryBible 反向更新嵌入章节生成主流程
- **范围**：`src/api/services/novel_generator.py` 或 `src/core/langgraph/nodes/chapter_generation.py`
- **修改内容**：
  1. 在章节生成成功并持久化到数据库后，调用 `update_bible_after_generation()`
  2. 调用位置选择：在 `novel_generator.py` 的 `_persist_to_novel()` 完成后，对每个成功生成的章节触发更新
  3. 使用 try/except 包裹，失败仅 log 不阻断
  4. 可选：批量生成时，每章生成后立即更新（确保后续章节能读到最新 StoryBible）
- **验收标准**：
  - 批量生成 3 章后，StoryBible 包含所有 3 章的事件和人物更新
  - 单章更新失败不影响后续章节生成
- **依赖**：Task 5

---

## 任务依赖关系

```
Task 1 (模型扩展)
  ├── Task 2 (API 更新)
  ├── Task 3 (约束抽取服务)
  │     └── Task 4 (注入替换)
  ├── Task 5 (反向更新服务)
  │     ├── Task 6 (冲突检测)
  │     └── Task 7 (流程集成)
  └── Task 6 (冲突检测) [也依赖 Task 5]
```

## 实施顺序建议

T1 → T2 → T3 → T4 → T5 → T7 → T6

理由：
- T1 是基础，所有后续任务依赖模型字段
- T2 紧跟 T1，确保 API 可用
- T3/T4 实现精准注入，是生成质量提升的核心
- T5/T7 实现反向更新，确保 StoryBible 数据持续积累
- T6 最后实现冲突检测，依赖 StoryBible 中有足够数据才有意义
