# 变更总结: 按章生成

**变更 ID**: CHANGE-012  
**完成时间**: 2026-05-16  
**状态**: 已完成

## 变更概述

新增按章节范围生成功能，允许用户指定 chapter_start 和 chapter_end 精确控制生成范围。

## 实现内容

- API: `POST /api/v1/projects/{novel_id}/generate-chapters`
- 核心函数: `generate_chapters_background`
- 自动注入前一章内容作为上下文
- 覆盖已有章节（status="regenerated"）
- 复用 CHAPTER_GENERATION_PROMPT + 文风注入
- CHAPTER_PROGRESS 实时进度推送

## 修改文件

| 文件 | 修改 |
|------|------|
| `src/api/services/novel_generator.py` | 新增 generate_chapters_background |
| `src/api/routes/projects.py` | 新增 generate-chapters 端点 |

## 各阶段结果

| 阶段 | 结果 |
|------|------|
| 05-代码检查 | 通过 |
| 06-专家评审 | 通过 |
| 07-单元测试 | 通过 (13/13) |
| 08-集成测试 | 通过 |
| 09-CI验证 | 通过 |
| 10-部署验证 | 通过 |

## 总结

小范围改动（2 文件），高复用度，全部验证通过。
