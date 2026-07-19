# 变更总结: 概览编辑、大纲多卷修复、总纲AI生成、故事线AI生成修复

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
