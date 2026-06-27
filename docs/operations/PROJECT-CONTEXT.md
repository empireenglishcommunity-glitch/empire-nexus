# 🧭 PROJECT CONTEXT — Empire English Community

> **Purpose:** Complete handoff document for any new AI agent, developer, or conversation.
> Read this top to bottom — everything needed to continue work is here.
>
> **Last updated:** June 22, 2026

---

## 0) ONE-LINE SUMMARY

**Empire English Community (EEC)** — a full-stack online English-learning community for Arabic speakers (sub-brand of MACAL Empire). We built and deployed: a Telegram sales bot, a Discord challenge bot, a LinkedIn content engine, landing pages, a mobile app, server infrastructure, and comprehensive marketing content.

---

## 1) WHERE EVERYTHING LIVES

| Resource | Location |
|----------|----------|
| **GitHub repo** | https://github.com/empireenglishcommunity-glitch/Claude |
| **Branch** | `main` (all work merged) |
| **VPS** | Hetzner CX23, Helsinki, `77.42.43.250` (SSH key-only) |
| **n8n** | `https://bot.empireenglish.online` (via Cloudflare Tunnel) |
| **Domain** | `empireenglish.online` (Namecheap → Cloudflare NS) |
| **Steering rules** | `.kiro/steering/project-rules.md` (auto-loaded by Kiro) |

---

## 2) ALL SYSTEMS — CURRENT STATE

| # | System | Platform | Status | Key File |
|---|--------|----------|--------|----------|
| 1 | **Telegram Sales Bot** | Cloudflare Worker | ✅ LIVE (v13) | `telegram-assistant/worker.js` |
| 2 | **30-Day Challenge Bot** | Docker on Hetzner | ✅ DEPLOYED (v1.0.0) | `empire-challenge-bot/src/bot.py` |
| 3 | **LinkedIn Content Engine** | Cloudflare Worker | ✅ DEPLOYED (June 22, 2026) | `linkedin-engine/worker.js` |
| 4 | **Landing Pages** | Not hosted | Built | `web/index.html`, `web/index-ar.html` |
| 5 | **Mobile App** | Not published | Phase 1 done | `app/` + `src/` |
| 6 | **Server Hardening** | Hetzner VPS | ✅ DEPLOYED | `server-hardening/` |
| 7 | **n8n Workflows** | Docker on Hetzner | ✅ RUNNING | `/opt/n8n/` on server |

---

## 3) TELEGRAM SALES BOT (System 1 — LIVE)

- **Platform:** Cloudflare Worker (single file), returns HTTP 200. Free + always-on.
- **Storage:** Cloudflare KV (`KV`) — stores learned answers, customer memory, invoices.
- **No AI** — keyword answer bank + button menus. Deliberate decision for 100% reliability.
- **Version:** v13. Check: send `/version` to the bot.

### Behavior
- First message → welcome + main menu buttons
- Buttons: الباقات / ساعدني أختار (quiz) / قارن الباقات / طرق الدفع / أسئلة شائعة / عايز أشترك
- Payment/crypto → admin approval FIRST, then customer sees response
- Unknown question → menu + escalates to admin + "🧠 رد + تعليم" (auto-learn)
- Payment proof photo → forwarded + logged + "✅ تأكيد الاشتراك" button
- Daily reminder funnel (Cron `0 16 * * *`): 5 messages over 5 days, stops on subscribe
- Admin commands: `/version` `/kv` `/list` `/stats`

### To modify
Edit `telegram-assistant/worker.js` → paste in Cloudflare dashboard → Deploy → `/version` to confirm.

---

## 4) 30-DAY CHALLENGE BOT (System 2 — DEPLOYED)

- **Platform:** Python 3.12 + discord.py, Docker container on Hetzner VPS
- **Location:** `/opt/empire-challenge/empire-challenge-bot/`
- **Container:** `empire-challenge-bot` (restart: unless-stopped)
- **Database:** SQLite (persisted in Docker volume `bot-db`)
- **AI:** Groq free API (llama-3.3-70b) + built-in Arabic fallback
- **Version:** v1.0.0. Check: `!version` in Discord.
- **Discord Server:** Empire English — تحدّي 30 يوم (ID: 1518615304035373106)
- **Start Date:** July 1, 2026 (auto-posts daily at 6 AM Asia/Dubai)

### Commands (13 total)
`!join` `!done` `!today` `!me` `!top` `!cert` `!recap` `!guide` `!version` `!status` `!setday` `!announce` `!reset`

### Content Package (in `empire-challenge-bot/data/`)
- 30 challenges JSON (bot reads automatically)
- 7 pre-launch teaser video scripts
- Day 0 live stream script (bilingual)
- 30 TikTok captions (Arabic + English)
- 30 poster text designs

### To update
```bash
ssh -i ~/.ssh/id_ed25519 root@77.42.43.250
cd /opt/empire-challenge && git pull
cd empire-challenge-bot && docker compose down && docker compose up -d --build
docker compose logs --tail=10  # verify "Bot online"
```

---

## 5) LINKEDIN CONTENT ENGINE (System 3 — Built, Not Deployed)

- **Platform:** Cloudflare Worker (single file `worker.js`)
- **AI:** Gemini 2.5 Flash Lite → Groq (fallback) → Evergreen bank (never empty)
- **Content:** 13 pillars × 9 formats, self-tuning rotation from approve/skip behavior
- **Features:** Daily draft → Telegram with 7 buttons (Approve/Regenerate/Hook/Tweak/Image/Carousel/Skip)
- **Setup guide:** `linkedin-engine/SETUP.md`

### To deploy
See `linkedin-engine/SETUP.md` — same pattern as Telegram bot (paste worker.js → set secrets → KV → webhook → cron).

