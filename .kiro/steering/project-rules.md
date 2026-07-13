# Empire English Community — AI Agent Steering Rules

> This file is automatically loaded by Kiro and any AI agent working on this repository.
> It provides critical context, constraints, and decision rules for all future work.

---

## 0. Session Management Protocol

> **⚠️ CORRECTED 2026-07-12:** the real, current source of truth for
> project state is `empireenglishcommunity-glitch/empire-chronicle`'s
> `SESSION_CONTINUITY.md` and `README.md` — NOT this repo's own
> `PROJECT_STATUS.md`, which predates that convention and has been stale
> since. `PROJECT_STATUS.md` is kept only as historical record; do not
> treat it as current without cross-checking empire-chronicle first.
>
> **This repo's own `.kiro/steering/sync-protocol.md` is now superseded**
> by the canonical version below — it had already drifted slightly out
> of sync with `Claude`'s copy of the same rules before this
> consolidation. Do not follow `sync-protocol.md`'s letter if it
> conflicts with `AI-AGENT-PROTOCOL.md`.

### Session Commands (`/start`, `/status`, `/sync`, `/sync dry`, `/checkpoint`)

The full protocol for all session commands is defined **once**, canonically,
in `empireenglishcommunity-glitch/empire-chronicle/.kiro/steering/AI-AGENT-PROTOCOL.md`.
Read that file — do not follow this repo's own `sync-protocol.md`, which
is kept only as historical record of the pre-consolidation rules.

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
| **Discord Learning Bot** | Docker at `/opt/empire-english-bot/` (symlink → `/opt/empire-english-bot-new/bots/discord-learning-bot`, a real git checkout) |
| **Challenge Bot** | Docker at `/opt/empire-challenge/empire-challenge-bot/` |
| **Monitoring** | Telegram watchdog (60s) + BetterStack (3min) |
| **Backup** | n8n/EMOS: daily 3 AM. discord-challenge-bot: daily 3 AM. **discord-learning-bot: daily 3:10 AM** (`docker exec empire-english-bot python3 scripts/backup.py`, added 2026-07-13 — was a real gap for a long time, see `.kiro/specs/production-safe-deploys/tasks.md` Phase 0). All 14-day rotation. |

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

### Feature flags (discord-learning-bot — Aegis Phase 1)
Any new risky or student-facing behavior added to `discord-learning-bot`
should be wrapped behind a feature flag rather than going live the
moment it's deployed. This decouples **deploy** (code reaches the
server, dormant) from **release** (a real student actually sees the new
behavior) — see `.kiro/specs/production-safe-deploys/design.md` for the
full rationale. The convention, consistently:

```python
if database.is_feature_enabled("<flag_name>", str(ctx.author.id)):
    ... new behavior ...
else:
    ... old behavior, or a no-op ...
```

- Admin-managed via `!flag list` / `!flag enable <name>` /
  `!flag disable <name>` (the kill switch — instant, no redeploy, no
  bot downtime) / `!flag beta <name> @user1 @user2` (test on yourself
  or a trusted few before a full release).
- Flags default to **disabled** if never explicitly set — fail closed,
  never fail open.
- If a flag-gated command is silently a no-op when its flag is off
  (see `!systemstatus` for the pattern), do NOT list it in `!help`
  until the flag has actually been turned on for everyone — advertising
  a dormant command creates the exact "looks broken to a curious
  student" problem this mechanism exists to prevent. Add the `!help`
  entry in the same session/commit that flips the flag on.
- Do not invent a second, different flagging pattern for a new
  feature — reuse `database.is_feature_enabled()`/`set_feature_flag()`
  every time, so `!flag list` stays the single place to see everything
  that's dormant or in beta.
- **Flag registry (`src/flag_registry.py`) MUST be updated in the SAME
  commit that creates or enables a new flag.** Never as a separate PR
  or afterthought. The registry is the source of truth for what flags
  exist, what they do, and which initiative they belong to. When adding
  a flag: add the REGISTRY entry with its name, description, initiative,
  and default_enabled state in the same commit. When enabling a flag
  that was previously default_enabled=False (e.g. after testing): update
  the registry's default to True in the same commit. This ensures
  `!flag list` always shows accurate descriptions and `default_enabled`
  always reflects the intended production state.

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
