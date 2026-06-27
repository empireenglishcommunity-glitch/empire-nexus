# Server Infrastructure Reference

**Document Type:** Technical Infrastructure Handover  
**Last Updated:** June 20, 2026  
**Purpose:** Reference document for any AI agent or developer who needs to understand the existing server environment before making changes or deployments.

---

## 1. Server Overview

| Field | Value |
|---|---|
| **Provider** | Hetzner Cloud |
| **Project Name** | Empire English |
| **Server Name** | `empire-n8n` |
| **Server Type** | CX23 (Shared vCPU) |
| **Location** | Helsinki, Finland (hel1) |
| **Public IPv4** | `77.42.43.250` |
| **Public IPv6** | `2a01:4f9:c014:7513::1` |
| **Monthly Cost** | $7.09/mo ($6.49 server + $0.60 IPv4) |
| **Billing** | Hourly ($0.010/h), billed monthly |

---

## 2. Hardware Specifications

| Resource | Specification |
|---|---|
| **CPU** | 2 vCPUs (Intel/AMD, shared) |
| **RAM** | 4 GB |
| **Storage** | 40 GB SSD (NVMe) |
| **Traffic** | 20 TB/month included |
| **Network** | Dual-stack IPv4 + IPv6 |

---

## 3. Operating System

| Field | Value |
|---|---|
| **OS** | Ubuntu 26.04 LTS |
| **Kernel** | 7.0.0-15-generic (x86_64) |
| **Architecture** | x86_64 (AMD64) |
| **Root Access** | Yes (direct root login via SSH) |

---

## 4. Installed Software & Services

### 4.1 Docker

| Field | Value |
|---|---|
| **Docker Engine** | Installed via official `get.docker.com` script |
| **Docker Compose** | Plugin installed (`docker compose` — v2 syntax, no hyphen) |
| **Purpose** | Containerized service deployment |

### 4.2 n8n (Workflow Automation)

| Field | Value |
|---|---|
| **Deployment** | Docker container (`n8nio/n8n:latest`) |
| **Container Name** | `empire-n8n` |
| **Internal Port** | 5678 |
| **Restart Policy** | `always` (auto-starts on reboot) |
| **Data Volume** | Named volume `n8n_data` (persists at `/var/lib/docker/volumes/n8n_data/`) |
| **Configuration** | `/opt/n8n/docker-compose.yml` |
| **Access URL** | `https://bot.empireenglish.online` (via Cloudflare Tunnel) |
| **Direct Access** | `http://77.42.43.250:5678` (HTTP, no SSL, direct) |

**n8n Environment Variables (from docker-compose.yml):**

```yaml
environment:
  - N8N_HOST=bot.empireenglish.online
  - N8N_PORT=5678
  - N8N_PROTOCOL=https
  - WEBHOOK_URL=https://bot.empireenglish.online/
  - N8N_SECURE_COOKIE=false
  - GENERIC_TIMEZONE=Asia/Dubai
  - TZ=Asia/Dubai
```

### 4.3 Cloudflare Tunnel (cloudflared)

| Field | Value |
|---|---|
| **Installation** | System package (`/usr/bin/cloudflared`) |
| **Tunnel Type** | Named Tunnel (permanent, authenticated) |
| **Tunnel Name** | `empire-n8n` |
| **Tunnel ID** | `0502cb57-380c-4d27-a415-15e0ecc39139` |
| **Config File** | `/root/.cloudflared/config.yml` |
| **Credentials File** | `/root/.cloudflared/0502cb57-380c-4d27-a415-15e0ecc39139.json` |
| **Certificate** | `/root/.cloudflared/cert.pem` (Cloudflare login auth) |
| **Systemd Service** | `/etc/systemd/system/cloudflared.service` |
| **Service Status** | Enabled + Active (auto-starts on boot) |
| **Mapped Hostname** | `bot.empireenglish.online` → `http://localhost:5678` |
| **Protocol** | QUIC (primary), HTTP/2 (fallback) |

**Tunnel Config (`/root/.cloudflared/config.yml`):**

```yaml
tunnel: 0502cb57-380c-4d27-a415-15e0ecc39139
credentials-file: /root/.cloudflared/0502cb57-380c-4d27-a415-15e0ecc39139.json

ingress:
  - hostname: bot.empireenglish.online
    service: http://localhost:5678
  - service: http_status:404
```

---

