# CHANGE-047 编码报告

## 变更摘要

实现大纲↔正文双向同步功能，包含后端服务、API路由、数据模型和前端交互。

## 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/api/services/outline_sync_service.py` | 329 | 同步服务核心逻辑 |
| `src/api/routes/outline_sync.py` | 104 | 7个REST API端点 |
| `tests/unit/test_outline_sync_service.py` | 229 | 9个单元测试 |

## 修改文件

| 文件 | 说明 |
|------|------|
| `src/api/models/db_models.py` | 新增 OutlineSyncSuggestion 模型 + Outline.deviation_summary 字段 |
| `src/api/routes/__init__.py` | 注册 outline_sync_router |
| `src/api/main.py` | 挂载 outline_sync_router |
| `frontend/src/views/OutlineEditor.vue` | 同步状态面板 + 建议管理UI |

## 功能实现

### 正向同步（大纲→正文）
- 大纲修改后 LLM 分析影响范围，生成建议列表
- 建议包含：受影响章节、影响类型、严重度、修改方向
- 用户可逐条或批量接受/拒绝建议
- 接受建议后标记章节为 needs_revision

### 反向同步（正文→大纲）
- 对比章节正文与章纲，LLM 评估偏离度(0-1)
- 偏离度 < 0.3 标记大纲为 completed
- 偏离度 >= 0.3 标记为 deviated 并记录偏离摘要

### 前端交互
- 保存总纲时自动触发影响分析
- 同步建议面板：显示严重度标签、影响类型、操作按钮
- 章节同步状态：彩色圆点指示 completed/deviated/draft

## 技术决策
- LLM 调用 30s 超时，失败时优雅降级（返回空结果）
- 重新分析时自动过期旧的 pending 建议
- 单例服务模式，与项目现有模式一致
- 数据库索引 ix_sync_novel_status 优化查询

## 验证
- ruff check: 通过
- pytest: 9/9 通过
- vite build: 成功
