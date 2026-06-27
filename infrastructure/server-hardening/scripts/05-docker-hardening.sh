#!/bin/bash
# ============================================================
#  05-docker-hardening.sh — Apply hardened Docker configuration
#  Priority: HIGH
#  Risk addressed: No resource limits, no log rotation, no healthcheck,
#                  unpinned image version, no global log cap
# ============================================================
set -euo pipefail

COMPOSE_DIR="/opt/n8n"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIGS_DIR="$(dirname "$SCRIPT_DIR")/configs"
DAEMON_JSON="/etc/docker/daemon.json"

echo "=== [1/5] Setting global Docker log rotation ==="
if [ -f "$DAEMON_JSON" ]; then
  echo "  ⚠️  $DAEMON_JSON already exists. Checking content..."
  if grep -q "max-size" "$DAEMON_JSON"; then
    echo "  ✅ Log rotation already configured globally."
  else
    echo "  ⚠️  File exists but no log rotation. Please merge manually:"
    echo '    {"log-driver":"json-file","log-opts":{"max-size":"10m","max-file":"3"}}'
  fi
else
  cat > "$DAEMON_JSON" << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
  echo "  ✅ Created $DAEMON_JSON with log rotation (10MB x 3 files)."
fi

echo ""
echo "=== [2/5] Backing up current docker-compose.yml ==="
if [ -f "$COMPOSE_FILE" ]; then
  BACKUP="${COMPOSE_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
  cp "$COMPOSE_FILE" "$BACKUP"
  echo "  ✅ Backup: $BACKUP"
else
  echo "  ⚠️  No existing compose file found at $COMPOSE_FILE"
  mkdir -p "$COMPOSE_DIR"
fi

echo ""
echo "=== [3/5] Deploying hardened docker-compose.yml ==="
cp "${CONFIGS_DIR}/docker-compose.yml" "$COMPOSE_FILE"
echo "  ✅ Hardened compose file deployed to $COMPOSE_FILE"
echo ""
echo "  Changes applied:"
echo "    • Image pinned to n8nio/n8n:1.97.1 (no more :latest surprises)"
echo "    • Memory limit: 2560M (container OOM-killed before server crashes)"
echo "    • CPU limit: 1.5 cores (leaves resources for OS + tunnel)"
echo "    • Log rotation: 10MB x 5 files per container"
echo "    • HEALTHCHECK: auto-restart if n8n process dies inside container"
echo "    • pids_limit: 200 (fork-bomb protection)"

echo ""
echo "=== [4/5] Recreating n8n container with new settings ==="
cd "$COMPOSE_DIR"
docker compose up -d
echo "  ✅ Container recreated."

echo ""
echo "=== [5/5] Verifying container health ==="
echo "  Waiting 35 seconds for healthcheck..."
sleep 35
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' empire-n8n 2>/dev/null || echo "unknown")
if [ "$HEALTH" = "healthy" ]; then
  echo "  ✅ Container is healthy."
elif [ "$HEALTH" = "starting" ]; then
  echo "  ⏳ Container still starting (healthcheck hasn't passed yet)."
  echo "     Check again in 30s: docker inspect --format='{{.State.Health.Status}}' empire-n8n"
else
  echo "  ⚠️  Health status: $HEALTH"
  echo "     Check logs: docker compose logs --tail=20"
fi

echo ""
echo "=== RESULT ==="
docker compose ps
echo ""
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.PIDs}}" empire-n8n
echo ""
echo "✅ Docker hardening complete."
echo ""
echo "⚠️  NOTE: To update n8n in the future, change the image tag in:"
echo "    $COMPOSE_FILE"
echo "    Then run: cd $COMPOSE_DIR && docker compose pull && docker compose up -d"