## 5. Networking & DNS

### 5.1 Domain Configuration

| Field | Value |
|---|---|
| **Domain** | `empireenglish.online` |
| **Registrar** | Namecheap |
| **Nameservers** | Cloudflare (delegated from Namecheap) |
| **Cloudflare Plan** | Free |
| **DNS Records** | `bot.empireenglish.online` → CNAME to Cloudflare Tunnel |

### 5.2 Firewall / Ports

| Port | Protocol | Service | Access |
|---|---|---|---|
| 22 | TCP | SSH | Open (public) |
| 5678 | TCP | n8n Web UI | Open (public — also accessible via tunnel) |

> **Note:** UFW (Uncomplicated Firewall) is enabled with rules for ports 22 and 5678.

### 5.3 SSL/TLS

- **HTTPS is provided by Cloudflare Tunnel** (edge termination) — no local SSL certificate on the server.
- Traffic path: `User → Cloudflare Edge (HTTPS) → Tunnel (encrypted QUIC) → Server (HTTP localhost:5678)`
- The server itself does NOT run HTTPS; Cloudflare handles all TLS termination.

---

## 6. Access & Connection

### 6.1 SSH Access

```
ssh root@77.42.43.250
```

- **Authentication:** SSH key (ED25519)
- **Key location (client-side):** `C:\Users\97150\.ssh\id_ed25519` (Windows)
- **Root login:** Enabled (direct)
- **Password login:** Needs confirmation (likely disabled since SSH key was configured at creation)

### 6.2 n8n Web Access

| Method | URL | Notes |
|---|---|---|
| Via Tunnel (production) | `https://bot.empireenglish.online` | HTTPS, permanent, recommended |
| Direct IP (backup) | `http://77.42.43.250:5678` | HTTP only, no SSL |

### 6.3 n8n Authentication

- **Type:** Owner account (built-in n8n user management)
- **Owner:** Mahmoud Ashri
- **Email:** macalempire@gmail.com
- **Password:** Stored privately (not in this document)

---

## 7. File System Layout

```
/opt/n8n/
  └── docker-compose.yml              ← n8n container configuration

/root/.cloudflared/
  ├── config.yml                       ← Tunnel routing config
  ├── cert.pem                         ← Cloudflare auth certificate
  └── 0502cb57-...39139.json           ← Tunnel credentials

/var/lib/docker/volumes/n8n_data/      ← n8n persistent data (workflows, credentials, settings)

/etc/systemd/system/
  └── cloudflared.service              ← Tunnel auto-start service
```

---

## 8. Services & Auto-Start Behavior

Both critical services auto-start on server reboot:

| Service | Auto-Start | Restart on Failure | Managed By |
|---|---|---|---|
| Docker Engine | Yes (systemd) | Yes | `systemctl` |
| n8n container | Yes (`restart: always`) | Yes | Docker |
| Cloudflare Tunnel | Yes (systemd, enabled) | Yes (`RestartSec=5`) | `systemctl` |

**After a full server reboot:** all services come up automatically. No manual intervention required.

---

## 9. Key Technical Decisions

| Decision | Rationale |
|---|---|
| **Hetzner over Oracle Cloud** | Oracle signup failed (card verification); Hetzner is stable, transparent pricing since 2003 |
| **Helsinki over Falkenstein** | CX23 type not available in Falkenstein at time of provisioning |
| **Docker for n8n** | Isolated environment, easy updates (`docker compose pull && up -d`), no Node.js version conflicts |
| **Cloudflare Named Tunnel over Let's Encrypt** | No need to manage certificates; permanent URL without nginx/reverse proxy complexity |
| **Service Account over OAuth2 for Google** | OAuth2 requires a domain for redirect URI callbacks at time of n8n connection; Service Account is more stable for always-on servers |
| **Single domain `bot.` subdomain** | Separates bot/automation endpoint from future website; allows adding more subdomains later (e.g., `app.`, `api.`) |
| **N8N_SECURE_COOKIE=false** | Required because n8n is accessed via mixed paths (direct IP for admin + tunnel for webhooks); Cloudflare handles actual HTTPS security |

---

## 10. Current Purpose

This server currently runs **one primary application:**

**n8n** — an open-source workflow automation platform used as the orchestration layer for the Empire English Community Telegram bot. It handles:
- Telegram bot webhook reception and response
- Google Sheets CRM read/write operations
- Cal.com booking webhook processing
- Scheduled tasks (daily backup, weekly reports, nudge automations)
- Lead scoring, segmentation, and event logging

