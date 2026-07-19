# CHANGE-009 归档记录

- 原名称：修复云服务器问题
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-009-修复云服务器问题`
- 归档路径：`archive/changes/CHANGE-009-修复云服务器问题`
- 关联提交：
  - a5d2939 2026-05-16 docs(CHANGE-009): add deployment verification report
  - 748b49d 2026-05-16 fix(CHANGE-009): improve task-novel navigation and regeneration UX

## 目标

用户在云服务器（115.190.142.169）上创建了小说生成任务，但遇到以下问题：
1. 无法查看生成进度（WebSocket 可能未正确工作）
2. 部分内容无法修改（前端编辑功能可能未正确对接 API）

需要排查并修复这些问题，确保线上功能完整可用。

**目标用户**: 平台使用者
**使用场景**: 通过浏览器访问 http://115.190.142.169 使用所有功能

## 主要设计决定

**变更 ID**: CHANGE-009
**创建时间**: 2026-05-16

## 1. 问题根因分析

### 问题 1: 看不到进度
**根因**: DeepSeek API key 无效 → 所有节点使用 fallback mock 数据 → 任务在 1-2 秒内完成 → 用户打开任务详情时已经是 `completed` 状态 → WebSocket 不连接（代码只在 pending/running 时连接）

**修复**:
- TaskDetail 页面在 `completed` 状态也显示完成信息和结果
- 添加从任务页面跳转回小说项目的链接
- WebSocket 和 Nginx 配置本身是正确的

### 问题 2: 内容无法修改
**根因**: 前端编辑页面（WorldEdit/Characters/ChapterEdit）通过 `/novels/:id/...` 路由访问，这些路由在 SPA 中正确配置。但需要验证：
- 编辑保存时 PUT 请求是否正确发送
- API 返回是否正确处理

**修复**:
- 确认前端 PUT 请求路径正确
- 在 NovelDetail 页面添加直接编辑入口
- 确保生成完成后小说状态正确更新

### 问题 3: API Key 无效
**根因**: .env 中的 key `[REDACTED_API_KEY]` 已失效

**修复**: 用户需要更新有效的 API key。代码层面无需修改。

## 2. 修复方案

### 2.1 TaskDetail 页面增强

- 已完成任务显示 "已完成" 状态和结果摘要
- 如果任务关联了 novel_id，显示"查看小说项目"链接
- 任务 API 返回 novel_id 字段

### 2.2 NovelDetail 页面增强

- 生成完成后自动刷新数据（当前需要手动刷新）
- 添加"重新生成"按钮（已完成状态下）

### 2.3 任务 API 返回 novel_id

当前 TaskDetailResponse 不包含 novel_id，需要添加。

## 3. 修改文件

| 文件 | 修改内容 |
|------|---------|
| `src/api/models/responses.py` | TaskDetailResponse 添加 novel_id 字段 |
| `frontend/src/views/TaskDetail.vue` | 添加"查看小说项目"链接，完成状态显示结果 |
| `frontend/src/views/NovelDetail.vue` | 完成后显示"重新生成"按钮 |

## 4. 不需要修改的部分

- nginx.conf — WebSocket 配置正确
- useWebSocket.js — URL 构建逻辑正确
- 后端 API 路由 — 无冲突

## 涉及模块

- `frontend/dist/`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/TaskDetail.vue`
- `src/api/models/responses.py`
- `src/api/routes/novels.py`

## 实施结果

**变更 ID**: CHANGE-009
**创建时间**: 2026-05-16
**优先级**: P0
用户在云服务器（115.190.142.169）上创建了小说生成任务，但遇到以下问题：
1. 无法查看生成进度（WebSocket 可能未正确工作）
2. 部分内容无法修改（前端编辑功能可能未正确对接 API）
需要排查并修复这些问题，确保线上功能完整可用。
**目标用户**: 平台使用者
**使用场景**: 通过浏览器访问 http://115.190.142.169 使用所有功能
**现象**: 创建任务后看不到实时进度
**可能原因**:
- Nginx WebSocket 代理配置问题（upgrade header）

## 测试与验证

| 指标 | 值 |
|------|-----|
| 总测试数 | 13 |
| 通过 | 13 |
| 失败 | 0 |
| 跳过 | 0 |
| 通过率 | 100% |

## 遗留事项

### 问题 1: 无法查看生成进度
**现象**: 创建任务后看不到实时进度
**可能原因**:
- Nginx WebSocket 代理配置问题（upgrade header）
- 前端 WebSocket URL 拼接错误（ws:// vs wss://）
- 任务生成太快（fallback 数据秒完成），来不及看进度

### 问题 2: 内容无法修改
**现象**: 世界观/人物/章节编辑页面可能无法保存
**可能原因**:
- 前端路由未正确匹配（SPA fallback 问题）
- API 端点 PUT 请求未正确处理
- 前端页面未正确调用 projects API

### 问题 3: DeepSeek API Key 失效
**现象**: 生成使用 fallback mock 数据而非真实 LLM 输出
**可能原因**:
- .env 中的 API key 已过期或无效

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
