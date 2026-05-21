# 需求文档：CHANGE-039 章节版本化评审系统 + UI Apple 风格重构

> 版本：v1.0 · 日期：2026-05-21

---

## 需求概述

将 NovelDetail 章节 Tab 的 UI 改为 Apple 风格（简洁、留白、高级感），增加章节删除功能，并构建完整的"章节版本化评审与回滚系统"，使每次生成、评分、修改、确认都可追踪、可比较、可恢复。

## 背景与动机

1. 当前 UI 视觉偏暗色游戏风，用户希望改为苹果式简洁高级风格
2. 章节列表中存在"章节不存在"的空记录（word_count=0），用户无法删除
3. 已有 `ChapterVersion` 模型和基础版本管理 API（CHANGE-037），但缺少：
   - 自动版本创建（生成时自动保存初稿版本）
   - 版本元数据（质量评分、模型信息、提示词摘要、diff）
   - 前端版本对比与回滚 UI
4. 章节重复显示问题（卷内 + 未分卷同时出现）——已在 CHANGE-038 T6 修复新生成逻辑，但历史数据需要修补

## 功能范围

### A. UI 苹果风格重构（章节 Tab + VolumeList）
- 去除深色游戏风，改为浅色/中性色调、大留白、圆角卡片
- VolumeList 组件：简洁卡片式，章节列表用细线分隔而非独立卡片
- 章节项：显示标题、字数、状态标签、版本数、删除按钮

### B. 章节删除功能
- 章节列表每项增加删除按钮（带确认弹窗）
- 调用已有 `DELETE /api/v1/projects/{novel_id}/chapters/{chapter_number}` API
- 删除后刷新列表

### C. 章节版本化评审系统（核心）
- 扩展 `ChapterVersion` 模型：增加 `quality_score`、`model_name`、`prompt_summary`、`diff_from_previous`、`kg_conflicts`、`user_notes`、`is_active` 字段
- 生成章节时自动创建版本（source="generation"）
- AI 重写时自动创建版本（source="ai_rewrite"，已有）
- 用户手动保存时创建版本（source="manual"，已有）
- 回滚时创建版本（source="rollback"，已有）
- 前端版本历史面板：时间线展示、版本对比（diff 高亮）、一键回滚、设为正式上下文

### D. 历史数据修补
- 提供一次性 API 为已有章节补充 volume_number

## 技术方案

### 涉及模块
- `src/api/models/db_models.py`: 扩展 ChapterVersion 字段
- `src/api/services/novel_manager.py`: 版本创建增强
- `src/api/services/novel_generator.py`: 生成时自动创建版本
- `src/api/routes/projects.py`: 版本 API 增强
- `frontend/src/views/NovelDetail.vue`: UI 重构
- `frontend/src/components/VolumeList.vue`: Apple 风格重写
- `frontend/src/views/ChapterEdit.vue`: 版本面板增强
- `alembic/versions/`: 新迁移文件

### 技术约束
- 保持与现有 ChapterVersion 表兼容（ALTER TABLE 增加列）
- CheckConstraint 的 source 枚举需扩展为包含 "generation"
- 前端保持 Vue 3 + Tailwind CSS，不引入新依赖

## 影响范围
- 影响的现有功能：章节生成流程（需在生成后自动创建版本）、ChapterEdit 页面
- 需要修改的文件：约 8-10 个
- 潜在风险：数据库迁移需要处理已有数据的 source 约束变更

## 验收标准
- [ ] 章节 Tab UI 为 Apple 简洁风格（浅色调、大留白、圆角）
- [ ] 章节列表可删除空章节，删除后列表刷新
- [ ] 生成章节后自动创建版本记录（source="generation"）
- [ ] ChapterEdit 页面可查看版本历史时间线
- [ ] 可对比任意两个版本的 diff
- [ ] 可回滚到任意历史版本
- [ ] 历史章节的 volume_number 被正确补充

## 1. 问题1：为什么"生成本卷章节"会超时（300s）

### 1.1 代码路径

用户点击"生成本卷章节"/"生成本卷"按钮：

- **OutlineEditor.vue** `generateVolumeContent(volNum)` → `POST /api/v1/projects/{novel_id}/generate-volume`
- **VolumeList.vue** `$emit('generate-volume')` → `NovelDetail.vue` `handleGenerateVolume` → 同一端点

后端：`src/api/routes/projects.py:312` `generate_volume` → `generate_volume_background`（`src/api/services/novel_generator.py:497`）

### 1.2 超时触发机制

`generate_volume_background` 对每章调用 `generate_single_chapter`（`src/core/llm/chapter_generator.py:16`），该函数用 `asyncio.wait_for(..., timeout=300)` 包裹内部逻辑（第 33-46 行）。

**300s 超时的真正原因是双重 LLM 调用**：

`_generate_single_chapter_inner` 对每章做**两次** LLM 调用：
- 第一次（第 136 行）：`chapter_plan = await client.generate(planning_prompt, max_tokens=3000)` — 章节规划
- 第二次（第 168 行）：`content = await client.generate(prompt, max_tokens=8000)` — 正文生成

