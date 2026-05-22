# 编码报告：CHANGE-040 修复章节分卷与图谱筛选

> 日期：2026-05-22

## 变更概览

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/api/services/novel_generator.py` | 修改 | T1: volume_number fallback + T2: 按章节替换策略 |
| `src/api/services/knowledge_graph_service.py` | 修改 | T4a: 频次筛选逻辑 |
| `src/api/routes/knowledge_graph.py` | 修改 | T4a: min_frequency 参数 |
| `frontend/src/views/RelationGraph.vue` | 修改 | T3: 生成故事线按钮 + T4b: 显示全部切换 |
| `frontend/src/views/ChapterEdit.vue` | 修改 | T5: 404 友好提示 |

## 各任务实现详情

### Task 1: 修复 volume_number 缺失

- `_find_volume_number()` 增加 fallback：先精确匹配 outline chapters 数组，失败后通过 volume 的 `chapter_start`/`chapter_end` 范围匹配
- 在 `generate_chapters_background()` 和 `_persist_to_novel()` 章节写入完成后调用 `novel_manager.fix_volume_numbers(novel_id)` 补充遗漏

### Task 2: 修复章节 404

- 将原来的"批量 DELETE 整个范围 → INSERT 所有章节"改为"逐章 DELETE+INSERT 仅成功章节"
- 过滤条件：`ch.get("content") and ch.get("word_count", 0) > 0`
- 失败章节的旧数据保留不动

### Task 3: 故事框架拓扑生成入口

- 空状态区域增加"一键生成故事线"按钮
- 调用 `POST /api/v1/projects/{novelId}/storylines/generate-ai`
- 加载状态 + 错误提示 + 成功后自动刷新

### Task 4: 三层图谱频次筛选

- 后端：统计每个实体在三元组中作为 subject/object 出现的次数
- `should_include()` 函数：foreshadowing 类型不过滤，其余按 min_frequency 阈值过滤
- API 路由增加 `min_frequency: int = Query(default=2, ge=1)` 参数
- 前端：增加"显示全部/只显示主要"切换按钮，切换时传递 min_frequency=1 或 2

### Task 5: 章节 404 友好提示

- 替换原来的纯文字"章节不存在"为带图标的卡片
- 包含说明文字、"刷新重试"按钮、"返回章节列表"链接

## 统计

- 修改文件数：5
- 新增行数：约 100 行
- 删除行数：约 10 行
- 未引入新依赖
