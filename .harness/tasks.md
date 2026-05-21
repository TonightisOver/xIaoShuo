# 任务清单：CHANGE-039 章节版本化评审 + UI 重构

> 版本：v1.0 · 日期：2026-05-21
> 按依赖顺序排列

---

## T1 — 数据库迁移：扩展 ChapterVersion 模型

**目标**：为 ChapterVersion 增加版本元数据字段，扩展 source 枚举
**范围**：`src/api/models/db_models.py`, `alembic/versions/`
**修改内容**：
- 模型新增字段：`quality_score` (Float, nullable), `model_name` (String(50), nullable), `prompt_summary` (Text, nullable), `diff_from_previous` (Text, nullable), `kg_conflicts` (JSON, nullable), `user_notes` (Text, nullable), `is_active` (Boolean, default=False)
- 修改 CheckConstraint：source IN ('manual', 'ai_rewrite', 'rollback', 'generation')
- 创建 Alembic 迁移文件
**验收标准**：迁移可执行，模型字段可正常读写
**依赖**：无

---

## T2 — 后端：生成章节时自动创建版本

**目标**：章节生成完成后自动保存为版本记录
**范围**：`src/api/services/novel_generator.py`, `src/api/services/novel_manager.py`
**修改内容**：
- 在 `_persist_to_novel` 和 `generate_chapters_background` 的章节写入逻辑后，调用 `create_chapter_version` 创建 source="generation" 的版本
- `create_chapter_version` 方法增加对新字段的支持（model_name, is_active 等）
**验收标准**：生成章节后 chapter_versions 表有对应记录
**依赖**：T1

---

## T3 — 后端：版本 API 增强

**目标**：增加版本对比、设为活跃版本的 API
**范围**：`src/api/routes/projects.py`, `src/api/services/novel_manager.py`
**修改内容**：
- `GET /{novel_id}/chapters/{chapter_number}/versions/{version_number}` — 获取单个版本详情（含 diff）
- `POST /{novel_id}/chapters/{chapter_number}/versions/{version_number}/activate` — 设为活跃版本（更新章节正文为该版本内容）
- `GET /{novel_id}/chapters/{chapter_number}/versions/compare?v1=X&v2=Y` — 对比两个版本
**验收标准**：API 可正常调用并返回正确数据
**依赖**：T1

---

## T4 — 后端：历史数据修补 API

**目标**：为已有章节补充 volume_number
**范围**：`src/api/routes/projects.py`, `src/api/services/novel_manager.py`
**修改内容**：
- `POST /{novel_id}/fix-volume-numbers` — 根据卷的 chapter_start/chapter_end 范围为章节设置 volume_number
**验收标准**：调用后无 volume_number 的章节被正确分配到卷
**依赖**：无

---

## T5 — 前端：NovelDetail 章节 Tab Apple 风格重构

**目标**：章节列表 UI 改为苹果简洁风格
**范围**：`frontend/src/views/NovelDetail.vue`, `frontend/src/components/VolumeList.vue`
**修改内容**：
- VolumeList：白色/浅灰背景卡片、细线分隔章节、去除深色背景
- 章节项：左侧标题+字数，右侧操作区（版本数 badge、删除按钮）
- 整体色调：白底、灰色文字、蓝色/紫色点缀、大圆角、阴影轻柔
- 删除按钮：点击弹出确认 Modal，确认后调用 DELETE API
**验收标准**：视觉简洁高级，删除功能可用
**依赖**：无

---

## T6 — 前端：ChapterEdit 版本历史面板增强

**目标**：在章节编辑页展示完整版本时间线和对比功能
**范围**：`frontend/src/views/ChapterEdit.vue`
**修改内容**：
- 版本时间线：纵向时间轴，每个版本显示来源标签、时间、字数变化、质量评分
- 版本对比：选择两个版本后高亮显示 diff（增/删/改）
- 回滚按钮：一键回滚到选中版本
- "设为正式上下文"按钮：将该版本标记为后续章节生成的参考
**验收标准**：可查看版本历史、对比 diff、执行回滚
**依赖**：T3

---

## 任务依赖关系

```
T1 (DB迁移) ← T2 (自动创建版本) 
T1 (DB迁移) ← T3 (版本API增强) ← T6 (前端版本面板)
T4 (数据修补) — 独立
T5 (UI重构) — 独立
```

## 实施顺序建议

T1 → T4 → T5 → T2 → T3 → T6

---

## T1 — 修复章节生成超时：提高 CHAPTER_TIMEOUT_SECONDS

**优先级**：P0（阻塞用户核心功能）

**文件**：`src/core/llm/chapter_generator.py`

**修改内容**：
- 第 13 行：将 `CHAPTER_TIMEOUT_SECONDS = 300` 改为 `CHAPTER_TIMEOUT_SECONDS = 600`

