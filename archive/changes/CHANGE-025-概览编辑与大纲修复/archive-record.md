# CHANGE-025 归档记录

- 原名称：概览编辑与大纲修复
- 状态：completed
- 时间范围：2026-05-18
- 原路径：`.harness/changes/CHANGE-025-概览编辑与大纲修复`
- 归档路径：`archive/changes/CHANGE-025-概览编辑与大纲修复`
- 关联提交：
  - 03fe5fd 2026-05-18 feat: improve full novel generation and storyline context

## 目标

修复4个用户反馈的功能缺陷：概览创意不可编辑、大纲章纲只有第一卷可用、总纲需人工输入、故事线/人物弧光AI生成无效。

---

## 主要设计决定

前端修复3处Vue组件 + 后端修复2处Python服务逻辑。

---

## 涉及模块

- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/OutlineEditor.vue`
- `frontend/src/views/StorylineManager.vue`
- `src/api/routes/outlines.py`
- `src/api/services/outline_service.py`
- `src/api/services/storyline_service.py`
- `tests/unit/test_change025_fixes.py`

## 实施结果

**变更 ID**: CHANGE-025
**创建时间**: 2026-05-18
**状态**: 已完成

---

## 需求概述

修复4个用户反馈的功能缺陷：概览创意不可编辑、大纲章纲只有第一卷可用、总纲需人工输入、故事线/人物弧光AI生成无效。

---

## 技术方案

前端修复3处Vue组件 + 后端修复2处Python服务逻辑。

---

## 核心变更

### 修改文件
- `frontend/src/views/NovelDetail.vue` - 概览tab添加创意/标题编辑模式
- `frontend/src/views/OutlineEditor.vue` - 添加AI生成总纲按钮
- `frontend/src/views/StorylineManager.vue` - AI生成添加错误反馈和结果预览
- `src/api/services/outline_service.py` - 修复多卷volume_number保存逻辑 + upsert_chapter_outline按volume_number隔离
- `src/api/services/storyline_service.py` - 修复generate_arcs_ai使用实际character_id

---

## 质量指标

- **单元测试覆盖率**: 待测
- **集成测试**: 待测
- **CI 验证**: 待测
- **代码检查**: 待测

---

**更新时间**: 2026-05-18

## 测试与验证

```
5 passed, 229 warnings in 0.93s
```

## 遗留事项

- Bug 2修复需要数据库层面的查询条件变更，需确认不破坏已有数据
- Bug 3新增后端接口，需确认与现有outline_service集成正确

## 原始文件清单

- `01-需求分析.md`
- `02-技术设计.md`
- `04-编码报告-v1.md`
- `07-单元测试报告-v1.md`
- `10-部署验证报告-v1.md`
- `summary.md`
