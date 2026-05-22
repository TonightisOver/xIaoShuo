# Test Report — CHANGE-040: 修复章节分卷与图谱筛选

**Date:** 2026-05-22

## 测试概览

| 指标 | 值 |
|------|-----|
| 测试文件 | `tests/unit/test_change040_volume_and_graph.py` |
| 测试用例数 | 15 |
| 通过 | 15 |
| 失败 | 0 |
| 耗时 | 2.08s |

## 测试覆盖范围

### 1. _find_volume_number fallback 逻辑 (5 tests)
- 精确匹配 outline chapters 数组
- fallback 通过 chapter_start/chapter_end 范围匹配
- 无匹配时返回 None
- outline 优先于 range 匹配
- chapter_start/chapter_end 为 None 时安全处理

### 2. 成功章节过滤逻辑 (3 tests)
- 过滤空 content 和 word_count=0 的章节
- 过滤有 content 但 word_count=0 的章节
- 保留有效章节

### 3. 知识图谱频次筛选 (5 tests)
- 高频实体被包含
- 低频实体被排除
- foreshadowing 类型始终包含
- min_frequency=1 包含所有实体
- 不在三元组中的孤立实体被排除

### 4. API 路由参数验证 (2 tests)
- Query import 存在
- 路由函数签名包含 min_frequency 参数

## 结论

所有 15 个测试用例通过，覆盖了 CHANGE-040 的核心逻辑变更。
