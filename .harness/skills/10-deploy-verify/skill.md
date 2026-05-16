# Skill: 部署验证

**阶段**: 10  
**版本**: v1.0

---

## 角色定位

你是部署工程师，负责验证代码可以成功部署并正常运行。

---

## 输入

- 完整的代码库
- CI 验证通过的代码

---

## 执行步骤

### 1. 本地部署验证

```bash
# 安装依赖
poetry install

# 启动应用
python -m src.main
```

### 2. 测试核心功能

- 测试 API 接口可访问
- 测试数据库连接
- 测试 Redis 连接
- 测试核心业务流程

### 3. 性能基准测试

- 测试 API 响应时间
- 测试并发处理能力
- 测试资源使用情况（CPU、内存）

### 4. 健康检查

```bash
# 访问健康检查接口
curl http://localhost:8000/health
```

---

## 产出物

生成 `10-部署验证报告-v1.md`：

```markdown
# 部署验证报告 v1: {需求简短描述}

**变更 ID**: CHANGE-XXX  
**创建时间**: YYYY-MM-DD

## 1. 部署概述

- **部署环境**: 本地 / 测试环境 / 生产环境
- **部署方式**: 直接运行 / Docker / Kubernetes
- **部署时间**: {日期时间}

## 2. 部署步骤

### 2.1 环境准备

**依赖服务**:
- ✅ PostgreSQL 已启动
- ✅ Redis 已启动
- ✅ DeepSeek API 可访问

**环境变量**:
```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
DEEPSEEK_API_KEY=sk-...
```

### 2.2 应用部署

**命令**:
```bash
poetry install
python -m src.main
```

**结果**: ✅ 成功 / ❌ 失败

**启动日志**:
```
{粘贴启动日志}
```

## 3. 功能验证

### 3.1 API 接口验证

| 接口 | 方法 | 状态 | 响应时间 |
|------|------|------|---------|
| `/health` | GET | ✅ 200 | 10ms |
| `/api/projects` | POST | ✅ 201 | 50ms |
| `/api/projects/{id}` | GET | ✅ 200 | 30ms |

### 3.2 数据库连接验证

**测试命令**:
```bash
# 测试数据库连接
python -c "from src.db.session import engine; engine.connect()"
```

**结果**: ✅ 成功 / ❌ 失败

### 3.3 Redis 连接验证

**测试命令**:
```bash
# 测试 Redis 连接
python -c "from redis import Redis; r = Redis.from_url('redis://localhost'); r.ping()"
```

**结果**: ✅ 成功 / ❌ 失败

### 3.4 核心业务流程验证

**测试场景**: 创建项目并生成章节

**步骤**:
1. 创建项目
2. 设置世界观
3. 设计人物
4. 生成大纲
5. 生成章节

**结果**: ✅ 成功 / ❌ 失败

**执行时间**: {X} 秒

## 4. 性能基准测试

### 4.1 API 响应时间

| 接口 | 平均响应时间 | P95 | P99 | 目标 | 状态 |
|------|-------------|-----|-----|------|------|
| POST /api/projects | 50ms | 80ms | 100ms | < 200ms | ✅ |
| GET /api/projects/{id} | 30ms | 50ms | 70ms | < 200ms | ✅ |

### 4.2 并发测试

**工具**: Apache Bench (ab)

**命令**:
```bash
ab -n 1000 -c 10 http://localhost:8000/api/projects
```

**结果**:
- **总请求数**: 1000
- **并发数**: 10
- **成功率**: 100%
- **平均响应时间**: 50ms
- **吞吐量**: 200 req/s

### 4.3 资源使用

**CPU 使用率**: {X}%  
**内存使用**: {Y} MB  
**磁盘 I/O**: {Z} MB/s

## 5. 健康检查

### 5.1 健康检查接口

**接口**: GET /health

**响应**:
```json
{
    "status": "healthy",
    "database": "connected",
    "redis": "connected",
    "version": "1.0.0"
}
```

**结果**: ✅ 健康

### 5.2 日志检查

**错误日志**: ✅ 无错误 / ⚠️ 有警告 / ❌ 有错误

**警告/错误清单**（如有）:
- {警告/错误描述}

## 6. 部署检查清单

- ✅ 应用成功启动
- ✅ 数据库连接正常
- ✅ Redis 连接正常
- ✅ API 接口可访问
- ✅ 核心功能可用
- ✅ 性能指标达标
- ✅ 健康检查通过
- ✅ 无错误日志

## 7. 回滚计划

**如果部署失败，回滚步骤**:
1. 停止应用
2. 恢复到上一个版本
3. 重启应用
4. 验证功能

**回滚命令**:
```bash
git checkout {上一个版本}
poetry install
python -m src.main
```

## 8. 质量门禁

**状态**: ✅ 通过 / ❌ 不通过

**检查项**:
- ✅ 部署成功
- ✅ 核心功能可用
- ✅ 性能达标
- ✅ 无严重错误

---

**部署状态**: ✅ 完成，等待用户确认
```

---

## 质量门禁

检查以下条件是否满足：

- ✅ 部署成功
- ✅ 核心功能可用
- ✅ 性能达标
- ✅ 健康检查通过

---

## 人工审核

**必需**。部署验证完成后，必须等待用户确认交付。

用户可能的反馈：
- **"通过"**: 确认交付，关闭变更
- **"修改 XXX"**: 根据反馈修改
- **"拒绝"**: 回退部署

---

## 部署最佳实践

### 1. 使用 Docker

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 Poetry
RUN pip install poetry

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 安装依赖
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# 复制源代码
COPY src/ ./src/

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["python", "-m", "src.main"]
```

### 2. 使用 docker-compose

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/xiaoshuo
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
  
  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=xiaoshuo
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:6
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 3. 健康检查

在 FastAPI 中添加健康检查接口：

```python
from fastapi import FastAPI
from src.db.session import engine
from redis import Redis

app = FastAPI()

@app.get("/health")
async def health_check():
    """健康检查接口"""
    # 检查数据库
    try:
        engine.connect()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    # 检查 Redis
    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
    
    status = "healthy" if db_status == "connected" and redis_status == "connected" else "unhealthy"
    
    return {
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0"
    }
```

---

## 常见问题

### Q1: 部署失败了怎么办？
**A**:
1. 查看启动日志，定位失败原因
2. 检查环境变量配置
3. 检查依赖服务（数据库、Redis）
4. 修复问题后重新部署

### Q2: 如何进行灰度发布？
**A**:
- 先部署到一小部分服务器
- 观察运行情况
- 逐步扩大部署范围

### Q3: 如何监控应用运行状态？
**A**:
- 使用健康检查接口
- 使用日志监控（ELK、Grafana）
- 使用 APM 工具（New Relic、Datadog）

---

**Skill 状态**: ✅ 已激活