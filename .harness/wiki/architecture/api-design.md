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

### 子资源 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | /api/v1/projects/{id}/world | 世界观 |
| GET/POST | /api/v1/projects/{id}/power-systems | 等级体系 |
| PUT/DELETE | /api/v1/projects/{id}/power-systems/{ps_id} | 单个体系 |
| GET/POST | /api/v1/projects/{id}/characters | 人物 |
| PUT/DELETE | /api/v1/projects/{id}/characters/{char_id} | 单个人物 |
| GET | /api/v1/projects/{id}/chapters | 章节列表 |
| GET/PUT | /api/v1/projects/{id}/chapters/{num} | 单个章节 |

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
