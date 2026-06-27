#!/bin/bash
# ============================================================
#  04-fail2ban-setup.sh — Install & configure Fail2Ban
#  Priority: HIGH
#  Risk addressed: Unlimited brute-force attempts on SSH
# ============================================================
set -euo pipefail

echo "=== [1/4] Installing Fail2Ban ==="
if command -v fail2ban-client &>/dev/null; then
  echo "✅ Fail2Ban is already installed."
else
  apt-get update -qq
  apt-get install -y -qq fail2ban
  echo "✅ Fail2Ban installed."
fi

echo ""
echo "=== [2/4] Creating jail configuration ==="
cat > /etc/fail2ban/jail.local << 'EOF'
# Empire English — Fail2Ban Configuration
# Created by server-hardening automation

[DEFAULT]
# Ban for 1 hour by default
bantime = 3600
# Look for failures within 10 minutes
findtime = 600
# Allow 3 retries before ban
maxretry = 3
# Use UFW as the ban action (integrates with our firewall)
banaction = ufw

[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
# SSH gets stricter: ban for 24 hours after 3 failures
maxretry = 3
bantime = 86400
findtime = 600
EOF
echo "✅ Jail configuration written to /etc/fail2ban/jail.local"

echo ""
echo "=== [3/4] Enabling and starting Fail2Ban ==="
systemctl enable fail2ban
systemctl restart fail2ban
echo "✅ Fail2Ban enabled and running."

echo ""
echo "=== [4/4] Verifying SSH jail ==="
sleep 2
fail2ban-client status sshd

echo ""
echo "=== RESULT ==="
echo "✅ Fail2Ban setup complete."
echo ""
echo "Useful commands:"
echo "  fail2ban-client status sshd        # Check SSH jail status"
echo "  fail2ban-client get sshd banip     # List banned IPs"
echo "  fail2ban-client set sshd unbanip <IP>  # Unban an IP"
echo "  journalctl -u fail2ban -f          # Watch fail2ban logs"
