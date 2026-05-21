# Gate 1 — 需求评审报告 (PASSED)

> CHANGE-039 章节版本化评审系统 + UI Apple 风格重构
> 日期：2026-05-21 · 评审结论：**APPROVED**

---

## 需求概述

将 NovelDetail 章节 Tab 的 UI 改为 Apple 风格（简洁、留白、高级感），增加章节删除功能，并构建完整的"章节版本化评审与回滚系统"。

## 四大改动方向

| 模块 | 内容 | 优先级 |
|------|------|--------|
| A. UI 重构 | 章节 Tab + VolumeList 改为 Apple 简洁风格（白底、大留白、轻阴影） | P1 |
| B. 章节删除 | 列表增加删除按钮 + 确认弹窗（后端 DELETE API 已存在） | P0 |
| C. 版本化评审系统 | 扩展 ChapterVersion 模型 + 自动版本创建 + 版本对比/回滚 | P1 |
| D. 历史数据修补 | 为已有章节补充 volume_number（解决"未分卷"重复显示） | P2 |

## 任务拆解（6 Tasks）

### T1 — DB 迁移：扩展 ChapterVersion
- 新增字段：quality_score, model_name, prompt_summary, diff_from_previous, kg_conflicts, user_notes, is_active
- source 枚举扩展：加入 "generation"
- 创建 Alembic 迁移

### T2 — 生成时自动创建版本
- `_persist_to_novel` 章节写入后 → 自动 `create_chapter_version(source="generation")`
- `generate_chapters_background` 同理

### T3 — 版本 API 增强
- GET 版本详情（含 diff）
- POST 激活版本（设为正式上下文）
- GET 版本对比（v1 vs v2）

### T4 — 历史数据修补 API
- POST `/{novel_id}/fix-volume-numbers`
- 根据卷的 chapter_start/chapter_end 为章节设置 volume_number

### T5 — 前端 Apple 风格重构 + 删除功能
- VolumeList：白色卡片、细线分隔、轻阴影
- 章节项增加删除按钮 + 确认 Modal
- 整体色调：白底灰字、蓝紫点缀

### T6 — ChapterEdit 版本历史面板
- 纵向时间轴展示版本
- 版本对比 diff 高亮
- 一键回滚 + 设为正式上下文

## 依赖关系

```
T1 ← T2, T3 ← T6
T4, T5 独立可并行
```

## 风险评估

- DB 迁移需处理已有 CheckConstraint 的 source 枚举变更（DROP + ADD）
- 前端 UI 大改可能影响其他 Tab 的视觉一致性（需限定范围在章节 Tab）
- 版本自动创建会增加 DB 写入量（每章多一条 version 记录，可接受）

## 评审结论

**APPROVED** — 需求明确，任务粒度合理，技术方案与现有架构兼容，无阻塞问题。

---

## 评审依据

逐一核查了以下文件：

- `src/core/llm/chapter_generator.py` — CHAPTER_TIMEOUT_SECONDS 定义与超时错误信息
- `src/api/services/novel_generator.py` — `_persist_to_novel`、`generate_chapters_background`、`generate_volume_background`
- `src/api/services/novel_manager.py` — `create_character`、`upsert_world_setting`
- `src/api/models/db_models.py` — Chapter 唯一约束
- `src/api/routes/storylines.py` — `/relations` 路由
- `src/api/routes/projects.py` — `generate-volume`、`generate-chapters` 端点
- `frontend/src/components/VolumeList.vue` — "生成本卷章节"按钮逻辑
- `frontend/src/views/NovelDetail.vue` — `/relations` 调用方式

---

## 各任务核查结果

### T1 — CHAPTER_TIMEOUT_SECONDS 300→600

**现状**：`src/core/llm/chapter_generator.py` 第 13 行 `CHAPTER_TIMEOUT_SECONDS = 300`，尚未修改。

**根因验证**：两次 LLM 调用（planning max_tokens=3000 + content max_tokens=8000）在网络延迟或模型负载高时确实可能超过 300s。600s 是合理上限。

**结论**：MUST FIX — 需将 300 改为 600。

---

### T2 — 修正超时错误信息

