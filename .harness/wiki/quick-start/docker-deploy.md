# Docker 部署指南

## 前提条件

- 服务器：Ubuntu 22.04+
- Docker 20.10+
- docker-compose v2.x

## 一键部署

```bash
# 1. 克隆代码
git clone https://github.com/TonightisOver/xIaoShuo.git /opt/xiaoshuo
cd /opt/xiaoshuo

# 2. 配置环境变量
cp .env.docker .env
nano .env  # 填入 DEEPSEEK_API_KEY

# 3. 启动
docker-compose up -d

# 4. 验证
docker-compose ps
curl http://localhost/api/v1/health
```

## 服务架构

```
Internet → :80 Nginx → :8000 FastAPI (API + 前端)
                                ↓
                           :5432 PostgreSQL (volume 持久化)
```

## 常用运维命令

```bash
# 查看日志
docker-compose logs -f api

# 重启服务
docker-compose restart api

# 更新代码并重新部署
git pull && docker-compose up -d --build

# 进入数据库
docker-compose exec db psql -U xiaoshuo

# 备份数据库
docker-compose exec db pg_dump -U xiaoshuo xiaoshuo > backup.sql
```

## 环境变量（.env）

```bash
DEEPSEEK_API_KEY=sk-xxx        # 必填
DB_PASSWORD=xiaoshuo2026        # 数据库密码
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro
LOG_LEVEL=INFO
```

## 当前部署

- 服务器：115.190.142.169
- 系统：Ubuntu 22.04.4 LTS
- Docker：29.1.3
- 状态：3 容器运行中
