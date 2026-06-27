# Server Infrastructure Reference

**Document Type:** Technical Infrastructure Handover
**Last Updated:** June 21, 2026
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
| **Swap** | 2 GB file (`/swapfile`, swappiness=10) |

---

## 3. Operating System

| Field | Value |
|---|---|
| **OS** | Ubuntu 26.04 LTS |
| **Kernel** | 7.0.0-22-generic (x86_64) |
| **Architecture** | x86_64 (AMD64) |
| **Root Access** | Yes (direct root login via SSH, key-only) |

---

## 4. Installed Software & Services

### 4.1 Docker

| Field | Value |
|---|---|
| **Docker Engine** | Installed via official `get.docker.com` script |
| **Docker Compose** | Plugin installed (`docker compose` — v2 syntax, no hyphen) |
| **Purpose** | Containerized service deployment |
| **Global Log Rotation** | `/etc/docker/daemon.json` — 10MB × 3 files |

### 4.2 n8n (Workflow Automation)

| Field | Value |
|---|---|
| **Deployment** | Docker container (`n8nio/n8n:2.26.8` — pinned) |
| **Container Name** | `empire-n8n` |
| **Port Binding** | `127.0.0.1:5678:5678` (localhost only — NOT public) |
| **Restart Policy** | `always` (auto-starts on reboot) |
| **Data Volume** | Named volume `n8n_data` (persists at `/var/lib/docker/volumes/n8n_data/`) |
| **Configuration** | `/opt/n8n/docker-compose.yml` |
| **Access URL** | `https://bot.empireenglish.online` (via Cloudflare Tunnel only) |
| **Direct Access** | ❌ Blocked — port 5678 not exposed to public |
| **Memory Limit** | 2560M (container OOM before server crash) |
| **CPU Limit** | 1.5 cores |
| **PID Limit** | 200 (fork-bomb protection) |
| **Healthcheck** | `wget --spider http://localhost:5678/healthz` every 30s |
| **Log Rotation** | 10MB × 5 files per container |

**n8n docker-compose.yml (`/opt/n8n/docker-compose.yml`):**

