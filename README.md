# Empire English Community — `empire-nexus`

> **Speak like an Emperor.** — An online English-learning community for Arabic
> speakers. Sub-brand of MACAL Empire.

The canonical monorepo. The **Discord Learning Bot** lives at
`bots/discord-learning-bot/` and is the heart of the product.

> **Rewritten 2026-08-29.** The previous version of this file described a
> repository that no longer exists — it drew `apps/mobile`, `apps/web`,
> `workers/linkedin-engine`, `bots/telegram-sales-bot` and `infrastructure/` in
> its structure tree, listed them as LIVE, and gave Quick Start commands for them.
> **None of those directories are in this repo.** Some moved out in the 2026-07-12
> restructure (`infrastructure/` → `empire-server-forge`); others predate it. It
> also described the curriculum as "L0", which was retired in favour of CEFR
> A1–C2 in 2026-08. See
> [`empire-chronicle`'s 2026-08-29 ecosystem audit](https://github.com/empireenglishcommunity-glitch/empire-chronicle/blob/main/audits/2026-08-29-ECOSYSTEM-AUDIT.md)
> (private repo).

---

## Where current state actually lives

**Not in this repo.** Cross-project state lives in the private
`empireenglishcommunity-glitch/empire-chronicle`:

| Read | For |
|---|---|
| `empire-chronicle/STATUS.md` | **Start here.** What is live, what is open, what is decided. |
| `empire-chronicle/SYSTEM-MAP.md` | What exists in the bot + practice site and why. Every count re-derived from code. |
| `empire-chronicle/audits/2026-08-29-ECOSYSTEM-AUDIT.md` | What is *verified* vs merely claimed. |
| `.kiro/steering/project-rules.md` (here) | Constraints and conventions for this repo. |
| `.kiro/specs/*/` (here) | Per-initiative requirements / design / tasks. |

> ⚠️ **`PROJECT_STATUS.md` and `REPOSITORY_AUDIT.md` in this repo are STALE
> historical records** (dated 2026-07-11 and 2026-06-27). `PROJECT_STATUS.md` even
> tells you to treat itself as current — it is not; it predates the entire CEFR
> restructure. Kept for history only.
>
> ⚠️ **`.kiro/specs/*/tasks.md` checkboxes are not a reliable progress signal.**
> The 2026-08-29 audit found two specs reading 0% complete while live in
> production, and one open box describing work that had already shipped. Each
> affected spec now carries a **status header** stating the verified reality —
> read that header before trusting any box beneath it.

---

## Repository Structure (verified 2026-08-29 — 942 tracked files)

```
empire-nexus/
│
├── bots/
│   ├── discord-learning-bot/     ← THE PRODUCT. Python/Docker. Auto-deploys on
│   │   │                            merge to main.
│   │   ├── src/                  ← 35 modules, ~29,600 lines. bot.py is the hub;
│   │   │                            database.py owns all SQLite (39 tables);
│   │   │                            api_server.py is the API the practice site calls.
│   │   ├── content/              ← CEFR curriculum: a1/ a2/ b1/ b2/ c1/ c2/ each with
│   │   │                            accent/ grammar/ reading/ mediation/ broadcast/,
│   │   │                            plus cefr/ (can-do descriptors, per-level
│   │   │                            ALIGNMENT.md + owner sign-off), placement/,
│   │   │                            patterns/, governance/, milestones/
│   │   ├── data/                 ← 90 weekly files {level}_week{n}.json (+1 index)
│   │   ├── tests/                ← 89 files, ~16,800 lines → 2,044 passing / 2 skipped
│   │   ├── scripts/              ← ops + migration tooling (setup_server.py,
│   │   │                            cefr_migrate_server.py, deploy.py, rollback.py,
│   │   │                            health_check.py, backup.py, bidi_check.py, …)
│   │   └── Dockerfile · docker-compose.yml · requirements*.txt · run.py
│   │
│   └── discord-challenge-bot/    ← Separate 30-day challenge bot. Also deployed,
│                                    but its own project — out of scope for the
│                                    learning-bot system map.
│
├── services/
│   └── nutq-scorer/              ← Free self-hosted pronunciation scorer (Nutq's
│                                    fallback engine). Own container + tests.
│                                    ⚠️ relative build context — see deploy note below.
│
├── .kiro/
│   ├── steering/                 ← AI agent rules for this repo
│   └── specs/                    ← 24 initiative specs (requirements/design/tasks)
│
├── .github/workflows/            ← learning-bot-test.yml · deploy-learning-bot.yml
│                                    · challenge-bot-test.yml
│
├── content/                      ← Marketing/brand assets: brand/ build-kit/
│                                    telegram-posts/
├── docs/                         ← business/ checkpoints/ infrastructure/
│                                    operations/ specs/ strategy/ — largely
│                                    HISTORICAL; several files still say L0–L3
└── scripts/fix_quiz.py           ← one-off
```

**The practice website is a separate repo:** `empire-dojo` (Cloudflare Pages, live
at practice.empireenglish.online). It generates its pages *from* this repo's
`content/` and `data/`.

---

## The product, in one paragraph

Students do 7 daily tasks. Five of them (accent, vocabulary, shadowing, listening,
speaking) happen on the **practice site**, which calls this bot's `/api/*`
endpoints; two (writing, community) happen in **Discord**. The bot records
progress in SQLite, posts recordings to `#showcase`, runs ~30 scheduled jobs
(daily task posts, reminders, weekly reports) and answers commands (`!done`,
`!progress`, `!today`, …). Levels are the **six CEFR levels A1–C2** across **90
curriculum weeks**. Student-facing wording is always **"CEFR-aligned, not
certified."**

---

## Deploying

**The learning bot auto-deploys.** Merging to `main` triggers
`.github/workflows/deploy-learning-bot.yml`, which SSHes to the server with a
pinned host key, pulls, rebuilds the container, and **fails the build if the
container is unhealthy or the curriculum does not load**. No manual SSH, and no
key to re-add after a sandbox reset.

⚠️ **If you ever deploy by hand, rebuild by service name:**

```bash
cd /opt/empire-english-bot && git pull --ff-only
docker compose up -d --build empire-english-bot   # NOT a bare --build
```

A bare `docker compose up -d --build` fails with
`path "/services/nutq-scorer" not found`, because `nutq-scorer`'s build context is
relative and does not resolve in the server's flattened sparse checkout. It is
non-destructive — the running containers are untouched — but the deploy silently
does not happen.

⚠️ **`empire-dojo` does NOT auto-deploy.** Merging is not deploying there; it
needs an explicit `wrangler pages deploy`. And when the bot and the page change
together, **deploy the page first** — the page renders both payload shapes, the
bot does not guess which page is live.

---

## Running the tests

```bash
cd bots/discord-learning-bot
python3.12 -m pip install -r requirements.txt -r requirements-dev.txt
python3.12 -m pytest -q            # 2,044 passed, 2 skipped
python3.12 -m src.coverage_ledger  # exit 0; content-coverage hard gate
```

**Use `python3.12`.** Under 3.9 collection fails with ~50 `X | Y` union-type
errors. CI uses 3.12 and runs both commands above.

---

## Design Principles

- **Zero vendor lock-in** — self-hosted, open-source tools preferred
- **Zero/near-zero cost** — Hetzner ~$7/mo, all APIs on free tiers
- **No AI dependency for critical paths** — keyword banks + fallback pools, so
  uptime never depends on a model being available
- **Human-in-the-loop** — all sensitive actions require admin approval
- **Arabic-first UX** — customer-facing copy in Egyptian Arabic dialect
- **Every risky feature behind a flag** — deploy and release are separate. Flags
  are declared in `src/flag_registry.py` (51 flags, 15 initiatives) and fail
  **closed** when unset. Register a flag in the same commit that creates it.

---

## Brand

- **Community:** Empire English Community
- **Parent Brand:** MACAL Empire ("Common Sense First")
- **Visual Identity:** Gold (#D4AF37) on matte black (#0A0A0B)
- **Voice:** Authoritative, sarcastic (scalpel not sledgehammer), paternal/protective
- **Owner:** Mahmoud Ashri (@macal_emperor)
