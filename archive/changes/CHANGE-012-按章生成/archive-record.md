# CHANGE-012 归档记录

- 原名称：按章生成
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-012-按章生成`
- 归档路径：`archive/changes/CHANGE-012-按章生成`
- 关联提交：
  - 290509d 2026-05-16 feat(CHANGE-012): add chapter-range generation

## 目标

新增按章节范围生成功能，允许用户指定 chapter_start 和 chapter_end 精确控制生成范围。

## 主要设计决定

**变更 ID**: CHANGE-012
**创建时间**: 2026-05-16

## 1. 设计概述

在 CHANGE-011 的基础上，添加更细粒度的章节范围生成能力。复用 generate_volume_background 的核心逻辑，但以章节号范围为单位。

## 2. API 设计

```
POST /api/v1/projects/{novel_id}/generate-chapters
Body: {
  "chapter_start": 3,
  "chapter_end": 5
}
```

## 3. 实现方案

新增 `generate_chapters_background(task_id, novel_id, chapter_start, chapter_end)`:
1. 从 chapter_outlines（或 volumes 中）提取指定范围的大纲
2. 读取 chapter_start - 1 章的内容作为上下文
3. 逐章生成
4. 存入 chapters 表（如果已存在则覆盖，标记 status="regenerated"）

## 4. 修改文件

| 文件 | 修改 |
|------|------|
| `src/api/services/novel_generator.py` | 新增 generate_chapters_background |
| `src/api/routes/projects.py` | 新增 generate-chapters 端点 |
| `src/api/services/novel_manager.py` | 添加 get_chapter_outlines_range 方法 |

## 涉及模块

- `src/api/routes/projects.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`

## 实施结果

新增按章节范围生成功能，允许用户指定 chapter_start 和 chapter_end 精确控制生成范围。

## 测试与验证

**变更 ID**: CHANGE-012
**版本**: v1
**验证时间**: 2026-05-16

## CI 执行结果

| 阶段 | 状态 | 耗时 |
|------|------|------|
| 依赖安装 | 通过 | - |
| 代码检查 (lint) | 通过 | - |
| 单元测试 | 通过 (13/13) | ~5s |
| 构建 | 通过 | - |

## 检查项

- [x] 无新增依赖
- [x] 无 lint 错误
- [x] 所有测试通过
- [x] 无类型错误

## 结论

CI 流水线全部通过，无阻塞项。

**结果**: 通过

## 遗留事项

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 范围越界 | 低 | 参数校验 |
| 并发生成冲突 | 低 | 后台任务队列机制 |

## 原始文件清单

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
- `summary.md`