```yaml
services:
  n8n:
    image: n8nio/n8n:2.26.8
    container_name: empire-n8n
    restart: always
    ports:
      - "127.0.0.1:5678:5678"
    environment:
      - N8N_HOST=bot.empireenglish.online
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://bot.empireenglish.online/
      - N8N_SECURE_COOKIE=false
      - GENERIC_TIMEZONE=Asia/Dubai
      - TZ=Asia/Dubai
    volumes:
      - n8n_data:/home/node/.n8n
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 2560M
          pids: 200
        reservations:
          memory: 512M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:5678/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

volumes:
  n8n_data:
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

### 4.4 Fail2Ban (Intrusion Prevention)

| Field | Value |
|---|---|
| **Installation** | System package (`apt install fail2ban`) |
| **Version** | 1.1.0-9 |
| **Config File** | `/etc/fail2ban/jail.local` |
| **SSH Jail** | Enabled — 3 failures → 24h ban via UFW |
| **Ban Action** | UFW (integrates with firewall) |
| **Service Status** | Enabled + Active (auto-starts on boot) |

### 4.5 Server Health Monitor (Watchdog)

| Field | Value |
|---|---|
| **Script** | `/opt/monitor/watchdog.sh` |
| **Runs Every** | 60 seconds (systemd timer) |
| **Service** | `/etc/systemd/system/empire-monitor.service` |
| **Timer** | `/etc/systemd/system/empire-monitor.timer` |
| **Alert Channel** | Telegram (@macal_guardian_bot → @macal_emperor) |
| **State Dir** | `/opt/monitor/state/` (deduplication) |
| **Cooldown** | 15 minutes between repeated alerts |

**What it monitors:**
- CPU utilization (warn >80%, critical >90%)
- RAM utilization (warn >80%, critical >90% + auto-restart n8n)
- Disk utilization (warn >80%, critical >90%)
- n8n container health (auto-restart on failure)
- Cloudflare Tunnel health (auto-restart on failure)

### 4.6 Automated Backup

| Field | Value |
|---|---|
| **Script** | `/opt/backups/backup-n8n.sh` |
| **Schedule** | Daily at 3:00 AM (crontab) |
| **Target** | n8n data volume (`n8n_data`) |
| **Storage** | `/opt/backups/n8n/` |
| **Rotation** | Keeps last 14 backups |
| **Method** | Alpine container reads volume (read-only), creates `.tar.gz` |
| **Log** | `/var/log/n8n-backup.log` |

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
| 22 | TCP | SSH | Rate-limited (`ufw limit 22/tcp`) |
| 5678 | TCP | n8n Web UI | ❌ Blocked from public (bound to 127.0.0.1 only) |

**UFW Status:**
```
Default: deny (incoming), allow (outgoing), deny (routed)
22/tcp    LIMIT IN    Anywhere
22/tcp    LIMIT IN    Anywhere (v6)
```

> **Note:** Docker bypasses UFW for published ports. That's why n8n is bound to `127.0.0.1` in docker-compose.yml — this is the actual enforcement mechanism. The UFW deny on 5678 is belt-and-suspenders.

### 5.3 SSL/TLS

- **HTTPS is provided by Cloudflare Tunnel** (edge termination) — no local SSL certificate on the server.
- Traffic path: `User → Cloudflare Edge (HTTPS) → Tunnel (encrypted QUIC) → Server (HTTP localhost:5678)`
- The server itself does NOT run HTTPS; Cloudflare handles all TLS termination.

---

## 6. Security Configuration

### 6.1 SSH Access

```
ssh root@77.42.43.250
```

| Setting | Value |
|---|---|
| **Authentication** | SSH key only (ED25519) |
| **Password Auth** | ❌ Disabled (`PasswordAuthentication no`) |
| **Keyboard Interactive** | ❌ Disabled (`KbdInteractiveAuthentication no`) |
| **Key location (client)** | `C:\Users\97150\.ssh\id_ed25519` (Windows) |
| **Root login** | Enabled (direct, key-only) |
| **MaxAuthTries** | 3 |
| **Idle Timeout** | 5 minutes (ClientAliveInterval 300, CountMax 2) |
| **Empty Passwords** | ❌ Disabled |
| **Config Backup** | `/etc/ssh/sshd_config.backup.20260621_215436` |

### 6.2 Brute-Force Protection

- **Fail2Ban:** 3 failed SSH attempts → 24-hour IP ban (via UFW)
- **UFW Rate Limiting:** max 6 connections in 30 seconds per IP
- Both layers work together — UFW rate-limits first, Fail2Ban catches persistent attackers

### 6.3 n8n Web Access

| Method | URL | Notes |
|---|---|---|
| Via Tunnel (production) | `https://bot.empireenglish.online` | HTTPS, permanent, only method |
| Direct IP | ❌ Blocked | Port 5678 bound to localhost only |

### 6.4 n8n Authentication

- **Type:** Owner account (built-in n8n user management)
- **Owner:** Mahmoud Ashri
- **Email:** macalempire@gmail.com
- **Password:** Stored privately (not in this document)

---

## 7. File System Layout

