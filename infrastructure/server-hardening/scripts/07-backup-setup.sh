#!/bin/bash
# ============================================================
#  07-backup-setup.sh — Automated n8n data volume backup
#  Priority: HIGH
#  Risk addressed: Data loss from corruption, failed updates, or deletion
# ============================================================
set -euo pipefail

BACKUP_DIR="/opt/backups/n8n"
BACKUP_SCRIPT="/opt/backups/backup-n8n.sh"
MAX_BACKUPS=14
CRON_SCHEDULE="0 3 * * *"  # Daily at 3:00 AM server time

echo "=== [1/4] Creating backup directory ==="
mkdir -p "$BACKUP_DIR"
echo "  ✅ $BACKUP_DIR"

echo ""
echo "=== [2/4] Deploying backup script ==="
cat > "$BACKUP_SCRIPT" << 'SCRIPT'
#!/bin/bash
# Daily n8n data backup with 14-day rotation
set -euo pipefail

BACKUP_DIR="/opt/backups/n8n"
MAX_BACKUPS=14
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_TAG="[n8n-backup]"

mkdir -p "$BACKUP_DIR"

# Copy the Docker volume data using a temporary alpine container
echo "${LOG_TAG} Starting backup..."
docker run --rm \
  -v n8n_data:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/n8n_${TIMESTAMP}.tar.gz" -C /source .

BACKUP_FILE="${BACKUP_DIR}/n8n_${TIMESTAMP}.tar.gz"
SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
echo "${LOG_TAG} ✅ Backup complete: n8n_${TIMESTAMP}.tar.gz (${SIZE})"

# Rotate old backups (keep last N)
cd "$BACKUP_DIR"
TOTAL=$(ls -1 n8n_*.tar.gz 2>/dev/null | wc -l)
if [ "$TOTAL" -gt "$MAX_BACKUPS" ]; then
  REMOVE=$((TOTAL - MAX_BACKUPS))
  ls -t n8n_*.tar.gz | tail -n "$REMOVE" | while read -r f; do
    rm -f "$f"
    echo "${LOG_TAG} 🗑️ Rotated: $f"
  done
fi

REMAINING=$(ls -1 n8n_*.tar.gz 2>/dev/null | wc -l)
echo "${LOG_TAG} 📦 Backups kept: ${REMAINING}/${MAX_BACKUPS}"
SCRIPT

chmod +x "$BACKUP_SCRIPT"
echo "  ✅ Script deployed: $BACKUP_SCRIPT"

echo ""
echo "=== [3/4] Adding to crontab ==="
# Remove existing backup cron if present, then add fresh
CRON_CMD="${CRON_SCHEDULE} ${BACKUP_SCRIPT} >> /var/log/n8n-backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "backup-n8n.sh") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
echo "  ✅ Cron job installed: ${CRON_SCHEDULE} (daily 3:00 AM)"

echo ""
echo "=== [4/4] Running first backup now ==="
"$BACKUP_SCRIPT"

echo ""
echo "=== RESULT ==="
ls -lh "$BACKUP_DIR"/
echo ""
echo "✅ Backup automation complete."
echo ""
echo "Commands:"
echo "  ${BACKUP_SCRIPT}                    # Run backup manually"
echo "  ls -lh ${BACKUP_DIR}/              # List backups"
echo "  cat /var/log/n8n-backup.log        # View backup logs"
echo "  crontab -l | grep backup           # Verify cron"
echo ""
echo "To restore from a backup:"
echo "  cd /opt/n8n && docker compose down"
echo "  docker run --rm -v n8n_data:/target -v ${BACKUP_DIR}:/backup alpine sh -c 'rm -rf /target/* && tar xzf /backup/n8n_YYYYMMDD_HHMMSS.tar.gz -C /target'"
echo "  docker compose up -d"
