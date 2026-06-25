# n8n-MCP Server — AI Workflow Builder

## What This Is

An MCP (Model Context Protocol) server that allows AI agents to **build, modify, and manage n8n workflows directly** — no manual node configuration needed.

## What It Enables

Once running, any MCP-compatible AI can:
- Create new workflows from natural language instructions
- Update existing workflows (add/remove nodes, fix connections)
- Validate workflows before deployment
- Auto-fix common errors
- Deploy templates from n8n's library
- Test/execute workflows
- Manage credentials
- Audit your instance for security issues

## Deployment

### Prerequisites
- Docker and Docker Compose on Hetzner server (already installed)
- n8n API key (already configured in docker-compose.yml)

### Deploy

```bash
# From your PC:
scp -i ~/.ssh/id_ed25519 -r /path/to/n8n-mcp root@77.42.43.250:/opt/n8n-mcp

# SSH into server:
ssh root@77.42.43.250

# Deploy:
cd /opt/n8n-mcp && bash deploy.sh
```

### Verify

```bash
curl http://localhost:3001/health
```

## Connecting AI Agents

### From Kiro/Claude (via HTTP MCP)

The MCP server is accessible at `http://localhost:3001` on the server. To expose it externally (for Kiro/Claude Code), add a Cloudflare Tunnel route:

```yaml
# In /root/.cloudflared/config.yml, add:
  - hostname: mcp.empireenglish.online
    service: http://localhost:3001
```

Then restart cloudflared: `systemctl restart cloudflared`

### From Claude Desktop (stdio mode)

```json
{
  "mcpServers": {
    "n8n": {
      "command": "npx",
      "args": ["-y", "@czlonkowski/n8n-mcp@latest"],
      "env": {
        "N8N_API_URL": "https://bot.empireenglish.online/api/v1",
        "N8N_API_KEY": "your-api-key"
      }
    }
  }
}
```

### From macal_pc Agent (future)

The agent daemon connects via HTTP MCP over Tailscale to `http://100.x.y.z:3001`.

## Architecture

```
AI Agent (Claude/Kiro/Ollama)
    │
    │ MCP Protocol (HTTP Streamable)
    ▼
n8n-MCP Server (Docker, port 3001)
    │
    │ n8n REST API (internal)
    ▼
n8n Instance (Docker, port 5678)
    │
    ▼
Your workflows, credentials, executions
```

## Security

- MCP server is bound to localhost (127.0.0.1) — not exposed to public internet
- Access requires the n8n API key
- External access only via Cloudflare Tunnel (HTTPS, authenticated)
- Container has resource limits (512MB RAM, 0.5 CPU)

## Monthly Cost: $0

Runs on existing Hetzner server with plenty of headroom.