```
/opt/n8n/
  └── docker-compose.yml              ← n8n container configuration (hardened)

/opt/monitor/
  ├── watchdog.sh                      ← Health monitoring script
  └── state/                           ← Alert deduplication state files

/opt/backups/
  ├── backup-n8n.sh                    ← Backup automation script
  └── n8n/                             ← Backup storage (14-day rotation)

/root/.cloudflared/
  ├── config.yml                       ← Tunnel routing config
  ├── cert.pem                         ← Cloudflare auth certificate
  └── 0502cb57-...39139.json           ← Tunnel credentials

/root/server-hardening/                ← Implementation scripts (archive)
  ├── deploy.sh
  ├── scripts/01-07*.sh
  ├── configs/
  └── systemd/

/var/lib/docker/volumes/n8n_data/      ← n8n persistent data

/etc/systemd/system/
  ├── cloudflared.service              ← Tunnel auto-start service
  ├── empire-monitor.service           ← Watchdog oneshot service
  └── empire-monitor.timer             ← Watchdog 60s timer

/etc/fail2ban/
  └── jail.local                       ← SSH jail config (24h ban)

/etc/docker/daemon.json                ← Global Docker log rotation

/swapfile                              ← 2GB swap (swappiness=10)
```

---

## 8. Services & Auto-Start Behavior

All critical services auto-start on server reboot:

| Service | Auto-Start | Restart on Failure | Managed By |
|---|---|---|---|
| Docker Engine | Yes (systemd) | Yes | `systemctl` |
| n8n container | Yes (`restart: always`) | Yes (+ healthcheck) | Docker |
| Cloudflare Tunnel | Yes (systemd, enabled) | Yes (`RestartSec=5`) | `systemctl` |
| Fail2Ban | Yes (systemd, enabled) | Yes | `systemctl` |
| Health Monitor | Yes (systemd timer, enabled) | Yes (every 60s) | `systemctl` |
| Swap | Yes (fstab) | N/A | Kernel |

**After a full server reboot:** all services come up automatically. No manual intervention required. Verified after kernel update reboot on June 21, 2026.

---

## 9. Monitoring & Alerting

### 9.1 Internal Monitoring (Telegram — 60 second checks)

| Check | Threshold | Action |
|-------|-----------|--------|
| CPU | >80% warn, >90% critical | Alert with top processes |
| RAM | >80% warn, >90% critical | Alert + auto-restart n8n |
| Disk | >80% warn, >90% critical | Alert (recommend docker prune) |
| n8n health | Unreachable | Auto-restart container + alert |
| Tunnel health | systemd inactive | Auto-restart service + alert |

**Alert delivery:** Telegram bot `@macal_guardian_bot` → chat with `@macal_emperor`

### 9.2 External Monitoring (BetterStack — 3 minute checks)

| Monitor | URL | Alert |
|---------|-----|-------|
| Empire n8n | `https://bot.empireenglish.online` | Email (covers total server failure) |

**Dashboard:** https://uptime.betterstack.com

### 9.3 Alert Coverage Matrix

| Failure Scenario | Detection | Speed | Auto-Recovery |
|-----------------|-----------|:-----:|:-------------:|
| n8n crashes | Internal watchdog | ~60s | ✅ Yes |
| Tunnel dies | Internal watchdog | ~60s | ✅ Yes |
| RAM spike | Internal watchdog | ~60s | ✅ Restarts n8n |
| Disk filling | Internal watchdog | ~60s | ❌ Alert only |
| CPU spike | Internal watchdog | ~60s | ❌ Alert only |
| Entire server down | BetterStack (external) | ~3min | ❌ Alert only |

---

## 10. Key Technical Decisions

| Decision | Rationale |
|---|---|
| **Hetzner over Oracle Cloud** | Oracle signup failed (card verification); Hetzner is stable, transparent pricing since 2003 |
| **Helsinki over Falkenstein** | CX23 type not available in Falkenstein at time of provisioning |
| **Docker for n8n** | Isolated environment, easy updates, resource limits, no Node.js version conflicts |
| **Cloudflare Named Tunnel over Let's Encrypt** | No need to manage certificates; permanent URL without nginx/reverse proxy complexity |
| **Port 5678 bound to localhost** | Docker bypasses UFW — binding to 127.0.0.1 is the real access control, not firewall rules |
| **n8n image pinned (2.26.8)** | Prevents surprise breaking updates; upgrade is intentional (`docker compose pull && up -d`) |
| **2GB swap + swappiness=10** | Safety net for memory spikes; prefers RAM, swap only as last resort before OOM |
| **Container memory limit 2560M** | If n8n leaks memory, Docker OOM-kills only n8n (which auto-restarts), not the whole server |
| **Fail2Ban + UFW limit (dual layer)** | UFW rate-limits connection flood; Fail2Ban bans persistent attackers by analyzing auth logs |
| **Telegram for monitoring** | Already used for business bots; instant mobile notification; zero cost |
| **BetterStack for external** | Covers the blind spot where internal monitoring can't alert (total server failure) |

