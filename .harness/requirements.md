# 需求文档：CHANGE-040 修复章节分卷与图谱筛选

> 版本：v1.0 · 日期：2026-05-22

---

## 需求概述

修复小说重新生成后的三个核心问题：章节未按卷分组显示、章节详情页404、知识图谱数据过载与故事框架拓扑无法渲染。

## 背景与动机

用户在对已有小说执行"重新生成"操作后，发现：
1. 章节列表全部显示为"未分卷章节"，丢失了卷归属关系
2. 点击章节链接后显示"章节不存在"
3. 知识图谱页面的"故事框架拓扑"Tab 无法生成可视化，"活态三层图谱"节点数量过多影响阅读

## 功能范围

### Bug 1: 章节重新生成后未分配 volume_number

**根因**：
- `generate_chapters_background()` 中的 `_find_volume_number()` 通过遍历 volumes 的 outline JSON 中的 chapters 数组匹配
- 当 outline 为空或 chapters 数组不包含目标章节号时返回 None
- 同时 `_persist_to_novel()` 中 `ch.get("volume_number")` 依赖 LangGraph 结果，如果 pipeline 未传递该字段也为 None

**修复方案**：在章节生成完成后自动调用 `fix_volume_numbers()` 补充 volume_number；改进 `_find_volume_number()` 增加 chapter_start/chapter_end 范围匹配 fallback

### Bug 2: 章节点击后显示不存在

**根因**：
- 重新生成时先 DELETE 再 INSERT，如果生成过程中某些章节失败（超时），则这些章节号被删除但未重新创建
- 前端 NovelDetail 的 chapters 列表仍显示旧数据（来自上次 fetchAll），点击后 API 返回 404

**修复方案**：
- 后端：生成失败时恢复旧章节数据（或不删除旧数据直到新数据生成成功）
- 前端：章节 404 时给出友好提示和刷新按钮

### Bug 3: 知识图谱问题

**3a. 故事框架拓扑无法生成**：
- `RelationGraph.vue` 的 `hasData` 检查 storylines/character_arcs/scenes 是否有数据
- 重新生成后这些数据可能为空（仅全功能生成的 Stage 10-12 才产生）
- **修复**：无数据时提供"一键生成故事线"按钮

**3b. 活态三层图谱节点过多**：
- `get_three_layer_graph()` 返回所有实体和三元组，无过滤
- **修复**：后端增加频次筛选（统计实体在三元组中出现次数），前端增加筛选控件

## 技术方案

### 涉及模块
- `src/api/services/novel_generator.py`: 修复 volume_number 分配 + 章节生成容错
- `src/api/services/knowledge_graph_service.py`: 三层图谱频次筛选
- `src/api/routes/knowledge_graph.py`: API 增加 min_frequency 参数
- `frontend/src/views/RelationGraph.vue`: 故事框架生成按钮 + 图谱筛选控件
- `frontend/src/views/ChapterEdit.vue`: 章节 404 友好提示

### 技术约束
- Python 3.11 + FastAPI + SQLAlchemy async
- Vue 3 + D3.js
- 不引入新依赖

## 验收标准
- [ ] 重新生成章节后，章节列表按卷分组显示
- [ ] 重新生成后的章节可以正常点击打开
- [ ] 故事框架拓扑 Tab 无数据时提供生成入口
- [ ] 活态三层图谱默认只显示高频实体，提供"显示全部"切换
- [ ] 图谱节点数量可控，不影响页面性能
