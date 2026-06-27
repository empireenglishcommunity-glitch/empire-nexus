# Empire English Community — Complete Repository Audit

**Audit Date:** June 27, 2026
**Scope:** Every file, directory, and component in the consolidated repository
**Total Files:** 261 | **Total Lines of Code/Content:** ~55,000+

---

## Executive Summary

This repository is **remarkably comprehensive** for a solo-operator project. It contains 4 deployed production systems, 2 undeployed apps, complete infrastructure automation, 6 weeks of marketing content, and 14,700+ lines of strategy/specification documentation.

**Overall Assessment: 8/10 — Production-quality architecture with documentation debt and a few security gaps.**

The core systems (Telegram bot, Discord bots, LinkedIn engine, server infrastructure) are **well-built, deployed, and running**. The main weaknesses are: outdated documentation referencing the old repo structure, one critical security issue (exposed API key), missing tests for 3 of 5 components, and some obsolete historical files that add noise.

---

## Repository Architecture Map

```
empire-english-community/           ← 261 files, single source of truth
│
├── bots/                           ← 3 bots (2 deployed, 1 deployed)
│   ├── telegram-sales-bot/         ← LIVE. Cloudflare Worker, v13, 355 lines JS
│   ├── discord-learning-bot/       ← LIVE. Python/Docker, 2,329 lines, 60+ JSON data files
│   └── discord-challenge-bot/      ← LIVE. Python/Docker, 943 lines, 49 tests passing
│
├── workers/                        ← Cloudflare Workers
│   └── linkedin-engine/            ← LIVE. v3.0, 1,037 lines JS, 17 test assertions
│
├── apps/                           ← Web & mobile (NOT deployed)
│   ├── mobile/                     ← Expo 56, TypeScript, pronunciation dictionary
│   └── web/                        ← Static landing pages + Next.js dashboard skeleton
│
├── infrastructure/                 ← Server configs & automation
│   ├── server-hardening/           ← DEPLOYED. 7 scripts, monitoring, backups
│   ├── n8n-mcp/                    ← DEPLOYED. AI workflow builder
│   └── n8n-workflows/              ← Reference. 3 workflow JSONs + docs
│
├── content/                        ← Marketing & operational content
│   ├── telegram-posts/             ← 6 weeks ready (36 posts + 14 WotD)
│   ├── build-kit/                  ← Phase 0 assembly kit (historical)
│   └── brand/                      ← MACAL brand bible (86 lines)
│
├── docs/                           ← 35 files, 14,713 lines
│   ├── strategy/                   ← Product + business strategy (2,903 lines)
│   ├── specs/                      ← Phase build specifications (4,223 lines)
│   ├── operations/                 ← Server, recovery, audits (3,689 lines)
│   ├── business/                   ← Feasibility, pricing, launch (1,448 lines)
│   ├── infrastructure/             ← n8n patterns, quiz audit (1,337 lines)
│   └── checkpoints/                ← Session history (518 lines)
│
├── .github/workflows/              ← 2 CI pipelines (both passing)
├── .kiro/steering/                 ← AI agent rules (251 lines)
├── README.md                       ← Project index (254 lines)
├── PROJECT_STATUS.md               ← Handover document (381 lines, OUTDATED)
└── .gitignore                      ← Comprehensive (52 lines)
```

---

## Component Status Summary

| Component | Lines | Tests | CI | Status | Health |
|-----------|:-----:|:-----:|:--:|--------|:------:|
| Telegram Sales Bot | 355 | 0 | No | LIVE (v13) | Good |
| Discord Learning Bot | 2,329 | 0 | No | LIVE (v1.0) | Good |
| Discord Challenge Bot | 943 | 49 | Yes | LIVE (v1.0) | Excellent |
| LinkedIn Engine | 1,037 | 17 | Yes | LIVE (v3.0) | Excellent |
| Mobile App | ~1,500 | 0 | No | NOT DEPLOYED | Needs work |
| Landing Pages | 884 | — | — | NOT DEPLOYED | Ready |
| Next.js Web App | ~800 | 0 | No | NOT DEPLOYED | Broken |
| Server Hardening | 514 | — | — | DEPLOYED | Excellent |
| n8n-MCP Server | — | — | — | DEPLOYED | Has security issue |
| n8n Workflows (7) | — | — | — | RUNNING | Good |

