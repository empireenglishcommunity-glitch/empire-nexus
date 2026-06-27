"""
Deploy n8n-MCP Server to Hetzner
Run from any machine with SSH access to the server.
Usage: python deploy_mcp.py

Prerequisites:
  - SSH key configured for root@77.42.43.250
  - .env file on server at /opt/n8n-mcp/.env with N8N_API_URL and N8N_API_KEY
"""
import subprocess
import sys
import time
import os

SERVER = "root@77.42.43.250"
# Auto-detect SSH key location (Linux/Mac or Windows)
KEY = os.path.expanduser("~/.ssh/id_ed25519")
REMOTE_DIR = "/opt/n8n-mcp"

# NOTE: The actual docker-compose.yml is in the repository at
# infrastructure/n8n-mcp/docker-compose.yml. This script deploys it.
# Secrets (N8N_API_KEY) are in .env on the server, NOT in this file.
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