---

## 11. Capacity & Scaling Considerations

### Current Usage (observed)

| Resource | Usage |
|---|---|
| CPU | ~0.15 load average (minimal) |
| RAM | ~27% (1.1 GB of 4 GB) |
| Disk | ~12.7% (5 GB of 40 GB) |
| Network | Negligible |

### Scaling Headroom

This server can comfortably handle:
- **n8n with 5,000–10,000+ webhook calls/day** without performance issues
- **Additional services** on the same server (e.g., PostgreSQL database, a lightweight web app, monitoring tools)
- **Multiple n8n workflows** (unlimited — no per-workflow cost)

### When to consider upgrading:
- RAM exceeds 80% sustained → upgrade to CX33 (8 GB, $8.99/mo)
- Need a real database (PostgreSQL) with large datasets → add a volume or upgrade disk
- Need isolated environments → add a second container

---

## 12. Maintenance Procedures

### Update n8n
```bash
cd /opt/n8n
docker compose pull
docker compose up -d
```

### Check service status
```bash
systemctl status cloudflared
docker compose -f /opt/n8n/docker-compose.yml ps
```

### View n8n logs
```bash
docker compose -f /opt/n8n/docker-compose.yml logs --tail=50
```

### View tunnel logs
```bash
journalctl -u cloudflared --no-pager -n 30
```

### Restart everything (if needed)
```bash
systemctl restart cloudflared
cd /opt/n8n && docker compose restart
```

---

## 13. Important Notes & Limitations

1. **No automated server backups** — Hetzner offers backup add-on (~€1.22/mo). Currently not enabled. n8n data lives in Docker volume; workflow export to JSON is the primary backup method.

2. **No monitoring/alerting** — No uptime monitor is configured. Recommended: add UptimeRobot (free tier) to monitor `https://bot.empireenglish.online`.

3. **Root-only access** — No non-root users created. For multi-developer access, create separate users with sudo. For single-operator use, root is acceptable.

4. **No fail2ban** — SSH brute-force protection not installed. The SSH key requirement provides adequate security for now. Consider adding fail2ban if password auth is ever enabled.

5. **Single server / single point of failure** — Acceptable for current scale (<1,000 users). At higher scale, consider load balancing or a standby server.

6. **Cloudflare Tunnel credentials are on the server** — If the server is compromised, the tunnel can be recreated from the Cloudflare dashboard. The credentials file should be treated as sensitive.

---

## 14. Adding New Services to This Server

If deploying additional applications on this server:

1. **Use Docker** — add another service to a new `docker-compose.yml` in a separate directory (e.g., `/opt/new-app/`)
2. **Route via Cloudflare Tunnel** — add another `ingress` entry in `/root/.cloudflared/config.yml` for the new subdomain:
   ```yaml
   ingress:
     - hostname: bot.empireenglish.online
       service: http://localhost:5678
     - hostname: app.empireenglish.online
       service: http://localhost:3000
     - service: http_status:404
   ```
3. **Add DNS in Cloudflare** — create a CNAME record for the new subdomain pointing to the tunnel:
   ```
   app.empireenglish.online → CNAME → 0502cb57-380c-4d27-a415-15e0ecc39139.cfargotunnel.com
   ```
   Or use: `cloudflared tunnel route dns empire-n8n app.empireenglish.online`
4. **Restart cloudflared** — `systemctl restart cloudflared`
5. **Check port conflicts** — ensure the new app uses a different port than 5678.

---

## 15. Credential Locations (Structure Only — No Secrets)

| Credential | Storage Location | Notes |
|---|---|---|
| SSH private key | Client machine (`~/.ssh/id_ed25519`) | Never on the server |
| Telegram Bot token | n8n credential store (encrypted) | Never in files/repo |
| Google Service Account JSON | n8n credential store (encrypted) | Key file was used once during setup, can be deleted from Downloads |
| Cloudflare tunnel credentials | `/root/.cloudflared/*.json` | Auto-generated during tunnel creation |
| Cloudflare auth certificate | `/root/.cloudflared/cert.pem` | Generated during `cloudflared tunnel login` |
| n8n login password | n8n internal database | Owner account only |

---

*End of Server Infrastructure Reference — v1.0*
