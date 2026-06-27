# Empire English Community — AI Agent Steering Rules

> This file is automatically loaded by Kiro and any AI agent working on this repository.
> It provides critical context, constraints, and decision rules for all future work.

---

## 0. Session Management Protocol

### `/sync` Command
When the user sends `/sync`, execute the full repository closing protocol:
1. **Session Review** — identify all changes made during the session
2. **Code Verification** — confirm modified code compiles, tests pass, no secrets/debug left
3. **Documentation Sync** — update PROJECT_STATUS.md, docs/checkpoints/ as needed
4. **Repository Cleanup** — remove orphaned files, check .gitignore, verify no untracked files
5. **Commit & Push** — stage all changes, write descriptive commit message, push to branch
6. **Final Report** — deliver summary with files changed, test results, doc updates, next steps

### `/status` Command
When the user sends `/status`, provide current repository state without making changes.

### `/start` Command
At the start of every new session, read this repo's README.md and PROJECT_STATUS.md to restore full context.

---

## 1. Project Identity

- **Project:** Empire English Community (EEC)
- **Parent Brand:** MACAL Empire ("Common Sense First")
- **Owner:** Mahmoud Ashri (@macal_emperor / @macal.empire)
- **Target Audience:** Arabic speakers learning English (Egyptian dialect primary)
- **Repository:** `empireenglishcommunity-glitch/empire-english-community` (consolidated monorepo)

---

## 2. Architecture Principles (MUST follow)

| Principle | Explanation |
|-----------|-------------|
| **Zero vendor lock-in** | Self-hosted, open-source tools preferred. Never recommend SaaS with restrictive limits. |
| **Zero/near-zero cost** | All APIs on free tiers. Server cost: $7/mo max. No paid subscriptions. |
| **No AI dependency for critical paths** | Keyword banks + fallback pools for 100% uptime. AI is optional enhancement. |
| **Human-in-the-loop for money** | All payment/sensitive actions require admin approval before reaching customers. |
| **Single-file deployments** | Cloudflare Workers = one self-contained `.js` file. No build steps. |
| **Arabic-first UX** | All customer-facing copy in Egyptian Arabic dialect. Clean, warm, motivating. |
| **5-year scalability test** | Every decision must pass: "Will this work in 5 years at 10x scale?" |
| **Idempotent operations** | Scripts safe to re-run. Database operations with conflict handling. |

---

## 3. Repository Structure

```
empire-english-community/
├── README.md                    ← Project index (start here)
├── PROJECT_STATUS.md            ← Current status & handover doc
├── .kiro/steering/              ← AI agent rules
├── .github/workflows/           ← CI/CD pipelines
├── docs/                        ← All documentation
│   ├── strategy/                ← Business strategy & roadmaps
│   ├── specs/                   ← Phase build specifications
│   ├── operations/              ← Server, recovery, audits, guides
│   ├── business/                ← Feasibility studies, pricing, launch
│   ├── infrastructure/          ← n8n patterns, quiz audit, server ref
│   └── checkpoints/             ← Session checkpoint files
├── bots/                        ← Bot source code
│   ├── discord-learning-bot/    ← Discord L0 learning system (Python/Docker)
│   ├── discord-challenge-bot/   ← 30-day challenge bot (Python/Docker)
│   └── telegram-sales-bot/      ← Telegram sales bot (Cloudflare Worker)
├── workers/                     ← Cloudflare Workers
│   └── linkedin-engine/         ← LinkedIn content automation
├── apps/                        ← Web & mobile applications
│   ├── mobile/                  ← React Native / Expo pronunciation app
│   └── web/                     ← Web apps (Next.js + static landing pages)
├── infrastructure/              ← Deployment & server configs
│   ├── server-hardening/        ← Security scripts for Hetzner VPS
│   ├── n8n-mcp/                 ← MCP server deployment
│   └── n8n-workflows/           ← n8n workflow JSON exports
└── content/                     ← Content & marketing assets
    ├── telegram-posts/          ← 6 weeks of Telegram channel posts
    ├── build-kit/               ← CRM templates, quiz logic, build assets
    └── brand/                   ← MACAL brand bible & voice guide
```

