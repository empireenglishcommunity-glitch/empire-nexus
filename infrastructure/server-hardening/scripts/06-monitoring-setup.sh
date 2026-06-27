#!/bin/bash
# ============================================================
#  06-monitoring-setup.sh — Deploy Telegram monitoring & alerting
#  Priority: CRITICAL
#  Risk addressed: Silent service failures, no visibility into health
# ============================================================
set -euo pipefail

MONITOR_DIR="/opt/monitor"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIGS_DIR="$(dirname "$SCRIPT_DIR")/configs"
SYSTEMD_DIR="$(dirname "$SCRIPT_DIR")/systemd"

echo "=== [1/5] Creating monitoring directory ==="
mkdir -p "$MONITOR_DIR"

echo ""
echo "=== [2/5] Deploying watchdog script ==="
cp "${CONFIGS_DIR}/watchdog.sh" "${MONITOR_DIR}/watchdog.sh"
chmod +x "${MONITOR_DIR}/watchdog.sh"
echo "  ✅ Deployed to ${MONITOR_DIR}/watchdog.sh"

echo ""
echo "=== [3/5] Checking configuration ==="
if grep -q "YOUR_BOT_TOKEN_HERE" "${MONITOR_DIR}/watchdog.sh"; then
  echo ""
  echo "  ⚠️  IMPORTANT: You must configure the watchdog before it will send alerts!"
  echo ""
  echo "  Edit: ${MONITOR_DIR}/watchdog.sh"
  echo "  Set these two values:"
  echo "    TELEGRAM_TOKEN=\"your-bot-token-from-botfather\""
  echo "    ADMIN_CHAT_ID=\"your-chat-id-from-userinfobot\""
  echo ""
  echo "  After editing, test with: ${MONITOR_DIR}/watchdog.sh"
  echo ""
fi

echo ""
echo "=== [4/5] Installing systemd service and timer ==="
cp "${SYSTEMD_DIR}/empire-monitor.service" /etc/systemd/system/
cp "${SYSTEMD_DIR}/empire-monitor.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable empire-monitor.timer
systemctl start empire-monitor.timer
echo "  ✅ Systemd timer installed and started (runs every 60s)."

echo ""
echo "=== [5/5] Verifying timer ==="
systemctl status empire-monitor.timer --no-pager
echo ""
systemctl list-timers | grep empire || true

echo ""
echo "=== RESULT ==="
echo "✅ Monitoring system deployed."
echo ""
echo "Files:"
echo "  Script:  ${MONITOR_DIR}/watchdog.sh"
echo "  Service: /etc/systemd/system/empire-monitor.service"
echo "  Timer:   /etc/systemd/system/empire-monitor.timer"
echo ""
echo "Commands:"
echo "  systemctl status empire-monitor.timer    # Timer status"
echo "  journalctl -u empire-monitor -f          # Watch monitor logs"
echo "  ${MONITOR_DIR}/watchdog.sh               # Run manually (test)"
echo ""
echo "⚠️  NEXT STEP: Configure TELEGRAM_TOKEN and ADMIN_CHAT_ID in ${MONITOR_DIR}/watchdog.sh"
