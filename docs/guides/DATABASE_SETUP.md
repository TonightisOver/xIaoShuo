# PostgreSQL 数据库设置指南

## 前提条件

在运行数据库迁移之前，需要先安装和配置 PostgreSQL。

## 1. 安装 PostgreSQL

### Windows

1. 下载 PostgreSQL 安装程序：
   - 访问 https://www.postgresql.org/download/windows/
   - 下载最新版本（推荐 PostgreSQL 15 或更高版本）

2. 运行安装程序：
   - 记住设置的 postgres 用户密码
   - 默认端口：5432
   - 默认安装路径：`C:\Program Files\PostgreSQL\<version>`

3. 验证安装：
   ```powershell
   psql --version
   ```

### macOS

```bash
# 使用 Homebrew
brew install postgresql@15
brew services start postgresql@15
```

### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## 2. 创建数据库和用户

打开 PowerShell（Windows）或终端（macOS/Linux），执行以下命令：

```powershell
# 连接到 PostgreSQL
psql -U postgres

# 在 psql 提示符下执行：
CREATE DATABASE xiaoshuo;
CREATE USER xiaoshuo WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE xiaoshuo TO xiaoshuo;

# 退出 psql
\q
```

**重要**：将 `your_password_here` 替换为你自己的密码。

## 3. 配置环境变量

编辑项目根目录的 `.env` 文件（如果不存在，从 `.env.example` 复制）：

```bash
# 复制示例文件
cp .env.example .env
```

编辑 `.env`，添加或更新数据库配置：

```env
DATABASE_URL=postgresql+asyncpg://xiaoshuo:your_password_here@localhost:5432/xiaoshuo
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
DATABASE_ECHO=false
```

**注意**：
- 将 `your_password_here` 替换为步骤 2 中设置的密码
- 如果 PostgreSQL 运行在不同的主机或端口，相应修改 URL

## 4. 运行数据库迁移

```bash
# 运行 Alembic 迁移，创建表结构
poetry run alembic upgrade head
```

预期输出：
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> e45b29ed4fe6, initial_schema
```

## 5. 迁移现有 JSON 数据（可选）

如果你有现有的任务数据在 `data/tasks.json`，可以迁移到数据库：

```bash
poetry run python scripts/migrate_json_to_db.py
```

预期输出：
```
INFO:__main__:Database initialized
INFO:__main__:Found X tasks in JSON file
INFO:__main__:Migrated task novel-...
INFO:__main__:Migration complete: X migrated, 0 skipped
INFO:__main__:Original JSON backed up to data/tasks.json.backup
```

## 6. 验证数据库

```powershell
# 连接到数据库
psql -U xiaoshuo -d xiaoshuo

# 查看表结构
\d tasks

# 查看任务数量
SELECT COUNT(*) FROM tasks;

# 查看最近的任务
SELECT task_id, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 5;

# 退出
\q
```

## 7. 启动 API 服务

```bash
poetry run python run_api.py
```

API 应该能够正常启动并连接到数据库。

## 故障排除

### 问题 1：连接被拒绝

**错误**：`could not connect to server: Connection refused`

**解决**：
1. 确认 PostgreSQL 服务正在运行：
   ```powershell
   # Windows
   Get-Service postgresql*
   
   # macOS
   brew services list
   
   # Linux
   sudo systemctl status postgresql
   ```

2. 如果未运行，启动服务：
   ```powershell
   # Windows（以管理员身份）
   Start-Service postgresql-x64-15
   
   # macOS
   brew services start postgresql@15
   
   # Linux
   sudo systemctl start postgresql
   ```

### 问题 2：认证失败

**错误**：`FATAL: password authentication failed for user "xiaoshuo"`

**解决**：
1. 检查 `.env` 文件中的密码是否正确
2. 重新设置用户密码：
   ```sql
   psql -U postgres
   ALTER USER xiaoshuo WITH PASSWORD 'new_password';
   \q
   ```

### 问题 3：数据库不存在

**错误**：`FATAL: database "xiaoshuo" does not exist`

**解决**：
```powershell
psql -U postgres -c "CREATE DATABASE xiaoshuo;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE xiaoshuo TO xiaoshuo;"
```

### 问题 4：asyncpg 安装失败

**错误**：`Microsoft Visual C++ 14.0 or greater is required`

**解决**：
asyncpg 已通过 pip 直接安装预编译版本，不需要编译器。如果仍有问题：
```bash
poetry run pip install asyncpg --only-binary asyncpg --force-reinstall
```

## 下一步

数据库设置完成后，你可以：

1. 运行 API 测试：
   ```bash
   # 创建测试数据库
   psql -U postgres -c "CREATE DATABASE xiaoshuo_test;"
   psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE xiaoshuo_test TO xiaoshuo;"
   
   # 运行测试
   poetry run pytest tests/api/test_routes.py -v
   ```

2. 使用 API 创建任务：
   ```bash
   curl -X POST http://localhost:8000/api/v1/novels \
     -H "Content-Type: application/json" \
     -d '{"idea": "测试创意", "novel_type": "玄幻", "target_words": 50000}'
   ```

3. 查看 API 文档：
   http://localhost:8000/docs
