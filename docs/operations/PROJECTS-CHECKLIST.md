# ✅ Empire English — Projects Checklist (what's inside this folder)

> Quick map of everything we built. Open this first when you come back.
> Repo: github.com/empireenglishcommunity-glitch/Claude · all merged into `main`.

---

## 🤖 1) Telegram Sales Bot  — ⭐ MAIN / LIVE
- [x] **`telegram-assistant/worker.js`** — the live bot (Cloudflare Worker, **v13**)
- [x] `telegram-assistant/SETUP.md` — setup steps (bot, KV, cron, webhook)
- [x] ~~`telegram-assistant/Code.gs`~~ — removed (deprecated, replaced by worker.js)

**What it does:** guided button menus (packages, compare, help-me-choose, FAQ, subscribe) ·
auto-replies to typed questions (keyword bank, no AI = free + reliable) ·
**payment approval gate** (money stuff goes to you first) · crypto/bank escalated to you ·
auto-learns new answers · daily 5-step reminder funnel · invoice capture · subscribe-confirm ·
feedback · admin commands `/version /kv /list /stats`.

---

## 💰 2) Pricing & Business Strategy
- [x] **`EEC-Feasibility-Study.md`** — Egypt (zero-cost bootstrap) + how many members = 3,000 AED salary
- [x] **`EEC-International-Pricing-and-Feasibility.md`** — Gulf/worldwide USD pricing + feasibility
- [x] Final pricing (in docs + bot): Recruit 199ج/$19 · Builder ⭐ 399ج/$39 · Empire 799ج/$89 · VIP 3,500ج/$249

---

## 🚀 3) Launch Playbook & Marketing Content
- [x] **`EEC-Launch-Night-Playbook.md`** — full A-to-Z launch ("The Gates Open"):
  - [x] Part B — finalized plan (TikTok + Telegram, timeline)
  - [x] Part C — soft founding-launch plan
  - [x] Part C.1 — ready Telegram announcement post (with prices + date)
  - [x] Part C.2 — package cards (features + image prompts + album caption)
  - [x] Part C.3 / C.4 — ChatGPT image prompts (English + Arabic)
  - [x] Part C.5 — final announcement post with payment details
  - [x] Part C.6 — per-package explainer DM messages (Egyptian Arabic)

---

## 🌐 4) Landing Pages (black + gold "empire" theme)
- [x] **`index.html`** — English landing page
- [x] **`index-ar.html`** — Arabic (RTL) landing page
- Features: animated gates, countdown, 🇪🇬/🌍 price toggle, packages, 9 testimonials (placeholders), FAQ, TikTok @macal.empire, logo/favicon slots

---

## 📚 5) Guides & Handoff (so you never lose work)
- [x] **`GUIDE.md`** — backup, folder structure, how to add answers/buttons, deploy cheat-sheet
- [x] **`PROJECT-CONTEXT.md`** — full handoff doc + ready prompt to continue in a new conversation
- [x] **`PROJECTS-CHECKLIST.md`** — this file

---

## 🛡️ 7) Server Infrastructure Hardening — ✅ DEPLOYED (June 21, 2026)
- [x] **`docs/SERVER_REFERENCE.md`** — complete server reference (v2.0, hardened)
- [x] **`docs/SERVER_AUDIT.md`** — full security audit report
- [x] **`docs/EMERGENCY-RECOVERY.md`** — standalone emergency recovery guide
- [x] **`server-hardening/`** — complete implementation package (deployed)

**Server:** Hetzner CX23 (`empire-n8n`), Helsinki, Ubuntu 26.04 LTS, 4GB RAM, 2 vCPU

**What was implemented:**
- [x] 2GB swap file (OOM crash protection, swappiness=10)
- [x] Port 5678 closed to public (n8n bound to localhost only)
- [x] SSH hardened (password auth disabled, key-only, MaxAuthTries=3, 5min timeout)
- [x] Fail2Ban installed (SSH jail: 3 failures → 24h ban via UFW)
- [x] UFW SSH rate-limiting (6 connections/30s per IP)
- [x] n8n Docker image pinned to v2.26.8
- [x] Container resource limits (2.5GB RAM, 1.5 CPU, 200 PIDs)
- [x] Docker healthcheck (auto-restart zombie containers)
- [x] Docker log rotation (10MB × 5 files)
- [x] Telegram monitoring watchdog (60s checks, auto-recovery, deduplication)
- [x] Automated daily backup (3AM, 14-day rotation)
- [x] External uptime monitoring (BetterStack, 3min checks, email alerts)
- [x] Kernel updated (7.0.0-22-generic) + verified full reboot recovery

