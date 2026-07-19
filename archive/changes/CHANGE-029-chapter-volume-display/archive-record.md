# CHANGE-029 归档记录

- 原名称：chapter-volume-display
- 状态：completed
- 时间范围：2026-05-19
- 原路径：`.harness/changes/CHANGE-029-chapter-volume-display`
- 归档路径：`archive/changes/CHANGE-029-chapter-volume-display`
- 关联提交：
  - 0637259 2026-05-19 feat: improve chapter display and api robustness

## 目标

补充 `volume_number` 字段的返回链路，修复前端卷内章节编号显示。

## 主要设计决定

## 1. 设计原则

- 最小改动：只修复两个 bug，不重构数据模型
- 向后兼容：历史数据（`volume_number = NULL`）继续正常显示
- 不改变 URL 路由结构（`/novels/:id/chapters/:num`）

---

## 2. 核心决策：`chapter_number` 语义统一为全局编号

**现状**：`chapter_number` 在 DB 中设计为全局唯一编号（跨卷连续），但 `generate_volume_background` 写入时可能使用卷内编号，导致语义混乱。

**决策**：统一 `chapter_number` 为**全局唯一编号**。路由 `:num` 传递全局编号，后端按全局编号查询。前端显示时，用卷内序号（`chapter_number - vol.chapter_start + 1`）展示给用户。

这样：
- 路由唯一性得到保证（不同卷的章节有不同 URL）
- 后端查询逻辑不变（已经是按 `chapter_number` 查）
- 前端显示"第N章"时用卷内序号，符合用户预期

---

## 3. 修改方案

### 修改 1：`novel_manager.py` — `list_chapters` 补充 `volume_number` 字段

**文件**：`src/api/services/novel_manager.py`
**位置**：第 244-248 行

**现状**：
```python
return [{"id": c.id, "chapter_number": c.chapter_number,
         "title": c.title, "content": c.content,
         "word_count": c.word_count, "status": c.status,
         "updated_at": c.updated_at}
        for c in result.scalars().all()]
```

**修改后**：
```python
return [{"id": c.id, "chapter_number": c.chapter_number,
         "volume_number": c.volume_number,
         "title": c.title, "content": c.content,
         "word_count": c.word_count, "status": c.status,
         "updated_at": c.updated_at}
        for c in result.scalars().all()]
```

**说明**：增加 `"volume_number": c.volume_number` 一行。这是问题 1 的根本修复，前端 `VolumeList.volumeChapters()` 的过滤逻辑依赖此字段。

---

### 修改 2：`novel_generator.py` — 全量生成时补充 `volume_number`

**文件**：`src/api/services/novel_generator.py`
**位置**：第 916-935 行（`persist_results` 函数中的 Chapters 写入段）

**现状**：
```python
chapters = result.get("chapters", [])
async with get_db_session() as session:
    for ch in chapters:
        if isinstance(ch, dict):
            chapter = Chapter(
                novel_id=novel_id,
                chapter_number=ch.get("chapter", 0),
                title=ch.get("title", ""),

## 涉及模块

- `frontend/src/components/VolumeList.vue`
- `frontend/src/views/ChapterEdit.vue`
- `frontend/src/views/NovelDetail.vue`
- `src/api/models/db_models.py`
- `src/api/models/responses.py`
- `src/api/routes/projects.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `tests/integration/test_change029_volume_number_api.py`
- `tests/unit/test_change029_volume_number.py`

## 实施结果

```
list_chapters() 不返回 volume_number
  → 前端 chapters 数组中所有章节的 volume_number 为 undefined
  → VolumeList.volumeChapters() 过滤结果为空 → 每卷显示"暂无章节"
  → unassignedChapters 包含全部章节 → 平铺显示，出现重复章节号
```

---

## 测试与验证

**11 passed, 0 failed** — 全部通过

```
tests/unit/test_change029_volume_number.py::TestListChaptersVolumeNumber::test_list_chapters_includes_volume_number_when_set PASSED
tests/unit/test_change029_volume_number.py::TestListChaptersVolumeNumber::test_list_chapters_volume_number_none_when_not_set PASSED
tests/unit/test_change029_volume_number.py::TestListChaptersVolumeNumber::test_list_chapters_returns_empty_list_when_no_chapters PASSED
tests/unit/test_change029_volume_number.py::TestListChaptersVolumeNumber::test_list_chapters_dict_contains_all_expected_keys PASSED
tests/unit/test_change029_volume_number.py::TestListChaptersVolumeNumber::test_list_chapters_mixed_volume_numbers PASSED
tests/unit/test_change029_volume_number.py::TestGetChapterVolumeNumber::test_get_chapter_includes_volume_number PASSED
tests/unit/test_change029_volume_number.py::TestGetChapterVolumeNumber::test_get_chapter_volume_number_none PASSED
tests/unit/test_change029_volume_number.py::TestGetChapterVolumeNumber::test_get_chapter_returns_none_when_not_found PASSED
tests/unit/test_change029_volume_number.py::TestGetChapterVolumeNumber::test_get_chapter_dict_contains_all_expected_keys PASSED
tests/unit/test_change029_volume_number.py::TestPersistToNovelVolumeNumber::test_persist_passes_volume_number_to_chapter PASSED
tests/unit/test_change029_volume_number.py::TestPersistToNovelVolumeNumber::test_persist_volume_number_none_when_missing_from_dict PASSED
```

---

## 遗留事项

1. **历史数据**：已生成的章节 `volume_number` 可能为 NULL（全量生成路径未写入）。修改 1 后这些章节会出现在"未分卷章节"区域，而不是卷内。这是正确的降级行为。

2. **`chapter_number` 语义**：如果 `generate_volume_background` 写入的是卷内编号（1、2、3...），则同一小说可能存在多条 `chapter_number = 1` 的记录，后端 `get_chapter` 的 `scalar_one_or_none()` 会抛出异常。需要在实现阶段验证实际数据，如有此情况需额外处理（如加 `volume_number` 联合查询条件）。

3. **`chapter_start` 字段**：`Volume` 表有 `chapter_start` 和 `chapter_end` 字段，但并非所有卷都有值（可能为 NULL）。`chapterIndexInVolume` 函数已处理降级逻辑。

## 原始文件清单

- `.gate1-approved`
- `.gate2-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`
