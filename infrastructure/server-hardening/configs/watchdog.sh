#!/bin/bash
# ============================================================
#  Empire Server Health Monitor (watchdog.sh)
#  Location on server: /opt/monitor/watchdog.sh
#  Runs every 60 seconds via systemd timer
#
#  Features:
#    - CPU / RAM / Disk threshold monitoring
#    - n8n container health check + auto-restart
#    - Cloudflare Tunnel health check + auto-restart
#    - Telegram alerts with full incident details
#    - Deduplication: won't spam the same alert repeatedly
# ============================================================
set -uo pipefail

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION — EDIT THESE TWO VALUES
# ═══════════════════════════════════════════════════════════════
TELEGRAM_TOKEN="YOUR_BOT_TOKEN_HERE"
ADMIN_CHAT_ID="YOUR_CHAT_ID_HERE"
# ═══════════════════════════════════════════════════════════════

HOSTNAME="empire-n8n"
STATE_DIR="/opt/monitor/state"
mkdir -p "$STATE_DIR"

# Thresholds
CPU_WARN=80
CPU_CRIT=90
RAM_WARN=80
RAM_CRIT=90
DISK_WARN=80
DISK_CRIT=90

# Cooldown: don't re-alert for the same issue within this many seconds
ALERT_COOLDOWN=900  # 15 minutes

# ═══════════════════════════════════════════════════════════════
#  FUNCTIONS
# ═══════════════════════════════════════════════════════════════

send_telegram() {
  local msg="$1"
  if [ "$TELEGRAM_TOKEN" = "YOUR_BOT_TOKEN_HERE" ] || [ "$ADMIN_CHAT_ID" = "YOUR_CHAT_ID_HERE" ]; then
    echo "[ALERT - NOT SENT - TOKEN NOT CONFIGURED] $msg"
    return 1
  fi
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="${ADMIN_CHAT_ID}" \
    -d parse_mode="HTML" \
    -d text="$msg" > /dev/null 2>&1
}

# Check if we've already alerted for this issue within cooldown period
should_alert() {
  local issue_id="$1"
  local state_file="${STATE_DIR}/${issue_id}"
  if [ -f "$state_file" ]; then
    local last_alert=$(cat "$state_file")
    local now=$(date +%s)
    local diff=$((now - last_alert))
    if [ "$diff" -lt "$ALERT_COOLDOWN" ]; then
      return 1  # Don't alert (within cooldown)
    fi
  fi
  date +%s > "$state_file"
  return 0  # Do alert
}

# Clear alert state when issue resolves
clear_alert() {
  local issue_id="$1"
  rm -f "${STATE_DIR}/${issue_id}"
}

get_cpu() {
  # Average of two samples (more accurate than single snapshot)
  top -bn2 -d1 | grep "Cpu(s)" | tail -1 | awk '{print int($2+$4)}'
}

get_ram() {
  free | awk '/Mem:/{printf "%.0f", $3/$2*100}'
}

get_disk() {
  df / | awk 'NR==2{print int($5)}'
}

restart_n8n() {
  echo "[$(date)] Attempting n8n restart..."
  cd /opt/n8n && docker compose restart 2>&1
  sleep 15
  if curl -sf -o /dev/null -m 5 http://localhost:5678/ 2>/dev/null; then
    echo "recovered"
  else
    echo "failed"
  fi
}

restart_tunnel() {
  echo "[$(date)] Attempting cloudflared restart..."
  systemctl restart cloudflared 2>&1
  sleep 10
  if systemctl is-active --quiet cloudflared; then
    echo "recovered"
  else
    echo "failed"
  fi
}

# ═══════════════════════════════════════════════════════════════
#  MAIN CHECKS
# ═══════════════════════════════════════════════════════════════

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
CPU=$(get_cpu)
RAM=$(get_ram)
DISK=$(get_disk)
SYSTEM_LINE="CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%"

# --- RAM Check ---
if [ "$RAM" -ge "$RAM_CRIT" ]; then
  if should_alert "ram_critical"; then
    RESULT=$(restart_n8n)
    RAM_AFTER=$(get_ram)
    if [ "$RESULT" = "recovered" ] && [ "$RAM_AFTER" -lt "$RAM_CRIT" ]; then
      send_telegram "$(echo -e "🟢 <b>RESOLVED: ${HOSTNAME}</b>\n\n📍 RAM was at ${RAM}% (critical)\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n🔄 Recovery: n8n restarted\n✅ RAM now at ${RAM_AFTER}%\n\nStatus: OPERATIONAL")"
      clear_alert "ram_critical"
    else
      send_telegram "$(echo -e "🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 RAM at ${RAM}% — OOM imminent\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n🔄 Recovery: n8n restarted\n❌ RAM still at ${RAM_AFTER}%\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250")"
    fi
  fi
