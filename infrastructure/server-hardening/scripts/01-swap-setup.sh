#!/bin/bash
# ============================================================
#  01-swap-setup.sh — Create 2GB swap file
#  Priority: CRITICAL
#  Risk addressed: OOM crash on 4GB RAM server with no memory safety net
# ============================================================
set -euo pipefail

SWAP_SIZE="2G"
SWAP_FILE="/swapfile"
SWAPPINESS=10

echo "=== [1/4] Checking existing swap ==="
if swapon --show | grep -q "$SWAP_FILE"; then
  echo "✅ Swap file already exists and is active:"
  swapon --show
  free -h | grep -i swap
  echo "Nothing to do."
  exit 0
fi

echo "=== [2/4] Creating ${SWAP_SIZE} swap file ==="
fallocate -l "$SWAP_SIZE" "$SWAP_FILE"
chmod 600 "$SWAP_FILE"
mkswap "$SWAP_FILE"
swapon "$SWAP_FILE"
echo "✅ Swap activated."

echo "=== [3/4] Making swap permanent (fstab) ==="
if ! grep -q "$SWAP_FILE" /etc/fstab; then
  echo "${SWAP_FILE} none swap sw 0 0" >> /etc/fstab
  echo "✅ Added to /etc/fstab."
else
  echo "✅ Already in /etc/fstab."
fi

echo "=== [4/4] Setting swappiness to ${SWAPPINESS} ==="
SYSCTL_FILE="/etc/sysctl.d/99-swap.conf"
echo "vm.swappiness=${SWAPPINESS}" > "$SYSCTL_FILE"
sysctl -p "$SYSCTL_FILE"
echo "✅ Swappiness set to ${SWAPPINESS} (prefer RAM, swap as safety net only)."

echo ""
echo "=== RESULT ==="
free -h
swapon --show
echo ""
echo "✅ Swap setup complete. Server now has OOM protection."
