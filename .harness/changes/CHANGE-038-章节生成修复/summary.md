# CHANGE-038 章节生成修复与数据去重

> 日期：2026-05-21

## 问题背景

生产环境发现多个问题：
1. 章节生成因双级联 LLM 调用（规划+正文）总耗时超过 300s 超时限制
2. 超时错误信息误导用户检查 API Key
3. 重复执行生成流程导致人物和章节重复插入，引发 500 错误
4. `generate_chapters_background` 生成的章节缺少 volume_number，显示为"未分卷"

## 修改内容

### T1 — 超时阈值提升
- `src/core/llm/chapter_generator.py`: `CHAPTER_TIMEOUT_SECONDS` 300→600

### T2 — 错误信息修正
- 超时提示从"请检查 API Key 配置后重试"改为"可能是模型响应较慢，请稍后重试"

### T3 — 人物去重（upsert）
- `src/api/services/novel_manager.py`: 新增 `get_character_by_name(novel_id, name)` 方法
- `src/api/services/novel_generator.py`: `_persist_to_novel` 人物写入改为先查同名→存在则 update，不存在则 insert

### T4 — 章节去重（先删后插）
- `src/api/services/novel_generator.py`: `_persist_to_novel` 章节写入前先 DELETE 同 chapter_number 记录
- `src/api/services/novel_manager.py`: `get_chapter` 改为 `order_by(id.desc()).limit(1)` 防止 MultipleResultsFound 500

### T5 — `/relations` 路由确认
- 确认 `GET /api/v1/projects/{novel_id}/relations` 存在于 `storylines.py`，返回格式与前端匹配

### T6 — 章节卷号补全
- `src/api/services/novel_generator.py`: `generate_chapters_background` 写入章节时通过 outline 查找并设置 `volume_number`

## 测试

- 新增 `tests/unit/test_change038_dedup_and_timeout.py`（3 tests）
- 全量 unit 测试 57 passed, 0 failed
