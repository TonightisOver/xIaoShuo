FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim
WORKDIR /app

RUN sed -i \
    -e "s|http://deb.debian.org/debian-security|http://mirrors.aliyun.com/debian-security|g" \
    -e "s|http://deb.debian.org/debian|http://mirrors.aliyun.com/debian|g" \
    /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
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

CMD ["sh", "-c", "alembic upgrade head && python run_api.py"]