每次 LLM 调用生成大量 tokens 时，实际响应时间可达 100-200s。两次合计极易超过 300s，触发 `asyncio.TimeoutError`，返回错误信息 `[章节生成失败：生成超时（300s），请检查 API Key 配置后重试]`，word_count=0。

### 1.3 关键配置冲突

| 参数 | 值 | 位置 |
|------|-----|------|
| `CHAPTER_TIMEOUT_SECONDS` | 300 | `chapter_generator.py:13` |
| `DEEPSEEK_TIMEOUT` | 120 | `config.py:17` |
| `DEEPSEEK_MAX_TOKENS` | 2000 | `config.py:16` |

`DEEPSEEK_MAX_TOKENS=2000` 是全局默认值，但 `generate_single_chapter` 调用时传入 `max_tokens=8000`（第 168 行），覆盖默认值。生成 8000 tokens 的中文正文在 DeepSeek 上可能需要 150-250s，加上规划阶段的 3000 tokens，总时间极易超过 300s。

### 1.4 根因总结

1. **主因**：每章两次 LLM 调用（规划 3000 tokens + 正文 8000 tokens），总耗时超过 300s 的 `asyncio.wait_for` 限制
2. **次因**：`CHAPTER_TIMEOUT_SECONDS=300` 对于双阶段生成来说太短
3. **API Key 无关**：错误信息"请检查 API Key 配置"具有误导性，实际是超时，不是认证失败

### 1.5 涉及文件和行号

- `src/core/llm/chapter_generator.py:13`：`CHAPTER_TIMEOUT_SECONDS = 300`
- `src/core/llm/chapter_generator.py:33-46`：`asyncio.wait_for` 超时包裹
- `src/core/llm/chapter_generator.py:136`：第一次 LLM 调用（规划，max_tokens=3000）
- `src/core/llm/chapter_generator.py:168`：第二次 LLM 调用（正文，max_tokens=8000）
- `src/core/config.py:17`：`DEEPSEEK_TIMEOUT = 120`

### 1.6 修复方案

**方案A（必须）：提高超时时间**
将 `CHAPTER_TIMEOUT_SECONDS` 从 300 提升到 600（每章两次调用各留 300s 余量）。

**方案B（必须）：修正错误信息**
超时时的错误信息改为"生成超时，可能是模型响应较慢，请稍后重试"，去掉误导性的"请检查 API Key"。

---

## 2. 问题2：重新走生成流程会不会覆盖已有设定

### 2.1 `generate_volume_background` 不覆盖设定

`generate_volume_background`（`novel_generator.py:497`）**不调用** `_persist_to_novel`，只做：
1. 读取已有世界观、人物、故事线（只读，不写）
2. 生成章节内容
3. 将章节写入 `Chapter` 表（INSERT，不删除已有章节）
4. 更新卷状态为 `completed`

**结论：`generate_volume_background` 不会覆盖世界观和人物设定。**

### 2.2 `_persist_to_novel` 的覆盖行为

`_persist_to_novel`（`novel_generator.py:808`）只在以下两个流程中被调用：
- `generate_novel_background`（第 111 行）— "分步生成"按钮
- `generate_novel_full_background`（第 293 行）— "一键全功能生成"按钮

`_persist_to_novel` 的行为：

| 数据类型 | 操作 | 是否覆盖已有数据 |
|---------|------|----------------|
| 世界观 | `upsert_world_setting`（`novel_manager.py:157`）| **会覆盖**：如果已有世界观记录，直接 `setattr` 更新所有字段 |
| 人物 | `create_character`（`novel_manager.py:239`）| **会追加**：每次都 INSERT 新记录，不检查同名人物是否已存在，导致重复 |
| 卷 | `create_volume` | **会追加**：不检查卷号是否已存在 |
| 章节 | `Chapter` INSERT | **会追加**：不删除已有章节，可能产生重复章节 |

### 2.3 风险场景

用户已有世界观和人物设定，点击"分步生成"或"一键全功能生成"：
1. 世界观会被 LangGraph 重新生成的内容**完全覆盖**
2. 人物会被**重复插入**（同名人物出现多条记录）
3. 章节会被**重复插入**（同章节号出现多条记录）

### 2.4 保护机制（现有）

`_build_initial_state`（`novel_generator.py:35`）会将已有世界观和人物注入 LangGraph 初始状态，理论上 LangGraph 会基于已有设定生成，但 `_persist_to_novel` 仍然无条件写入结果，不做去重。

### 2.5 涉及文件和行号

- `src/api/services/novel_generator.py:808-886`：`_persist_to_novel`
- `src/api/services/novel_manager.py:157-171`：`upsert_world_setting`（覆盖逻辑）
- `src/api/services/novel_manager.py:239-245`：`create_character`（无去重）
- `src/api/services/novel_generator.py:35-80`：`_build_initial_state`（注入已有设定）

### 2.6 修复方案