---

## Critical Issues (Fix Immediately)

### 1. SECURITY: Exposed n8n API Key in Repository

**Location:** `infrastructure/n8n-mcp/docker-compose.yml` (line ~23) and `infrastructure/n8n-mcp/deploy_mcp.py` (line ~12)

**Impact:** A real JWT API key for the n8n instance is committed in plaintext. Anyone with repo access can control your n8n workflows.

**Fix:** Move the key to a `.env` file (already gitignored), replace with `${N8N_API_KEY}` environment variable reference in docker-compose.yml. Consider rotating the key after fixing.

### 2. Next.js Web App: Static Export Conflicts with API Route

**Location:** `apps/web/next-app/next.config.js` has `output: 'export'` but `app/api/feedback/route.js` exists.

**Impact:** The app cannot build. API routes are incompatible with static export in Next.js.

**Fix:** Either remove the API route (move feedback logic client-side) or remove `output: 'export'` and deploy as a server.

### 3. PROJECT_STATUS.md Severely Outdated

**Location:** Root `PROJECT_STATUS.md`

**Impact:** The handover document says "migration is 40% complete" and references Make.com as active — both wrong since June 25. Anyone reading this as a handover document will get incorrect context.

**Fix:** Rewrite to reflect current state (Phase 0 complete, all 7 n8n workflows running, Make.com fully abandoned).

---

## High-Priority Issues (Fix Soon)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | Discord Learning Bot has ZERO tests | `bots/discord-learning-bot/tests/` | No regression protection for the most complex bot |
| 5 | Telegram Sales Bot SETUP.md references v8, code is v13 | `bots/telegram-sales-bot/SETUP.md` | Confusing for anyone deploying/maintaining |
| 6 | Duplicate SERVER_REFERENCE docs | `docs/operations/` vs `docs/infrastructure/` | Confusion about which is canonical |
| 7 | LinkedIn Engine package.json says v2.0, code is v3.0 | `workers/linkedin-engine/package.json` | Version confusion |
| 8 | Mobile app dependencies not in package.json | `apps/mobile/package.json` | `npm install` fails without running `setup` script |
| 9 | Multiple docs reference old "Claude" repo paths | Various docs, DEPLOYMENT.md files | Broken links, incorrect instructions |
| 10 | Learning bot !exam command referenced but not implemented | `bots/discord-learning-bot/src/bot.py` | User sees "type !exam" but command doesn't exist |

---

## Medium-Priority Issues (Technical Debt)

| # | Issue | Location | Notes |
|---|-------|----------|-------|
| 11 | No CI for Discord Learning Bot | `.github/workflows/` | Highest-risk component with no safety net |
| 12 | Landing page countdown targets past date | `apps/web/landing-pages/index.html` | Shows negative countdown |
| 13 | Pricing inconsistency (EGP vs AED vs USD) | Telegram bot vs Next.js app vs landing pages | Different currencies on different surfaces |
| 14 | make-scenarios.md is obsolete | `content/build-kit/` | Make.com fully abandoned, file adds confusion |
| 15 | Next.js components are 1-line minified | `apps/web/next-app/components/` | Unmaintainable; should be formatted |
| 16 | Google Sheets CRM config exists but not implemented in learning bot | `bots/discord-learning-bot/src/config.py` | Config references Sheets but no API calls in code |
| 17 | Learning bot data/README.md outdated | `bots/discord-learning-bot/data/README.md` | Says weeks 3-8 "to be created" but they all exist |
| 18 | L0 Week 7 vocabulary has 55 words (should be 56) | `bots/discord-learning-bot/data/l0_week7.json` | Off-by-one |
| 19 | LinkedIn Engine carousel.gs is dead code | `workers/linkedin-engine/carousel.gs` | v3.0 has self-contained carousel |

