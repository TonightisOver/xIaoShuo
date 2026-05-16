# 项目运行指南

## 本地运行

```bash
# 确保 PostgreSQL 在运行（端口 5433）
# 确保 .env 已配置

poetry run python run_api.py
```

服务启动后：
- 前端界面：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/v1/health

## 常用操作

### 创建小说项目

```bash
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"idea": "一个程序员穿越修仙世界", "novel_type": "玄幻", "target_words": 100000, "title": "代码修仙录"}'
```

### 触发生成

```bash
curl -X POST http://localhost:8000/api/v1/projects/{novel_id}/generate
```

### 查看进度

浏览器打开 http://localhost:8000，点击对应任务查看实时进度。

或通过 WebSocket：
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}')
ws.onmessage = (e) => console.log(JSON.parse(e.data))
```

## 环境变量说明

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| DEEPSEEK_API_KEY | ✅ | - | DeepSeek API 密钥 |
| DATABASE_URL | ✅ | - | PostgreSQL 连接字符串 |
| LOG_LEVEL | ❌ | INFO | 日志级别 |
| API_PORT | ❌ | 8000 | API 端口 |
| API_RELOAD | ❌ | false | 热重载（开发用） |
