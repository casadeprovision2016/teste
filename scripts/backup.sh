#!/bin/bash
# scripts/backup.sh
# Production backup script for Edital Processor

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/edital-processor}"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "🚀 Starting backup process - $DATE"

# 1. Database backup
echo "📋 Backing up SQLite database..."
docker exec edital-api cp /app/data/editais.db /app/data/editais_backup_$DATE.db
docker cp edital-api:/app/data/editais_backup_$DATE.db "$BACKUP_DIR/db_backup_$DATE.db"
docker exec edital-api rm /app/data/editais_backup_$DATE.db

# 2. Storage backup (processed files)
echo "📁 Backing up storage files..."
if [ -d "storage" ]; then
    tar -czf "$BACKUP_DIR/storage_backup_$DATE.tar.gz" storage/
fi

# 3. Logs backup
echo "📜 Backing up logs..."
if [ -d "logs" ]; then
    tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" logs/
fi

# 4. Configuration backup
echo "⚙️ Backing up configuration..."
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
    docker-compose.yml \
    .env \
    nginx/ \
    scripts/ \
    2>/dev/null || true

# 5. Cleanup old backups
echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -type f -name "*.db" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -type f -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# 6. Generate backup report
echo "📊 Generating backup report..."
BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR" | wc -l)

cat > "$BACKUP_DIR/backup_report_$DATE.txt" << EOF
Edital Processor Backup Report
==============================
Date: $DATE
Backup Directory: $BACKUP_DIR
Total Size: $BACKUP_SIZE
Total Files: $BACKUP_COUNT

Files Created:
- db_backup_$DATE.db (SQLite database)
- storage_backup_$DATE.tar.gz (processed files)
- logs_backup_$DATE.tar.gz (application logs)
- config_backup_$DATE.tar.gz (configuration files)

Retention Policy: $RETENTION_DAYS days
Status: ✅ SUCCESS
EOF

echo "✅ Backup completed successfully!"
echo "   Backup location: $BACKUP_DIR"
echo "   Total size: $BACKUP_SIZE"

# Optional: Send notification (uncomment and configure as needed)
# curl -X POST "https://your-webhook-url" -H "Content-Type: application/json" \
#   -d "{\"text\": \"✅ Edital Processor backup completed successfully ($BACKUP_SIZE)\"}"