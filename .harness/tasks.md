# 任务清单：CHANGE-040 修复章节分卷与图谱筛选

> 版本：v1.0 · 日期：2026-05-22

---

## 任务总览
- 总任务数：5
- 预估复杂度：中

## 任务列表

### Task 1: 修复章节生成后 volume_number 缺失

- **目标**：确保章节生成完成后正确分配 volume_number
- **范围**：`src/api/services/novel_generator.py`
- **修改内容**：
  1. 改进 `_find_volume_number()` 函数：增加通过 volume 的 chapter_start/chapter_end 范围匹配的 fallback
  2. 在 `generate_chapters_background()` 和 `_persist_to_novel()` 的章节写入完成后，调用 `fix_volume_numbers()` 补充遗漏
- **验收标准**：重新生成章节后，章节在前端按卷分组显示
- **依赖**：无

### Task 2: 修复章节生成失败导致 404

- **目标**：章节重新生成时不丢失旧数据
- **范围**：`src/api/services/novel_generator.py`
- **修改内容**：
  1. `generate_chapters_background()` 中改为"先生成，后替换"策略：先生成所有章节到临时列表，全部成功后再 DELETE + INSERT
  2. 如果部分章节生成失败，只替换成功的章节，保留失败章节的旧数据
- **验收标准**：即使部分章节生成超时，已有章节仍可正常访问
- **依赖**：无

### Task 3: 故事框架拓扑无数据时提供生成入口

- **目标**：在故事框架拓扑 Tab 无数据时，提供一键生成故事线的按钮
- **范围**：`frontend/src/views/RelationGraph.vue`
- **修改内容**：
  1. 在 `!hasData` 的空状态区域增加"一键生成故事线"按钮
  2. 按钮调用 `POST /api/v1/projects/{novelId}/storylines/generate-ai`
  3. 生成完成后自动刷新数据并渲染拓扑图
- **验收标准**：无故事线数据时可通过按钮触发 AI 生成，生成后拓扑图正常渲染
- **依赖**：无

### Task 4: 活态三层图谱增加频次筛选

- **目标**：减少图谱节点数量，只显示重要实体
- **范围**：`src/api/services/knowledge_graph_service.py`, `src/api/routes/knowledge_graph.py`, `frontend/src/views/RelationGraph.vue`
- **修改内容**：
  1. 后端 `get_three_layer_graph()` 增加 `min_frequency` 参数
  2. 统计每个实体在三元组中出现的次数（作为 subject 或 object）
  3. 过滤掉出现次数 < min_frequency 的实体及其关联边
  4. 默认值：character_graph min_frequency=3, plot_graph min_frequency=2, foreshadowing_graph=1（不过滤）
  5. 前端增加"显示全部/只显示主要"切换按钮
  6. API 路由增加 `min_frequency` query 参数
- **验收标准**：默认图谱只显示高频实体，切换后可显示全部
- **依赖**：无

### Task 5: 前端章节 404 友好提示

- **目标**：章节不存在时给出有意义的提示而非空白
- **范围**：`frontend/src/views/ChapterEdit.vue`
- **修改内容**：
  1. 当 `chapter` 为 null 时，显示"该章节可能正在重新生成中"提示
  2. 增加"刷新"按钮重新加载
  3. 增加"返回章节列表"链接
- **验收标准**：章节 404 时用户看到友好提示和操作选项
- **依赖**：无

---

## 任务依赖关系

所有任务相互独立，可并行执行。

## 实施顺序建议

T1 → T2 → T4 → T3 → T5

优先修复 T1（volume_number）和 T2（404），这两个直接影响用户核心体验。