**Monitoring bots:**
- `@macal_guardian_bot` → alerts `@macal_emperor` via Telegram (internal, 60s)
- BetterStack → email alerts (external, 3min, covers total server failure)

**Infrastructure Score: 3.7/10 → 9.0/10**

**What YOU need to do (ongoing):**
- [ ] Periodically check n8n releases and update version in `/opt/n8n/docker-compose.yml`
- [ ] Consider enabling Hetzner backup add-on (~€1.22/mo) for full disk-level protection
- [ ] Review Fail2Ban banned IPs occasionally (`fail2ban-client status sshd`)

---

## 🔜 Possible next steps (not done yet)
- [ ] Add real success stories/testimonials (landing page + bot)
- [ ] og-image (social share image) + analytics pixels (Meta/TikTok)
- [ ] Custom domain for the landing page
- [ ] Fill bot crypto (USDT/Binance) + bank-transfer details (currently handled by you manually)
- [ ] Weekly stats report from the bot

---

## 🎯 6) 30-Day Challenge Bot (Discord) — ✅ DEPLOYED (June 22, 2026)
- [x] **`empire-challenge-bot/`** — complete Discord bot + content package
- [x] `src/bot.py` — main bot: 12 commands (join, done, today, me, top, cert, recap, guide, status, setday, announce, reset)
- [x] `src/database.py` — SQLite storage (participants + progress)
- [x] `src/challenges.py` — load/serve 30 challenges from JSON
- [x] `src/ai_coach.py` — Groq AI motivation + Arabic fallback (100% works without key)
- [x] `src/certificate.py` — PDF certificates with Cairo Arabic font
- [x] `data/challenges.json` — all 30 challenge definitions
- [x] `data/tiktok-captions.md` — 30 Arabic TikTok captions
- [x] `data/tiktok-captions-en.md` — 30 English TikTok captions
- [x] `data/poster-text.md` — 30 poster text designs + 3 templates
- [x] `data/launch-week-promo.md` — 7 teaser video scripts (Day -7 to -1)
- [x] `data/launch-day-live-script.md` — Day 0 live stream script (45 min, bilingual)
- [x] `data/CONTENT-INDEX.md` — content index + launch flow diagram
- [x] `fonts/Cairo-Variable.ttf` — Arabic font for PDF certificates (OFL licensed)
- [x] `tests/` — 49 automated tests (pytest)
- [x] `.github/workflows/challenge-bot-test.yml` — CI (runs on push/PR)
- [x] `Dockerfile` + `docker-compose.yml` — containerized deployment
- [x] `DEPLOYMENT.md` — deployment guide (Docker / direct / free cloud)
- [x] `scripts/backup.py` — SQLite backup utility with rotation
- [x] `README.md` — full setup guide (bilingual EN/AR)

**What it does:** Auto-posts daily challenge · tracks progress & streaks · AI motivation ·
auto-assigns Discord rank roles (4 tiers) · PDF certificates · leaderboard · weekly recap ·
admin commands (status, setday, announce, reset) · cron backup. 100% free, zero vendor lock-in.

**What YOU still need to do (human-only steps):**
- [x] Create Discord bot at discord.com/developers ✅
- [x] Create Discord server with full channel/role structure ✅ (automated via `scripts/setup_server.py`)
- [x] Fill `.env` with credentials ✅
- [x] Deploy (`docker compose up -d`) on Hetzner VPS ✅
- [x] Credentials rotated after initial exposure ✅
- [x] Daily backup cron configured (3 AM) ✅

**Deployment details:**
- Server: Hetzner CX23 (`empire-n8n`), `/opt/empire-challenge/empire-challenge-bot/`
- Container: `empire-challenge-bot` (Docker, restart: unless-stopped)
- Start date: July 1, 2026 (daily post at 6 AM Asia/Dubai)
- Discord server: Empire English — تحدّي 30 يوم (ID: 1518615304035373106)

**Remaining (creative/human tasks before July 1):**
- [x] Set `START_DATE=2026-07-01` in .env ✅
- [ ] Design 30 posters in Canva from `data/poster-text.md` (creative work)
- [ ] Record 7 teaser videos from `data/launch-week-promo.md` (creative work)
- [ ] Run Day 0 live session using `data/launch-day-live-script.md`
- [ ] Post welcome/rules content in `#اقرأ-أولًا` and `#القوانين`

