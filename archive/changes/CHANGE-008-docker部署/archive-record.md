# CHANGE-008 归档记录

- 原名称：docker部署
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-008-docker部署`
- 归档路径：`archive/changes/CHANGE-008-docker部署`
- 关联提交：
  - 37e475f 2026-05-16 docs: complete 10-stage harness documentation for CHANGE-003~008
  - f950c4e 2026-05-16 docs: add CHANGE-003 to CHANGE-008 harness documentation

## 目标

实现 Docker 容器化部署，支持一键启动完整服务栈（API + PostgreSQL + Nginx），部署到云服务器。

---

## 主要设计决定

- 多阶段 Dockerfile（Node.js 构建前端 + Python 运行后端）
- docker-compose 编排三个服务
- Nginx 反向代理（HTTP + WebSocket）
- 健康检查确保启动顺序
- 环境变量配置（.env.docker 模板）

---

## 涉及模块

- 未在原始文档中识别出明确模块路径

## 实施结果

**变更 ID**: CHANGE-008
**创建时间**: 2026-05-16
**完成时间**: 2026-05-16
**状态**: ✅ 已完成

---

## 需求概述

实现 Docker 容器化部署，支持一键启动完整服务栈（API + PostgreSQL + Nginx），部署到云服务器。

---

## 技术方案

- 多阶段 Dockerfile（Node.js 构建前端 + Python 运行后端）
- docker-compose 编排三个服务
- Nginx 反向代理（HTTP + WebSocket）
- 健康检查确保启动顺序
- 环境变量配置（.env.docker 模板）

---

## 核心变更

### 新增文件

- `Dockerfile` — 多阶段构建（frontend-build → python runtime）
- `docker-compose.yml` — db + api + nginx 三服务编排
- `nginx.conf` — 反向代理配置（含 WebSocket upgrade）
- `.dockerignore` — 排除不必要文件
- `.env.docker` — 部署环境变量模板
- `deploy.sh` — Ubuntu 一键部署脚本（自动装 Docker）
- `deploy-guide.html` — 可视化部署指南

---

## 架构

```
Internet → :80 Nginx → :8000 API (FastAPI + 前端静态文件)
                              ↓
                         :5432 PostgreSQL
```

## docker-compose 服务

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| db | postgres:17-alpine | 5433:5432 | 数据持久化（volume） |
| api | 自建 | 8000 | FastAPI + 前端 + Alembic 迁移 |
| nginx | nginx:alpine | 80:80 | 反向代理 + WebSocket |

---

## 部署流程

```bash
git clone <repo> /opt/xiaoshuo
cp .env.docker .env  # 填入 DEEPSEEK_API_KEY
docker-compose up -d

## 测试与验证

- 总测试项: 6
- 通过: 6
- 失败: 0
- 跳过: 0

## 遗留事项

原始资料未明确记录遗留事项。

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
- `summary.md`
