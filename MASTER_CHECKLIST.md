# Empire English Community — Master Progress Checklist

**Generated:** June 27, 2026 (evidence-verified against actual repository files)
**Repository:** `empireenglishcommunity-glitch/EEC-REPO` (branch: `main-consolidation-merge`)

---

## Legend

- [x] = Completed and verified
- [~] = Partially complete (details noted)
- [ ] = Not started / remaining
- [B] = Blocked (dependency noted)
- [O] = Optional / future improvement

---

## 1. INFRASTRUCTURE & SERVER

### Hetzner VPS (77.42.43.250)

- [x] Server provisioned (Hetzner CX23, Helsinki, $7/mo)
- [x] SSH hardened (key-only, password auth disabled)
- [x] UFW firewall configured (port 5678 closed, SSH rate-limited)
- [x] Fail2Ban installed (24h ban after 3 failed SSH attempts)
- [x] 2GB swap configured (swappiness=10)
- [x] Docker installed and hardened (memory/CPU limits, healthcheck)
- [x] n8n Docker container deployed (pinned v2.26.8, 127.0.0.1 only)
- [x] Cloudflare Tunnel active (bot.empireenglish.online → localhost:5678)
- [x] MCP route added (mcp.empireenglish.online → localhost:3001)
- [x] Monitoring watchdog deployed (60s systemd timer, auto-restart n8n + tunnel)
- [x] BetterStack external uptime monitor configured (3min checks)
- [x] Daily backup automated (n8n data, 3 AM, 14-day rotation)
- [x] Server hardening scripts version-controlled (7 scripts, idempotent, re-runnable)
- [x] Master deploy.sh script with --only flag for individual steps

### Cloudflare

- [x] Domain `empireenglish.online` configured with Cloudflare DNS
- [x] Named Tunnel `empire-n8n` active
- [x] Worker deployed: Telegram Sales Bot
- [x] Worker deployed: LinkedIn Engine v3.0
- [ ] **Landing pages not deployed to Cloudflare Pages** — Built and ready, just needs the 5-click setup in Cloudflare dashboard (see `apps/web/landing-pages/DEPLOYMENT.md`)

### n8n-MCP Server

- [x] Docker container deployed (ghcr.io/czlonkowski/n8n-mcp)
- [x] Health check passing
- [x] Accessible via Cloudflare Tunnel at mcp.empireenglish.online
- [x] API key moved to .env (security fix applied June 27)
- [x] .env.example created for deployment reference
- [ ] **Rotate the n8n API key on server** — Old key was exposed in git history. Generate new key from n8n Settings → API, update /opt/n8n-mcp/.env on server

---

## 2. TELEGRAM SALES BOT (bots/telegram-sales-bot/)

### Core Functionality

- [x] Cloudflare Worker deployed (v13, live)
- [x] Welcome message + 5-button main menu
- [x] Package info (Recruit, Builder, Empire, VIP) with pricing
- [x] Package comparison system (all 6 pair comparisons + "compare all")
- [x] Recommendation engine ("budget"/"speak"/"goal"/"personal" → package)
- [x] FAQ system (6 topics with inline keyboard navigation)
- [x] Arabic keyword matching (27+ answer patterns, normalized Arabic)
- [x] Payment flow with admin approval gate
- [x] Invoice capture (photo/document → forwarded to admin with confirm button)
- [x] Subscription confirmation (admin confirms → welcome msg + stops reminders)
- [x] Auto-learn system (new questions → admin answers → stored for next time)
- [x] KV-backed user memory (stage tracking, timestamps, reminder state)
- [x] Daily reminder funnel (5 sequential reminders, 20h cooldown, stops on subscribe)
- [x] Cron trigger configured (daily 4 PM UTC)
- [x] Admin commands: /version, /kv, /list, /stats
- [x] Non-admin crypto/bank requests escalated to admin with reply button

### Documentation

- [x] SETUP.md with full deployment guide (updated to v13)
- [ ] **No wrangler.toml for this worker** — Deployed via dashboard paste; if CLI deploy needed in future, create wrangler.toml
- [ ] **No .env.example / .dev.vars.example** — Secrets are documented in SETUP.md but no template file exists

---

## 3. DISCORD LEARNING BOT (bots/discord-learning-bot/)

