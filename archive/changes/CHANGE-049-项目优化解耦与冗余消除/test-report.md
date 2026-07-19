# CHANGE-049 单元测试报告

## 测试概要

- 测试文件: `tests/unit/test_change049_refactoring.py`
- 执行时间: 2.10s
- 结果: **18 passed, 0 failed**
- 框架: pytest 9.0.3 + pytest-asyncio 1.3.0

## 覆盖模块

| 模块 | 测试数 | 状态 |
|------|--------|------|
| `src/core/context/novel_context.py` (NovelContextBuilder) | 5 | PASS |
| `src/core/quality/evaluator.py` (evaluate_chapter_quality) | 4 | PASS |
| `src/core/llm/helpers.py` (generate_and_parse_json) | 5 | PASS |
| `src/api/services/ai_generation_service.py` (AIGenerationService) | 4 | PASS |

## 测试用例明细

### NovelContextBuilder (5 tests)

1. `test_build_generation_context_happy_path` — 正常路径：novel + world + characters + storylines 全部存在
2. `test_build_generation_context_novel_not_found` — novel 不存在时返回默认值
3. `test_build_rewrite_context_happy_path` — 改写上下文正常构建
4. `test_build_rewrite_context_chapter_not_found` — chapter 不存在时字段为空
5. `test_build_blueprint_context_happy_path` — 蓝图上下文正常构建

### evaluate_chapter_quality (4 tests)

1. `test_evaluate_happy_path` — LLM 返回合法 JSON，解析为 QualityResult
2. `test_evaluate_malformed_json_fallback` — malformed JSON 时使用 default_score 降级
3. `test_evaluate_score_range_validation` — 边界值 0.0/1.0 正确保留
4. `test_evaluate_missing_overall_calculates_average` — 缺少 overall_score 时自动计算平均

### generate_and_parse_json (5 tests)

1. `test_normal_json_response` — 正常 JSON 解析成功
2. `test_non_json_response_uses_fallback` — 非 JSON 文本使用 fallback
3. `test_fallback_none_behavior` — fallback=None 时返回 None
4. `test_llm_exception_returns_fallback` — LLM 异常时返回 fallback
5. `test_json_in_markdown_block_extracted` — markdown 包裹的 JSON 正确提取

### AIGenerationService (4 tests)

1. `test_generate_storylines_ai_happy_path` — 故事线生成正常流程
2. `test_generate_storylines_ai_novel_not_found` — 小说不存在抛 ValueError
3. `test_generate_power_systems_ai_happy_path` — 力量体系生成正常流程
4. `test_generate_power_systems_ai_novel_not_found` — 小说不存在抛 ValueError

## 执行日志

```
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0
plugins: anyio-4.13.0, langsmith-0.8.5, asyncio-1.3.0, cov-7.1.0
asyncio: mode=Mode.AUTO
collected 18 items
18 passed in 2.10s
============================= 18 passed in 2.10s ==============================
```
