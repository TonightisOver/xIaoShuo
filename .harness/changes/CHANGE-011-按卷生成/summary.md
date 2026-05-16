# CHANGE-011 按卷生成 - 变更总结

## 变更概述

为小说平台新增按卷生成功能，支持将小说按卷组织并逐卷生成章节内容。

## 变更内容

### 数据库
- 新增 `volumes` 表: novel_id, volume_number, title, summary, outline(JSON), status, chapter_start, chapter_end
- `chapters` 表新增 `volume_number` 列

### 后端
- 修改大纲生成 prompt，输出 volumes 结构
- 新增 API: GET/PUT `/projects/{id}/volumes/{num}`, POST `/projects/{id}/generate-volume`
- 新增 `generate_volume_background` 函数，支持前卷上下文传递
- `_persist_to_novel` 增加 volumes 保存逻辑

### 兼容性
- 旧格式 (chapter_outlines 无 volumes) 继续支持，无破坏性变更

## 验证状态

| 阶段 | 状态 |
|------|------|
| 代码检查 | PASS |
| 专家评审 | PASS |
| 单元测试 (13 cases) | PASS |
| 集成测试 | PASS |
| CI 验证 | PASS |
| 部署验证 | PASS |

## 结论

变更已完成全部验证，功能正常，向后兼容，可正式发布。
