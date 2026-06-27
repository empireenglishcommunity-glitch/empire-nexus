# 🛡️ Server Hardening Package — Empire English

> Production-grade security, monitoring, and resilience for the Hetzner `empire-n8n` server.
> Implements all 12 remediation items from the [Server Infrastructure Audit](../docs/SERVER_AUDIT.md).

---

## ✅ DEPLOYMENT STATUS: COMPLETE

**Deployed:** June 21, 2026
**Server:** `empire-n8n` (77.42.43.250)
**Result:** Infrastructure score 3.7/10 → 9.0/10

All scripts in this package have been executed successfully on the production server. This directory is now an **archive of what was deployed** — useful for reference, re-deployment on a new server, or if the server needs to be rebuilt from scratch.

---

## Re-Deployment (New Server / Rebuild)

If rebuilding the server from scratch, upload this directory and run:

```bash
# 1. Upload this directory to the server
scp -r server-hardening/ root@NEW_SERVER_IP:/root/

# 2. SSH into the server
ssh root@NEW_SERVER_IP

# 3. Run everything
cd /root/server-hardening
sudo bash deploy.sh
```

The script runs all 7 steps in order, is idempotent (safe to re-run), and pauses after SSH changes so you can verify you're not locked out.

> **Note:** The `configs/docker-compose.yml` in this directory uses `n8nio/n8n:2.26.8`. Update the version tag to the latest stable before re-deploying on a new server.

---

## What Gets Deployed

| Step | Script | What It Does | Priority | Status |
|:----:|--------|--------------|:--------:|:------:|
| 1 | `01-swap-setup.sh` | Creates 2GB swap file, sets swappiness=10 | 🔴 Critical | ✅ Deployed |
| 2 | `02-firewall-hardening.sh` | Closes port 5678, rate-limits SSH, enables IPv6 | 🔴 Critical | ✅ Deployed |
| 3 | `03-ssh-hardening.sh` | Disables password auth, enforces key-only, sets timeouts | 🔴 Critical | ✅ Deployed |
| 4 | `04-fail2ban-setup.sh` | Installs fail2ban, 24h SSH ban after 3 failures | 🟠 High | ✅ Deployed |
| 5 | `05-docker-hardening.sh` | Pins n8n version, sets memory/CPU limits, healthcheck, log rotation | 🟠 High | ✅ Deployed |
| 6 | `06-monitoring-setup.sh` | Deploys Telegram alerting watchdog (systemd timer, every 60s) | 🔴 Critical | ✅ Deployed |
| 7 | `07-backup-setup.sh` | Daily n8n data backup with 14-day rotation | 🟠 High | ✅ Deployed |

> **Additional manual steps performed during deployment (not in scripts):**
> - n8n port binding changed to `127.0.0.1:5678:5678` (Docker bypasses UFW — this is the real fix)
> - n8n image pinned to actual running version `2.26.8` (scripts had `1.97.1` placeholder)
> - Kernel updated from `7.0.0-15` to `7.0.0-22` via reboot
> - BetterStack external uptime monitor configured (email alerts, 3-min checks)

---

## Running Individual Steps (Re-deployment only)

If rebuilding and you only want to run one step:

```bash
sudo bash deploy.sh --only 1   # Just swap
sudo bash deploy.sh --only 5   # Just Docker hardening
sudo bash deploy.sh --only 6   # Just monitoring
```

Or run scripts directly:

```bash
sudo bash scripts/01-swap-setup.sh
```

---

## Directory Structure

```
server-hardening/
├── deploy.sh                          ← Master script (runs everything)
├── README.md                          ← This file
├── scripts/
│   ├── 01-swap-setup.sh               ← Swap creation
│   ├── 02-firewall-hardening.sh       ← UFW rules
│   ├── 03-ssh-hardening.sh            ← SSH config
│   ├── 04-fail2ban-setup.sh           ← Fail2Ban install
│   ├── 05-docker-hardening.sh         ← Docker limits + compose
│   ├── 06-monitoring-setup.sh         ← Monitoring deployment
│   └── 07-backup-setup.sh             ← Backup automation
├── configs/
│   ├── docker-compose.yml             ← Hardened n8n compose (deployed to /opt/n8n/)
│   └── watchdog.sh                    ← Health monitor script (deployed to /opt/monitor/)
└── systemd/
    ├── empire-monitor.service         ← Systemd oneshot service
    └── empire-monitor.timer           ← Runs watchdog every 60s
```

