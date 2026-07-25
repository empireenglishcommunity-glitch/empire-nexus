#!/usr/bin/env bash
#
# Off-site backup — push the newest learning-bot DB backup to Cloudflare R2.
#
# WHY: scripts/backup.py keeps 14 rolling local backups, but they live on the
# SAME server/volume as the live database. If that box or volume is lost, the
# backups are lost with it. This copies the newest backup OFF the server every
# night so a total-server-loss is recoverable.
#
# It runs AFTER the local daily backup (which the cron fires at 03:10), reads
# the newest DB from the bot's backup docker volume, and uploads it to R2.
#
# ── One-time setup (server) ──────────────────────────────────────────────
#  1) Cloudflare dashboard → R2 → create a bucket (default: empire-english-backups)
#     and an R2 API token with "Object Read & Write". Note the Access Key ID,
#     Secret Access Key, and your account's S3 endpoint:
#        https://<ACCOUNT_ID>.r2.cloudflarestorage.com
#  2) Install rclone (single static binary):
#        curl https://rclone.org/install.sh | sudo bash
#  3) Configure the remote (creds live ONLY on this server, never in git):
#        rclone config create r2 s3 provider=Cloudflare \
#          access_key_id=<KEY> secret_access_key=<SECRET> \
#          endpoint=https://<ACCOUNT_ID>.r2.cloudflarestorage.com acl=private
#  4) Add the cron (runs 10 min after the local backup):
#        20 3 * * * /opt/empire-english-bot/offsite_backup.sh >> /var/log/learning-bot-offsite.log 2>&1
#
# Retention off-site: files are small (~0.5 MB/day). Either leave them, or set
# an R2 lifecycle rule to expire objects after N days; this script also prunes
# copies older than R2_RETENTION_DAYS (default 90) as a belt-and-braces step.
# ─────────────────────────────────────────────────────────────────────────
set -euo pipefail

REMOTE_NAME="${R2_REMOTE:-r2}"
BUCKET="${R2_BUCKET:-empire-english-backups}"
RETENTION_DAYS="${R2_RETENTION_DAYS:-90}"
SRC_DIR="/var/lib/docker/volumes/empire-english-bot_bot-backups/_data"
DEST="${REMOTE_NAME}:${BUCKET}/learning-bot"

ts() { date -Is; }

if ! command -v rclone >/dev/null 2>&1; then
    echo "$(ts) ERROR: rclone not installed — see setup notes in this script." >&2
    exit 1
fi

# Newest local backup by modification time (works for daily + tagged names).
newest="$(ls -t "${SRC_DIR}"/empire_english_*.db 2>/dev/null | head -1 || true)"
if [ -z "${newest}" ]; then
    echo "$(ts) ERROR: no local backup found in ${SRC_DIR}" >&2
    exit 1
fi

echo "$(ts) Uploading $(basename "${newest}") ($(du -h "${newest}" | cut -f1)) -> ${DEST}/"
rclone copy "${newest}" "${DEST}/" --s3-no-check-bucket
echo "$(ts) OK: off-site copy complete"

# Belt-and-braces retention (R2 lifecycle rules are the primary mechanism).
if [ "${RETENTION_DAYS}" -gt 0 ] 2>/dev/null; then
    rclone delete --min-age "${RETENTION_DAYS}d" "${DEST}/" 2>/dev/null || true
    echo "$(ts) Pruned off-site copies older than ${RETENTION_DAYS} days"
fi
