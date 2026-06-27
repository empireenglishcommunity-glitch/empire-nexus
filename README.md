# Empire English Community

> **Speak like an Emperor.** — An online English-learning community for Arabic speakers.
> Sub-brand of MACAL Empire.

---

## What This Repository Is

This is the **single source of truth** for all Empire English Community assets — strategy, code, infrastructure, content, documentation, and automation. Everything lives here.

---

## Repository Structure

```
empire-english-community/
│
├── bots/                               ← All bot source code
│   ├── discord-learning-bot/           ← Discord L0 learning system (Python/Docker)
│   │   ├── src/                        ← Bot modules (ai_engine, database, tasks)
│   │   ├── content/                    ← L0 curriculum (accent, grammar, speaking, writing, immersion)
│   │   ├── data/                       ← Week 1-8 JSON data files + advancement exam
│   │   ├── scripts/                    ← Server setup automation
│   │   ├── Dockerfile + docker-compose.yml
│   │   └── requirements.txt
│   │
│   ├── discord-challenge-bot/          ← 30-day challenge bot (Python/Docker)
│   │   ├── src/                        ← Bot, AI coach, certificates, challenges, database
│   │   ├── data/                       ← Challenge data, captions, promo content
│   │   ├── tests/                      ← 49 pytest tests
│   │   ├── fonts/                      ← Cairo Arabic font (PDF certificates)
│   │   ├── scripts/                    ← Backup, server setup
│   │   ├── Dockerfile + docker-compose.yml
│   │   └── DEPLOYMENT.md
│   │
│   └── telegram-sales-bot/             ← Telegram sales/funnel bot (Cloudflare Worker)
│       ├── worker.js                   ← Live bot (v13) — single-file deployment
│       └── SETUP.md
│
├── workers/                            ← Cloudflare Workers (serverless)
│   └── linkedin-engine/                ← LinkedIn content automation (v3.0)
│       ├── worker.js                   ← 55 hooks, 25 styles, 15 formats, carousel
│       ├── wrangler.toml               ← Cloudflare Worker config
│       ├── SETUP.md
│       └── _test.mjs                   ← Smoke test
│
├── apps/                               ← Web & mobile applications
│   ├── mobile/                         ← React Native / Expo pronunciation dictionary
│   │   ├── app/                        ← Expo Router screens
│   │   ├── src/                        ← Components, data, services, theme
│   │   ├── package.json
│   │   ├── app.json
│   │   └── tsconfig.json
│   │
│   └── web/                            ← Web applications
│       ├── landing-pages/              ← Static HTML (EN + AR RTL)
│       │   ├── index.html
│       │   └── index-ar.html
│       └── next-app/                   ← Next.js web app (student dashboard)
│           ├── app/
│           ├── components/
│           └── lib/
│
├── infrastructure/                     ← Deployment & server configuration
│   ├── server-hardening/               ← Hetzner VPS security (7 hardening scripts)
│   │   ├── deploy.sh                   ← Master deployment script
│   │   ├── scripts/                    ← Swap, firewall, SSH, fail2ban, Docker, monitoring, backup
│   │   ├── configs/                    ← docker-compose.yml, watchdog.sh
│   │   └── systemd/                    ← Monitor timer + service
│   │
│   ├── n8n-mcp/                        ← MCP server for AI workflow building
│   │   ├── docker-compose.yml
│   │   ├── deploy.sh
│   │   └── deploy_mcp.py
│   │
│   └── n8n-workflows/                  ← n8n workflow JSON exports
│       ├── EMPIRE-BOT-FINAL.json
│       ├── empire-bot-main-v2.json
│       └── IMPORT_INSTRUCTIONS.md
│
├── content/                            ← Content & marketing assets
│   ├── telegram-posts/                 ← 6 weeks of Telegram channel posts
│   │   ├── WEEK_1_POSTS.md → WEEK_6_POSTS.md
│   │   ├── GROUP_SEEDING_WEEK1.md
│   │   └── WORD_OF_THE_DAY_14.md
│   │
│   ├── build-kit/                      ← CRM templates, quiz logic, operational assets
│   │   ├── crm/                        ← Google Sheets CRM templates (CSV)
│   │   ├── quiz-logic.md
│   │   ├── botfather-setup.md
│   │   └── weekly-report.gs
│   │
│   └── brand/                          ← MACAL brand voice & identity
│       └── macal-brand-bible.md
│
├── docs/                               ← All documentation
│   ├── strategy/                       ← Business strategy & roadmaps
│   │   ├── Empire English Community Learning System.md
│   │   ├── STRATEGIC_EXPANSION_ROADMAP.md
│   │   ├── CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md
│   │   ├── MASTER_IMPLEMENTATION_ROADMAP.md
│   │   └── FULL_IMPLEMENTATION_ROADMAP.md
│   │
│   ├── specs/                          ← Phase build specifications
│   │   ├── phase-0/                    ← Bot, quiz, CRM, automations
│   │   ├── phase-1/                    ← Content, discussion group, 3 American Sounds
│   │   ├── learning-system/            ← Discord L0 curriculum plan
│   │   └── ecosystem/                  ← Brand universe, ecosystem architecture
│   │
│   ├── operations/                     ← Server, recovery, audits, operational guides
│   │   ├── SERVER_REFERENCE.md
│   │   ├── EMERGENCY-RECOVERY.md
│   │   ├── SERVER_AUDIT.md
│   │   ├── GUIDE.md
│   │   ├── PROJECT-CONTEXT.md
│   │   └── PROJECTS-CHECKLIST.md
│   │
│   ├── business/                       ← Feasibility studies, pricing, launch
│   │   ├── EEC-Feasibility-Study.md
│   │   ├── EEC-International-Pricing-and-Feasibility.md
│   │   ├── EEC-Launch-Night-Playbook.md
│   │   └── تحدي-30-يوم-المنطقة-غير-المريحة.md
│   │
│   ├── infrastructure/                 ← Technical infrastructure docs
│   │   ├── N8N_WORKFLOW_PATTERNS.md
│   │   ├── QUIZ_SYSTEM_TECHNICAL_AUDIT.md
│   │   └── EEC_SERVER_REFERENCE.md
│   │
│   └── checkpoints/                    ← Session checkpoint history
│       ├── CHECKPOINT_2026-06-19.md
│       ├── CHECKPOINT_2026-06-20.md
│       ├── CHECKPOINT_2026-06-25.md
│       └── CHECKPOINT_2026-06-25-B.md
│
├── .github/workflows/                  ← CI/CD pipelines
│   ├── challenge-bot-test.yml
│   └── linkedin-engine-smoke-test.yml
│
├── .kiro/steering/                     ← AI agent rules & protocols
│   ├── project-rules.md
│   └── sync-protocol.md
│
├── PROJECT_STATUS.md                   ← Current project status & handover
├── .gitignore
└── README.md                           ← This file
```

