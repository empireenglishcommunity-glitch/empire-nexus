#!/bin/bash
# ============================================================
#  02-firewall-hardening.sh — Close port 5678 + rate-limit SSH
#  Priority: CRITICAL (port 5678) + MEDIUM (SSH rate limit)
#  Risk addressed: n8n admin exposed on public IP; SSH brute-force noise
# ============================================================
set -euo pipefail

echo "=== [1/5] Verifying UFW is active ==="
if ! ufw status | grep -q "Status: active"; then
  echo "❌ UFW is not active. Enabling with safe defaults..."
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow 22/tcp
  ufw --force enable
fi
echo "✅ UFW is active."

echo ""
echo "=== [2/5] Current UFW rules (before changes) ==="
ufw status numbered

echo ""
echo "=== [3/5] Closing port 5678 (n8n direct access) ==="
echo "    n8n remains accessible via Cloudflare Tunnel (bot.empireenglish.online)"
# Delete any existing 5678 rules (both IPv4 and IPv6)
ufw delete allow 5678 2>/dev/null || true
ufw delete allow 5678/tcp 2>/dev/null || true
echo "✅ Port 5678 closed to public. n8n accessible via tunnel only."

echo ""
echo "=== [4/5] Adding SSH rate limiting ==="
# Remove plain allow rule, replace with rate-limited version
ufw delete allow 22/tcp 2>/dev/null || true
ufw delete allow 22 2>/dev/null || true
ufw limit 22/tcp
echo "✅ SSH rate-limited (max 6 connections in 30s per IP before block)."

echo ""
echo "=== [5/5] Ensuring IPv6 is enabled in UFW ==="
if grep -q "^IPV6=no" /etc/default/ufw 2>/dev/null; then
  sed -i 's/^IPV6=no/IPV6=yes/' /etc/default/ufw
  echo "✅ IPv6 enabled in UFW. Reloading..."
  ufw reload
else
  echo "✅ IPv6 already enabled (or file not found — default is yes)."
fi

echo ""
echo "=== RESULT ==="
ufw status verbose
echo ""
echo "✅ Firewall hardening complete."
echo ""
echo "⚠️  VERIFY: https://bot.empireenglish.online still works (via Cloudflare Tunnel)"
echo "⚠️  VERIFY: http://77.42.43.250:5678 is now UNREACHABLE (as intended)"
