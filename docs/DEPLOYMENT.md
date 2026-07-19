# xIaoShuo 服务器部署指南

本文档指导在 Ubuntu 服务器上用 Docker 部署 xIaoShuo。

## 前置要求

- Ubuntu 20.04+ 服务器（root 或 sudo 权限）
- 已购 DeepSeek API Key
- 服务器开放端口 **7000**（前端/API 入口）和可选的 8000（API 直连）、5433（DB）

## 一、首次部署

### 1. 上传代码到服务器

在本地（项目根目录）执行：

```bash
# 方式 A：scp 上传（首次）
scp -r . root@<服务器IP>:/opt/xiaoshuo/

# 方式 B：服务器 git clone（推荐，便于后续更新）
ssh root@<服务器IP> "git clone <你的仓库地址> /opt/xiaoshuo"
```

### 2. 服务器上运行部署脚本

```bash
ssh root@<服务器IP>
cd /opt/xiaoshuo
bash deploy.sh
```

脚本会：自动安装 Docker、创建 `.env` 配置文件模板。

### 3. 编辑 .env 填入必填项

```bash
nano /opt/xiaoshuo/.env
```

**必填项**：

| 配置 | 说明 | 获取方式 |
|------|------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | DeepSeek 控制台 |
| `LLM_ENCRYPTION_KEY` | LLM 配置加密密钥 | 运行 `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_TOKEN` | 管理员令牌 | 自定义随机字符串 |

`DB_PASSWORD`、`DEEPSEEK_MODEL` 等有默认值，按需修改。

生成任务队列默认启用，通常无需修改：

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `TASK_QUEUE_ENABLED` | `true` | 是否在 API 进程内启动 PostgreSQL 队列 worker |
| `TASK_QUEUE_POLL_SECONDS` | `1.0` | 无任务时的轮询间隔 |
| `TASK_QUEUE_LEASE_SECONDS` | `120` | 单次执行租约时长；worker 会在执行中续租 |
| `TASK_QUEUE_RETRY_DELAY_SECONDS` | `5` | 仅对明确允许重试的任务生效的延迟 |

### 4. 构建并启动服务

```bash
cd /opt/xiaoshuo
docker compose up -d --build
```

首次构建约 5-10 分钟（下载依赖 + 前端 npm build）。

### 5. 验证部署

```bash
# 查看服务状态
docker compose ps

# 检查 API 健康
curl http://localhost:8000/api/v1/health
# 期望返回：{"status":"healthy",...}

# 查看 API 启动日志（确认 alembic 迁移成功）
docker compose logs api | head -50

# 浏览器访问前端
# http://<服务器IP>:7000
```

## 二、更新代码后重新部署

```bash
cd /opt/xiaoshuo
git pull                    # 拉取最新代码
docker compose up -d --build  # 重建并重启（db 数据保留）
```

## 三、常用运维命令

```bash
# 查看实时日志
docker compose logs -f api
docker compose logs -f nginx

# 重启某个服务
docker compose restart api

# 进入容器排查
docker compose exec api bash

# 手动跑数据库迁移
docker compose exec api alembic upgrade head

# 容器内跑测试（可选）
docker compose exec api pytest tests/unit/ -q

# 停止所有服务（数据保留）
docker compose down

# 停止并清除数据（危险！会删数据库）
docker compose down -v
```

## 四、服务架构

```
浏览器 :7000 ──> nginx ──┬── 静态前端 (dist 打进 nginx 镜像)
                          └── /api, /ws 代理 ──> api:8000 ──> db:5432 (PostgreSQL)
```

- **nginx** (端口 7000)：serve 前端 + 反向代理 API/WebSocket
- **api** (端口 8000)：FastAPI + LangGraph，启动时自动跑 alembic 迁移
- **db** (端口 5433)：PostgreSQL 17，数据持久化到 `pgdata` volume

## 五、本次部署相关的重要变更

1. **移除 psycopg2-binary**：alembic 迁移改用 asyncpg（与业务一致），Dockerfile 不再需要 libpq-dev/gcc，镜像更小
2. **LLM 模型降级**：pro 模型限流时自动降级到 flash（需确保 `DEEPSEEK_MODEL_FLASH` 配置正确，默认 `deepseek-v4-flash`）
3. **持久化任务恢复**：尚未执行的 queued 任务在重启后继续领取；已经开始且不安全重放的生成任务会明确标记为 failed
4. **nginx 自带前端**：dist 打进 nginx 镜像，不再依赖宿主机 `./frontend/dist`

## 六、持久化生成任务队列

小说生成、全功能生成、长篇生成、按卷/章节生成和 HITL 审核恢复均写入 PostgreSQL
`tasks` 表，不再依赖请求进程内的 FastAPI `BackgroundTasks`。

- `queue_state=queued`：任务参数已持久化，服务重启后仍可领取。
- `queue_state=leased`：某个 worker 正在执行并定期续租。
- `queue_state=idle`：任务已完成、失败、暂停或正在等待人工审核，不应被领取。
- 历史 `queue_state IS NULL` 的 pending/running 任务缺少可重建参数，启动时会标记失败。
- 当前生成流程可能产生部分数据库写入，因此统一使用 `max_attempts=1`。已经开始后进程中断的任务不会盲目重放，避免重复章节、故事线或人物数据。
- 多个 API worker/实例可同时运行；领取使用 PostgreSQL `FOR UPDATE SKIP LOCKED`，不会同时领取同一行。

部署新版本前必须先执行 Alembic 迁移：

```bash
docker compose exec api alembic upgrade head
```

查看正在排队或执行的任务：

```sql
SELECT task_id, status, queue_state, task_type, attempt_count,
       lease_owner, lease_expires_at
FROM tasks
WHERE queue_state IN ('queued', 'leased')
ORDER BY created_at;
```

关闭服务时，应用会先停止 worker，再关闭 LangGraph checkpointer 和数据库连接。不要直接删除
leased 行；异常中断后的租约会在下次启动时按 `attempt_count/max_attempts` 分类恢复或失败。

## 七、故障排查

### API 启动失败：`validate_encryption_key` / `validate_admin_token`
`.env` 里 `LLM_ENCRYPTION_KEY` 或 `ADMIN_TOKEN` 为空，按第 3 步填入。

### alembic 迁移失败
```bash
docker compose logs api | grep -i alembic
# 手动重试
docker compose exec api alembic upgrade head
```

### 前端 404 / 白屏
确认 nginx 镜像构建成功（`docker compose logs nginx`）。新架构 dist 打进镜像，无需宿主机 build。

### DeepSeek API 调用失败
```bash
# 容器内测试 API Key
docker compose exec api curl -s -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  https://api.deepseek.com/v1/models | head
```

### 数据库连接失败
```bash
docker compose ps db  # 确认 db 健康
docker compose exec db psql -U xiaoshuo -d xiaoshuo -c "SELECT 1"
```
