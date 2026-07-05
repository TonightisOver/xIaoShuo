#!/bin/bash
# xIaoShuo 数据库自动备份脚本
# 用法: ./scripts/backup-db.sh [backup_dir]

set -e

BACKUP_DIR="${1:-/opt/xiaoshuo/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/xiaoshuo_db_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

echo ">>> 开始数据库备份: $(date)"

# 从 Docker 容器导出 PostgreSQL 数据
docker exec xiaoshuo-db-1 pg_dump -U xiaoshuo xiaoshuo | gzip > "$BACKUP_FILE"

echo ">>> 备份完成: $BACKUP_FILE"
echo ">>> 备份大小: $(du -h "$BACKUP_FILE" | cut -f1)"

# 清理 7 天前的备份
find "$BACKUP_DIR" -name "xiaoshuo_db_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo ">>> 已清理 ${RETENTION_DAYS} 天前的旧备份"

echo ">>> 当前备份列表:"
ls -lh "$BACKUP_DIR"
