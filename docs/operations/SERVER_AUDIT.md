# 🛡️ Server Infrastructure Audit & Optimization Assessment

**Server:** `empire-n8n` (Hetzner CX23, Helsinki)
**Audit Date:** June 21, 2026
**Auditor Role:** Senior DevOps Architect / Infrastructure Security Engineer
**Classification:** Mission-Critical Business Infrastructure
**Evidence Source:** `SERVER_REFERENCE.md` (verified handover document, last updated June 20, 2026)

---

## ✅ IMPLEMENTATION STATUS: ALL ITEMS COMPLETE

**Remediation Deployed:** June 21, 2026
**Infrastructure Score:** 3.7/10 → **9.0/10**

All 12 remediation items from this audit have been implemented, verified, and confirmed operational after a full server reboot. See `SERVER_REFERENCE.md` (v2.0) for the current production state.

| # | Remediation Item | Status | Notes |
|---|-----------------|:------:|-------|
| 1 | Create 2GB swap file | ✅ Done | `/swapfile`, swappiness=10, persistent via fstab |
| 2 | Close port 5678 in UFW | ✅ Done | Port bound to `127.0.0.1` (Docker bypass fix) |
| 3 | Verify SSH password auth disabled | ✅ Done | `PasswordAuthentication no` enforced |
| 4 | Install & configure Fail2Ban | ✅ Done | SSH jail, 24h ban, 4 attackers caught on day 1 |
| 5 | Add container memory/CPU limits | ✅ Done | 2560M RAM, 1.5 CPU, 200 PIDs |
| 6 | Deploy Telegram monitoring | ✅ Done | 60s checks, auto-recovery, @macal_guardian_bot |
| 7 | Configure Docker log rotation | ✅ Done | 10MB × 5 files per container |
| 8 | Add Docker HEALTHCHECK | ✅ Done | wget healthz every 30s, 3 retries |
| 9 | Pin n8n Docker image version | ✅ Done | Pinned to 2.26.8 |
| 10 | Set up automated backup | ✅ Done | Daily 3AM, 14-day rotation |
| 11 | Add external uptime monitoring | ✅ Done | BetterStack, 3min checks, email alerts |
| 12 | Add UFW SSH rate limiting | ✅ Done | `ufw limit 22/tcp` |

**Additional items completed beyond the original plan:**
- Kernel updated from 7.0.0-15 to 7.0.0-22 (security patches)
- Full reboot verified (all services auto-recovered)
- Docker-UFW bypass addressed (localhost binding instead of firewall rule)
- Alert deduplication (15-min cooldown prevents spam)

---

> **The audit sections below are preserved as a historical record of what was found and why each fix was needed. For the current server state, see `SERVER_REFERENCE.md` (v2.0, Hardened).**

---

## Table of Contents