---

## Low-Priority Issues (Cleanup When Convenient)

| # | Issue | Notes |
|---|-------|-------|
| 20 | No README.md in discord-learning-bot, mobile app, next-app | Missing entry-point documentation |
| 21 | n8n-mcp/fix_quiz.py is a one-time script, not infrastructure | Should be in scripts/ or removed |
| 22 | deploy_mcp.py has Windows-specific paths | Not portable |
| 23 | Mobile app uses unofficial Google Translate endpoint | May break without notice |
| 24 | tsconfig paths configured but unused in mobile app | Dead configuration |
| 25 | empire-bot-main-v2.json alongside EMPIRE-BOT-FINAL.json | Unclear which is canonical |
| 26 | Docker restart policy inconsistency (always vs unless-stopped) | Minor standardization |
| 27 | Telegram bot header says v11, VERSION const says v13 | Comment drift |
| 28 | docs/operations/GUIDE.md overlaps with component SETUP.md files | Could be removed |
| 29 | No docs/README.md explaining documentation reading order | Readers must guess structure |
| 30 | Checkpoint files lack consistent template | Minor documentation hygiene |

---

## What's Complete and Working

| System | Deployed | Verified |
|--------|:--------:|:--------:|
| Telegram Sales Bot (funnel + quiz + CRM + payment gate) | Yes | Yes |
| 7 n8n workflows (bot, report, quiz nudge, call nudge, booking sync, backup, lead scoring) | Yes | Yes |
| Discord Learning Bot (L0 curriculum, 8 weeks, streaks, tasks, AI feedback) | Yes | Yes |
| Discord Challenge Bot (30-day program, certificates, leaderboard) | Yes | Yes |
| LinkedIn Engine v3.0 (daily posts, image gen, carousel, approval cockpit) | Yes | Yes |
| Server hardening (swap, firewall, SSH, fail2ban, Docker limits, monitoring, backups) | Yes | Yes |
| MCP Server (AI workflow building) | Yes | Yes |
| Cloudflare Tunnel routing | Yes | Yes |
| 6 weeks Telegram content (36 posts + 14 WotD + group seeding) | Written | Ready to schedule |
| L0 curriculum (8 weeks × 56 vocab × 7 speaking × 7 writing) | Written | In bot data/ |
| 25 AI prompts for content factory | Written | In bot content/prompts/ |
| Placement system (4 assessment modules + scoring algorithm) | Designed | In bot content/placement/ |

---

## What's Partially Implemented

| Item | What Exists | What's Missing |
|------|-------------|----------------|
| Mobile pronunciation app | Phase 1 complete (29 words, TTS, search) | Not published, no build config, deps incomplete |
| Next.js web app | Marketing pages + dashboard skeleton | Auth not working, API route broken, not deployed |
| Static landing pages | Complete EN + AR, deployment guide | Not deployed to any host, missing og-image |
| Google Sheets CRM integration in learning bot | Config references exist | No actual API calls implemented |
| !exam advancement command | Referenced in bot output | Not coded in bot.py |
| Discussion group automation | Setup docs exist | n8n workflow for auto-moderation not built |

---

## What's Planned but Not Started

| Item | Spec Location | Priority |
|------|---------------|:--------:|
| Phase 2 (Growth: paid ads, content scaling) | docs/strategy/MASTER_IMPLEMENTATION_ROADMAP.md | Low (after pilot) |
| Phase 3 (Scale: team, multi-level, paid tools) | docs/strategy/MASTER_IMPLEMENTATION_ROADMAP.md | Low |
| L1/L2/L3 curriculum content | Config defined in learning bot | After L0 validated |
| Payment integration (Stripe/Supabase) | Next.js app has Pricing component | Not started |
| Mobile app store publishing | No eas.json or build config | After pilot |
| KPI_Weekly + Stories tabs in CRM | Mentioned in next priorities | Not created |
| Cal.com webhook URL configuration | Documented in master index | Needs dashboard action |

---

## Repository Statistics

