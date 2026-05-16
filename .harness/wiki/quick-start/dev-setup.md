# 开发环境搭建

## 前提条件

- Python 3.14+
- Poetry 1.8+
- PostgreSQL 15+（端口 5433）
- Node.js 20+（前端构建）
- DeepSeek API Key

## 步骤

### 1. 克隆代码

```bash
git clone https://github.com/TonightisOver/xIaoShuo.git
cd xIaoShuo
```

### 2. 安装 Python 依赖

```bash
poetry install
```

注意：asyncpg 需要单独安装（避免编译问题）：
```bash
poetry run pip install asyncpg --only-binary asyncpg
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入：
# - DEEPSEEK_API_KEY
# - DATABASE_URL（指向本地 PostgreSQL）
```

### 4. 数据库设置

```bash
# 创建数据库
psql -U postgres -p 5433 -c "CREATE DATABASE xiaoshuo;"
psql -U postgres -p 5433 -c "CREATE USER xiaoshuo WITH PASSWORD 'xiaoshuo2026';"
psql -U postgres -p 5433 -c "GRANT ALL PRIVILEGES ON DATABASE xiaoshuo TO xiaoshuo;"

# 运行迁移
poetry run alembic upgrade head
```

### 5. 前端构建

```bash
cd frontend
npm install
npm run build
cd ..
```

### 6. 启动服务

```bash
poetry run python run_api.py
# 访问 http://localhost:8000
```

### 7. 运行测试

```bash
# 创建测试数据库
psql -U postgres -p 5433 -c "CREATE DATABASE xiaoshuo_test;"
psql -U postgres -p 5433 -c "GRANT ALL PRIVILEGES ON DATABASE xiaoshuo_test TO xiaoshuo;"

# 运行测试
poetry run pytest tests/api/ -v
```

## 前端开发模式

```bash
cd frontend
npm run dev
# Vite dev server 在 http://localhost:5173，自动代理 API 到 8000
```
