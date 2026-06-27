# Empire English — n8n Self-Host Migration Plan

**Migration Specification v1.0** · *Confidential* · **Date:** June 2026

> **Purpose.** This document provides a complete, step-by-step plan to migrate the Empire English bot automation from **Make.com** (ops-limited, paid at scale) to **n8n self-hosted** ($0/month, unlimited operations, unlimited workflows). Follow in order. The result is the same system — identical behavior, same CRM, same bot — running on infrastructure you own with zero per-operation cost.

> **Why migrate.** Make.com charges per operation. The current bot uses ~80–100 ops per full user journey. At scale (500+ active users), costs become $16–99/mo and growing. n8n self-hosted is open-source, unlimited operations, and hostable on Oracle Cloud's Always Free tier ($0 forever).

> **What stays the same.** The Telegram bot (@EmpireEnglishBot), the Google Sheets CRM, the Cal.com booking, the quiz logic, the scoring, the plan templates — everything. Only the "orchestrator" layer changes (Make.com → n8n). The bot token stays the same. Users notice nothing.

---

## Table of Contents

1. [Architecture Comparison](#1-architecture-comparison)
2. [Hosting Decision: Oracle Cloud Free Tier](#2-hosting-decision-oracle-cloud-free-tier)
3. [Server Setup (Oracle Cloud + Docker + n8n)](#3-server-setup-oracle-cloud--docker--n8n)
4. [n8n Configuration & First Login](#4-n8n-configuration--first-login)
5. [Connecting Services (Telegram + Google Sheets)](#5-connecting-services-telegram--google-sheets)
6. [Workflow Migration: A1 Welcome + Router](#6-workflow-migration-a1-welcome--router)
7. [Workflow Migration: Quiz (Optimized)](#7-workflow-migration-quiz-optimized)
8. [Workflow Migration: A3–A6 (Resource, Offer, Booking, Community)](#8-workflow-migration-a3a6)
9. [Workflow Migration: A7 Score, A8 Backup, A9 Alert](#9-workflow-migration-a7-a8-a9)
10. [Workflow Migration: Weekly Report + Nudges (Phase 1)](#10-workflow-migration-weekly-report--nudges)
11. [Testing & Parallel Run](#11-testing--parallel-run)
12. [Cutover (Switch from Make.com to n8n)](#12-cutover)
13. [Maintenance & Updates](#13-maintenance--updates)
14. [Rollback Plan](#14-rollback-plan)

---

## 1. Architecture Comparison

| Aspect | Make.com (current) | n8n self-host (target) |
|---|---|---|
| **Cost** | Free tier: 1,000 ops/mo; scales to $9–99/mo | **$0/mo forever** (Oracle free tier) |
| **Operations limit** | Per-plan cap (1K/10K/etc.) | **Unlimited** |
| **Active scenarios limit** | 2 (free), 5 (Core), unlimited (Pro) | **Unlimited** |
| **Interface** | Visual drag-and-drop | Visual drag-and-drop (very similar) |
| **Hosting** | Managed by Make.com | Self-managed (Docker on your server) |
| **Data ownership** | Make.com stores execution data | You own everything |
| **Telegram integration** | Native module | Native node (built-in) |
| **Google Sheets integration** | Native module | Native node (built-in) |
| **Webhook support** | Managed URL | Self-hosted URL (your domain) |
| **Reliability** | Make.com's SLA | Your server uptime (Oracle: 99.9%) |
| **Maintenance** | Zero (managed) | Minimal (Docker auto-restart + monthly update) |

---

## 2. Hosting Decision: Oracle Cloud Free Tier

### Why Oracle Cloud

Oracle Cloud's "Always Free" tier provides compute resources that **never expire and never charge**. It's not a trial — it's permanently free infrastructure.

**What you get (Always Free):**
- **VM:** Up to 4 OCPUs + 24 GB RAM (ARM-based Ampere A1) — massively more than needed
- **Storage:** 200 GB block volume
- **Network:** 10 TB outbound/month
- **No credit card charge** (card required for signup verification only)

**What we'll use:**
- 1 VM with 1 OCPU + 6 GB RAM (plenty for n8n + your bot serving thousands of users)
- Ubuntu 22.04 (standard Linux)
- Docker (to run n8n)

### Alternative hosting (if Oracle signup fails)

Oracle sometimes has availability issues for free-tier VMs in popular regions. Alternatives:

| Provider | Cost | Notes |
|---|---|---|
| **Railway.app** | ~$5/mo (usage-based) | One-click n8n deploy, easiest option |
| **Hetzner Cloud** | €4.15/mo (~$4.50) | Reliable European hosting |
| **DigitalOcean** | $4/mo (basic droplet) | Well-documented |
| **Fly.io** | Free tier available | Newer, good for containers |
| **Home server / Raspberry Pi** | $0 (electricity) | Only if you have stable internet |

> **Recommendation:** Try Oracle first (free forever). If unavailable, Railway is the easiest paid fallback.

---

## 3. Server Setup (Oracle Cloud + Docker + n8n)

### Step 3.1 — Create Oracle Cloud Account

1. Go to [cloud.oracle.com/sign-up](https://cloud.oracle.com/sign-up)
2. Fill in your details (name, email, country)
3. **Choose your Home Region** carefully — pick the one closest to your users (Middle East: Jeddah or Abu Dhabi if available; otherwise Frankfurt or London)
4. Enter a credit/debit card (for verification only — you will NOT be charged)
5. Complete signup → wait for activation email (usually 5–30 minutes)

### Step 3.2 — Create a Free VM

1. Log into Oracle Cloud Console → **Compute → Instances → Create Instance**
2. Name: `empire-n8n`
3. **Image:** Ubuntu 22.04 (Canonical) — under "Change Image" → Platform images → Ubuntu
4. **Shape:** Click "Change Shape" → **Ampere** (ARM) → VM.Standard.A1.Flex → set to **1 OCPU, 6 GB RAM** (Always Free eligible)
5. **Networking:** accept defaults (public subnet, auto-assign public IP)
6. **SSH Key:** Click "Generate a key pair" → **Download both keys** (private + public). Save the private key file somewhere safe — you'll need it to connect.
7. Click **Create** → wait for status = "Running" (1–3 minutes)
8. Note the **Public IP Address** shown (e.g., `132.145.xxx.xxx`)

### Step 3.3 — Open Firewall Ports

Your n8n needs ports 443 (HTTPS) and 5678 (n8n web UI) accessible:

1. In Oracle Console → **Networking → Virtual Cloud Networks** → click your VCN → **Security Lists** → Default Security List
2. **Add Ingress Rules:**
   - Source CIDR: `0.0.0.0/0`, Protocol: TCP, Destination Port: `443`
   - Source CIDR: `0.0.0.0/0`, Protocol: TCP, Destination Port: `5678`
3. Save

### Step 3.4 — Connect to Your Server (SSH)

From your computer's terminal (or PuTTY on Windows):

```bash
ssh -i /path/to/your-private-key.key ubuntu@YOUR_PUBLIC_IP
```

> On Windows: use PuTTY or Windows Terminal with the SSH command. The username is `ubuntu`.

### Step 3.5 — Install Docker + Docker Compose

Run these commands on your server (copy-paste one by one):

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to docker group (avoids needing sudo)
sudo usermod -aG docker ubuntu

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Verify
docker --version
docker compose version

# Log out and back in for group change to take effect
exit
```

Then SSH back in:
```bash
ssh -i /path/to/your-private-key.key ubuntu@YOUR_PUBLIC_IP
```

### Step 3.6 — Also open the port in Ubuntu's firewall

```bash
sudo iptables -I INPUT -p tcp --dport 5678 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

> If `netfilter-persistent` isn't installed: `sudo apt install iptables-persistent -y`

---

## 4. n8n Configuration & First Login

### Step 4.1 — Create the n8n directory and config

```bash
mkdir ~/n8n && cd ~/n8n
```

Create the Docker Compose file:

```bash
nano docker-compose.yml
```

Paste this content:

```yaml
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: empire-n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=YOUR_PUBLIC_IP
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://YOUR_PUBLIC_IP:5678/
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=YOUR_SECURE_PASSWORD
      - GENERIC_TIMEZONE=Asia/Riyadh
      - TZ=Asia/Riyadh
    volumes:
      - n8n_data:/home/node/.n8n

volumes:
  n8n_data:
```

**Replace:**
- `YOUR_PUBLIC_IP` → your Oracle VM's public IP (e.g., `132.145.xxx.xxx`)
- `YOUR_SECURE_PASSWORD` → a strong password for n8n login
- `Asia/Riyadh` → your timezone (or `Asia/Dubai`, `Africa/Cairo`, etc.)

Save: `Ctrl+O`, Enter, `Ctrl+X`

### Step 4.2 — Start n8n

```bash
cd ~/n8n
docker compose up -d
```

Wait 30 seconds, then check it's running:

```bash
docker compose logs --tail=20
```

You should see n8n starting up with "Editor is now accessible via: http://..."

### Step 4.3 — Access the n8n UI

Open your browser: `http://YOUR_PUBLIC_IP:5678`

Log in with:
- Username: `admin`
- Password: whatever you set in the compose file

You should see the n8n dashboard — an empty workspace ready for workflows.

### Step 4.4 — Verify webhook URL works

In n8n, create a test workflow:
1. Add a **Webhook** node → copy the "Test URL" it shows
2. Open that URL in your browser → if you see a response, webhooks work
3. Delete the test workflow

> **Important:** The `WEBHOOK_URL` environment variable must match your public IP. Telegram will send callbacks to this URL.

---

## 5. Connecting Services (Telegram + Google Sheets)

### Step 5.1 — Add Telegram Bot credentials

1. In n8n → **Settings** (gear icon, bottom-left) → **Credentials** → **Add Credential**
2. Search: **Telegram** → select "Telegram Bot API"
3. Name: `Empire Bot`
4. Access Token: paste your **BotFather token** (the same one you used in Make.com)
5. Click **Test** → should show success
6. Save

### Step 5.2 — Add Google Sheets credentials

1. **Credentials** → **Add Credential** → search **Google Sheets**
2. Select **"Google Sheets account"** (OAuth2)
3. Follow the n8n prompts to sign in with your Google account (the one that owns Empire CRM)
4. Grant permissions (Sheets + Drive access)
5. Test → should connect successfully
6. Save

> **Alternative (Service Account method):** If OAuth doesn't work well for a server-based setup, create a Google Cloud Service Account, download the JSON key, and use that in n8n. Service accounts are more reliable for always-on servers.

---

## 6. Workflow Migration: A1 Welcome + Router

### n8n equivalent of the Make.com A1 scenario

In n8n, create a new workflow: **"Empire Bot — Main"**

This single workflow replaces your entire Make.com A1 scenario (trigger + router + all routes).

**Node 1 — Telegram Trigger**
- Add node: **Telegram Trigger**
- Credential: Empire Bot
- Updates to receive: select **`message`** and **`callback_query`** (both)

**Node 2 — Switch (Router)**
- Add node: **Switch**
- Connect from Telegram Trigger
- Mode: **Rules**
- Rules:
  - Output 0: `{{$json.message.text}}` → **Contains** → `/start` → name it "start"
  - Output 1: `{{$json.callback_query.data}}` → **Equals** → `quiz` → name it "quiz_start"
  - Output 2: `{{$json.callback_query.data}}` → **Equals** → `resource` → name it "resource"
  - Output 3: `{{$json.callback_query.data}}` → **Equals** → `how` → name it "how"
  - Output 4: `{{$json.callback_query.data}}` → **Equals** → `call` → name it "call"
  - Output 5: `{{$json.callback_query.data}}` → **Equals** → `community` → name it "community"
  - Output 6: `{{$json.callback_query.data}}` → **Equals** → `menu` → name it "menu"
  - Output 7: `{{$json.callback_query.data}}` → **Starts with** → `q` → name it "quiz_answer"

### "start" branch (Output 0):

**Node 3 — Google Sheets: Search Rows**
- Operation: Search Rows (or Read/Get)
- Spreadsheet: Empire CRM
- Sheet: Subscribers
- Filter: `telegram_id` = `{{$node["Telegram Trigger"].json.message.from.id}}`

**Node 4 — IF (new vs returning)**
- Condition: `{{$json.length}}` → **Equals** → `0` (no results = new user)

**Node 5a — (TRUE/new) Google Sheets: Append Row**
- Sheet: Subscribers
- Values:
  - telegram_id: `{{$node["Telegram Trigger"].json.message.from.id}}`
  - username: `{{$node["Telegram Trigger"].json.message.from.username}}`
  - first_name: `{{$node["Telegram Trigger"].json.message.from.first_name}}`
  - language: `ar`
  - status: `New`
  - consent: `FALSE`
  - source: `{{$node["Telegram Trigger"].json.message.text}}`
  - first_seen_at: `{{$now.toISO()}}`
  - last_active_at: `{{$now.toISO()}}`
  - lead_score: (the formula — same as Make.com)
  - segment: (the formula — same as Make.com)

**Node 5b — (FALSE/returning) Google Sheets: Update Row**
- Filter by telegram_id → update only `last_active_at`

**Node 6 — Google Sheets: Append Row (Events)**
- Sheet: Events
- event_id: `{{$node["Telegram Trigger"].json.update_id}}-JOINED_BOT`
- telegram_id: from trigger
- event_type: `JOINED_BOT`
- timestamp: `{{$now.toISO()}}`

**Node 7 — Telegram: Send Message**
- Chat ID: `{{$node["Telegram Trigger"].json.message.chat.id}}`
- Text: Your welcome message (Arabic)
- Reply Markup (Inline Keyboard): the 5-button JSON

### "menu" branch (Output 6):

**Node — Telegram: Send Message**
- Chat ID: `{{$node["Telegram Trigger"].json.callback_query.message.chat.id}}`
- Text: Menu text
- Reply Markup: same 5-button inline keyboard JSON

### Patterns for other branches

Each branch follows the same pattern as Make.com:
- "how" → Send 3 messages + log OFFER_OPENED
- "call" → Send booking message with Cal.com link (include tid) 
- "community" → Send stub/invite + log COMMUNITY_CLICK
- "resource" → Send stub/resource + log RESOURCE_CLAIMED

---

## 7. Workflow Migration: Quiz (Optimized)

### The big optimization: reduce from ~60 ops to ~10

In Make.com, each quiz question was a separate trigger+response cycle (7 rounds × ~8 ops = ~56 ops). In n8n, this costs nothing extra (unlimited executions), but we'll still optimize for speed and simplicity.

**Architecture in n8n:**

The "quiz_answer" branch (Output 7 of the Switch) handles ALL quiz callbacks (`q1_*` through `q7_*`):

**Node — Switch (which question)**
- `{{$json.callback_query.data}}` Starts with `q1_` → Q1 handler
- `{{$json.callback_query.data}}` Starts with `q2_` → Q2 handler
- ... through q7_

**Each Q1–Q6 handler:**
1. Google Sheets: Update Row (Subscribers) → set `qN` value + advance `quiz_state`
2. Telegram: Send Message → next question text + buttons

**Q7 handler (final — scoring + plan):**
1. Google Sheets: Search Rows → get the subscriber row (read q1–q5 values)
2. Code Node (JavaScript) → compute score:
```javascript
const q1 = parseInt(items[0].json.q1) || 0;
const q2 = parseInt(items[0].json.q2) || 0;
const q3 = items[0].json.q3 === '3' ? 3 : (items[0].json.q3 === '1' ? 1 : 0);
const q4 = items[0].json.q4 === '3' ? 3 : 0;
const q5 = parseInt(items[0].json.q5) || 0;

const score = q1 + q2 + q3 + q4 + q5;
let level = 'L0';
if (score > 3) level = 'L1';
if (score > 7) level = 'L2';
if (score > 11) level = 'L3';

return [{ json: { level_score: score, level: level } }];
```
3. Google Sheets: Update Row → write level, level_score, time_track, quiz_state=done
4. Google Sheets: Append Row (Events) → QUIZ_COMPLETED
5. Switch (by level) → 4 Telegram Send Message nodes (one per plan)

> **n8n advantage:** The Code Node lets you do the scoring in ONE step with real JavaScript — no chaining Set Variable modules or worrying about module references. Cleaner and instant.

---

## 8. Workflow Migration: A3–A6

These are simple and map almost 1:1:

| Make.com | n8n equivalent |
|---|---|
| A3 Resource | Branch from main Switch → Send Message + Append Event row |
| A4 Offer/How | Branch → 3× Send Message + Append Event row |
| A5 Booking | **Separate workflow** with Webhook trigger (Cal.com calls it) → Search → Update → Append Event → Send Alert |
| A6 Community | Branch → Send Message + Append Event row |

### A5 Booking Sync (separate workflow)

Create: **"Empire Bot — Booking Sync"**

1. **Webhook** node (n8n generates a URL like `http://YOUR_IP:5678/webhook/booking`)
2. **Google Sheets: Search Rows** → Subscribers where telegram_id = `{{$json.body.payload.responses.tid.value}}`
3. **Google Sheets: Update Row** → booked=TRUE, status=Hot
4. **Google Sheets: Append Row** → Events: BOOKED
5. **Telegram: Send Message** → to FOUNDER_CHAT_ID (hot lead alert)

Then update your Cal.com webhook URL to point to this n8n webhook URL.

---

## 9. Workflow Migration: A7, A8, A9

### A7 Score/Segment

Already handled by Google Sheets formulas (INDIRECT+ROW approach). No n8n workflow needed. ✅

### A8 Daily Backup

Create: **"Empire Bot — Daily Backup"**

1. **Schedule Trigger** → Every day at 03:00
2. **Google Drive: Copy File** → Copy Empire CRM → name with date

### A9 Hot-Lead Alert

Built into A5 (booking sync) workflow — the last node sends the Telegram alert. No separate workflow needed.

---

## 10. Workflow Migration: Weekly Report + Nudges (Phase 1)

### Weekly Report

Create: **"Empire — Weekly Report"**

1. **Schedule Trigger** → Every Monday 08:00
2. **Google Sheets: Get Many** → Events tab, filter last 7 days
3. **Code Node** → Count events by type, calculate rates:
```javascript
const events = items;
const joined = events.filter(e => e.json.event_type === 'JOINED_BOT').length;
const quizzed = events.filter(e => e.json.event_type === 'QUIZ_COMPLETED').length;
const offered = events.filter(e => e.json.event_type === 'OFFER_OPENED').length;
const booked = events.filter(e => e.json.event_type === 'BOOKED').length;
const resources = events.filter(e => e.json.event_type === 'RESOURCE_CLAIMED').length;
const community = events.filter(e => e.json.event_type === 'COMMUNITY_CLICK').length;

const rateQuiz = joined > 0 ? Math.round(quizzed/joined*100) : 0;
const rateOffer = quizzed > 0 ? Math.round(offered/quizzed*100) : 0;
const rateBook = offered > 0 ? Math.round(booked/offered*100) : 0;

return [{ json: { joined, quizzed, offered, booked, resources, community, rateQuiz, rateOffer, rateBook } }];
```
4. **Telegram: Send Message** → to FOUNDER_CHAT_ID, formatted digest

### Nudges

Create: **"Empire — Nudges"**

1. **Schedule Trigger** → Daily 18:00
2. **Google Sheets: Get Many** → Subscribers where nudge_quiz_sent ≠ TRUE
3. **Code Node** → Filter to those with JOINED_BOT >3 days ago, no QUIZ_COMPLETED
4. **Loop** → For each qualifying user:
   - Telegram: Send Message (quiz nudge)
   - Google Sheets: Update Row (set nudge_quiz_sent = TRUE)

---

## 11. Testing & Parallel Run

### Strategy: run both systems simultaneously for 1 week

1. Create a **test bot** via BotFather (e.g., `@EmpireTestBot`) with a different token
2. Build all n8n workflows using the test bot token
3. Test all flows end-to-end (same T1–T10 acceptance tests)
4. Once all pass → switch to the real bot token

### Test checklist

| Test | Pass condition |
|---|---|
| T1 | /start → welcome + menu + CRM row + JOINED_BOT event |
| T2 | Quiz → correct level + plan message |
| T3 | CRM row has all fields filled |
| T4 | Menu button works from all flows |
| T5 | Booking webhook → CRM updated + alert received |
| T6 | Resource stub delivered + event logged |
| T7 | All 6 event types logged |
| T8 | Lead score + segment calculate (sheet formulas) |
| T9 | Daily backup runs |
| T10 | Repeated /start → no duplicate row |

---

## 12. Cutover (Switch from Make.com to n8n)

Once all tests pass on n8n:

1. **Turn OFF** all Make.com scenarios (don't delete yet — keep as documentation)
2. In n8n, switch the Telegram credential from the test bot token to the **real bot token** (@EmpireEnglishBot)
3. **Activate** all n8n workflows
4. Update **Cal.com webhook URL** to point to n8n's booking webhook
5. Test one more time with the live bot
6. **Done** — n8n is now serving your real users

### Keep Make.com for 30 days as backup
- Don't delete your Make.com scenarios immediately
- If something breaks in n8n, you can reactivate Make.com in seconds
- After 30 days of stable n8n operation, you can safely archive/delete Make.com

---

## 13. Maintenance & Updates

### Keeping n8n updated (monthly, 5 minutes)

```bash
cd ~/n8n
docker compose pull
docker compose up -d
```

That's it. n8n updates are backward-compatible.

### Monitoring

- **Check daily (first week):** SSH in, run `docker compose logs --tail=50` to ensure no errors
- **After first week:** check weekly or set up a simple uptime monitor (e.g., UptimeRobot free tier)
- **Auto-restart:** Docker's `restart: always` policy means if the server reboots, n8n restarts automatically

### Backup your n8n workflows

Periodically export your workflows (n8n Settings → Export All Workflows → JSON file). Store in the repo or Google Drive.

---

## 14. Rollback Plan

If n8n has issues and you need to go back to Make.com:

1. SSH into server → `docker compose down` (stops n8n)
2. In Make.com → Turn ON your scenarios (they're still there, untouched)
3. Update Cal.com webhook back to the Make.com URL
4. Bot is back on Make.com instantly

**This is a 2-minute rollback.** No data is lost because the CRM (Google Sheets) is the same for both systems.

---

## 15. Timeline

| Week | Action |
|---|---|
| **Week 1** | Oracle Cloud signup + server setup + n8n installed |
| **Week 2** | Migrate main workflow (welcome + quiz + all routes) |
| **Week 3** | Migrate A5 booking + backup + test all |
| **Week 4** | Parallel run (test bot) → cutover to live bot |
| **Week 5+** | n8n is live; add Phase 1 workflows (report + nudges) directly in n8n |

> Total effort: ~3–5 days of focused work, spread across 4 weeks (no rush — Make.com keeps working during migration).

---

## 16. Cost Comparison (Final)

| Timeframe | Make.com cost | n8n self-host cost |
|---|---|---|
| Today (57 members) | $0 (free tier) | $0 |
| 6 months (200 members) | $9/mo ($54 total) | **$0** |
| 1 year (500 members) | $16/mo ($192 total) | **$0** |
| 2 years (2000+ members) | $29–99/mo ($700–2400) | **$0** |
| **Lifetime total** | **$1,000–5,000+** | **$0** |

The migration pays for itself in the first month after you'd hit the free tier limit.

---

*End of n8n Migration Plan v1.0 — planning artifact. No migration has been performed.*