---

## 4. Server Infrastructure (DO NOT break)

| Item | Details |
|------|---------|
| **Server** | Hetzner CX23, Helsinki, `77.42.43.250`, Ubuntu 26.04 |
| **SSH** | Key-only (`C:\Users\97150\.ssh\id_ed25519`). Password auth DISABLED. |
| **n8n** | Docker at `/opt/n8n/`, pinned v2.26.8, bound to `127.0.0.1:5678` |
| **Tunnel** | Cloudflare Named Tunnel → `bot.empireenglish.online` |
| **Discord Learning Bot** | Docker at `/opt/empire-english-bot/` |
| **Challenge Bot** | Docker at `/opt/empire-challenge/empire-challenge-bot/` |
| **Monitoring** | Telegram watchdog (60s) + BetterStack (3min) |
| **Backup** | Daily 3 AM, 14-day rotation |

**CRITICAL RULES:**
- Never expose port 5678 to public (binding to 127.0.0.1 IS the enforcement)
- Never modify SSH config without testing from a second terminal first
- Never run destructive git commands on the VPS without explicit user permission
- Always verify existing services still work after any change

---

## 5. n8n Workflow Rules (Critical)

- Switch node expressions DO NOT reliably evaluate nested JSON paths — use Code Node router first
- After Google Sheets nodes: use explicit `$('NodeName').first().json...` references
- Google Sheets credential type is `googleApi` (Service Account), NOT `googleSheetsOAuth2Api`
- Sheets credential ID: `k6ND5geKqsYEj25I`, name: "Empire CRM"
- Sheet GID for subscribers: `421473979`, events: `1549846062`
- Document ID: `13fJFzyeTMYHFKj2YDEy620fHfznbFvhTieqD8N1KUCg`
- Use `mode: "list"` with numeric GID value for sheetName (not text name)

---

## 6. Code Conventions

### Telegram/LinkedIn Workers (JavaScript)
- Single self-contained file (`worker.js`)
- All secrets via Cloudflare environment variables
- Always return HTTP 200 to Telegram (prevents webhook retry storms)
- Version constant at top of file — bump on every change

### Discord Bots (Python)
- Modular: `src/` package with separate modules per concern
- Config via `.env` (python-dotenv) — never commit `.env`
- Tests: `pytest` in `tests/` — must pass before deployment
- Docker: `docker compose up -d --build` to deploy changes

### General
- Commit messages: `type(scope): description`
- Branch naming: `component/description`
- Always push to a branch, never directly to main (create PR)
- Arabic text: use Egyptian dialect, warm tone, consistent emojis

---

## 7. What NOT to Do

- Do NOT add paid dependencies or services without explicit permission
- Do NOT auto-publish content to LinkedIn/TikTok (human-in-the-loop always)
- Do NOT store real credentials in code (always `.env` or Cloudflare secrets)
- Do NOT modify bots without bumping version and testing
- Do NOT remove the payment approval gate from any system
- Do NOT assume Make.com/Zapier as solutions (user migrated away deliberately)
- Do NOT suggest tools with operation limits, credit caps, or usage-based pricing
- Do NOT break existing running services when deploying new ones

---

## 8. File Delivery to User's PC

The user's PC is Windows 11. Copy-paste from browser to Notepad corrupts quotes/newlines.
- Prefer pushing to GitHub → user does `git pull`
- For server commands: user SSHs in, pastes commands directly in Linux terminal
- Never use Windows CMD heredocs (EOF) — they don't work

---

## 9. Contact & Accounts

| Service | Account |
|---------|---------|
| GitHub | `empireenglishcommunity-glitch` |
| Telegram (admin) | `@macal_emperor` |
| TikTok | `@macal.empire` |
| Domain | `empireenglish.online` (Namecheap → Cloudflare NS) |
| Cloudflare | Free plan |
| Hetzner | Project "Empire English" |
| n8n | `https://bot.empireenglish.online` (owner: macalempire@gmail.com) |
| Discord (Learning) | Empire English Community \|EEC (ID: 1519797013565280446) |
| Discord (Challenge) | Empire English — تحدّي 30 يوم (ID: 1518615304035373106) |