---

## 📝 8) LinkedIn Content Engine — ✅ DEPLOYED (June 22, 2026)
- [x] **`linkedin-engine/worker.js`** — Cloudflare Worker (text + image + carousel + Telegram cockpit)
- [x] `linkedin-engine/SETUP.md` — full setup guide (dashboard + CLI)
- [x] `linkedin-engine/carousel.gs` — Google Apps Script for PDF carousel generation
- [x] `linkedin-engine/brand/macal-brand-bible.md` — MACAL voice reference
- [x] `linkedin-engine/_test.mjs` — smoke test (mocks Telegram + Gemini + AI)
- [x] `linkedin-engine/wrangler.toml` — Cloudflare Workers config
- [x] `.github/workflows/linkedin-engine-smoke-test.yml` — CI (syntax + wrangler dry-run)

**What it does:** Generates daily brand-voice LinkedIn posts (hook + body + hashtags + image + carousel) via Gemini AI → delivers to Telegram with inline buttons (Approve / Regenerate / Other hook / Tweak / New image / Carousel / Skip). Self-tuning topic rotation. Zero cost.

**What YOU still need to do (to deploy):**
- [x] Create Cloudflare Worker (`linkedin-engine`) and paste `worker.js` ✅
- [x] Create KV namespace and bind as `KV` ✅
- [x] Add secrets: `TELEGRAM_TOKEN`, `ADMIN_CHAT_ID`, `GEMINI_API_KEY` ✅
- [x] (Optional) Bind Workers AI as `AI` for image generation ✅
- [x] Set Telegram webhook to worker URL ✅
- [x] Add Cron trigger (`0 5 * * *` = 7 AM Cairo / 9 AM Dubai) ✅
- [x] Test with `/new` command in Telegram ✅
- [ ] Replace `BEST_POSTS` with your real top-performing posts (quality lever)
- [ ] Rotate Telegram token + Gemini key (exposed in chat — do ASAP)

**Deployment details:**
- Worker: `linkedin-engine.macalempire.workers.dev`
- KV: `linkedin-kv`
- Cron: `0 5 * * *` (daily 9 AM Dubai)
- Telegram cockpit: connected and responding

---

ℹ️ Note: the repo also contains a separate **mobile app** ("Phase 1 — The Core", React Native/Expo) merged via PR #4 from another effort — not part of the work in this conversation.

---

## 📱 9) Mobile App (Pronunciation Dictionary) — Phase 1 Complete (Parked)
- [x] Expo/React Native app structure (Expo Router, TypeScript strict)
- [x] 30 curated words with Arabic meanings, syllable breakdowns, IPA
- [x] Speech service (slow/normal speed pronunciation)
- [x] Dictionary service (offline-first + API fallback)
- [x] 8 branded UI components (gold-on-black theme)
- [x] 3 screens: Splash → Dictionary/Sentences tabs → Word detail

**Status:** Development complete. Not published to app stores.
**Next:** Publish to Apple App Store + Google Play when ready (requires developer accounts).

---

## 📋 Master Priority List (What's Left Across All Projects)

### 🔴 Before July 1, 2026 (Challenge Launch)
- [ ] Record 7 teaser videos (`empire-challenge-bot/data/launch-week-promo.md`)
- [ ] Design 30 posters in Canva (`empire-challenge-bot/data/poster-text.md`)
- [ ] Post welcome/rules in Discord `#اقرأ-أولًا` + `#القوانين`
- [ ] Run Day 0 live session (June 30)
- [ ] Share Discord invite link on TikTok

### 🟡 Short-term (July 2026)
- [ ] Host landing pages (Cloudflare Pages or GitHub Pages)
- [ ] Add real testimonials (landing page + Telegram bot)
- [ ] Add OG image + analytics pixels to landing pages
- [ ] Replace `BEST_POSTS` in LinkedIn Engine with real top posts
- [ ] Rotate LinkedIn Engine credentials (Telegram token + Gemini key)

### 🟢 Medium-term (when ready)
- [ ] Make repository private (no impact on any service)
- [ ] Publish mobile app to stores
- [ ] Custom domain for landing page
- [ ] Fill crypto (USDT/Binance) details in Telegram bot
- [ ] Enable Hetzner backup add-on (~€1.22/mo)

---

*Last updated: June 22, 2026*