**现状**：`chapter_generator.py` 第 53 行错误信息为：
```
f"[章节生成失败：生成超时（{CHAPTER_TIMEOUT_SECONDS}s），请检查 API Key 配置后重试]"
```
超时与 API Key 无关，提示用户"检查 API Key"会造成误导。

**结论**：MUST FIX — 错误信息应改为类似"生成超时，请稍后重试或缩短章节字数"。

---

### T3 — 人物写入去重（upsert）

**现状**：`_persist_to_novel`（第 829-839 行）对每个人物直接调用 `manager.create_character()`，无任何查重逻辑。`novel_manager.py` 中 `create_character` 也是直接 INSERT，无 upsert。`characters` 表无 `(novel_id, name)` 唯一约束，因此重复调用会产生重复人物记录。

**结论**：MUST FIX — 需在写入前按 name 查重，存在则 update，不存在则 insert（upsert 语义）。

---

### T4 — 章节写入去重（先删后插）

**现状**：`_persist_to_novel`（第 865-878 行）直接 `session.add(chapter)`，无删除旧记录逻辑。`chapters` 表有 `UniqueConstraint("novel_id", "chapter_number", name="uq_chapter_novel_number")`，重复调用会触发数据库唯一约束异常。

**结论**：MUST FIX — 需在批量插入前先 DELETE 同 novel_id 的旧章节记录（或使用 ON CONFLICT DO UPDATE）。

---

### T5 — 确认/修复 /relations 路由

**现状**：`src/api/routes/storylines.py` 第 149-152 行已存在：
```python
@router.get("/{novel_id}/relations")
async def get_relations(novel_id: str):
    service = get_storyline_service()
    return await service.get_relations(novel_id)
```
路由前缀为 `/api/v1/projects`，完整路径为 `/api/v1/projects/{novel_id}/relations`。

`NovelDetail.vue` 第 534 行调用 `fetch('/api/v1/projects/${novelId}/relations')`，路径完全匹配。

**结论**：路由已存在且路径正确，T5 无需修复，可从任务清单移除。

---

### T6 — generate_chapters_background 补充 volume_number

**现状**：`generate_chapters_background`（第 765-782 行）在持久化章节时构造 `Chapter` 对象，未设置 `volume_number` 字段：
```python
chapter = Chapter(
    novel_id=novel_id,
    chapter_number=ch["chapter"],
    title=ch["title"],
    content=ch["content"],
    word_count=ch["word_count"],
    status="regenerated",
)
```
`chapter_result` 来自 `generate_single_chapter`，其返回值也不包含 `volume_number`。对比 `generate_volume_background`（第 619-630 行）正确设置了 `volume_number=volume_number`。

**结论**：MUST FIX — `generate_chapters_background` 需要在写入时补充 `volume_number`，可通过 volumes 表按章节号范围反查对应卷号。

---

### 附加观察：VolumeList.vue 大纲检查缺失

**现状**：`VolumeList.vue` 第 12-18 行"生成本卷章节"按钮直接 emit `generate-volume` 事件，无大纲存在性检查。后端 `generate_volume` 端点已有 fallback 逻辑（先查 volumes 表，再查 outlines 表），若两者均无数据则返回 404。

**评估**：后端有保护，前端缺少大纲检查只影响用户体验（会收到 404 错误而非友好提示），不属于数据损坏类问题。计划中未将此列为 MUST FIX，维持原判，可作为 SHOULD FIX 在后续迭代处理。

---

## 汇总

| 任务 | 状态 | 严重性 |
|------|------|--------|
| T1 CHAPTER_TIMEOUT_SECONDS 300→600 | 未修复，代码确认需改 | MUST FIX |
| T2 修正超时错误信息 | 未修复，信息确认有误导 | MUST FIX |
| T3 人物写入去重 | 未修复，确认存在重复插入风险 | MUST FIX |
| T4 章节写入去重 | 未修复，确认会触发唯一约束异常 | MUST FIX |
| T5 /relations 路由 | 路由已存在，路径正确 | 无需修复 |
| T6 generate_chapters_background 补充 volume_number | 未修复，确认缺失 | MUST FIX |

---

## 结论

**REVISION_REQUIRED**

存在 5 项 MUST FIX（T1、T2、T3、T4、T6），需实施后方可进入 Gate 2。T5 已确认路由存在，可从任务清单移除。