### Core Bot

- [x] Python bot deployed on Hetzner (Docker, empire-english-bot container)
- [x] 15 commands implemented (!join, !done, !progress, !streak, !top, !streaks, !level, !week, !help, !status, !setlevel, !announce, !members, !version — missing: !assess)
- [x] 3 scheduled tasks (daily task post, weekly assessment prompt, hourly streak check)
- [x] Auto writing feedback (detects submissions in #writing-feedback, evaluates via AI)
- [x] Level role assignment system (auto-creates and assigns level roles)
- [x] Streak tracking with bonus point thresholds (7/14/30/60/100 days)
- [x] Points system (15/task, 100 bonus for all 7, streak bonuses)
- [x] Leaderboards (points + streaks)
- [x] Inactive member intervention system (DM after 1/2/3/5/7 days)
- [x] Dual AI provider (Gemini primary, Groq fallback) with graceful degradation
- [x] SQLite database with 6 tables + WAL mode + indexes

### Content / Curriculum

- [x] L0 Week 1-8 data files complete (all 8 verified: 56 vocab × 7 speaking × 7 writing each)
- [x] L0 advancement exam JSON
- [x] 8 accent drill files (weeks 1-8, phoneme progressions)
- [x] 9 grammar files (weeks 1-8 + quick_fix_index)
- [x] 3 immersion resource files (clips, music, youtube/podcasts)
- [x] 1 speaking template file
- [x] 1 writing framework file
- [x] 6 placement assessment files (4 modules + scoring + onboarding flow)
- [x] 9 AI prompt template files (25 prompts total across 9 categories)
- [x] Evaluation system files (4: weekly assessment, monthly review, progress dashboard, submission pipeline)
- [x] Governance file (privacy and safety policies)
- [x] Documentation file (proof system)

### Discord Server

- [x] Server created (Empire English Community |EEC, ID: 1519797013565280446)
- [x] 44 text channels created across 11 categories
- [x] 12 voice channels created
- [x] 9 custom roles with correct hierarchy and permissions
- [x] Level-gated permissions (L0 can't see L1+ zones)
- [x] Welcome, Rules, Roles-Info content posted
- [x] Bot online and responding to commands
- [x] setup_server.py script for full server rebuild (~60 seconds)

### Missing / Incomplete

- [ ] **Zero test coverage** — tests/__init__.py is empty. Need at minimum: database ops, config validation, task generation tests. Model after challenge bot's test structure.
- [ ] **!exam / !assess command not implemented** — Config and database support advancement exams, but no command exists to trigger them. Reference removed from !level output but the feature itself is needed for pilot.
- [ ] **Google Sheets CRM integration not implemented** — Config has all Sheets credentials (service account, sheet ID, GIDs) but zero API calls exist in the code. Members exist only in SQLite. Need: sync to Sheets on join, sync events, read config.
- [ ] **No health check in Docker** — Challenge bot has HEALTHCHECK in Dockerfile but learning bot does not.
- [B] **Gemini API key not working on server** — Requires SSH from home network to fix: `sed -i 's|GEMINI_API_KEY=.*|GEMINI_API_KEY=<new_key>|' /opt/empire-english-bot/.env && docker compose restart`

---

## 4. DISCORD CHALLENGE BOT (bots/discord-challenge-bot/)

### Core Functionality

- [x] Python bot deployed on Hetzner (Docker, empire-challenge-bot container)
- [x] 30-day challenge data complete (challenges.json with all 30 days)
- [x] Daily auto-post at configured hour
- [x] Commands: !join, !done, !me, !top, !today, !recap, !cert, !guide, !version, !status, !setday, !announce, !reset
- [x] AI coaching (Groq) with built-in fallback messages (works without API key)
- [x] PDF certificate generation (Arabic, Cairo font, gold-on-black design)
- [x] Streak tracking (consecutive days)
- [x] Rank progression (4 tiers: بدأ الرحلة → مثابر → محارب → بطل المرونة)
- [x] Leaderboard
- [x] Telegram lifecycle alerts (bot_online / bot_offline)
- [x] Comprehensive test suite (49 tests, all passing in 0.22s)
- [x] CI pipeline (GitHub Actions, triggers on push/PR)
- [x] DEPLOYMENT.md with 3 deployment options (Docker, Python, cloud)

### Content

- [x] 30 challenges with task + tip + domain + difficulty level
- [x] TikTok captions (Arabic + English, 30 each)
- [x] Launch day live script
- [x] Launch week promo content
- [x] Poster text

### Missing

- [ ] **No mechanism for challenge recycling** — The bot only supports one 30-day run. For a second cohort, !reset deletes ALL data. Need: cohort concept or archive-then-reset.
- [O] Marketing assets (poster-text, tiktok-captions) mixed in data/ folder. Could be separated to content/ but functional as-is.

---

## 5. LINKEDIN ENGINE (workers/linkedin-engine/)

- [x] Cloudflare Worker deployed (v3.0, 1,037 lines)
- [x] 55 power hooks across 5 categories
- [x] 25 visual composition styles for image generation
- [x] 15 content formats
- [x] 13 content pillars
- [x] Angle randomizer (perspective × emotion × structure)
- [x] Self-contained carousel (8-10 slides as Telegram text)
- [x] 16 evergreen fallback posts
- [x] Approval-weighted topic rotation (learns from approve/skip)
- [x] Idea inbox (text any idea → next draft uses it)
- [x] Image generation (Cloudflare Workers AI, Flux model)
- [x] Full Telegram cockpit (7 buttons: Approve, Regenerate, Hook, Tweak, Image, Carousel, Skip)
- [x] Admin commands: /new, /queue, /export, /clearqueue, /stats, /pillars, /version
- [x] Triple fallback LLM chain (Gemini → Groq → Evergreen bank)
- [x] Daily cron (5:00 UTC auto-generates draft)
- [x] Smoke test (17 assertions, all passing)
- [x] CI pipeline (GitHub Actions)
- [x] SETUP.md with dashboard + CLI deployment guides
- [x] .dev.vars.example for secrets
- [x] wrangler.toml with placeholder KV ID

### Missing

- [ ] **BEST_POSTS only has 3 brand-bible examples** — Should contain 6-10 of YOUR real top-performing LinkedIn posts for best voice matching. Need: after publishing 10+ posts, paste best ones into worker.js BEST_POSTS array.
- [O] carousel.gs (Google Apps Script for actual PDF carousels) exists but is optional legacy since v3.0 has self-contained text carousel.

---

## 6. MOBILE APP (apps/mobile/)

- [x] Expo 56 / React Native project scaffolded
- [x] TypeScript configuration
- [x] Expo Router (file-based routing)
- [x] 4 screens (splash/gate, dictionary home, sentence studio, word detail)
- [x] 8 reusable components (EmpireCard, Logo, GoldButton, OrnamentDivider, RoyalBackground, SectionLabel, SpeakerButton, SyllableBreakdown)
- [x] Imperial gold-on-black design system (comprehensive theme file)
- [x] Text-to-speech (expo-speech, American accent, slow/normal speeds)
- [x] 29 curated dictionary words with IPA, syllables, Arabic meanings
- [x] Online dictionary fallback (dictionaryapi.dev)
- [x] Translation service (curated offline + Google Translate fallback)
- [x] History & bookmarks (AsyncStorage)
- [x] Word of the Day
- [x] Animated cinematic splash screen
- [x] Sentence pronunciation studio with Arabic translation
- [x] All dependencies properly listed in package.json (fixed June 27)

### Not Done

- [ ] **App not published** — No eas.json or build configuration. Expo Go only.
- [ ] **No tests**
- [ ] **No README.md** — No documentation explaining the app
- [O] Translation service uses unofficial Google Translate endpoint — works but could break
- [O] tsconfig paths configured but unused (code uses relative imports)

---

## 7. WEB APPLICATIONS (apps/web/)

### Static Landing Pages (apps/web/landing-pages/)

- [x] English landing page (467 lines, full marketing page)
- [x] Arabic RTL landing page (417 lines)
- [x] _redirects (/ → Arabic, /en → English)
- [x] _headers (security headers)
- [x] DEPLOYMENT.md (Cloudflare Pages + GitHub Pages instructions, updated paths)
- [x] Countdown timer (updated to July 12, 2026)

### Not Done

- [ ] **Not deployed to any host** — Ready to deploy to Cloudflare Pages (5-click setup)
- [ ] **og-image.png missing** — Referenced in meta tags but file doesn't exist
- [ ] **No favicon file** — Uses emoji fallback

### Next.js Web App (apps/web/next-app/)

- [x] Next.js 14 project with Tailwind CSS
- [x] Arabic-first RTL layout
- [x] Marketing page components (Hero, Problem, System, Levels, Proof, Pricing, FAQ, CTA, Footer)
- [x] Student dashboard skeleton (DailyTasks, WritingTask, AudioRecorder)
- [x] AI writing feedback endpoint (/api/feedback → Gemini)
- [x] Supabase auth client initialized
- [x] Login/signup page shells
- [x] .env.example for configuration
- [x] Static export conflict fixed (removed output:'export', June 27)
- [x] @supabase/supabase-js added to dependencies (June 27)
- [x] PRICING_NOTE.md documenting pricing across surfaces

### Not Done

- [ ] **Not deployed** — No hosting configured
- [ ] **Auth not functional** — Login/signup pages exist but no actual auth flow
- [ ] **Student dashboard incomplete** — Components are shells, not wired to data
- [ ] **No README**
- [ ] **No tests**
- [O] Some components still 1-line minified (FAQ, Levels, Pricing, Problem, Proof, System) — functional but hard to maintain

---

## 8. n8n AUTOMATION WORKFLOWS

### Deployed & Running (on server)

- [x] Empire Bot — Main v2 (ID: lC9SVi4JDXZvAogr) — Real-time Telegram bot handler
- [x] Empire Weekly Report (ID: MBQvHBmLd4RrnxpY) — Monday 8 AM
- [x] Empire Quiz Nudge (ID: Wmp6s6ImewLkmZ9Y) — Daily 6 PM
- [x] Empire Call Nudge (ID: N7KR2sk1CjrZVxuh) — Daily 6 PM
- [x] Empire — Booking Sync (ID: qtpi5Hmwjoo4iUyO) — Webhook from Cal.com
- [x] Empire — Daily CRM Backup (ID: eSNBttijnIOXkAIx) — Daily 2 AM
- [x] Empire — Lead Score Recompute (ID: 5LJv9TowMuVKhpzE) — Daily 3 AM

### Repository Backups

- [x] 3 workflow JSON exports (EMPIRE-BOT-FINAL, empire-bot-main-v2, empire-routes-complete)
- [x] IMPORT_INSTRUCTIONS.md
- [x] ROUTE_CODE_BLOCKS.md

### Not Done

- [ ] **Only 3 of 7 workflows exported as JSON** — Missing exports for: Quiz Nudge, Call Nudge, Booking Sync, Daily Backup, Lead Score. Should export all 7 for disaster recovery.
- [ ] **Cal.com webhook URL not configured** — Webhook endpoint exists in n8n (qtpi5Hmwjoo4iUyO) but Cal.com dashboard doesn't have the URL set yet. Action: Add `https://bot.empireenglish.online/webhook/calcom-booking` in Cal.com → Webhooks.
- [ ] **KPI_Weekly tab not created in Google Sheets** — Weekly report workflow appends to this tab but it doesn't exist yet. Create in the CRM spreadsheet.
- [ ] **Stories tab not created in Google Sheets** — For testimonial collection. Create in CRM.

---

## 9. CONTENT & MARKETING

### Telegram Channel Content

- [x] Week 1 posts (6 posts)
- [x] Week 2 posts (6 posts)
- [x] Week 3 posts (6 posts)
- [x] Week 4 posts (6 posts)
- [x] Week 5 posts (6 posts)
- [x] Week 6 posts (6 posts)
- [x] Word of the Day (14 posts)
- [x] Discussion group seeding content (Week 1)
- [x] 3 American Sounds lead magnet content documented

### Not Done

- [ ] **Posts not scheduled/published** — All 36 posts are written but none have been posted to the Telegram channel yet. Need: schedule Week 1 (6 posts over 6 days).
- [ ] **Discussion group not seeded** — Group exists (t.me/empireenglishcommunity) but seeding posts haven't been published.
- [ ] **Week 7+ content not written** — 6 weeks is sufficient for Phase 1 launch but will need more eventually.

### Brand & Lead Magnets

- [x] MACAL Brand Bible (86 lines, voice guide)
- [x] 3 American Sounds content (documented in docs/specs/phase-1/)
- [x] PDF lead magnet hosted on Google Drive
- [ ] **3 audio clips not recorded** — The "3 American Sounds" lead magnet is documented but actual audio recordings don't exist yet. Bot serves PDF text with "audio coming soon" note.

---

## 10. CRM & DATA

### Google Sheets CRM

- [x] Spreadsheet created (ID: 13fJFzyeTMYHFKj2YDEy620fHfznbFvhTieqD8N1KUCg)
- [x] Subscribers tab (GID: 421473979)
- [x] Events tab (GID: 1549846062)
- [x] Service Account configured (credential ID: k6ND5geKqsYEj25I, name: "Empire CRM")
- [x] n8n Google Sheets integration working (Service Account auth, mode: list with GID)
- [x] CRM templates version-controlled (4 CSVs in content/build-kit/crm/)
- [x] Quiz scoring logic documented (content/build-kit/quiz-logic.md)
- [x] Lead score formula defined and auto-computed (n8n workflow)

### Not Done

- [ ] **KPI_Weekly tab missing** — Create in CRM spreadsheet for weekly report data
- [ ] **Stories tab missing** — Create for testimonial collection
- [ ] **Config tab links not all filled** — config.csv has placeholders for some URLs (DISCORD_INVITE needs current value)

---

## 11. DOCUMENTATION

### Strategy & Planning (Complete)

- [x] Empire English Community Learning System (1,034 lines — the product vision)
- [x] Strategic Expansion Roadmap (454 lines — pricing, monetization)
- [x] Channel Growth & Conversion Blueprint (649 lines — funnel, 10 decisions)
- [x] Master Implementation Roadmap (317 lines — P0→P3 overview)
- [x] Full Implementation Roadmap (449 lines — 6-phase execution plan)
- [x] Learning System Implementation Plan (1,571 lines — most detailed spec)
- [x] Phase 0 Spec + Content Assets (1,123 lines combined)
- [x] Phase 1 Spec (514 lines)
- [x] 30-day Challenge Program Design (Arabic, 266 lines)
- [x] Ecosystem architecture docs (2 files, 885 lines)

### Operations (Complete)

- [x] Server Reference (566 lines)
- [x] Emergency Recovery Guide (808 lines)
- [x] Security Audit (953 lines)
- [x] Projects Checklist (220 lines)
- [x] Project Context / handoff (234 lines)
- [x] Complete Project Audit (452 lines)
- [x] N8N Workflow Patterns (423 lines — MANDATORY reference)
- [x] Quiz System Technical Audit (571 lines)
- [x] Repository Audit (284 lines — June 27)

### Business

- [x] Egypt Feasibility Study
- [x] International Pricing & Feasibility
- [x] Launch Night Playbook (860 lines)

### Repository Organization

- [x] README.md (comprehensive project index)
- [x] PROJECT_STATUS.md (current state, rewritten June 27)
- [x] REPOSITORY_AUDIT.md (full technical audit)
- [x] docs/README.md (documentation reading order guide)
- [x] .kiro/steering/ (AI agent rules, 2 files)
- [x] 4 checkpoint files (session history)

---

## 12. CI/CD & TESTING

- [x] Challenge bot CI (GitHub Actions, pytest, 49 tests passing)
- [x] LinkedIn engine CI (GitHub Actions, node smoke test, 17 assertions passing)
- [ ] **Discord Learning Bot has zero tests** — Highest-risk component with no safety net
- [ ] **Telegram Sales Bot has no tests or CI**
- [ ] **Mobile App has no tests or CI**
- [ ] **Next.js Web App has no tests or CI**

---

## 13. SECURITY

- [x] SSH key-only authentication
- [x] Fail2Ban configured (24h ban)
- [x] n8n bound to 127.0.0.1 (not exposed to internet)
- [x] API key removed from committed files (June 27 fix)
- [x] .env.example files in place (no real secrets in repo)
- [x] .gitignore covers .env, .dev.vars, *.db, node_modules
- [ ] **Rotate n8n API key** — Old key was in git history. Generate new one on server.
- [ ] **No secret scanning configured** — Could add GitHub secret scanning or a pre-commit hook

---

## 14. BLOCKED TASKS (require specific actions outside this repo)

| Task | Blocker | Action Required |
|------|---------|-----------------|
| Fix Gemini key on Discord bot | Requires SSH from home network | `nano /opt/empire-english-bot/.env` → update GEMINI_API_KEY → `docker compose restart` |
| Rotate n8n API key | Requires n8n admin access | n8n Settings → API → Regenerate → update /opt/n8n-mcp/.env |
| Add Cal.com webhook | Requires Cal.com dashboard access | Cal.com → Webhooks → Add URL: `https://bot.empireenglish.online/webhook/calcom-booking` |
| Assign Founder role | Requires Discord server access | Server Settings → Roles → assign to yourself |
| Create CRM tabs | Requires Google Sheets access | Open CRM sheet → add KPI_Weekly + Stories tabs |
| Deploy landing pages | Requires Cloudflare dashboard | Pages → Create → Connect repo → set output dir |
| Schedule Telegram posts | Requires Telegram channel access | Use Telegram native scheduler or n8n |

---

## 15. RECOMMENDED NEXT ACTIONS (Priority Order)

### This Session (if SSH available):

1. Fix Gemini API key on Hetzner
2. Rotate n8n API key
3. Test Discord bot commands live

### Quick Wins (no code required):

4. Create KPI_Weekly + Stories tabs in Google Sheets
5. Add Cal.com webhook URL
6. Assign Founder role in Discord
7. Deploy landing pages to Cloudflare Pages

### Content Launch:

8. Schedule Week 1 Telegram posts (6 posts over 6 days)
9. Seed discussion group with GROUP_SEEDING_WEEK1 content
10. Start approving LinkedIn Engine daily posts (/new)

### Pilot Preparation:

11. Recruit 3-5 pilot members for Discord
12. Test full onboarding flow (!join → !done → !progress → !streak)
13. Monitor for 1 week before inviting more

### Development Priorities (for next coding session):

14. Write tests for Discord Learning Bot (database + tasks modules)
15. Export remaining 4 n8n workflows as JSON backup
16. Record 3 American Sounds audio clips (lead magnet)
17. Add BEST_POSTS to LinkedIn engine (after 10+ published posts)

---

## 16. OPTIONAL FUTURE IMPROVEMENTS

- [O] Add tests for Telegram Sales Bot
- [O] Publish mobile app to App Store / Play Store (needs eas.json)
- [O] Deploy Next.js web app (needs hosting decision: Vercel/Cloudflare/self-host)
- [O] Implement !exam advancement command in learning bot
- [O] Implement Google Sheets CRM sync in learning bot
- [O] Add Docker HEALTHCHECK to learning bot Dockerfile
- [O] Add challenge bot cohort management (archive + restart)
- [O] Format remaining minified Next.js components
- [O] Add pre-commit hook for secret scanning
- [O] Build L1/L2/L3 curriculum content
- [O] Implement Phase 2 (A/B testing, follow-up drips, reactivation)
- [O] Implement Phase 3 (referral system, paid ads, UGC, second channel)

---

## Summary Statistics

| Category | Complete | Partial | Remaining |
|----------|:--------:|:-------:|:---------:|
| Infrastructure | 15/15 | 0 | 0 |
| Telegram Bot | 16/16 | 0 | 0 |
| Discord Learning Bot | 26/30 | 1 | 3 |
| Discord Challenge Bot | 16/17 | 0 | 1 |
| LinkedIn Engine | 20/21 | 0 | 1 |
| Mobile App | 15/19 | 0 | 4 |
| Web (Landing) | 6/9 | 0 | 3 |
| Web (Next.js) | 11/16 | 0 | 5 |
| n8n Workflows | 9/13 | 0 | 4 |
| Content | 11/14 | 0 | 3 |
| CRM & Data | 7/10 | 0 | 3 |
| Documentation | 30/30 | 0 | 0 |
| CI/CD & Testing | 2/6 | 0 | 4 |
| Security | 5/7 | 0 | 2 |
| **TOTAL** | **189/223** | **1** | **33** |

**Overall Completion: 85%**

---

*Checklist generated from evidence-based review of 261 repository files on June 27, 2026.*
