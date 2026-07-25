#!/usr/bin/env bash
#
# Backup freshness alert — pings the ops Telegram if the LOCAL or the OFF-SITE
# (R2) database backup is missing or older than ~26h.
#
# WHY: the daily backup silently self-deleted for a week before anyone noticed
# (a filename-sort rotation bug). A backup you don't monitor is a backup you
# can't trust. This is the tripwire: run it daily, AFTER both backups, and it
# shouts on Telegram the moment either one stops being fresh. Silent on success
# (no daily noise) — it only messages when something is wrong.
#
# Alerts go via the same ops bot the system already uses (OPS_BOT_TOKEN /
# OPS_CHAT_ID from the bot's .env — never hard-coded here).
#
# Cron (after the 03:10 local + 03:20 off-site backups):
#   0 4 * * * /opt/empire-english-bot/backup_healthcheck.sh >> /var/log/learning-bot-backup-health.log 2>&1
#
# Run with `--test` to send a one-off confirmation message (proves delivery).
# ─────────────────────────────────────────────────────────────────────────
set -uo pipefail

ENV_FILE="${BOT_ENV_FILE:-/opt/empire-english-bot/.env}"
VOL="/var/lib/docker/volumes/empire-english-bot_bot-backups/_data"
REMOTE="${R2_REMOTE:-r2}:${R2_BUCKET:-empire-english-backups}/learning-bot"
MAX_AGE="26h"
MAX_MIN=1560   # 26h in minutes

getenv() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'\'' '; }
TOKEN="$(getenv OPS_BOT_TOKEN)"
CHAT="$(getenv OPS_CHAT_ID)"

send_tg() {
    # $1 = message text
    if [ -z "${TOKEN}" ] || [ -z "${CHAT}" ]; then
        echo "$(date -Is) WARN: OPS_BOT_TOKEN/OPS_CHAT_ID not found in ${ENV_FILE}; cannot send Telegram" >&2
        return 0
    fi
    curl -s -o /dev/null --max-time 20 \
        --data "chat_id=${CHAT}" \
        --data-urlencode "text=$1" \
        "https://api.telegram.org/bot${TOKEN}/sendMessage" || true
}

# --test: prove Telegram delivery works, then exit.
if [ "${1:-}" = "--test" ]; then
    send_tg "✅ Empire English — backup healthcheck is active. You'll only hear from this again if a backup goes missing or stale."
    echo "$(date -Is) test message sent"
    exit 0
fi

problems=""

# Local backup fresh?
if [ -z "$(find "${VOL}" -name 'empire_english_*.db' -mmin "-${MAX_MIN}" 2>/dev/null | head -1)" ]; then
    problems="${problems}
• No LOCAL backup newer than ${MAX_AGE} (${VOL})."
fi

# Off-site (R2) backup fresh?
if command -v rclone >/dev/null 2>&1; then
    if [ -z "$(rclone lsf --max-age "${MAX_AGE}" "${REMOTE}/" 2>/dev/null | head -1)" ]; then
        problems="${problems}
• No OFF-SITE (R2) backup newer than ${MAX_AGE} (${REMOTE})."
    fi
else
    problems="${problems}
• rclone not installed — off-site backup cannot run."
fi

if [ -n "${problems}" ]; then
    echo "$(date -Is) ALERT:${problems}"
    send_tg "⚠️ Empire English BACKUP problem — investigate:${problems}"
    exit 1
fi

echo "$(date -Is) OK: local + off-site backups are both fresh (< ${MAX_AGE})"
