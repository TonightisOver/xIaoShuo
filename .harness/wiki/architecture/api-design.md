# API 设计规范

## 基础信息

- 基础路径：`/api/v1/`
- 内容类型：`application/json`
- 认证：暂无（后续添加）

## 端点总览

### 旧版任务 API（兼容）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/health | 健康检查 |
| POST | /api/v1/novels | 创建生成任务 |
| GET | /api/v1/novels/{task_id} | 查询任务详情 |
| GET | /api/v1/novels | 列出任务 |

### 项目管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/projects | 创建小说项目 |
| GET | /api/v1/projects | 列出项目 |
| GET | /api/v1/projects/{id} | 项目详情 |
| PUT | /api/v1/projects/{id} | 更新项目 |
| DELETE | /api/v1/projects/{id} | 删除项目 |
| POST | /api/v1/projects/{id}/generate | 触发生成 |

### 全功能生成 API（CHANGE-026）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/projects/full-generate | 创建项目 + 启动 13 阶段全功能生成 |
| POST | /api/v1/projects/{id}/generate-full | 对已有项目启动全功能生成 |
| POST | /api/v1/projects/{id}/generate-volume | 按卷生成章节（支持 outlines 表 fallback） |
| POST | /api/v1/projects/{id}/generate-chapters | 按章节范围生成 |

### 子资源 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | /api/v1/projects/{id}/world | 世界观（不存在返回 404） |
| GET/POST | /api/v1/projects/{id}/power-systems | 力量体系（不存在返回 404） |
| PUT/DELETE | /api/v1/projects/{id}/power-systems/{ps_id} | 单个体系（不存在返回 404） |
| GET/POST | /api/v1/projects/{id}/characters | 人物（不存在返回 404） |
| PUT/DELETE | /api/v1/projects/{id}/characters/{char_id} | 单个人物（不存在返回 404） |
| GET | /api/v1/projects/{id}/chapters | 章节列表（不存在返回 404） |
| GET/PUT/DELETE | /api/v1/projects/{id}/chapters/{num} | 单个章节（不存在返回 404） |
| GET | /api/v1/projects/{id}/volumes | 卷列表（不存在返回 404） |
| GET/PUT | /api/v1/projects/{id}/volumes/{num} | 单卷（不存在返回 404） |

### 子资源一致性（CHANGE-026 v2）

所有子资源端点（GET/POST/PUT/DELETE）统一先校验项目存在性：
- 项目存在但有数据 → 正常返回数据或空数据
- 项目存在但无数据 → 返回空列表或 null 字段（200）
- 项目不存在 → 统一返回 404 `{"detail": "Novel not found"}`

### WebSocket

| 路径 | 说明 |
|------|------|
| /ws/tasks/{task_id} | 实时进度推送 |

## 响应格式

### 成功

```json
{
  "novel_id": "novel-20260516...",
  "status": "draft"
}
```

### 列表

```json
{
  "novels": [...],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

### 错误

```json
{
  "detail": "Novel not found"
}
```

## HTTP 状态码

| 码 | 含义 |
|----|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 202 | 已接受（异步任务） |
| 400 | 业务验证失败 |
| 404 | 资源不存在 |
| 422 | 请求格式错误 |
| 500 | 服务器内部错误 |

## 数据隔离原则（CHANGE-024）

所有子资源 API 均以 `novel_id` 作为隔离边界：

- **service 层强制 novel_id**：update/delete 方法的 novel_id 参数无默认值，调用方必须显式传递
- **双键查询**：`WHERE resource_id = X AND novel_id = Y`，跨小说访问返回 404
- **confirm_message 三元组**：`msg_id + conv_id + novel_id` JOIN 校验，防止跨小说误写
- **关联表过滤**：`get_relations` 通过 DB JOIN 过滤，不做 Python 层过滤
