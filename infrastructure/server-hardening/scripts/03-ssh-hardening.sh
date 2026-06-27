#!/bin/bash
# ============================================================
#  03-ssh-hardening.sh — Verify & enforce SSH security settings
#  Priority: CRITICAL
#  Risk addressed: Unverified password auth + weak default settings
# ============================================================
set -euo pipefail

SSHD_CONFIG="/etc/ssh/sshd_config"
BACKUP="${SSHD_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"

echo "=== [1/5] Backing up current sshd_config ==="
cp "$SSHD_CONFIG" "$BACKUP"
echo "✅ Backup saved to: $BACKUP"

echo ""
echo "=== [2/5] Current authentication settings ==="
echo "--- Before changes ---"
grep -E "^#*(PasswordAuthentication|PubkeyAuthentication|KbdInteractiveAuthentication|ChallengeResponseAuthentication|MaxAuthTries|ClientAliveInterval|ClientAliveCountMax|PermitRootLogin)" "$SSHD_CONFIG" || echo "(no matching lines found — using defaults)"

echo ""
echo "=== [3/5] Enforcing secure SSH settings ==="

# Function to set a config value (uncomments if needed, replaces if exists)
set_sshd_option() {
  local key="$1" value="$2"
  if grep -qE "^#*${key}\s" "$SSHD_CONFIG"; then
    sed -i "s/^#*${key}\s.*/${key} ${value}/" "$SSHD_CONFIG"
  else
    echo "${key} ${value}" >> "$SSHD_CONFIG"
  fi
  echo "  ✅ ${key} = ${value}"
}

# Disable password authentication (CRITICAL)
set_sshd_option "PasswordAuthentication" "no"

# Disable keyboard-interactive (another password vector)
set_sshd_option "KbdInteractiveAuthentication" "no"

# Ensure public key auth is enabled
set_sshd_option "PubkeyAuthentication" "yes"

# Limit auth attempts to reduce brute-force window
set_sshd_option "MaxAuthTries" "3"

# Idle session timeout (5 min idle = disconnect)
set_sshd_option "ClientAliveInterval" "300"
set_sshd_option "ClientAliveCountMax" "2"

# Disable empty passwords
set_sshd_option "PermitEmptyPasswords" "no"

echo ""
echo "=== [4/5] Validating sshd_config syntax ==="
if sshd -t 2>&1; then
  echo "✅ Configuration syntax is valid."
else
  echo "❌ Syntax error detected! Restoring backup..."
  cp "$BACKUP" "$SSHD_CONFIG"
  echo "⚠️  Original config restored. Fix the issue manually."
  exit 1
fi

echo ""
echo "=== [5/5] Restarting SSH daemon ==="
systemctl restart sshd
echo "✅ SSH daemon restarted with hardened settings."

echo ""
echo "=== RESULT ==="
echo "--- Active settings ---"
grep -E "^(PasswordAuthentication|PubkeyAuthentication|KbdInteractiveAuthentication|MaxAuthTries|ClientAliveInterval|ClientAliveCountMax|PermitEmptyPasswords)" "$SSHD_CONFIG"
echo ""
echo "✅ SSH hardening complete."
echo ""
echo "⚠️  CRITICAL: Test SSH from a SECOND terminal NOW before closing this session!"
echo "    Run: ssh root@77.42.43.250"
echo "    If it fails, restore backup: cp $BACKUP $SSHD_CONFIG && systemctl restart sshd"