---

## 11. Current Purpose

This server runs **one primary application:**

**n8n** — an open-source workflow automation platform used as the orchestration layer for the Empire English Community Telegram bot. It handles:
- Telegram bot webhook reception and response
- Google Sheets CRM read/write operations
- Cal.com booking webhook processing
- Scheduled tasks (daily backup, weekly reports, nudge automations)
- Lead scoring, segmentation, and event logging

---

## 12. Capacity & Scaling Considerations

### Current Usage (post-hardening, June 21, 2026)

| Resource | Usage | Limit |
|---|---|---|
| CPU | ~1% average | 2 vCPUs (1.5 allocated to n8n) |
| RAM | ~26% (1.0 GB of 4 GB) | n8n capped at 2.5GB |
| Disk | ~19% (7.1 GB of 40 GB) | Logs capped, backups rotated |
| Swap | 0% (0 of 2 GB) | Available as safety net |
| Network | Negligible | 20 TB/month |

### Scaling Headroom

This server can comfortably handle:
- **n8n with 5,000–10,000+ webhook calls/day** without performance issues
- **Additional services** on the same server (e.g., PostgreSQL, challenge bot, lightweight web app)
- **Multiple n8n workflows** (unlimited — no per-workflow cost)

### When to consider upgrading:
- RAM exceeds 80% sustained → upgrade to CX33 (8 GB, $8.99/mo)
- Need a real database (PostgreSQL) with large datasets → add a volume or upgrade disk
- Need isolated environments → add a second container

---

## 13. Maintenance Procedures

### Update n8n
```bash
cd /opt/n8n
# 1. Check latest version: https://github.com/n8n-io/n8n/releases
# 2. Edit docker-compose.yml — change image tag
nano docker-compose.yml
# 3. Pull and restart
docker compose pull
docker compose up -d
# 4. Verify health
sleep 35 && docker inspect --format='{{.State.Health.Status}}' empire-n8n
```

### Check service status
```bash
systemctl status cloudflared
systemctl status fail2ban
systemctl status empire-monitor.timer
docker inspect --format='{{.State.Health.Status}}' empire-n8n
docker stats --no-stream empire-n8n
```

### View logs
```bash
# n8n
docker compose -f /opt/n8n/docker-compose.yml logs --tail=50

# Tunnel
journalctl -u cloudflared --no-pager -n 30

# Monitoring
journalctl -u empire-monitor --no-pager -n 20

# Fail2Ban
fail2ban-client status sshd

# Backup
cat /var/log/n8n-backup.log
```

### Restart services
```bash
# Restart n8n only
cd /opt/n8n && docker compose restart

# Restart tunnel
systemctl restart cloudflared

# Restart everything (safe)
systemctl restart cloudflared
cd /opt/n8n && docker compose restart
```

### Manual backup
```bash
/opt/backups/backup-n8n.sh
ls -lh /opt/backups/n8n/
```

### Unban an IP (Fail2Ban)
```bash
fail2ban-client get sshd banip          # List banned IPs
fail2ban-client set sshd unbanip 1.2.3.4  # Unban specific IP
```

---

## 14. Adding New Services to This Server

If deploying additional applications on this server:

1. **Use Docker** — add another service to a new `docker-compose.yml` in a separate directory (e.g., `/opt/new-app/`)
2. **Bind to localhost** — use `127.0.0.1:PORT:PORT` to prevent Docker from bypassing the firewall
3. **Route via Cloudflare Tunnel** — add another `ingress` entry in `/root/.cloudflared/config.yml`:
   ```yaml
   ingress:
     - hostname: bot.empireenglish.online
       service: http://localhost:5678
     - hostname: app.empireenglish.online
       service: http://localhost:3000
     - service: http_status:404
   ```
4. **Add DNS in Cloudflare** — create a CNAME record for the new subdomain:
   ```
   cloudflared tunnel route dns empire-n8n app.empireenglish.online
   ```
5. **Restart cloudflared** — `systemctl restart cloudflared`
6. **Set resource limits** — add `deploy.resources.limits` in the new compose file
7. **Add to monitoring** — update `/opt/monitor/watchdog.sh` to check the new service
8. **Add to backup** — if the new service has persistent data

---

## 15. Credential Locations (Structure Only — No Secrets)

| Credential | Storage Location | Notes |
|---|---|---|
| SSH private key | Client machine (`~/.ssh/id_ed25519`) | Never on the server |
| Telegram Bot token (n8n bot) | n8n credential store (encrypted) | Never in files/repo |
| Telegram Bot token (monitoring) | `/opt/monitor/watchdog.sh` (root-only) | `@macal_guardian_bot` |
| Google Service Account JSON | n8n credential store (encrypted) | Key file used once during setup |
| Cloudflare tunnel credentials | `/root/.cloudflared/*.json` | Auto-generated during tunnel creation |
| Cloudflare auth certificate | `/root/.cloudflared/cert.pem` | Generated during `cloudflared tunnel login` |
| n8n login password | n8n internal database | Owner account only |

---

## 16. Security Hardening Summary (Implemented June 21, 2026)

| Layer | Protection | Status |
|-------|-----------|:------:|
| SSH | Key-only auth, password disabled, 3 max retries, 5min timeout | ✅ |
| Firewall | UFW deny all incoming, SSH rate-limited, port 5678 not exposed | ✅ |
| Brute-force | Fail2Ban SSH jail (3 attempts → 24h ban) | ✅ |
| Network | n8n bound to localhost, all external via Cloudflare Tunnel | ✅ |
| Container | Memory 2.5GB cap, CPU 1.5, PID 200, healthcheck, log rotation | ✅ |
| Memory | 2GB swap (swappiness=10), prevents OOM server crash | ✅ |
| Monitoring | Internal (Telegram, 60s) + External (BetterStack, 3min) | ✅ |
| Recovery | Auto-restart on failure (Docker + systemd + watchdog) | ✅ |
| Backup | Daily 3AM, 14-day rotation, volume-level tar.gz | ✅ |

**Overall Infrastructure Score: 9.0/10** (audited June 21, 2026)

---

## 17. Important Notes & Remaining Considerations

1. **Single server / single point of failure** — Acceptable for current scale (<1,000 users). At higher scale, consider a standby server or Hetzner snapshot schedule.

2. **Hetzner backup add-on** (~€1.22/mo) — Not currently enabled. The daily volume backup covers n8n data; Hetzner backup would additionally protect OS-level configs. Consider enabling for full disaster recovery.

3. **Root-only access** — No non-root users created. For multi-developer access, create separate users with sudo. For single-operator use, root is acceptable.

4. **Cloudflare Tunnel credentials are on the server** — If the server is compromised, the tunnel can be recreated from the Cloudflare dashboard. The credentials file should be treated as sensitive.

5. **n8n version pinned** — Will not auto-update. Check releases periodically and update manually (see section 13).

6. **Kernel updates** — Ubuntu auto-downloads security patches. Apply them during maintenance windows with `reboot` after verifying no critical workflows are in-flight.

---

*End of Server Infrastructure Reference — v2.0 (Hardened)*