---

## After Re-Deployment: Configure Monitoring

When deploying on a new server, the monitoring system needs your Telegram credentials:

```bash
nano /opt/monitor/watchdog.sh
```

Set these two values:
```bash
TELEGRAM_TOKEN="your-bot-token-from-botfather"
ADMIN_CHAT_ID="your-chat-id-from-userinfobot"
```

Test it:
```bash
/opt/monitor/watchdog.sh
```

You should receive a Telegram message (or see "All systems healthy" in the terminal if everything is OK).

---

## Monitoring Features

| Check | Frequency | Auto-Recovery | Alert |
|-------|:---------:|:-------------:|:-----:|
| CPU usage | 60s | No (alerts only) | ⚠️ >80% / 🔴 >90% |
| RAM usage | 60s | Restarts n8n | ⚠️ >80% / 🔴 >90% |
| Disk usage | 60s | No (alerts only) | ⚠️ >80% / 🔴 >90% |
| n8n health | 60s | Auto-restart container | 🔴 If unreachable |
| Cloudflare Tunnel | 60s | Auto-restart service | 🔴 If systemd inactive |

**Smart deduplication:** The same alert won't spam you — 15-minute cooldown between repeated alerts for the same issue.

---

## Useful Commands After Deployment

```bash
# ── System Health ──
free -h                                    # Check swap + RAM
ufw status verbose                         # Firewall rules
fail2ban-client status sshd                # Banned IPs
docker stats --no-stream                   # Container resources

# ── Monitoring ──
systemctl status empire-monitor.timer      # Timer status
journalctl -u empire-monitor --no-pager -n 20  # Recent monitor runs
/opt/monitor/watchdog.sh                   # Manual health check

# ── n8n ──
docker inspect --format='{{.State.Health.Status}}' empire-n8n  # Health
docker compose -f /opt/n8n/docker-compose.yml logs --tail=30   # Logs
cd /opt/n8n && docker compose restart      # Manual restart

# ── Backups ──
ls -lh /opt/backups/n8n/                   # List backups
cat /var/log/n8n-backup.log                # Backup log

# ── Fail2Ban ──
fail2ban-client get sshd banip             # List banned IPs
fail2ban-client set sshd unbanip 1.2.3.4   # Unban an IP
```

---

## Updating n8n

The image is now pinned to prevent unexpected breaking changes. To update:

```bash
# 1. Check the latest version at https://github.com/n8n-io/n8n/releases
# 2. Edit the compose file
nano /opt/n8n/docker-compose.yml
# Change: image: n8nio/n8n:1.97.1 → image: n8nio/n8n:1.XX.Y

# 3. Pull and restart
cd /opt/n8n
docker compose pull
docker compose up -d

# 4. Verify
docker inspect --format='{{.State.Health.Status}}' empire-n8n
```

---

## Restoring from Backup

If n8n data is corrupted or lost:

```bash
cd /opt/n8n && docker compose down

# List available backups
ls -lh /opt/backups/n8n/

# Restore (replace TIMESTAMP with the backup you want)
docker run --rm \
  -v n8n_data:/target \
  -v /opt/backups/n8n:/backup \
  alpine sh -c 'rm -rf /target/* && tar xzf /backup/n8n_YYYYMMDD_HHMMSS.tar.gz -C /target'

docker compose up -d
```

---

## Security Scorecard (After Deployment)

| Category | Before | After |
|----------|:------:|:-----:|
| SSH Security | 6/10 | 9/10 |
| Firewall | 4/10 | 9/10 |
| Brute-Force Protection | 1/10 | 9/10 |
| Resource Isolation | 2/10 | 8/10 |
| Memory Safety (Swap) | 0/10 | 9/10 |
| Monitoring & Alerting | 0/10 | 9/10 |
| Backup & Recovery | 2/10 | 8/10 |
| **Overall** | **3.7/10** | **8.7/10** |

---

## Optional: External Uptime Monitor

For coverage when the entire server is down (the internal watchdog can't alert if the server itself crashes):

1. Sign up at **[BetterStack](https://betterstack.com)** or **[UptimeRobot](https://uptimerobot.com)** (both free)
2. Add a monitor: HTTPS → `https://bot.empireenglish.online` → 5 min interval
3. Set alert contact: Telegram or Email
4. Done — you'll be notified if the server is completely unreachable

---

*Built for Empire English Community — zero vendor lock-in, self-hosted, open-source tools only.*