---

## Live Systems (Deployed)

| System | Platform | Status | Source |
|--------|----------|:------:|--------|
| Telegram Sales Bot | Cloudflare Worker | LIVE (v13) | `bots/telegram-sales-bot/` |
| Discord Learning Bot | Docker on Hetzner | LIVE | `bots/discord-learning-bot/` |
| Discord Challenge Bot | Docker on Hetzner | LIVE | `bots/discord-challenge-bot/` |
| LinkedIn Engine | Cloudflare Worker | LIVE (v3.0) | `workers/linkedin-engine/` |
| n8n Workflows (7) | Docker on Hetzner | RUNNING | `infrastructure/n8n-workflows/` |
| Server Hardening | Hetzner VPS | DEPLOYED | `infrastructure/server-hardening/` |
| MCP Server | Docker on Hetzner | RUNNING | `infrastructure/n8n-mcp/` |

---

## Infrastructure

| Layer | Tool | Status |
|-------|------|:------:|
| **Server** | Hetzner CX23 (Helsinki, 4GB RAM, Ubuntu 26.04) | Running |
| **Automation** | n8n (Docker, pinned v2.26.8) | Running |
| **Routing** | Cloudflare Tunnel → `bot.empireenglish.online` | Running |
| **MCP** | AI workflow builder → `mcp.empireenglish.online` | Running |
| **Monitoring** | Telegram watchdog (60s) + BetterStack (3min) | Active |
| **Security** | Key-only SSH, Fail2Ban, UFW, resource limits | Hardened |
| **Backups** | Daily 3AM, 14-day rotation | Automated |

---

## Project Phases

| Phase | Description | Status |
|:-----:|-------------|:------:|
| 0 | Funnel (Telegram bot, quiz, CRM, automations, booking) | COMPLETE |
| 1 | Content (6 weeks posts, discussion group, report + KPI) | IN PROGRESS |
| L0 | Learning System (Discord, curriculum, bot, 8 weeks) | DEPLOYED |
| 2 | Growth (paid ads, content scaling) | NOT STARTED |
| 3 | Scale (team, multi-level, paid tools) | NOT STARTED |

---

## Quick Start (by component)

### Telegram Sales Bot (live)
```bash
# Already deployed on Cloudflare Workers
# Edit: bots/telegram-sales-bot/worker.js → paste in Cloudflare dashboard → Deploy
```

### LinkedIn Engine (live)
```bash
# Already deployed on Cloudflare Workers
# Edit: workers/linkedin-engine/worker.js → wrangler deploy
```

### Discord Learning Bot (deployed)
```bash
# On Hetzner: /opt/empire-english-bot/
# Update: ssh in → cd /opt/empire-english-bot && git pull && docker compose up -d --build
```

### Discord Challenge Bot (deployed)
```bash
# On Hetzner: /opt/empire-challenge/empire-challenge-bot/
# Update: ssh in → cd /opt/empire-challenge && git pull && docker compose up -d --build
```

### Mobile App (Expo)
```bash
cd apps/mobile
npm install
npx expo start --tunnel
```

---

## For New AI Agents / Developers

Start with these files in order:
1. **This README** — understand the project map
2. **`PROJECT_STATUS.md`** — current state & priorities
3. **`docs/operations/PROJECT-CONTEXT.md`** — full handoff context
4. **`docs/operations/SERVER_REFERENCE.md`** — server architecture
5. **`.kiro/steering/project-rules.md`** — constraints & conventions

---

## Design Principles

- **Zero vendor lock-in** — self-hosted, open-source tools preferred
- **Zero/near-zero cost** — Cloudflare free, Hetzner $7/mo, all APIs on free tiers
- **No AI dependency for critical paths** — keyword banks + fallback pools for 100% uptime
- **Human-in-the-loop** — all sensitive actions require admin approval
- **Single-file deployments** — each Cloudflare Worker is one self-contained `.js` file
- **Arabic-first UX** — all customer-facing copy in Egyptian Arabic dialect

---

## Brand

- **Community:** Empire English Community
- **Parent Brand:** MACAL Empire ("Common Sense First")
- **Visual Identity:** Gold (#D4AF37) on matte black (#0A0A0B)
- **Voice:** Authoritative, sarcastic (scalpel not sledgehammer), paternal/protective
- **Owner:** Mahmoud Ashri (@macal_emperor)