elif [ "$RAM" -ge "$RAM_WARN" ]; then
  if should_alert "ram_warning"; then
    send_telegram "$(echo -e "⚠️ <b>WARNING: ${HOSTNAME}</b>\n\n📍 RAM usage at ${RAM}%\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n💡 Approaching critical (${RAM_CRIT}%)")"
  fi
else
  clear_alert "ram_critical"
  clear_alert "ram_warning"
fi

# --- Disk Check ---
if [ "$DISK" -ge "$DISK_CRIT" ]; then
  if should_alert "disk_critical"; then
    send_telegram "$(echo -e "🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 Disk usage at ${DISK}%\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n💡 Run: docker system prune -f\n⚠️ Server may crash if disk fills")"
  fi
elif [ "$DISK" -ge "$DISK_WARN" ]; then
  if should_alert "disk_warning"; then
    send_telegram "$(echo -e "⚠️ <b>WARNING: ${HOSTNAME}</b>\n\n📍 Disk at ${DISK}%\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n💡 Run: docker system prune -f")"
  fi
else
  clear_alert "disk_critical"
  clear_alert "disk_warning"
fi

# --- CPU Check ---
if [ "$CPU" -ge "$CPU_CRIT" ]; then
  if should_alert "cpu_critical"; then
    TOP_PROCS=$(ps aux --sort=-%cpu | head -4 | tail -3 | awk '{printf "  %s (%s%%)\n", $11, $3}')
    send_telegram "$(echo -e "🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 CPU at ${CPU}%\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n🔝 Top processes:\n${TOP_PROCS}")"
  fi
elif [ "$CPU" -ge "$CPU_WARN" ]; then
  if should_alert "cpu_warning"; then
    send_telegram "$(echo -e "⚠️ <b>WARNING: ${HOSTNAME}</b>\n\n📍 CPU at ${CPU}%\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}")"
  fi
else
  clear_alert "cpu_critical"
  clear_alert "cpu_warning"
fi

# --- n8n Health Check ---
N8N_OK=true
if ! curl -sf -o /dev/null -m 5 http://localhost:5678/ 2>/dev/null; then
  N8N_OK=false
fi

if [ "$N8N_OK" = false ]; then
  if should_alert "n8n_down"; then
    RESULT=$(restart_n8n)
    if [ "$RESULT" = "recovered" ]; then
      send_telegram "$(echo -e "🟢 <b>RESOLVED: ${HOSTNAME}</b>\n\n📍 n8n was unreachable\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n🔄 Recovery: Container restarted\n✅ Service restored")"
      clear_alert "n8n_down"
    else
      send_telegram "$(echo -e "🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 n8n DOWN — restart FAILED\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250\nLogs: docker compose -f /opt/n8n/docker-compose.yml logs --tail=30")"
    fi
  fi
else
  clear_alert "n8n_down"
fi

# --- Cloudflare Tunnel Health Check ---
TUNNEL_OK=true
if ! systemctl is-active --quiet cloudflared; then
  TUNNEL_OK=false
fi

if [ "$TUNNEL_OK" = false ]; then
  if should_alert "tunnel_down"; then
    RESULT=$(restart_tunnel)
    if [ "$RESULT" = "recovered" ]; then
      send_telegram "$(echo -e "🟢 <b>RESOLVED: ${HOSTNAME}</b>\n\n📍 Cloudflare Tunnel was down\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n🔄 Recovery: Service restarted\n✅ Tunnel restored")"
      clear_alert "tunnel_down"
    else
      send_telegram "$(echo -e "🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 Cloudflare Tunnel DOWN — restart FAILED\n⏰ ${TIMESTAMP}\n📊 ${SYSTEM_LINE}\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250\nLogs: journalctl -u cloudflared --no-pager -n 20")"
    fi
  fi
else
  clear_alert "tunnel_down"
fi

# --- All OK (silent unless debugging) ---
if [ "$N8N_OK" = true ] && [ "$TUNNEL_OK" = true ] && [ "$RAM" -lt "$RAM_WARN" ] && [ "$DISK" -lt "$DISK_WARN" ] && [ "$CPU" -lt "$CPU_WARN" ]; then
  echo "[$(date)] ✅ All systems healthy: ${SYSTEM_LINE}"
fi
