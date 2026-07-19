# CHANGE-038 归档记录

- 原名称：章节生成修复
- 状态：archived-completed
- 时间范围：2026-05-21
- 原路径：`.harness/changes/CHANGE-038-章节生成修复`
- 归档路径：`archive/changes/CHANGE-038-章节生成修复`
- 关联提交：
  - e52f87f 2026-05-21 fix: chapter generation timeout, dedup, and volume_number (CHANGE-038)

## 目标

该历史变更主题为“章节生成修复”；原始资料未单独记录目标章节。

## 主要设计决定

> 日期：2026-05-21
生产环境发现多个问题：
1. 章节生成因双级联 LLM 调用（规划+正文）总耗时超过 300s 超时限制
2. 超时错误信息误导用户检查 API Key
3. 重复执行生成流程导致人物和章节重复插入，引发 500 错误
4. `generate_chapters_background` 生成的章节缺少 volume_number，显示为"未分卷"
- `src/core/llm/chapter_generator.py`: `CHAPTER_TIMEOUT_SECONDS` 300→600
- 超时提示从"请检查 API Key 配置后重试"改为"可能是模型响应较慢，请稍后重试"
- `src/api/services/novel_manager.py`: 新增 `get_character_by_name(novel_id, name)` 方法
- `src/api/services/novel_generator.py`: `_persist_to_novel` 人物写入改为先查同名→存在则 update，不存在则 insert
- `src/api/services/novel_generator.py`: `_persist_to_novel` 章节写入前先 DELETE 同 chapter_number 记录
- `src/api/services/novel_manager.py`: `get_chapter` 改为 `order_by(id.desc()).limit(1)` 防止 MultipleResultsFound 500

## 涉及模块

- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `src/core/llm/chapter_generator.py`
- `tests/unit/test_change038_dedup_and_timeout.py`

## 实施结果

- [x] T1 — CHAPTER_TIMEOUT_SECONDS 300→600
- [x] T2 — 超时错误信息不再提及 API Key
- [x] T3 — 人物 upsert（同名更新，不重复插入）
- [x] T4 — 章节先删后插（同 chapter_number 不重复）
- [x] T5 — `/relations` 路由已确认存在且返回格式正确
- [x] T6 — `generate_chapters_background` 写入章节时设置 volume_number

## 测试与验证

```
tests/unit/test_change038_dedup_and_timeout.py: 3 passed
全量 unit 测试（不含 DB 依赖）: 57 passed, 0 failed
```

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `04-编码报告-v1.md`
- `summary.md`
