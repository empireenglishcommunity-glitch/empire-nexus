#!/bin/bash
# ============================================================
#  Empire English — Server Hardening Master Deployment
# ============================================================
#
#  This script runs ALL hardening steps in the correct order.
#  It is safe to run multiple times (all scripts are idempotent).
#
#  USAGE:
#    # Run everything:
#    sudo bash deploy.sh
#
#    # Run a specific step only:
#    sudo bash deploy.sh --only 1     # Just swap
#    sudo bash deploy.sh --only 3     # Just SSH hardening
#
#  PREREQUISITES:
#    - Root access (sudo or root user)
#    - Internet connection (for apt installs)
#    - This entire server-hardening/ directory uploaded to the server
#
#  EXECUTION ORDER (by dependency):
#    1. Swap (no deps — enables safe memory for all following steps)
#    2. Firewall (no deps — closes exposed ports immediately)
#    3. SSH hardening (no deps — locks down authentication)
#    4. Fail2Ban (requires: SSH config done)
#    5. Docker hardening (requires: swap exists for safe OOM handling)
#    6. Monitoring (requires: Docker running for health checks)
#    7. Backup (requires: Docker running, n8n_data volume exists)
#
# ============================================================
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="${SCRIPT_DIR}/scripts"
LOG_FILE="/var/log/empire-hardening.log"

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

banner() {
  echo ""
  echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}  $1${NC}"
  echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
  echo ""
}

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error()   { echo -e "${RED}❌ $1${NC}"; }

run_step() {
  local num="$1"
  local name="$2"
  local script="$3"

  banner "STEP ${num}/7: ${name}"

  if [ ! -f "${SCRIPTS}/${script}" ]; then
    error "Script not found: ${SCRIPTS}/${script}"
    return 1
  fi

  bash "${SCRIPTS}/${script}" 2>&1 | tee -a "$LOG_FILE"
  local rc=${PIPESTATUS[0]}

  if [ $rc -eq 0 ]; then
    success "Step ${num} complete: ${name}"
  else
    error "Step ${num} FAILED: ${name} (exit code: $rc)"
    warning "Check log: $LOG_FILE"
    warning "You can re-run this step with: sudo bash deploy.sh --only ${num}"
    return $rc
  fi
  echo ""
}

# ═══════════════════════════════════════════════════════════════
#  PRE-FLIGHT CHECKS
# ═══════════════════════════════════════════════════════════════

if [ "$(id -u)" -ne 0 ]; then
  error "This script must be run as root. Use: sudo bash deploy.sh"
  exit 1
fi

if [ ! -d "$SCRIPTS" ]; then
  error "Scripts directory not found at: $SCRIPTS"
  error "Make sure you're running from the server-hardening/ directory."
  exit 1
fi

# ═══════════════════════════════════════════════════════════════
#  PARSE ARGUMENTS
# ═══════════════════════════════════════════════════════════════

ONLY_STEP=""
if [ "${1:-}" = "--only" ] && [ -n "${2:-}" ]; then
  ONLY_STEP="$2"
fi

# ═══════════════════════════════════════════════════════════════
#  EXECUTION
# ═══════════════════════════════════════════════════════════════

echo "" | tee -a "$LOG_FILE"
echo "╔══════════════════════════════════════════════════════════════╗" | tee -a "$LOG_FILE"
echo "║   EMPIRE ENGLISH — SERVER HARDENING DEPLOYMENT              ║" | tee -a "$LOG_FILE"
echo "║   Server: empire-n8n (Hetzner CX23)                        ║" | tee -a "$LOG_FILE"
echo "║   Date: $(date '+%Y-%m-%d %H:%M:%S %Z')                    ║" | tee -a "$LOG_FILE"
echo "╚══════════════════════════════════════════════════════════════╝" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ -n "$ONLY_STEP" ]; then
  warning "Running ONLY step ${ONLY_STEP}"
  echo ""
fi

FAILED=0

# Step 1: Swap
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "1" ]; then
  run_step 1 "Swap Setup (2GB)" "01-swap-setup.sh" || FAILED=$((FAILED+1))
fi

# Step 2: Firewall
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "2" ]; then
  run_step 2 "Firewall Hardening" "02-firewall-hardening.sh" || FAILED=$((FAILED+1))
fi

# Step 3: SSH
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "3" ]; then
  run_step 3 "SSH Hardening" "03-ssh-hardening.sh" || FAILED=$((FAILED+1))
  if [ -z "$ONLY_STEP" ]; then
    echo ""
    warning "SSH was restarted. Verify you can still connect from another terminal!"
    warning "Press Enter to continue (or Ctrl+C to abort)..."
    read -r
  fi
fi

# Step 4: Fail2Ban
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "4" ]; then
  run_step 4 "Fail2Ban Setup" "04-fail2ban-setup.sh" || FAILED=$((FAILED+1))
fi

# Step 5: Docker
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "5" ]; then
  run_step 5 "Docker Hardening" "05-docker-hardening.sh" || FAILED=$((FAILED+1))
fi

# Step 6: Monitoring
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "6" ]; then
  run_step 6 "Telegram Monitoring" "06-monitoring-setup.sh" || FAILED=$((FAILED+1))
fi

# Step 7: Backup
if [ -z "$ONLY_STEP" ] || [ "$ONLY_STEP" = "7" ]; then
  run_step 7 "Automated Backup" "07-backup-setup.sh" || FAILED=$((FAILED+1))
fi

# ═══════════════════════════════════════════════════════════════
#  SUMMARY
# ═══════════════════════════════════════════════════════════════

banner "DEPLOYMENT SUMMARY"

if [ $FAILED -eq 0 ]; then
  success "All steps completed successfully!"
else
  error "${FAILED} step(s) had errors. Check log: $LOG_FILE"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  POST-DEPLOYMENT CHECKLIST:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  1. ✅ Verify SSH still works:  ssh root@77.42.43.250"
echo "  2. ✅ Verify n8n via tunnel:   https://bot.empireenglish.online"
echo "  3. ❌ Verify port 5678 closed: http://77.42.43.250:5678 (should fail)"
echo "  4. 📝 Configure monitoring:    Edit /opt/monitor/watchdog.sh"
echo "        Set TELEGRAM_TOKEN and ADMIN_CHAT_ID"
echo "  5. 🧪 Test monitoring:         /opt/monitor/watchdog.sh"
echo "  6. 📊 Check container health:  docker inspect --format='{{.State.Health.Status}}' empire-n8n"
echo ""
echo "  Full log: $LOG_FILE"
echo ""

if [ $FAILED -gt 0 ]; then
  exit 1
fi
