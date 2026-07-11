# ─── 阶段 1：前端构建 ───
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# ─── 阶段 2：API 镜像 ───
FROM python:3.14-slim AS api
WORKDIR /app

# asyncpg 是纯协议实现（不需要 libpq），但其 C 扩展可能需要 gcc 编译
# （通常有预编译 wheel，保留 gcc 作为源码编译 fallback，避免网络问题导致构建失败）
RUN sed -i \
    -e "s|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g" \
    -e "s|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g" \
    /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl gcc && \
    rm -rf /var/lib/apt/lists/*

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry config installer.max-workers 1 && \
    (poetry config requests.max-retries 5 || true)

COPY pyproject.toml poetry.lock* ./
RUN poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple || true
RUN poetry lock --no-interaction && poetry install --only main --no-root --no-interaction

COPY src/ ./src/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY run_api.py ./

COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

# 启动：先跑 alembic 迁移（async 引擎，asyncpg），再启动 API
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && python run_api.py"]

# ─── 阶段 3：Nginx 镜像（自带前端 dist，无需宿主机挂载）───
FROM nginx:alpine AS nginx
# 把前端构建产物打进 nginx 镜像，消除对宿主机 ./frontend/dist 的依赖
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
# nginx.conf 由 compose 挂载（便于配置变更无需重建）