1. **人物去重**：`_persist_to_novel` 中写人物前先查询同名人物是否存在，存在则 update，不存在才 insert
2. **章节去重**：写章节前先删除同章节号的旧记录，或改用 upsert
3. **世界观保护**（可选）：如果已有世界观且内容非空，跳过覆盖，或仅更新空字段

---

## 3. 问题3：NovelDetail 页面功能全面检查

### 3.1 卷纲展示

**位置**：`NovelDetail.vue:158-194`，`activeTab === 'outlines'`

**数据来源**：`GET /api/v1/projects/{novel_id}/outlines` → `outline_service.get_outline_tree`

**展示逻辑**：显示 `outlineTree.master`（总纲）和 `outlineTree.volumes`（卷纲列表）

**问题**：`outlineTree` 数据来自 `outlines` 表（三级大纲体系），而 `volumes` 数据来自 `volumes` 表。两套数据可能不同步。如果用户通过"生成本卷章节"生成了内容，但没有通过大纲编辑器生成卷纲，`outlineTree.volumes` 可能为空，但 `volumes` 列表有数据。

**结论**：卷纲展示功能本身正常，但依赖大纲编辑器的数据，与章节生成流程的数据源不同。

### 3.2 "生成章节大纲"按钮

**位置**：`OutlineEditor.vue:53-55`，按钮文字"生成章纲"

**API 调用**：`POST /api/v1/projects/{novel_id}/outlines/generate-chapters/{volume_number}`

**后端**：`src/api/routes/outlines.py:80-87` → `outline_service.generate_chapter_outlines`

**说明**：该按钮在 `OutlineEditor.vue` 中，不在 `NovelDetail.vue` 中。`NovelDetail.vue` 的"大纲"tab 只有一个跳转到大纲编辑器的链接，没有直接的"生成章节大纲"按钮。功能本身正常。

### 3.3 "生成本卷章节"按钮

**两个入口**：

**入口1**：`OutlineEditor.vue:56-58`
- 条件：`v-if="chaptersByVolume[vol.volume_number]"` — 只有当该卷已有章节大纲时才显示
- 调用：`POST /api/v1/projects/{novel_id}/generate-volume`

**入口2**：`VolumeList.vue:12-18`（在 `NovelDetail.vue` 的章节 tab 中）
- 条件：`v-if="vol.status !== 'generating'"` — 只要卷不在生成中就显示
- 调用：`POST /api/v1/projects/{novel_id}/generate-volume`

**问题**：
- `VolumeList.vue` 的按钮没有检查卷是否有章节大纲，可能在没有大纲的情况下触发生成
- `generate_volume_background` 有 fallback 逻辑（第 510-528 行），会尝试从 `outlines` 表获取章节数据，但如果两个表都没有数据，会抛出 `ValueError: Volume {volume_number} has no outline`，导致任务失败

### 3.4 章节列表展示

**位置**：`NovelDetail.vue:287-336`，`activeTab === 'chapters'`

**数据来源**：`volumes`（`GET /volumes`）+ `chapters`（`GET /chapters`）

**问题**：`generate_chapters_background`（`novel_generator.py:780`）生成的章节没有设置 `volume_number`，会出现在"未分卷"列表中，而不是归属到对应卷。

### 3.5 前端 API 调用检查

| 功能 | 前端调用 | 后端端点 | 状态 |
|------|---------|---------|------|
| 加载小说详情 | `GET /api/v1/projects/{id}` | `projects.py:117` | 正常 |
| 加载卷列表 | `GET /api/v1/projects/{id}/volumes` | `projects.py:271` | 正常 |
| 加载章节列表 | `GET /api/v1/projects/{id}/chapters` | `projects.py:507` | 正常 |
| 加载大纲树 | `GET /api/v1/projects/{id}/outlines` | `outlines.py:40` | 正常 |
| 加载故事线 | `GET /api/v1/projects/{id}/relations` | **需确认路由是否存在** | 待查 |
| 生成本卷章节 | `POST /api/v1/projects/{id}/generate-volume` | `projects.py:312` | 正常，但有超时问题 |
| 按范围生成章节 | `POST /api/v1/projects/{id}/generate-chapters` | `projects.py:350` | 正常 |

**潜在问题**：`NovelDetail.vue:534` 调用 `GET /api/v1/projects/{id}/relations`，需要确认该路由是否存在。如果不存在，`slRes.ok` 为 false，`storylinesData` 保持 null，故事线 tab 显示空状态，不会报错但功能缺失。

---

## 4. 总结

| 问题 | 根因 | 严重程度 |
|------|------|---------|
| 章节生成超时 | 双阶段 LLM 调用（规划+正文）总耗时超过 300s | 高 |
| 错误信息误导 | 超时错误提示"请检查 API Key"，实际与 Key 无关 | 中 |
| 人物重复插入 | `_persist_to_novel` 无去重，每次全功能生成都追加 | 中 |
| 世界观覆盖 | `upsert_world_setting` 无条件覆盖已有内容 | 中 |
| 章节重复插入 | `_persist_to_novel` 章节无去重 | 中 |
| relations 路由 | 前端调用 `/relations` 端点，需确认后端路由存在 | 低 |
