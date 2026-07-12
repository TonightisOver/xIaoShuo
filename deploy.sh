#!/bin/bash
# xIaoShuo 一键部署脚本（Ubuntu）
# 用法: bash deploy.sh

set -e

echo "=== xIaoShuo 部署开始 ==="

# 1. 安装 Docker（如果未安装）
if ! command -v docker &> /dev/null; then
    echo ">>> 安装 Docker..."
    apt-get update
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    echo ">>> Docker 安装完成"
else
    echo ">>> Docker 已安装"
fi

# 2. 创建项目目录
PROJECT_DIR=/opt/xiaoshuo
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

echo ">>> 项目目录: $PROJECT_DIR"

# 3. 创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo ">>> 创建 .env 配置文件..."
    cat > .env << 'EOF'
# DeepSeek API（必填）
DEEPSEEK_API_KEY=your-api-key-here

# 数据库密码
DB_PASSWORD=xiaoshuo2026

# 可选配置
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_MODEL_FLASH=deepseek-v4-flash
LOG_LEVEL=INFO

# LLM 加密密钥（首次部署需生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"）
LLM_ENCRYPTION_KEY=

# 管理员令牌（访问 LLM 配置接口用，可自定义随机字符串）
ADMIN_TOKEN=
EOF
    echo ""
    echo "!!! 请编辑 .env 填入以下必填项 !!!"
    echo "    DEEPSEEK_API_KEY  - DeepSeek API 密钥"
    echo "    LLM_ENCRYPTION_KEY - 运行上方注释中的命令生成"
    echo "    ADMIN_TOKEN       - 自定义管理员令牌"
    echo "    nano $PROJECT_DIR/.env"
    echo ""
fi

echo "=== 部署准备完成 ==="
echo ""
echo "下一步："
echo "  1. 编辑 .env:  nano $PROJECT_DIR/.env"
echo "  2. 上传代码到 $PROJECT_DIR（scp 或 git clone）"
echo "  3. 启动服务:  cd $PROJECT_DIR && docker compose up -d --build"
echo "  4. 查看日志:  docker compose logs -f api"
echo "  5. 健康检查:  curl http://localhost:8000/api/v1/health"
echo ""
echo "服务启动后访问: http://$(hostname -I | awk '{print $1}'):7000"