**原因**：每章需要两次 LLM 调用（规划 max_tokens=3000 + 正文 max_tokens=8000），总耗时可达 300-500s，超过原有 300s 限制。

**验收标准**：
- 单章生成不再因超时失败（在正常网络条件下）
- `CHAPTER_TIMEOUT_SECONDS` 值为 600

---

## T2 — 修复超时错误信息误导性文字

**优先级**：P1

**文件**：`src/core/llm/chapter_generator.py`

**修改内容**：
- 第 53 行：将错误信息从
  `f"[章节生成失败：生成超时（{CHAPTER_TIMEOUT_SECONDS}s），请检查 API Key 配置后重试]"`
  改为
  `f"[章节生成失败：生成超时（{CHAPTER_TIMEOUT_SECONDS}s），可能是模型响应较慢，请稍后重试]"`

**原因**：超时与 API Key 无关，误导用户排查方向。

**验收标准**：
- 超时时显示的错误信息不再包含"请检查 API Key"字样

---

## T3 — 修复 `_persist_to_novel` 人物重复插入

**优先级**：P1

**文件**：`src/api/services/novel_generator.py`

**修改内容**：
在 `_persist_to_novel` 函数（第 808 行）的人物写入逻辑（第 828-839 行）中，写入前先查询同名人物是否已存在：
- 如果已存在同名人物（`name` 相同），则 update 已有记录
- 如果不存在，才 insert 新记录

伪代码：
```python
for char in characters:
    if isinstance(char, dict) and char.get("name"):
        existing = await manager.get_character_by_name(novel_id, char["name"])
        if existing:
            await manager.update_character(novel_id, existing["id"], ...)
        else:
            await manager.create_character(novel_id, ...)
```

需要在 `NovelManager`（`src/api/services/novel_manager.py`）中新增 `get_character_by_name` 方法。

**验收标准**：
- 重复执行"分步生成"或"一键全功能生成"后，同名人物在数据库中只有一条记录
- 已有人物的字段被更新，不产生重复

---

## T4 — 修复 `_persist_to_novel` 章节重复插入

**优先级**：P1

**文件**：`src/api/services/novel_generator.py`

**修改内容**：
在 `_persist_to_novel` 函数（第 858-878 行）的章节写入逻辑中，写入前先删除同章节号的已有记录：

```python
async with get_db_session() as session:
    for ch in chapters:
        if isinstance(ch, dict):
            # 先删除已有同章节号记录
            await session.execute(
                delete(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == ch.get("chapter", 0),
                )
            )
            # 再插入新记录
            chapter = Chapter(...)
            session.add(chapter)
```

**验收标准**：
- 重复执行生成后，同章节号在数据库中只有一条记录
- 章节内容为最新生成的内容

---

## T5 — 确认 `/relations` 路由是否存在

**优先级**：P2

**文件**：`src/api/routes/` 目录下所有路由文件

**任务**：
1. 搜索是否存在 `GET /api/v1/projects/{novel_id}/relations` 端点
2. 如果不存在，在 `NovelDetail.vue:534` 中将 `fetch('/api/v1/projects/${novelId}/relations')` 改为正确的故事线 API 端点（如 `/api/v1/projects/${novelId}/storylines` 或类似端点）
3. 如果存在，确认返回数据格式与前端 `storylinesData` 的使用方式匹配

**验收标准**：
- `NovelDetail.vue` 的故事线 tab 能正确显示数据，或明确标注"暂无数据"而不是因 API 404 静默失败

---

## T6 — 修复 `generate_chapters_background` 章节缺少 volume_number

**优先级**：P2

**文件**：`src/api/services/novel_generator.py`

**修改内容**：
在 `generate_chapters_background`（第 657 行）的章节写入逻辑（第 773-782 行）中，为每章设置正确的 `volume_number`。

需要根据 `chapter_number` 查找对应的卷号：
```python
# 根据章节号找到对应卷
def find_volume_number(chapter_num, volumes):
    for vol in volumes:
        outline = vol.get("outline") or {}
        for ch in outline.get("chapters", []):
            if ch.get("chapter") == chapter_num:
                return vol.get("volume_number")
    return None
```

**验收标准**：
- 通过"按范围重新生成章节"生成的章节，在章节列表中归属到正确的卷，不出现在"未分卷"列表中

---

## 任务依赖关系

```
T1 (超时修复) — 独立，立即可执行
T2 (错误信息) — 独立，立即可执行
T3 (人物去重) — 需要先在 novel_manager.py 新增 get_character_by_name
T4 (章节去重) — 独立，立即可执行
T5 (relations路由) — 独立，需要先搜索路由
T6 (volume_number) — 独立，立即可执行
```

## 实现顺序建议

T1 → T2 → T4 → T3 → T5 → T6

优先修复 T1（超时）和 T2（错误信息），这两个直接影响用户体验且改动最小。
