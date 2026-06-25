#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Deploy n8n-MCP Server on Hetzner
# Run this ON the server (after scp'ing the folder)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

echo "════════════════════════════════════════"
echo "  Deploying n8n-MCP Server"
echo "════════════════════════════════════════"

cd /opt/n8n-mcp

# Pull latest image
echo "→ Pulling latest n8n-MCP image..."
docker compose pull

# Start the container
echo "→ Starting n8n-MCP server..."
docker compose up -d

# Wait for health check
echo "→ Waiting for health check..."
sleep 10

# Verify
if docker inspect --format='{{.State.Health.Status}}' empire-n8n-mcp 2>/dev/null | grep -q "healthy"; then
  echo "✅ n8n-MCP server is healthy and running!"
else
  echo "⏳ Still starting... checking logs:"
  docker compose logs --tail=20
fi

echo ""
echo "════════════════════════════════════════"
echo "  MCP Server: http://localhost:3001"
echo "  Container:  empire-n8n-mcp"
echo "════════════════════════════════════════"
echo ""
echo "To test: curl http://localhost:3001/health"
echo "To stop: docker compose down"
echo "Logs:    docker compose logs -f"