---

## 6) SERVER INFRASTRUCTURE

| Parameter | Value |
|-----------|-------|
| **Provider** | Hetzner Cloud (CX23, Helsinki) |
| **IP** | `77.42.43.250` |
| **OS** | Ubuntu 26.04 LTS |
| **SSH** | Key-only (Ed25519). Key: `C:\Users\97150\.ssh\id_ed25519` |
| **RAM** | 4 GB (n8n capped at 2.5 GB) |
| **Monthly cost** | ~$7 |
| **Security score** | 9.0/10 |

### Running services (all auto-start on reboot)
- Docker Engine + n8n container (`empire-n8n`)
- Challenge Bot container (`empire-challenge-bot`)
- Cloudflare Tunnel (`cloudflared.service`)
- Fail2Ban (SSH jail, 24h ban)
- Monitoring watchdog (systemd timer, 60s)
- Backup (cron, daily 3 AM)

### Key files on server
```
/opt/n8n/docker-compose.yml          ← n8n configuration
/opt/empire-challenge/               ← Challenge bot repo clone
/opt/monitor/watchdog.sh             ← Health monitoring script
/opt/backups/backup-n8n.sh           ← n8n backup script
/root/.cloudflared/config.yml        ← Tunnel routing
/etc/fail2ban/jail.local             ← SSH jail config
```

### Full reference
- Architecture: `docs/SERVER_REFERENCE.md`
- Emergency recovery: `docs/EMERGENCY-RECOVERY.md`

---

## 7) PRICING (confirmed & active)

| Tier | 🇪🇬 Egypt /mo | 🌍 Worldwide /mo |
|------|--------------|------------------|
| Recruit | 199 EGP | $19 |
| Builder ⭐ | 399 EGP | $39 |
| Empire | 799 EGP | $89 |
| VIP 1-on-1 | 3,500 EGP | $249 |

- Founding price locked forever. Annual ≈ 35% off.
- 7-day money-back guarantee.
- Regional pricing: "fair like Netflix" framing.

### Payment Methods
- 🇪🇬 Vodafone Cash: 01004581035 · InstaPay: 01004581035 / mohamedashry10041
- 🌍 PayPal: paypal.me/bioroma
- 🪙 USDT (Binance) & 🏦 bank transfer → admin sends details personally

---

## 8) KEY DECISIONS (do not reverse without discussion)

| Decision | Rationale |
|----------|-----------|
| No AI in Telegram sales bot | Free tier AI was unreliable; keyword bank = 100% uptime |
| SQLite for Challenge Bot | Zero-cost, zero-setup, perfect for <10K users |
| n8n over Make.com/Zapier | No operation limits, self-hosted, no vendor lock-in |
| Cloudflare Workers for bots | Always-on, free, no process management needed |
| SSH key-only authentication | Security requirement — passwords permanently disabled |
| Docker for all services | Isolation, reproducibility, resource limits, auto-restart |
| Port 5678 localhost-only | Docker bypasses UFW — binding to 127.0.0.1 is real enforcement |
| Human-in-the-loop for money | All payments require admin approval before customer sees |

---

## 9) BRAND & VOICE

- **Community:** Empire English Community
- **Parent:** MACAL Empire ("Common Sense First")
- **Visual:** Gold (#D4AF37) on matte black (#0A0A0B)
- **Voice (LinkedIn/MACAL):** Authoritative, sarcastic (scalpel not sledgehammer), paternal/protective
- **Voice (Telegram/Discord):** Egyptian Arabic, warm, motivating, sales-oriented, consistent emojis
- **Owner:** Mahmoud Ashri (@macal_emperor)
- **TikTok:** @macal.empire

---

## 10) WHAT'S LEFT TO DO

### Before July 1, 2026 (Challenge Launch)
- [ ] Record 7 teaser videos (scripts in `empire-challenge-bot/data/launch-week-promo.md`)
- [ ] Design 30 posters in Canva (text in `empire-challenge-bot/data/poster-text.md`)
- [ ] Post welcome/rules in Discord #اقرأ-أولًا + #القوانين
- [ ] Run Day 0 live session (June 30)
- [ ] Share Discord invite on TikTok

### Short-term
- [ ] Deploy LinkedIn Engine to Cloudflare
- [ ] Host landing pages
- [ ] Add real testimonials
- [ ] Make repository private

### Full task list
See `docs/PROJECTS-CHECKLIST.md` → "Master Priority List" section.

---

## 11) HANDOFF PROMPT (for new AI conversations)

Copy-paste this into any new AI chat to continue work:

---

> I'm continuing a project called **Empire English Community** — a monorepo with multiple systems for an English-learning community for Arabic speakers. The repo is `empireenglishcommunity-glitch/Claude` on GitHub.
>
> **Currently deployed:**
> - Telegram Sales Bot (Cloudflare Worker, v13, live)
> - 30-Day Challenge Bot (Discord, Python/Docker on Hetzner VPS, v1.0.0, live — starts July 1)
> - Server infrastructure (Hetzner CX23, hardened, monitored, backed up)
>
> **Built but not yet deployed:**
> - LinkedIn Content Engine (Cloudflare Worker, ready)
> - Landing pages (HTML, ready)
>
> **Key files:** `README.md` (project map), `docs/PROJECTS-CHECKLIST.md` (everything built), `.kiro/steering/project-rules.md` (AI rules), `docs/SERVER_REFERENCE.md` (infrastructure).
>
> I want to [DESCRIBE WHAT YOU WANT]. The repo has full documentation — read the steering file and checklist first.

---

> With this file + the repo + the steering rules, any AI or developer can continue exactly where we left off. 👑