1. [Security Hardening Audit](#part-1-security-hardening-audit)
2. [Stability & Infrastructure Resilience Audit](#part-2-stability--infrastructure-resilience-audit)
3. [Monitoring, Alerting & Automated Recovery System](#part-3-monitoring-alerting--automated-recovery-system)
4. [Gap Analysis](#part-4-gap-analysis)
5. [Prioritized Remediation Plan](#part-5-prioritized-remediation-plan)
6. [Implementation Plan (Detailed)](#part-6-implementation-plan-detailed)

---


## PART 1: SECURITY HARDENING AUDIT

### 1.1 SSH Authentication

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| SSH Key Authentication | ED25519 key pair configured; root login via `ssh root@77.42.43.250` | ✅ Yes | Low | None — strong key type | — |
| Password Authentication Disabled | Document states: *"Needs confirmation (likely disabled since SSH key was configured at creation)"* | ⚠️ Unverified | **HIGH** | Must SSH in and verify `PasswordAuthentication no` in `/etc/ssh/sshd_config` | **Critical** |
| Root Direct Login | Enabled — no non-root users exist | ✅ Yes (by design) | Medium | Acceptable for single operator; create a sudo user if team grows | Low |
| SSH Port | Default port 22, publicly accessible | ✅ Yes | Medium | Consider changing to non-standard port (e.g., 2222) to reduce automated scan noise | Medium |
| SSH Protocol Version | Ubuntu 26.04 defaults to Protocol 2 only | ✅ Yes | Low | None | — |
| Idle Session Timeout | Not documented — likely Ubuntu default (no timeout) | ❌ No | Low | Set `ClientAliveInterval 300` + `ClientAliveCountMax 2` | Low |
| Max Auth Tries | Not documented — likely default (6) | ⚠️ Unknown | Low | Set `MaxAuthTries 3` in sshd_config | Low |

**SSH Risk Summary:**
- **Critical gap:** Password authentication status is *unverified*. If enabled, the server is vulnerable to brute-force attacks with NO fail2ban installed.
- **Acceptable:** Root login for single-operator use with key auth enforced.


---

### 1.2 Firewall Protection (UFW)

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| UFW Installed & Active | Confirmed active per documentation | ✅ Yes | Low | None | — |
| Port 22 (SSH) | Open to public | ✅ Yes | Medium | Acceptable; consider rate-limiting (`ufw limit 22/tcp`) | Medium |
| Port 5678 (n8n) | Open to public **directly** | ✅ Yes | **HIGH** | **Should be blocked from public**. n8n is already accessible via Cloudflare Tunnel. Direct access exposes unauthenticated HTTP n8n on public IP. | **Critical** |
| IPv6 Firewall | Not documented; UFW may only cover IPv4 | ⚠️ Unknown | Medium | Verify `IPV6=yes` in `/etc/default/ufw` | Medium |
| Outbound Rules | Not documented — likely all outbound allowed (default) | ⚠️ Default | Low | Acceptable for this use case | — |
| Default Deny Inbound | Not explicitly confirmed | ⚠️ Assumed | Medium | Verify `ufw default deny incoming` is set | Medium |

**Firewall Critical Finding:**

> ⚠️ **Port 5678 is publicly accessible on the raw IP address (`http://77.42.43.250:5678`).**
>
> This means the n8n admin interface is reachable directly, bypassing Cloudflare's security layers. If n8n has any vulnerability, session hijacking exposure, or weak password — an attacker can reach it directly. The tunnel already provides full access; port 5678 should be firewalled to `localhost` only.


---

### 1.3 Cloudflare Protection

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| Traffic via Cloudflare Tunnel | All production traffic to `bot.empireenglish.online` routes through Cloudflare edge | ✅ Yes | Low | None — properly configured | — |
| Server IP Hidden from DNS | CNAME points to tunnel UUID, not IP | ✅ Yes | Low | None | — |
| Server IP Publicly Known | IP `77.42.43.250` is documented and port 5678 is open — any scanner will find n8n | ❌ Exposed | **HIGH** | Close port 5678 in UFW; all n8n access via tunnel only | **Critical** |
| Cloudflare WAF / Bot Protection | Free plan — basic protection only | ⚠️ Limited | Medium | Acceptable for current scale; revisit at growth | Low |
| Tunnel Authentication | Named tunnel with credential file + systemd auto-start | ✅ Yes | Low | None | — |
| Tunnel Catch-All | `http_status:404` for unmatched hostnames | ✅ Yes | Low | Good — prevents probe exposure | — |

**Cloudflare Critical Finding:**

> The Cloudflare Tunnel correctly hides the server IP at the DNS level. However, **port 5678 being open on UFW completely negates this protection** — any internet scanner (Shodan, Censys) will discover the n8n instance on the public IP. This is the #1 security vulnerability.


---

### 1.4 Brute-Force Protection

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| Fail2Ban | **Not installed** (explicitly stated in documentation) | ❌ No | **HIGH** | Install and configure for SSH at minimum | **High** |
| SSH Rate Limiting (UFW) | Not configured | ❌ No | Medium | Add `ufw limit 22/tcp` as immediate mitigation | High |
| n8n Login Rate Limiting | No rate limiting — default n8n behavior, now exposed on public IP | ❌ No | **HIGH** | Close port 5678 publicly (eliminates risk); if kept open, add reverse proxy with rate limiting | **Critical** |
| Cloudflare Rate Limiting | Not configured (tunnel traffic only) | ❌ No | Low | Optional — Cloudflare handles DDoS at edge | Low |
| Automated Ban/Alert on Failed Attempts | No mechanism exists | ❌ No | High | Fail2Ban + Telegram notification on ban events | High |

**Brute-Force Risk Summary:**
- **SSH** is protected by key-only authentication (if confirmed), but without fail2ban, failed attempts still consume resources and fill logs with noise. At scale, this can become a slow DoS.
- **n8n** has zero brute-force protection on the public-facing port 5678. The built-in auth has no lockout mechanism.

---


## PART 2: STABILITY & INFRASTRUCTURE RESILIENCE AUDIT

### 2.1 Docker Architecture

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| n8n Containerized | Running as Docker container (`n8nio/n8n:latest`) | ✅ Yes | Low | None | — |
| Docker Compose Used | `/opt/n8n/docker-compose.yml` — v2 plugin syntax | ✅ Yes | Low | None | — |
| Persistent Data Volume | Named volume `n8n_data` at `/var/lib/docker/volumes/n8n_data/` | ✅ Yes | Low | None — survives rebuilds | — |
| Image Pinning | Uses `:latest` tag | ⚠️ Risky | Medium | Pin to specific version (e.g., `n8nio/n8n:1.x.y`) to prevent breaking updates | Medium |
| Docker Log Rotation | Not documented — likely default (unlimited JSON logs) | ⚠️ Unknown | Medium | Configure log rotation to prevent disk exhaustion | Medium |
| Docker Network Isolation | Not documented — likely default bridge | ⚠️ Default | Low | Acceptable for single-container setup | — |
| Unused Images/Containers Cleanup | No automated pruning documented | ❌ No | Low | Add monthly `docker system prune -f` cron | Low |


---

### 2.2 Container Auto-Recovery

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| n8n Restart Policy | `restart: always` — auto-recovers on crash and reboot | ✅ Yes | Low | None — properly configured | — |
| Cloudflare Tunnel Recovery | systemd with `enabled` + `RestartSec=5` | ✅ Yes | Low | None — properly configured | — |
| Docker Engine Auto-Start | systemd managed, auto-starts on boot | ✅ Yes | Low | None | — |
| Full Reboot Recovery | All services confirmed to auto-start after full server reboot | ✅ Yes | Low | None | — |
| Health Check (n8n container) | Not documented — likely no Docker HEALTHCHECK | ❌ No | Medium | Add `healthcheck` directive to docker-compose.yml | Medium |
| Dependency Ordering | Not documented — n8n starts before tunnel could theoretically cause race | ⚠️ Assumed OK | Low | Docker `restart: always` handles this through retries | — |

---

### 2.3 Resource Isolation

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| CPU Limits (n8n container) | **No limits configured** in docker-compose.yml | ❌ No | Medium | Add `deploy.resources.limits.cpus: '1.5'` | Medium |
| RAM Limits (n8n container) | **No limits configured** | ❌ No | **HIGH** | Add `deploy.resources.limits.memory: 2560M` — without this, a memory leak can kill the entire server | **High** |
| OOM (Out-of-Memory) Killer Priority | Default — kernel decides what to kill | ⚠️ Default | Medium | With memory limits, Docker handles OOM per container | Medium |
| Disk Usage Limits | No per-container disk quotas | ❌ No | Low | Monitor manually; 40GB with 12.7% used = safe headroom | Low |
| Process Limits (pids) | Not configured | ❌ No | Low | Add `pids_limit: 200` as fork-bomb protection | Low |


---

### 2.4 Swap Configuration

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| Swap Space Exists | **Not documented — likely not configured** (Hetzner cloud VMs typically ship without swap) | ❌ No | **HIGH** | Create swap file immediately | **Critical** |
| Swap Size | N/A | ❌ No | **HIGH** | Recommended: 2 GB (50% of RAM for a 4GB server) | **Critical** |
| Swappiness Setting | N/A | ❌ No | Medium | Set `vm.swappiness=10` (prefer RAM, use swap only as safety net) | High |
| OOM Protection Without Swap | With no swap and no container memory limits, a memory spike = instant OOM kill = potential server crash | — | **CRITICAL** | Swap is the last line of defense before OOM killer triggers | **Critical** |

**Swap Critical Finding:**

> ⚠️ A 4GB RAM server with NO swap and NO container memory limits is vulnerable to complete system failure from any memory spike. n8n workflows processing large payloads, a burst of concurrent webhooks, or a memory leak would trigger the Linux OOM killer — potentially killing critical processes (Docker, sshd, cloudflared) and rendering the server unrecoverable without a hard reboot from Hetzner's console.
>
> **This is the #1 stability risk on this server.**

---


## PART 3: MONITORING, ALERTING & AUTOMATED RECOVERY SYSTEM

### 3.1 Current Monitoring State

| Component | Current Status | Implemented | Risk Level | Action Required | Priority |
|-----------|---------------|:-----------:|:----------:|-----------------|:--------:|
| CPU Monitoring | None | ❌ No | **HIGH** | Implement resource monitoring stack | **Critical** |
| RAM Monitoring | None | ❌ No | **HIGH** | Implement resource monitoring stack | **Critical** |
| Disk Monitoring | None | ❌ No | **HIGH** | Implement resource monitoring stack | **Critical** |
| Service Availability Monitoring | None | ❌ No | **HIGH** | Implement service health checks | **Critical** |
| Uptime Monitoring | None (explicitly documented as missing) | ❌ No | **HIGH** | External uptime check on `bot.empireenglish.online` | **Critical** |
| Log Aggregation | None — logs only in Docker/journald | ❌ No | Medium | Optional for current scale | Low |
| Telegram Alerting | None | ❌ No | **HIGH** | Primary alert channel | **Critical** |
| Automated Recovery | None (only Docker restart policies exist) | ⚠️ Partial | High | Implement watchdog scripts | High |


---

### 3.2 Recommended Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    SERVER: empire-n8n                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  MONITORING STACK (systemd timer, every 60s)          │   │
│  │                                                       │   │
│  │  ┌─────────────┐   ┌──────────────┐   ┌──────────┐  │   │
│  │  │ watchdog.sh │   │ health-check │   │  alerts  │  │   │
│  │  │ (cron 1min) │   │  (curl/API)  │   │(Telegram)│  │   │
│  │  └──────┬──────┘   └──────┬───────┘   └─────┬────┘  │   │
│  │         │                  │                  │       │   │
│  │         ▼                  ▼                  ▼       │   │
│  │  ┌──────────────────────────────────────────────────┐│   │
│  │  │           DECISION ENGINE (bash script)          ││   │
│  │  │                                                   ││   │
│  │  │  1. Check CPU/RAM/Disk thresholds                ││   │
│  │  │  2. Check service health (n8n, cloudflared)      ││   │
│  │  │  3. If threshold breached → attempt recovery     ││   │
│  │  │  4. Send Telegram alert with status              ││   │
│  │  └──────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Docker    │  │ cloudflared │  │   n8n container      │  │
│  │  Engine    │  │  (systemd)  │  │  (restart:always)    │  │
│  └────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│  Telegram Bot API    │
│  (Your admin chat)   │
│  Alert notifications │
└──────────────────────┘
```


---

### 3.3 Alert Thresholds & Triggers

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|:-----------------:|:------------------:|--------|
| CPU | >80% for 3 min | >90% for 5 min | Alert → identify process → report |
| RAM | >80% for 2 min | >90% for 1 min | Alert → attempt container restart → report |
| Disk | >80% | >90% | Alert → clean Docker + logs → report |
| n8n Unreachable | Fails 2 consecutive checks | Fails 3 consecutive checks | Restart container → verify → report |
| Cloudflare Tunnel Down | Fails 1 check | Fails 2 checks | Restart systemd service → verify → report |
| SSH Unreachable | — | Fails 3 checks | **External alert only** (can't self-heal) |

---

### 3.4 Automated Recovery Workflow

```
┌────────────────────┐
│  Detect Failure    │  (health check fails / threshold breached)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Log Incident      │  (timestamp, service, metric values)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Attempt Recovery  │  (restart container/service, max 2 attempts)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Verify Health     │  (wait 15s, re-check service endpoint)
└────────┬───────────┘
         │
    ┌────┴────┐
    │         │
  SUCCESS   FAILURE
    │         │
    ▼         ▼
┌─────────┐ ┌───────────────────────────┐
│  Send   │ │  Send CRITICAL alert       │
│  ✅ OK  │ │  🚨 Manual intervention    │
│  alert  │ │  required                  │
└─────────┘ └───────────────────────────┘
```


---

### 3.5 Example Telegram Alert Formats

**Recovery Success:**
```
🟢 RESOLVED: empire-n8n

📍 Incident: n8n container unreachable
⏰ Detected: 2026-06-21 14:32:05 UTC
📊 System: CPU 12% | RAM 67% | Disk 14%

🔄 Recovery: Container restarted
✅ Result: Service restored (15s downtime)

Status: ALL SYSTEMS OPERATIONAL
```

**Recovery Failed — Manual Intervention Required:**
```
🔴 CRITICAL: empire-n8n

📍 Incident: RAM usage 94% (OOM imminent)
⏰ Detected: 2026-06-21 14:32:05 UTC
📊 System: CPU 45% | RAM 94% | Disk 14%

🔄 Recovery: n8n container restarted (attempt 1/2)
❌ Result: RAM still at 91% after restart

⚠️ MANUAL INTERVENTION REQUIRED
SSH: ssh root@77.42.43.250
```

**Resource Warning:**
```
⚠️ WARNING: empire-n8n

📍 Issue: Disk usage at 82%
⏰ Detected: 2026-06-21 09:15:00 UTC
📊 System: CPU 8% | RAM 55% | Disk 82%

💡 Recommendation: Run docker system prune
⏳ Critical threshold: 90%
```

---


## PART 4: GAP ANALYSIS

### Critical Gaps (Immediate Risk)

| # | Gap | Risk | Impact if Unaddressed |
|---|-----|------|----------------------|
| 1 | **No swap space** | OOM crash | Complete server failure from memory spike — unrecoverable without Hetzner console reboot |
| 2 | **Port 5678 publicly open** | Unauthorized access | n8n admin interface exposed on public IP, bypassing all Cloudflare protection |
| 3 | **No monitoring or alerting** | Silent failures | Services could be down for hours/days without anyone knowing |
| 4 | **No fail2ban** | Brute-force | Unlimited SSH/service attack attempts with no blocking or notification |
| 5 | **SSH password auth unverified** | Full compromise | If passwords are enabled, the server is one weak-password guess away from total compromise |
| 6 | **No container memory limits** | Resource starvation | A single workflow memory leak can consume all 4GB RAM and crash everything |

### High Gaps (Near-Term Risk)

| # | Gap | Risk | Impact if Unaddressed |
|---|-----|------|----------------------|
| 7 | No automated backups | Data loss | n8n workflows, credentials, and settings lost if disk fails or data corruption occurs |
| 8 | No Docker HEALTHCHECK | Zombie containers | Container running but n8n process dead inside — Docker won't auto-restart |
| 9 | No Docker log rotation | Disk exhaustion | Logs grow indefinitely → fill 40GB disk → all services crash |
| 10 | Docker image uses `:latest` | Breaking updates | `docker compose pull` could deploy an incompatible version with no rollback |

### Medium Gaps (Operational Improvement)

| # | Gap | Risk | Impact if Unaddressed |
|---|-----|------|----------------------|
| 11 | No SSH rate limiting in UFW | Log pollution, slow DoS | Thousands of failed attempts per day consume resources |
| 12 | No swappiness tuning | Suboptimal RAM use | Kernel may swap too aggressively if swap is added without tuning |
| 13 | No external uptime monitoring | Blind spots | If the server itself is down, internal monitoring can't alert |

---


## PART 5: PRIORITIZED REMEDIATION PLAN

### Implementation Order (by priority & dependency)

| Order | Action | Priority | Time | Dependencies |
|:-----:|--------|:--------:|:----:|:-------------|
| **1** | Create 2GB swap file | 🔴 Critical | 5 min | None |
| **2** | Close port 5678 in UFW | 🔴 Critical | 2 min | Verify tunnel access works first |
| **3** | Verify SSH password auth is disabled | 🔴 Critical | 3 min | SSH access |
| **4** | Install & configure Fail2Ban | 🟠 High | 10 min | After SSH hardening |
| **5** | Add container memory/CPU limits | 🟠 High | 5 min | Swap must exist first (order 1) |
| **6** | Deploy Telegram monitoring/alerting system | 🔴 Critical | 30 min | Telegram bot token needed |
| **7** | Configure Docker log rotation | 🟠 High | 5 min | None |
| **8** | Add Docker HEALTHCHECK to n8n | 🟡 Medium | 5 min | None |
| **9** | Pin n8n Docker image version | 🟡 Medium | 3 min | None |
| **10** | Set up automated backup (n8n data volume) | 🟠 High | 15 min | None |
| **11** | Add external uptime monitoring | 🟡 Medium | 5 min | None (UptimeRobot/BetterStack free) |
| **12** | Add UFW SSH rate limiting | 🟡 Medium | 2 min | None |

---


## PART 6: IMPLEMENTATION PLAN (Detailed)

### 🔴 Implementation 1: Create 2GB Swap File

**What:** Create a 2GB swap file as an emergency memory overflow buffer.

**Why:** With 4GB RAM, no swap, and no container memory limits, any memory spike triggers the Linux OOM killer which can terminate critical system processes (Docker daemon, sshd, cloudflared). This can crash the server to a state unreachable by SSH — requiring a hard reboot from Hetzner's web console.

**Benefit:** Provides a safety net that absorbs temporary memory spikes, giving the system time to recover or alert before crashing.

**Implementation:**
```bash
# Create swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Tune swappiness (prefer RAM, use swap only as safety net)
echo 'vm.swappiness=10' >> /etc/sysctl.d/99-swap.conf
sysctl -p /etc/sysctl.d/99-swap.conf

# Verify
free -h
swapon --show
```

---


### 🔴 Implementation 2: Close Port 5678 (UFW)

**What:** Remove the public firewall rule for port 5678, restricting n8n access to the Cloudflare Tunnel only.

**Why:** n8n is already fully accessible via `https://bot.empireenglish.online` through the tunnel. The public port 5678 exposes the admin interface on plain HTTP to the entire internet, allowing attackers to bypass Cloudflare's DDoS protection, WAF, and audit logging.

**Benefit:** Eliminates the server's single largest attack surface. All access forces through Cloudflare's security stack.

**Implementation:**
```bash
# Verify tunnel access works first
# Test from browser: https://bot.empireenglish.online

# Remove the UFW rule
ufw delete allow 5678

# Verify
ufw status numbered

# Test: http://77.42.43.250:5678 should now be unreachable
# Test: https://bot.empireenglish.online should still work perfectly
```

**Note:** n8n still binds to `0.0.0.0:5678` inside Docker, and cloudflared connects to `localhost:5678` — this continues to work because the tunnel is local traffic.

---


### 🔴 Implementation 3: Verify & Enforce SSH Password Disable

**What:** Confirm password authentication is disabled in SSH configuration.

**Why:** The documentation states this is *"likely disabled"* but unverified. If enabled, combined with no fail2ban, the server is vulnerable to automated brute-force attacks from botnets.

**Benefit:** Guarantees that SSH access is only possible with the correct private key.

**Implementation:**
```bash
# Check current config
grep -E "^(PasswordAuthentication|PermitRootLogin|PubkeyAuthentication)" /etc/ssh/sshd_config

# Enforce (edit sshd_config):
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# Also harden:
echo "MaxAuthTries 3" >> /etc/ssh/sshd_config
echo "ClientAliveInterval 300" >> /etc/ssh/sshd_config
echo "ClientAliveCountMax 2" >> /etc/ssh/sshd_config

# Restart SSH (DO NOT DISCONNECT until verified from a second terminal)
systemctl restart sshd

# IMPORTANT: Test from a SECOND terminal before closing the current session
ssh root@77.42.43.250
```

---


### 🟠 Implementation 4: Install Fail2Ban

**What:** Install fail2ban with SSH jail protection and Telegram notification capability.

**Why:** Even with key-only SSH, fail2ban blocks IPs that repeatedly fail authentication — reducing log noise, CPU consumption from crypto operations, and providing intrusion awareness.

**Benefit:** Automatic IP banning after 3 failed attempts; protection layer for any future service; reduces attack surface noise.

**Implementation:**
```bash
apt update && apt install -y fail2ban

# Create local jail config (overrides defaults safely)
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
banaction = ufw

[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF

systemctl enable fail2ban
systemctl start fail2ban

# Verify
fail2ban-client status sshd
```

---


### 🟠 Implementation 5: Add Container Resource Limits

**What:** Set CPU and memory limits on the n8n Docker container.

**Why:** Without limits, a memory leak or runaway workflow in n8n can consume all 4GB of RAM + all swap, killing the entire system. With limits, Docker constrains the container and OOM-kills only n8n (which then auto-restarts due to `restart: always`).

**Benefit:** Isolates n8n failures to the container level; prevents cascading server failure.

**Implementation** (edit `/opt/n8n/docker-compose.yml`):
```yaml
services:
  n8n:
    image: n8nio/n8n:1.x.y  # pin to current stable version
    container_name: empire-n8n
    restart: always
    ports:
      - "5678:5678"
    volumes:
      - n8n_data:/home/node/.n8n
    environment:
      - N8N_HOST=bot.empireenglish.online
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://bot.empireenglish.online/
      - N8N_SECURE_COOKIE=false
      - GENERIC_TIMEZONE=Asia/Dubai
      - TZ=Asia/Dubai
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 2560M   # 2.5GB — leaves 1.5GB for OS/Docker/tunnel
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

Then apply:
```bash
cd /opt/n8n && docker compose up -d
```

---


### 🔴 Implementation 6: Telegram Monitoring & Alerting System

**What:** A lightweight monitoring daemon that checks system health every 60 seconds and sends Telegram alerts with auto-recovery capabilities.

**Why:** Currently, if n8n crashes, the tunnel goes down, or disk fills up — no one knows until a customer complains (or the server becomes unreachable). This is unacceptable for business-critical infrastructure.

**Benefit:** Instant awareness of problems; automated first-response recovery; documented incident trail; peace of mind.

**Implementation:** A single bash script managed by a systemd timer (no external dependencies, zero cost, survives reboots).

**Step 1: Create the watchdog script** at `/opt/monitor/watchdog.sh`:
```bash
#!/bin/bash
# /opt/monitor/watchdog.sh — Empire Server Health Monitor
# Runs every 60 seconds via systemd timer

set -euo pipefail

# === CONFIGURATION ===
TELEGRAM_TOKEN="YOUR_BOT_TOKEN_HERE"
ADMIN_CHAT_ID="YOUR_CHAT_ID_HERE"
HOSTNAME="empire-n8n"
STATE_FILE="/opt/monitor/.state"

# Thresholds
CPU_WARN=80
CPU_CRIT=90
RAM_WARN=80
RAM_CRIT=90
DISK_WARN=80
DISK_CRIT=90

# === FUNCTIONS ===
send_telegram() {
  local msg="$1"
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="${ADMIN_CHAT_ID}" \
    -d parse_mode="HTML" \
    -d text="${msg}" > /dev/null 2>&1
}

get_cpu() {
  top -bn2 -d0.5 | grep "Cpu(s)" | tail -1 | awk '{print int($2+$4)}'
}

get_ram() {
  free | awk '/Mem:/{printf "%.0f", $3/$2*100}'
}

get_disk() {
  df / | awk 'NR==2{print int($5)}'
}

check_service() {
  local name="$1" check_cmd="$2"
  if eval "$check_cmd" > /dev/null 2>&1; then
    echo "ok"
  else
    echo "down"
  fi
}

restart_n8n() {
  cd /opt/n8n && docker compose restart
  sleep 15
  if curl -sf -o /dev/null -m 5 http://localhost:5678/ 2>/dev/null; then
    echo "recovered"
  else
    echo "failed"
  fi
}

restart_tunnel() {
  systemctl restart cloudflared
  sleep 10
  if systemctl is-active --quiet cloudflared; then
    echo "recovered"
  else
    echo "failed"
  fi
}

# === MAIN CHECKS ===
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S UTC')
CPU=$(get_cpu)
RAM=$(get_ram)
DISK=$(get_disk)

ALERT=""
SEVERITY=""

# Resource checks
if [ "$RAM" -ge "$RAM_CRIT" ]; then
  SEVERITY="CRITICAL"
  ALERT="🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 RAM usage at ${RAM}% (OOM imminent)\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%"
  # Attempt recovery
  RESULT=$(restart_n8n)
  RAM_AFTER=$(get_ram)
  if [ "$RESULT" = "recovered" ] && [ "$RAM_AFTER" -lt "$RAM_CRIT" ]; then
    ALERT="${ALERT}\n\n🔄 Recovery: n8n restarted\n✅ RAM now at ${RAM_AFTER}%"
  else
    ALERT="${ALERT}\n\n🔄 Recovery attempted: n8n restarted\n❌ RAM still at ${RAM_AFTER}%\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250"
  fi
elif [ "$RAM" -ge "$RAM_WARN" ]; then
  SEVERITY="WARNING"
  ALERT="⚠️ <b>WARNING: ${HOSTNAME}</b>\n\n📍 RAM usage at ${RAM}%\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%\n\n💡 Approaching critical threshold (${RAM_CRIT}%)"
fi

if [ "$DISK" -ge "$DISK_CRIT" ]; then
  SEVERITY="CRITICAL"
  ALERT="🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 Disk usage at ${DISK}%\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%\n\n💡 Run: docker system prune -f"
elif [ "$DISK" -ge "$DISK_WARN" ] && [ -z "$ALERT" ]; then
  SEVERITY="WARNING"
  ALERT="⚠️ <b>WARNING: ${HOSTNAME}</b>\n\n📍 Disk usage at ${DISK}%\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%\n\n💡 Run: docker system prune -f"
fi

# Service health checks
N8N_STATUS=$(check_service "n8n" "curl -sf -o /dev/null -m 5 http://localhost:5678/")
TUNNEL_STATUS=$(check_service "cloudflared" "systemctl is-active --quiet cloudflared")

if [ "$N8N_STATUS" = "down" ]; then
  RESULT=$(restart_n8n)
  if [ "$RESULT" = "recovered" ]; then
    ALERT="🟢 <b>RESOLVED: ${HOSTNAME}</b>\n\n📍 n8n was unreachable\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%\n\n🔄 Recovery: Container restarted\n✅ Service restored"
  else
    ALERT="🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 n8n DOWN — restart failed\n⏰ ${TIMESTAMP}\n📊 CPU ${CPU}% | RAM ${RAM}% | Disk ${DISK}%\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250"
  fi
  SEVERITY="CRITICAL"
fi

if [ "$TUNNEL_STATUS" = "down" ]; then
  RESULT=$(restart_tunnel)
  if [ "$RESULT" = "recovered" ]; then
    ALERT="🟢 <b>RESOLVED: ${HOSTNAME}</b>\n\n📍 Cloudflare Tunnel was down\n⏰ ${TIMESTAMP}\n\n🔄 Recovery: Service restarted\n✅ Tunnel restored"
  else
    ALERT="🔴 <b>CRITICAL: ${HOSTNAME}</b>\n\n📍 Cloudflare Tunnel DOWN — restart failed\n⏰ ${TIMESTAMP}\n\n⚠️ MANUAL INTERVENTION REQUIRED\nSSH: ssh root@77.42.43.250"
  fi
  SEVERITY="CRITICAL"
fi

# Send alert if needed
if [ -n "$ALERT" ]; then
  send_telegram "$(echo -e "$ALERT")"
fi
```


**Step 2: Create systemd service and timer:**
```bash
# Create directory
mkdir -p /opt/monitor
chmod +x /opt/monitor/watchdog.sh

# Systemd service
cat > /etc/systemd/system/empire-monitor.service << 'EOF'
[Unit]
Description=Empire Server Health Monitor
After=network.target docker.service

[Service]
Type=oneshot
ExecStart=/opt/monitor/watchdog.sh
StandardOutput=journal
StandardError=journal
EOF

# Systemd timer (runs every 60 seconds)
cat > /etc/systemd/system/empire-monitor.timer << 'EOF'
[Unit]
Description=Run Empire Health Monitor every 60s

[Timer]
OnBootSec=60
OnUnitActiveSec=60
AccuracySec=5

[Install]
WantedBy=timers.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable empire-monitor.timer
systemctl start empire-monitor.timer

# Verify
systemctl status empire-monitor.timer
systemctl list-timers | grep empire
```

**Step 3: Send a test alert:**
```bash
# Run manually once to test
/opt/monitor/watchdog.sh

# Or test Telegram connectivity directly:
curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id="<CHAT_ID>" \
  -d text="✅ Empire monitoring system online."
```

---


### 🟠 Implementation 7: Configure Docker Log Rotation

**What:** Set global Docker log rotation to prevent log files from filling the disk.

**Why:** By default, Docker stores container logs as unlimited JSON files. Over weeks/months, these can grow to gigabytes and fill the 40GB disk — crashing all services.

**Benefit:** Prevents silent disk exhaustion; caps total log storage at a safe level.

**Implementation:**
```bash
# Create Docker daemon config
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Restart Docker to apply (will briefly restart all containers)
systemctl restart docker

# Verify
docker info | grep -A 3 "Logging Driver"
```

---

### 🟠 Implementation 10: Automated Backup (n8n Data Volume)

**What:** Daily automated backup of the n8n data volume to a local directory with rotation.

**Why:** n8n stores workflows, credentials (encrypted), and settings in its data volume. If the volume is corrupted or accidentally deleted, all automation is lost with no recovery path.

**Benefit:** Recoverability from data corruption, accidental deletion, or failed updates. Combined with Hetzner's optional backup add-on (~€1.22/mo), provides full disaster recovery.

**Implementation:**
```bash
# Create backup script
mkdir -p /opt/backups

cat > /opt/backups/backup-n8n.sh << 'EOF'
#!/bin/bash
# Daily n8n data backup with 14-day rotation
BACKUP_DIR="/opt/backups/n8n"
MAX_BACKUPS=14
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Copy the Docker volume data
docker run --rm \
  -v n8n_data:/source:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/n8n_${TIMESTAMP}.tar.gz" -C /source .

# Rotate old backups
cd "$BACKUP_DIR" && ls -t n8n_*.tar.gz | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm

echo "✅ Backup complete: n8n_${TIMESTAMP}.tar.gz ($(du -sh "$BACKUP_DIR/n8n_${TIMESTAMP}.tar.gz" | cut -f1))"
EOF

chmod +x /opt/backups/backup-n8n.sh

# Add to crontab (daily at 3:00 AM server time)
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/backups/backup-n8n.sh >> /var/log/n8n-backup.log 2>&1") | crontab -

# Test
/opt/backups/backup-n8n.sh
```

---


### 🟡 Implementation 11: External Uptime Monitoring

**What:** Set up a free external uptime monitor that checks `https://bot.empireenglish.online` every 5 minutes and alerts via Telegram if unreachable.

**Why:** If the entire server goes down (hardware failure, network issue, Hetzner outage), the internal monitoring script cannot send alerts because it's also down. An external monitor provides coverage for this scenario.

**Benefit:** Coverage for total server failure scenarios; independent verification layer.

**Options (all free):**
- **BetterStack (betterstack.com)** — free tier, Telegram integration, 3-min checks
- **UptimeRobot (uptimerobot.com)** — free tier, 5-min checks, Telegram via webhook
- **Cronitor (cronitor.io)** — free tier, good for cron job monitoring too

**Setup (UptimeRobot example):**
1. Sign up at uptimerobot.com (free)
2. Add monitor: HTTPS, URL = `https://bot.empireenglish.online`, interval = 5 min
3. Add alert contact: Telegram (or email → Telegram via n8n workflow)
4. Done — alerts if the URL is unreachable for 2+ consecutive checks

---

### 🟡 Implementation 12: UFW SSH Rate Limiting

**What:** Add connection rate limiting to SSH port in UFW.

**Why:** Even with key-only authentication, botnets generate thousands of connection attempts per day. Each attempt consumes CPU for crypto negotiation. Rate limiting reduces this noise to near zero.

**Benefit:** Reduces log clutter and CPU waste from automated scanners; complements fail2ban.

**Implementation:**
```bash
# Replace the current SSH allow rule with a rate-limited version
ufw delete allow 22/tcp
ufw limit 22/tcp

# Verify
ufw status

# This limits SSH to 6 connections in 30 seconds per IP before blocking
```

---


## SUMMARY: AUDIT SCORECARD

| Category | Score | Grade |
|----------|:-----:|:-----:|
| SSH Security | 6/10 | ⚠️ Needs verification |
| Firewall | 4/10 | 🔴 Critical gap (port 5678) |
| Cloudflare Integration | 7/10 | ⚠️ Undermined by open port |
| Brute-Force Protection | 1/10 | 🔴 Not implemented |
| Docker Architecture | 7/10 | ✅ Solid base |
| Auto-Recovery | 8/10 | ✅ Good (restart policies) |
| Resource Isolation | 2/10 | 🔴 No limits set |
| Swap / Memory Safety | 0/10 | 🔴 Critical gap |
| Monitoring & Alerting | 0/10 | 🔴 Not implemented |
| Backup & Recovery | 2/10 | 🔴 Manual only, no automation |
| **Overall Infrastructure** | **3.7/10** | **🔴 High Risk** |

---

## EXECUTIVE SUMMARY

This server has a **solid architectural foundation** (Docker, Cloudflare Tunnel, auto-start services) but **critical gaps in security, monitoring, and memory protection** that expose it to silent failures, unauthorized access, and unrecoverable crashes.

**The top 3 actions that will deliver the most immediate risk reduction:**

1. **Create swap space** (5 minutes) → eliminates OOM crash risk
2. **Close port 5678** (2 minutes) → eliminates the #1 security vulnerability
3. **Deploy Telegram monitoring** (30 minutes) → eliminates silent failure risk

These three actions alone would raise the overall score from **3.7/10 to approximately 6.5/10**.

Completing all 12 items in the remediation plan would bring the server to a **production-grade 8.5+/10** — appropriate for mission-critical business infrastructure.

---

*End of Server Infrastructure Audit — v1.0*
