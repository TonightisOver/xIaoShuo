# 编码报告：CHANGE-046 导出与发布系统

## 变更概述
实现了完整的小说导出功能，支持 TXT/EPUB/DOCX 三种格式，含排版模板引擎、流式下载 API 和前端导出对话框。

## 变更文件清单

| 文件路径 | 变更类型 | 说明 |
|---------|---------|------|
| pyproject.toml | 修改 | 新增 python-docx、ebooklib 依赖 |
| src/api/models/export_models.py | 新增 | 导出请求/响应 Pydantic 模型 |
| src/api/services/export_service.py | 新增 | FormatEngine + TXT/EPUB/DOCX 导出器 |
| src/api/routes/export.py | 新增 | POST /novels/{id}/export + GET /export/templates |
| src/api/routes/__init__.py | 修改 | 注册 export_router |
| src/api/main.py | 修改 | 注册 export_router |
| frontend/src/components/ExportDialog.vue | 新增 | 导出对话框组件 |
| frontend/src/views/NovelDetail.vue | 修改 | 添加导出按钮 + 引入 ExportDialog |
| frontend/src/views/ChapterEdit.vue | 修改 | 添加一键复制按钮 |
| tests/unit/test_export_service.py | 新增 | 21 个单元测试 |

## 实现说明

### 排版格式化引擎 (FormatEngine)
- 预置 3 种模板 (default/qidian/fanqie)，支持自定义模板
- 统一处理章节标题格式化、段首缩进、段间距、卷首页

### 导出器
- TxtExporter: 纯文本 UTF-8 输出
- EpubExporter: 基于 ebooklib，含目录/元数据/分章
- DocxExporter: 基于 python-docx，含标题样式/分页符

### API 路由
- POST /api/v1/novels/{novel_id}/export — StreamingResponse 流式下载
- GET /api/v1/export/templates — 模板列表

### 前端
- ExportDialog.vue: 格式/范围/模板选择 → fetch blob → 触发下载
- ChapterEdit.vue: Clipboard API 一键复制正文

## 测试结果
- 21 tests passed (1.92s)
- ruff check: All checks passed

## 待验证项
- [ ] EPUB 文件在实际阅读器中打开验证
- [ ] 大文件（100+ 章节）导出性能
- [ ] 前端导出对话框 UI 交互
