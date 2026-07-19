# CHANGE-042 归档记录

- 原名称：chapter-bug-and-loadtest
- 状态：archived-completed
- 时间范围：2026-05-23
- 原路径：`.harness/changes/CHANGE-042-chapter-bug-and-loadtest`
- 归档路径：`archive/changes/CHANGE-042-chapter-bug-and-loadtest`
- 关联提交：
  - 5799e10 2026-05-23 fix: resolve chapter content inaccessible bug and add Locust load tests (CHANGE-042)

## 目标

LOADTEST_HOST=http://staging.example.com locust -f loadtest/locustfile.py
```

### 使用前准备

1. 将 `loadtest/data/seed.json` 中的 `"replace-with-real-novel-id"` 替换为数据库中真实存在的 novel_id
2. 按需调整 `chapter_numbers` 列表

---

## 验证

- `novel_manager.py` 两处修改均为最小外科手术式变更，未触及其他逻辑
- `ChapterResponse` 模型（`src/api/models/responses.py` 第 135-145 行）包含 `novel_id: str` 必填字段，修复后序列化可正常通过
- 压测脚本所有 TaskSet 均继承自 `locust.TaskSet`，`locustfile.py` 中 User 类通过字典权重引用 TaskSet，符合 Locust 官方用法

## 主要设计决定

## Bug A 修复方案

### 根因确认

`ChapterResponse`（`src/api/models/responses.py` 第 135-145 行）要求 `novel_id: str` 为必填字段：

```python
class ChapterResponse(BaseModel):
    novel_id: str          # 必填，无默认值
    chapter_number: int
    ...
```

但 `NovelManager.get_chapter()`（`src/api/services/novel_manager.py` 第 319-323 行）返回的字典**不包含 `novel_id`**：

```python
return {"id": c.id, "chapter_number": c.chapter_number,
        "volume_number": c.volume_number,
        "title": c.title, "content": c.content,
        "word_count": c.word_count, "status": c.status,
        "updated_at": c.updated_at}
```

FastAPI 用 `ChapterResponse` 序列化时，`novel_id` 缺失，返回 422 Unprocessable Entity。前端 `load()` 函数判断 `!res.ok`，将 `chapter.value` 置为 `null`，触发"章节暂时无法访问"错误页。

章节列表页显示字数正常，是因为 `list_chapters` 不使用 `ChapterResponse` 模型，直接返回原始字典，不经过 Pydantic 验证。

### 修复方案

**方案一（推荐）：在 `get_chapter` 返回值中补充 `novel_id` 字段**

文件：`src/api/services/novel_manager.py`

修改位置：第 319-323 行

```python

## 涉及模块

- `frontend/src/views/ChapterEdit.vue`
- `loadtest/.gitignore`
- `loadtest/config.py`
- `loadtest/data/seed.json`
- `loadtest/locustfile.py`
- `loadtest/tasks/__init__.py`
- `loadtest/tasks/ai_rewrite.py`
- `loadtest/tasks/chapter_generate.py`
- `loadtest/tasks/chapter_list.py`
- `loadtest/tasks/chapter_read.py`
- `src/api/models/responses.py`
- `src/api/routes/projects.py`
- `src/api/services/novel_manager.py`
- `tests/unit/test_change029_volume_number.py`

## 实施结果

`frontend/src/views/ChapterEdit.vue` 第 3-24 行：
```html
<div v-if="!chapter" class="text-center py-20">
  <h3>章节暂时无法访问</h3>
  <p>该章节可能正在重新生成中，或生成过程中出现了异常。</p>
</div>
```
触发条件：`chapter` ref 为 `null`。`chapter` 在 `load()` 函数中赋值：
```js
// ChapterEdit.vue 第 635-644 行
async function load() {
  const res = await fetch(`/api/v1/projects/${novelId.value}/chapters/${chapterNum.value}`)

## 测试与验证

locust -f locustfile.py --host http://localhost:8000 \
  --users 50 --spawn-rate 5 --run-time 5m \
  --headless --csv reports/chapter_read
```

### 验收标准

| 接口 | P50 | P95 | 错误率 |
|------|-----|-----|--------|
| GET /chapters/{num} | < 100ms | < 500ms | < 1% |
| GET /chapters | < 200ms | < 800ms | < 1% |
| GET /projects/{id} | < 150ms | < 600ms | < 1% |
| POST /generate-chapters | < 2s（任务创建） | < 5s | < 2% |
| POST /rewrite | < 30s | < 60s | < 5% |

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `.gate2-approved`
- `01-需求分析.md`
- `02-实施方案.md`
- `03-编码报告.md`
- `04-验证报告.md`