| Metric | Count |
|--------|:-----:|
| Total files | 261 |
| Source code files (JS/TS/Python) | ~45 |
| Documentation files (MD) | ~60 |
| JSON data/content files | ~80 |
| Configuration files | ~25 |
| Shell scripts | ~10 |
| CSV/HTML/other | ~40 |
| Lines of production code | ~5,500 |
| Lines of test code | ~370 |
| Lines of documentation | ~19,000 |
| Lines of content/data | ~30,000 |
| CI workflows | 2 (both passing) |
| Test assertions | 66 total (49 + 17) |

---

## Recommendations (Priority Order)

### Immediate (This Session or Next)

1. **Remove the exposed API key** from n8n-mcp docker-compose.yml and deploy_mcp.py. Replace with environment variable. Rotate the key on the server.
2. **Update PROJECT_STATUS.md** to reflect current state (Phase 0 complete, n8n migration done, Make.com abandoned).
3. **Fix old repo path references** in DEPLOYMENT.md files and docs that still say "Claude/..."

### Short-Term (Next 1-3 Sessions)

4. **Write tests for Discord Learning Bot** — at minimum: database operations, task generation, config validation. Model after the challenge bot's test structure.
5. **Update Telegram bot SETUP.md** to reflect v13 features and correct all version references.
6. **Remove duplicate** `docs/infrastructure/EEC_SERVER_REFERENCE.md` (keep operations/ version).
7. **Fix Next.js app**: either remove API route or change deployment strategy. Fix missing dependencies.
8. **Deploy landing pages** to Cloudflare Pages (5-minute task per DEPLOYMENT.md).

### Medium-Term (When Building Next Feature)

9. **Add mobile app dependencies** to package.json properly (not just via setup script).
10. **Implement !exam command** in learning bot or remove the reference from !level output.
11. **Format minified Next.js components** for maintainability.
12. **Consolidate pricing** across all surfaces (decide on one currency strategy).
13. **Add CI workflow for learning bot** once tests exist.

### Ongoing (Maintenance)

14. Mark historical files clearly (add "HISTORICAL" prefix or move to an archive/ folder): `make-scenarios.md`, `N8N_MIGRATION_PLAN.md`, `PATCH-001-fixes.md`, `carousel.gs`
15. Keep checkpoints consistent with a template.
16. Export remaining 4 n8n workflows as JSON backups.

---

## Architecture Quality Assessment

| Dimension | Score | Notes |
|-----------|:-----:|-------|
| **Code Organization** | 9/10 | Clean separation of concerns, clear folder structure |
| **Code Quality** | 8/10 | Well-documented, modular, follows conventions |
| **Testing** | 5/10 | Only 2 of 5 components tested (challenge bot excellent, others zero) |
| **Documentation** | 7/10 | Extensive but has duplicates, outdated refs, no reading-order guide |
| **Security** | 7/10 | Good practices overall, one critical exposed key |
| **Scalability** | 9/10 | SQLite → Postgres path clear, Docker isolation, self-hosted |
| **Maintainability** | 7/10 | Good for deployed systems, apps need cleanup |
| **Infrastructure** | 9/10 | Hardened, monitored, backed up, auto-recovering |
| **Deployment** | 8/10 | 4 systems auto-deploy, 2 apps not yet deployed |
| **Reliability** | 9/10 | Triple fallback on AI, watchdog monitoring, graceful degradation |

**Overall Repository Health: 7.8/10**

---

## For New AI Agents / Developers: Read Order

1. **This file** (REPOSITORY_AUDIT.md) — understand everything at a glance
2. **README.md** — project structure and quick start
3. **docs/strategy/Empire English Community Learning System.md** — the product vision
4. **.kiro/steering/project-rules.md** — constraints and conventions
5. **docs/operations/SERVER_REFERENCE.md** — if doing infrastructure work
6. **docs/infrastructure/N8N_WORKFLOW_PATTERNS.md** — if touching n8n workflows

---

*Audit performed by Kiro AI Agent on June 27, 2026. Every file in the repository was read and analyzed.*
