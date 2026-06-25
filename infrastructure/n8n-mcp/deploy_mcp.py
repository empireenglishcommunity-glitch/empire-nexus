"""
Deploy n8n-MCP Server to Hetzner
Run from: C:\Users\97150\macal_pc\ (or anywhere)
Usage: python deploy_mcp.py
"""
import subprocess
import sys
import time

SERVER = "root@77.42.43.250"
KEY = r"C:\Users\97150\.ssh\id_ed25519"
REMOTE_DIR = "/opt/n8n-mcp"

COMPOSE_CONTENT = '''version: '3.8'
services:
  n8n-mcp:
    image: ghcr.io/czlonkowski/n8n-mcp:latest
    container_name: empire-n8n-mcp
    restart: unless-stopped
    environment:
      N8N_API_URL: https://bot.empireenglish.online/api/v1
      N8N_API_KEY: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzODExZjBlMC0xYzIyLTQ4MmEtOTk5ZC0wZThlYzVkZDk3YjkiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiMTE2NGM3ODUtZTlmMy00MWQwLWE0MzctZDg3MjFlMzAyMGUyIiwiaWF0IjoxNzgyMzkyNDA5fQ.FyfkFGAdV7kCOdMUUk_lab2PnDzSKbmAzSVK-TJVgfw
      MCP_TRANSPORT: http
      MCP_HTTP_PORT: "3001"
      MCP_HTTP_HOST: 0.0.0.0
      NODE_ENV: production
      LOG_LEVEL: info
    ports:
      - 127.0.0.1:3001:3001
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.5"
    logging:
      driver: json-file
      options:
        max-size: 10m
        max-file: "3"
'''


def ssh(cmd, check=True):
    """Run a command on the remote server via SSH."""
    full_cmd = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=no", SERVER, cmd]
    print(f"  → {cmd}")
    result = subprocess.run(full_cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()}")
    if result.stderr.strip() and result.returncode != 0:
        print(f"    ⚠️ {result.stderr.strip()}")
    if check and result.returncode != 0:
        print(f"    ❌ Failed (exit code {result.returncode})")
        return False
    return True


def main():
    print("=" * 50)
    print("  DEPLOYING n8n-MCP SERVER TO HETZNER")
    print("=" * 50)
    print()

    # Step 1: Create directory
    print("[1/5] Creating directory...")
    ssh(f"mkdir -p {REMOTE_DIR}")

    # Step 2: Write docker-compose.yml
    print("[2/5] Writing docker-compose.yml...")
    # Escape for shell
    escaped = COMPOSE_CONTENT.replace("'", "'\\''")
    ssh(f"cat > {REMOTE_DIR}/docker-compose.yml << 'ENDOFFILE'\n{COMPOSE_CONTENT}ENDOFFILE")

    # Step 3: Pull image
    print("[3/5] Pulling n8n-MCP Docker image (may take 1-2 minutes)...")
    ssh(f"cd {REMOTE_DIR} && docker compose pull")

    # Step 4: Start container
    print("[4/5] Starting n8n-MCP server...")
    ssh(f"cd {REMOTE_DIR} && docker compose up -d")

    # Step 5: Verify
    print("[5/5] Waiting for startup (15 seconds)...")
    time.sleep(15)

    print("\n  Checking container status...")
    ssh("docker ps --format 'table {{.Names}}\t{{.Status}}' | grep mcp", check=False)

    print("\n  Checking health endpoint...")
    ssh("curl -s http://localhost:3001/health || echo 'Not responding yet - may need more time'", check=False)

    print()
    print("=" * 50)
    print("  DEPLOYMENT COMPLETE")
    print("=" * 50)
    print()
    print("  Container: empire-n8n-mcp")
    print("  Endpoint:  http://localhost:3001 (on server)")
    print("  Status:    docker ps | grep mcp")
    print("  Logs:      ssh root@77.42.43.250 'docker logs empire-n8n-mcp --tail=20'")
    print()


if __name__ == "__main__":
    main()
