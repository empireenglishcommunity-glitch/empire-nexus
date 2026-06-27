# 🚨 Emergency Recovery & Operations Guide

**Server:** `empire-n8n` — Hetzner CX23, Helsinki
**Last Verified:** June 21, 2026
**Purpose:** Standalone emergency reference. Download and store locally on your PC.

> **This file contains everything needed to recover the server from any failure scenario.**
> Keep a local copy at: `C:\Users\97150\Documents\EmpireEnglish\EMERGENCY-RECOVERY.md`

---

## Table of Contents

1. [Quick Reference (Connection Details)](#1-quick-reference)
2. [Service Health Check (Run First)](#2-service-health-check)
3. [Common Problems & Solutions](#3-common-problems--solutions)
4. [n8n Recovery](#4-n8n-recovery)
5. [Cloudflare Tunnel Recovery](#5-cloudflare-tunnel-recovery)
6. [SSH Access Recovery](#6-ssh-access-recovery)
7. [Memory / OOM Recovery](#7-memory--oom-recovery)
8. [Disk Full Recovery](#8-disk-full-recovery)
9. [Backup & Restore Procedures](#9-backup--restore-procedures)
10. [Fail2Ban Management](#10-fail2ban-management)
11. [Monitoring System Recovery](#11-monitoring-system-recovery)
12. [Full Server Rebuild (Disaster Recovery)](#12-full-server-rebuild)
13. [Docker Operations](#13-docker-operations)
14. [Firewall Management](#14-firewall-management)
15. [Critical File Locations](#15-critical-file-locations)
16. [Credential Locations](#16-credential-locations)
17. [Important Configuration Values](#17-important-configuration-values)

---

## 1. Quick Reference

### Connection

```
SSH:     ssh root@77.42.43.250
n8n:     https://bot.empireenglish.online
Direct:  BLOCKED (port 5678 is localhost-only)
```

### Emergency Access (if SSH fails)

1. **Hetzner Console:** https://console.hetzner.cloud → Projects → Empire English → server `empire-n8n` → Console (web VNC)
2. **Hetzner Rescue Mode:** Same page → Rescue tab → Enable (provides temporary Linux to fix disk/boot issues)

### SSH Key Location (your Windows PC)

```
C:\Users\97150\.ssh\id_ed25519       (private key — NEVER share)
C:\Users\97150\.ssh\id_ed25519.pub   (public key)
```

---

## 2. Service Health Check

**Run this first when investigating ANY issue:**

```bash
echo "=== SYSTEM ===" && uname -r && uptime && echo ""
echo "=== RESOURCES ===" && free -h && echo "" && df -h / && echo ""
echo "=== SWAP ===" && swapon --show && echo ""
echo "=== SERVICES ===" 
echo -n "Docker: " && systemctl is-active docker
echo -n "Tunnel: " && systemctl is-active cloudflared
echo -n "Fail2Ban: " && systemctl is-active fail2ban
echo -n "Monitor: " && systemctl is-active empire-monitor.timer
echo ""
echo "=== N8N ===" 
docker inspect --format='Health: {{.State.Health.Status}} | Running: {{.State.Running}}' empire-n8n 2>/dev/null || echo "Container not found!"
curl -sf -o /dev/null -w "HTTP: %{http_code}\n" http://localhost:5678/ || echo "n8n NOT responding!"
echo ""
echo "=== RECENT ISSUES ==="
journalctl -u empire-monitor --no-pager -n 5 --since "1 hour ago"
```

---

## 3. Common Problems & Solutions

### Problem: "bot.empireenglish.online is down"

**Diagnosis flow:**

```
Can you SSH in?
├── NO → Server is completely down → Go to Hetzner Console (section 6)
└── YES → Run health check (section 2)
         ├── n8n unhealthy/stopped → Section 4
         ├── Tunnel inactive → Section 5
         ├── RAM >90% → Section 7
         └── Disk >90% → Section 8
```

### Problem: "I got a Telegram alert"

| Alert Message | What To Do |
|--------------|------------|
| 🟢 RESOLVED | Nothing — system self-healed |
| ⚠️ WARNING (RAM/CPU/Disk) | Monitor; may self-resolve |
| 🔴 CRITICAL + "Service restored" | System recovered, but investigate root cause |
| 🔴 CRITICAL + "MANUAL INTERVENTION" | SSH in immediately, follow relevant section below |

### Problem: "I got a BetterStack email"

The entire server is unreachable from the internet:
1. Try SSH: `ssh root@77.42.43.250`
2. If SSH fails → Go to Hetzner Console (web VNC)
3. If SSH works → Check tunnel: `systemctl status cloudflared`
4. If Hetzner console also fails → Check Hetzner status page for outages

### Problem: "I'm locked out of SSH"

→ Go directly to Section 6

---

## 4. n8n Recovery

### n8n container stopped / unhealthy

```bash
# Check status
docker ps -a | grep empire-n8n
docker inspect --format='{{.State.Status}} | Health: {{.State.Health.Status}}' empire-n8n

# View recent logs (what went wrong)
docker logs empire-n8n --tail=50

# Restart
cd /opt/n8n && docker compose restart

# Wait and verify
sleep 30
docker inspect --format='{{.State.Health.Status}}' empire-n8n
curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:5678/
```

### n8n container completely missing

```bash
cd /opt/n8n
docker compose up -d

# Verify
sleep 30
docker inspect --format='{{.State.Health.Status}}' empire-n8n
```

### n8n starts but keeps crashing (restart loop)

```bash
# Check logs for the error
docker logs empire-n8n --tail=100

# Common causes:
# 1. Corrupted database → restore from backup (section 9)
# 2. Bad workflow → access n8n UI, disable the problematic workflow
# 3. Memory issue → check: docker stats --no-stream empire-n8n
# 4. Version issue → pin a known-good version in docker-compose.yml
```

### n8n UI loads but webhooks don't work

```bash
# Verify tunnel is delivering traffic
systemctl status cloudflared
journalctl -u cloudflared --no-pager -n 20

# Verify webhook URL is correct
docker exec empire-n8n env | grep WEBHOOK
# Should show: WEBHOOK_URL=https://bot.empireenglish.online/

# Test from outside
curl -I https://bot.empireenglish.online/
```

---

## 5. Cloudflare Tunnel Recovery

### Tunnel service not running

```bash
# Check status
systemctl status cloudflared

# Restart
systemctl restart cloudflared

# Verify
sleep 5
systemctl is-active cloudflared
journalctl -u cloudflared --no-pager -n 10
```

### Tunnel running but bot.empireenglish.online unreachable

```bash
# Check tunnel logs for errors
journalctl -u cloudflared --no-pager -n 30

# Verify config
cat /root/.cloudflared/config.yml

# Verify n8n is actually running locally
curl -sf http://localhost:5678/ && echo "n8n OK" || echo "n8n DOWN"

# Full restart (tunnel + n8n)
systemctl restart cloudflared
cd /opt/n8n && docker compose restart
```

### Tunnel credentials corrupted / need recreation

```bash
# Delete old tunnel (from Cloudflare dashboard or CLI)
cloudflared tunnel delete empire-n8n

# Create new tunnel
cloudflared tunnel create empire-n8n

# Re-route DNS
cloudflared tunnel route dns empire-n8n bot.empireenglish.online

# Update config with new tunnel ID
nano /root/.cloudflared/config.yml
# Change the tunnel: and credentials-file: lines to new values

# Restart
systemctl restart cloudflared
```

---

## 6. SSH Access Recovery

### "Connection refused" or "Connection timed out"

**Possible causes:**
1. Server is completely down → Hetzner Console
2. UFW locked you out → Hetzner Console
3. Fail2Ban banned your IP → Hetzner Console

**Recovery via Hetzner Console:**

1. Go to: https://console.hetzner.cloud
2. Select server `empire-n8n` → **Console** tab (web VNC)
3. Login as `root` (you'll need the root password set during server creation, or use Rescue mode)

**If your IP was banned by Fail2Ban:**
```bash
# In Hetzner Console:
fail2ban-client set sshd unbanip YOUR.IP.ADDRESS
```

**If SSH config is broken:**
```bash
# In Hetzner Console:
cp /etc/ssh/sshd_config.backup.20260621_215436 /etc/ssh/sshd_config
systemctl restart sshd
```

**If UFW locked everything:**
```bash
# In Hetzner Console:
ufw allow 22/tcp
ufw reload
```

### "Permission denied (publickey)"

Your SSH key isn't being sent or doesn't match:
```powershell
# On your Windows PC, verify the key exists:
dir C:\Users\97150\.ssh\id_ed25519

# Force use of specific key:
ssh -i C:\Users\97150\.ssh\id_ed25519 root@77.42.43.250

# If key was lost — use Hetzner Console to add a new public key:
# In Console: nano ~/.ssh/authorized_keys → paste your new public key
```

---

## 7. Memory / OOM Recovery

### Server unresponsive due to OOM

If you can SSH in:
```bash
# Check what's consuming memory
free -h
docker stats --no-stream

# Kill and restart n8n (releases its memory)
cd /opt/n8n && docker compose restart

# If that's not enough, clear Docker cache
docker system prune -f

# Check swap usage
swapon --show
```

If you CANNOT SSH in:
1. Use Hetzner Console (web VNC)
2. Or: Hetzner dashboard → Power → Reset (hard reboot)
3. After reboot, all services auto-start

### Prevent future OOM

The current setup already protects against this:
- n8n limited to 2.5GB RAM (Docker kills only n8n, not server)
- 2GB swap provides buffer
- Watchdog alerts at 80% RAM and auto-restarts n8n at 90%

If it keeps happening, upgrade to CX33 (8GB RAM, $8.99/mo) via Hetzner dashboard.

---

## 8. Disk Full Recovery

### Signs: services crashing, "no space left on device" errors

```bash
# Check disk usage
df -h /
du -sh /var/lib/docker/ /var/log/ /opt/backups/ /tmp/ 2>/dev/null

# Quick fix: clean Docker
docker system prune -f
docker image prune -a -f

# Clean old logs
journalctl --vacuum-time=3d
truncate -s 0 /var/log/n8n-backup.log

# Clean old backups (keep last 3)
cd /opt/backups/n8n && ls -t n8n_*.tar.gz | tail -n +4 | xargs -r rm

# Verify
df -h /
```

### If disk is 100% full and services won't start

```bash
# Emergency space recovery (safe commands):
rm -f /tmp/*
journalctl --vacuum-size=50M
docker system prune -f

# Then restart services
cd /opt/n8n && docker compose up -d
systemctl restart cloudflared
```

---

## 9. Backup & Restore Procedures

### Run a manual backup NOW

```bash
/opt/backups/backup-n8n.sh
```

### List available backups

```bash
ls -lh /opt/backups/n8n/
```

### Restore n8n from backup

⚠️ **This replaces ALL n8n data (workflows, credentials, settings) with the backup version.**

```bash
# 1. Stop n8n
cd /opt/n8n && docker compose down

# 2. List backups and choose one
ls -lh /opt/backups/n8n/

# 3. Restore (replace FILENAME with the actual backup file)
docker run --rm \
  -v n8n_data:/target \
  -v /opt/backups/n8n:/backup \
  alpine sh -c 'rm -rf /target/* && tar xzf /backup/FILENAME.tar.gz -C /target'

# 4. Start n8n
docker compose up -d

# 5. Verify
sleep 30
docker inspect --format='{{.State.Health.Status}}' empire-n8n
curl -sf -o /dev/null -w "%{http_code}\n" http://localhost:5678/
```

### Backup doesn't exist / all backups corrupted

If you need to start fresh:
```bash
# Remove corrupted volume
cd /opt/n8n && docker compose down
docker volume rm n8n_data

# Start fresh (you'll need to reconfigure n8n from scratch)
docker compose up -d
```

Then re-import workflows from the GitHub repo or from n8n's built-in export (if you previously exported JSON files).

---

## 10. Fail2Ban Management

### Check status and banned IPs

```bash
fail2ban-client status sshd
```

### Unban a specific IP

```bash
fail2ban-client set sshd unbanip 1.2.3.4
```

### Unban ALL IPs

```bash
fail2ban-client unban --all
```

### Fail2Ban not running

```bash
systemctl status fail2ban
systemctl restart fail2ban

# If config is broken:
cat /etc/fail2ban/jail.local   # Check for syntax errors
fail2ban-client -t             # Test config
```

### Temporarily disable Fail2Ban (emergency access)

```bash
systemctl stop fail2ban
# ... do your work ...
systemctl start fail2ban
```

---

## 11. Monitoring System Recovery

### Watchdog not sending alerts

```bash
# Check timer is running
systemctl status empire-monitor.timer
systemctl list-timers | grep empire

# Run manually to test
/opt/monitor/watchdog.sh

# Check if Telegram credentials are correct
grep -E "TELEGRAM_TOKEN|ADMIN_CHAT_ID" /opt/monitor/watchdog.sh

# Test Telegram delivery directly
curl -s -X POST "https://api.telegram.org/bot$(grep TELEGRAM_TOKEN /opt/monitor/watchdog.sh | cut -d'"' -f2)/sendMessage" \
  -d chat_id="$(grep ADMIN_CHAT_ID /opt/monitor/watchdog.sh | cut -d'"' -f2)" \
  -d text="Test alert from manual check"
```

### Restart monitoring

```bash
systemctl restart empire-monitor.timer
systemctl status empire-monitor.timer
```

### Reset alert deduplication (force re-alert)

```bash
rm -f /opt/monitor/state/*
```

---

## 12. Full Server Rebuild (Disaster Recovery)

If the server is completely lost (hardware failure, irreparable corruption):

### Step 1: Create new Hetzner server

1. https://console.hetzner.cloud → New Server
2. Location: Helsinki (hel1)
3. Image: Ubuntu 26.04
4. Type: CX23 (or CX33 for more RAM)
5. SSH key: Add your public key from `C:\Users\97150\.ssh\id_ed25519.pub`
6. Name: `empire-n8n`

### Step 2: Run the hardening package

```bash
# Install git and Docker
apt update && apt install -y git
curl -fsSL https://get.docker.com | sh

# Clone the repo
git clone https://github.com/empireenglishcommunity-glitch/Claude.git /tmp/empire
cp -r /tmp/empire/server-hardening /root/server-hardening

# Run hardening (all steps)
cd /root/server-hardening
bash deploy.sh
```

### Step 3: Restore Cloudflare Tunnel

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create empire-n8n

# Route DNS
cloudflared tunnel route dns empire-n8n bot.empireenglish.online

# Configure
cat > /root/.cloudflared/config.yml << EOF
tunnel: <NEW_TUNNEL_ID>
credentials-file: /root/.cloudflared/<NEW_TUNNEL_ID>.json

ingress:
  - hostname: bot.empireenglish.online
    service: http://localhost:5678
  - service: http_status:404
EOF

# Enable as service
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
```

### Step 4: Restore n8n from backup

If you have a backup file saved off-server:
```bash
# Upload backup to new server
scp backup_file.tar.gz root@NEW_IP:/opt/backups/n8n/

# Restore (section 9 procedure)
```

If no backup exists, start fresh in n8n and reconfigure workflows manually.

### Step 5: Update monitoring credentials

```bash
nano /opt/monitor/watchdog.sh
# Set TELEGRAM_TOKEN and ADMIN_CHAT_ID
```

### Step 6: Update BetterStack

In BetterStack dashboard, update the monitor if the URL changed.

---

## 13. Docker Operations

### View all containers

```bash
docker ps -a
```

### View n8n resource usage

```bash
docker stats --no-stream empire-n8n
```

### View n8n logs

```bash
docker logs empire-n8n --tail=100
docker logs empire-n8n --since="1 hour ago"
docker logs empire-n8n -f          # Follow live (Ctrl+C to exit)
```

### Enter n8n container shell

```bash
docker exec -it empire-n8n sh
```

### Clean Docker disk space

```bash
docker system prune -f              # Remove stopped containers + unused networks
docker image prune -a -f            # Remove ALL unused images
docker volume prune -f              # ⚠️ CAREFUL: removes unused volumes
```

### Update n8n to a new version

```bash
cd /opt/n8n

# 1. Backup first!
/opt/backups/backup-n8n.sh

# 2. Edit version
nano docker-compose.yml
# Change: image: n8nio/n8n:2.26.8 → image: n8nio/n8n:X.Y.Z

# 3. Pull and restart
docker compose pull
docker compose up -d

# 4. Verify
sleep 35
docker inspect --format='{{.State.Health.Status}}' empire-n8n
docker exec empire-n8n n8n --version
```

### Rollback n8n to previous version

```bash
cd /opt/n8n

# 1. Change back to old version
nano docker-compose.yml
# Change image tag back to: n8nio/n8n:2.26.8

# 2. Restart
docker compose up -d

# 3. If data is also corrupted, restore backup (section 9)
```

---

## 14. Firewall Management

### View current rules

```bash
ufw status verbose
```

### Current expected state

```
Default: deny (incoming), allow (outgoing), deny (routed)
22/tcp    LIMIT IN    Anywhere
22/tcp    LIMIT IN    Anywhere (v6)
+ Fail2Ban REJECT rules for banned IPs
```

### Temporarily allow a port (for debugging)

```bash
ufw allow 8080/tcp
# ... do your work ...
ufw delete allow 8080/tcp
```

### If you lock yourself out (from Hetzner Console)

```bash
ufw allow 22/tcp
ufw reload
```

### Reset UFW to safe state

```bash
ufw reset
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp
ufw enable
```

---

## 15. Critical File Locations

```
/opt/n8n/docker-compose.yml              ← n8n configuration (THE source of truth)
/opt/monitor/watchdog.sh                  ← Monitoring script (contains Telegram token)
/opt/backups/backup-n8n.sh                ← Backup script
/opt/backups/n8n/                         ← Backup files (14-day rotation)
/root/.cloudflared/config.yml             ← Tunnel routing
/root/.cloudflared/*.json                 ← Tunnel credentials
/root/.cloudflared/cert.pem               ← Cloudflare auth certificate
/etc/ssh/sshd_config                      ← SSH configuration
/etc/ssh/sshd_config.backup.20260621_*    ← SSH config backup (pre-hardening)
/etc/fail2ban/jail.local                  ← Fail2Ban jail config
/etc/docker/daemon.json                   ← Docker global log rotation
/etc/sysctl.d/99-swap.conf                ← Swap tuning (swappiness=10)
/etc/fstab                                ← Swap persistence (/swapfile entry)
/swapfile                                 ← 2GB swap file
/var/lib/docker/volumes/n8n_data/         ← n8n persistent data (DO NOT DELETE)
/var/log/n8n-backup.log                   ← Backup log
/etc/systemd/system/empire-monitor.*      ← Monitoring systemd units
/etc/systemd/system/cloudflared.service   ← Tunnel systemd unit
```

---

## 16. Credential Locations

| Credential | Where It Lives | How to Access |
|---|---|---|
| SSH private key | Your PC: `C:\Users\97150\.ssh\id_ed25519` | Never on server |
| n8n login | n8n internal database | Login at https://bot.empireenglish.online |
| Telegram bot token (monitoring) | `/opt/monitor/watchdog.sh` | `grep TELEGRAM_TOKEN /opt/monitor/watchdog.sh` |
| Telegram bot token (n8n bots) | n8n credential store (encrypted) | Via n8n UI → Credentials |
| Google Service Account | n8n credential store (encrypted) | Via n8n UI → Credentials |
| Cloudflare tunnel creds | `/root/.cloudflared/*.json` | Auto-generated |
| Cloudflare auth cert | `/root/.cloudflared/cert.pem` | Generated via `cloudflared tunnel login` |

> ⚠️ **If the server is compromised:** Revoke/rotate the Telegram token (@BotFather), recreate the Cloudflare tunnel (dashboard), change the n8n password, and regenerate any Google Service Account keys.

---

## 17. Important Configuration Values

| Parameter | Value | Where Set |
|---|---|---|
| n8n version | 2.26.8 | `/opt/n8n/docker-compose.yml` |
| n8n memory limit | 2560M | `/opt/n8n/docker-compose.yml` |
| n8n CPU limit | 1.5 cores | `/opt/n8n/docker-compose.yml` |
| n8n PID limit | 200 | `/opt/n8n/docker-compose.yml` |
| n8n port | 127.0.0.1:5678 | `/opt/n8n/docker-compose.yml` |
| n8n webhook URL | https://bot.empireenglish.online/ | Environment variable in compose |
| Swap size | 2GB | `/swapfile` + `/etc/fstab` |
| Swappiness | 10 | `/etc/sysctl.d/99-swap.conf` |
| SSH MaxAuthTries | 3 | `/etc/ssh/sshd_config` |
| SSH idle timeout | 5 min | `/etc/ssh/sshd_config` (ClientAliveInterval=300) |
| Fail2Ban max retries | 3 | `/etc/fail2ban/jail.local` |
| Fail2Ban ban time | 24 hours | `/etc/fail2ban/jail.local` |
| Backup schedule | 3:00 AM daily | crontab (`crontab -l`) |
| Backup retention | 14 days | `/opt/backups/backup-n8n.sh` |
| Monitor interval | 60 seconds | `/etc/systemd/system/empire-monitor.timer` |
| Monitor alert cooldown | 15 minutes | `/opt/monitor/watchdog.sh` |
| RAM warn threshold | 80% | `/opt/monitor/watchdog.sh` |
| RAM critical threshold | 90% | `/opt/monitor/watchdog.sh` |
| Disk warn threshold | 80% | `/opt/monitor/watchdog.sh` |
| Disk critical threshold | 90% | `/opt/monitor/watchdog.sh` |
| Tunnel hostname | bot.empireenglish.online | `/root/.cloudflared/config.yml` |
| Tunnel ID | 0502cb57-380c-4d27-a415-15e0ecc39139 | `/root/.cloudflared/config.yml` |
| Server timezone | Asia/Dubai | n8n environment variable |
| Server IP | 77.42.43.250 | Hetzner assignment |
| Server IPv6 | 2a01:4f9:c014:7513::1 | Hetzner assignment |

---

## Quick Command Cheat Sheet

```bash
# ── STATUS ──
docker inspect --format='{{.State.Health.Status}}' empire-n8n
systemctl is-active cloudflared fail2ban empire-monitor.timer
free -h && df -h /
fail2ban-client status sshd

# ── RESTART SERVICES ──
cd /opt/n8n && docker compose restart     # Restart n8n
systemctl restart cloudflared              # Restart tunnel
systemctl restart fail2ban                 # Restart fail2ban
systemctl restart empire-monitor.timer     # Restart monitoring

# ── LOGS ──
docker logs empire-n8n --tail=50           # n8n logs
journalctl -u cloudflared -n 20           # Tunnel logs
journalctl -u empire-monitor -n 20        # Monitor logs
cat /var/log/n8n-backup.log               # Backup log

# ── BACKUP ──
/opt/backups/backup-n8n.sh                 # Run backup now
ls -lh /opt/backups/n8n/                   # List backups

# ── EMERGENCY ──
docker system prune -f                     # Free disk space
fail2ban-client set sshd unbanip X.X.X.X  # Unban IP
rm -f /opt/monitor/state/*                 # Reset alert cooldowns
reboot                                     # Full reboot (all auto-starts)
```

---

*End of Emergency Recovery Guide — v1.0*
*Keep a local copy. This is your insurance policy.*
