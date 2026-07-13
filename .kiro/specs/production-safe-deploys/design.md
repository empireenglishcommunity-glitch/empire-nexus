# Design — Aegis: Production-Safe Deploys

## Guiding idea

Separate three things that are currently one and the same action
("edit code, push, `docker compose up -d --build`, hope"):

| Today (fused) | Aegis (separated) |
|---|---|
| Write code → it's live | Write code → **merge** → **deploy** (dormant) → **release** (visible) |
| Test = read the code carefully | Test = run it for real against realistic data, automatically, before a human even reviews it |
| Rollback = re-edit and redeploy | Rollback = point at the previous image tag + restore a snapshot, in one command |
| "Did it break?" = wait for a student to say so | "Did it break?" = an automated check tells you within minutes |

Every mechanism below exists to make one of those arrows cheap and fast,
using only what's already available (SQLite, Docker, GitHub Actions free
tier, Cloudflare Pages preview deploys, the bot's own Discord API access)
— no new paid service, no new account, nothing that needs to be
remembered by hand every time.

## Architecture overview

```
                     ┌─────────────────────────────────────────┐
                     │   GitHub PR opened (bot or empire-dojo)  │
                     └───────────────────┬───────────────────────┘
                                         │
                     ┌───────────────────▼───────────────────────┐
                     │  CI: pytest + "student journey" simulation │
                     │  (bot)  OR  regenerate + html.parser sweep │
                     │  (empire-dojo)                              │
                     └───────────────────┬───────────────────────┘
                                         │ green
                     ┌───────────────────▼───────────────────────┐
                     │  Merge to main                             │
                     │   - empire-dojo: Cloudflare Pages auto-    │
                     │     deploys (existing, atomic swap)         │
                     │   - bot: code sits in git, NOT yet running  │
                     │     on the server (deploy is a deliberate   │
                     │     separate step, see below)               │
                     └───────────────────┬───────────────────────┘
                                         │
                     ┌───────────────────▼───────────────────────┐
                     │  DEPLOY (operator or agent, on request):   │
                     │   1. pre-deploy DB snapshot (automatic)    │
                     │   2. build new image, TAG with git SHA     │
                     │   3. swap container to new tagged image    │
                     │   4. post-deploy health probe (automated)  │
                     │   5. set bot presence back to normal        │
                     └───────────────────┬───────────────────────┘
                                         │ new code now running,
                                         │ but new BEHAVIOR still off
                     ┌───────────────────▼───────────────────────┐
                     │  RELEASE (separate decision, any time      │
                     │  after deploy, zero downtime):             │
                     │   !flag enable <feature> [--for @user]     │
                     │   - test on yourself first                 │
                     │   - then a trusted few                     │
                     │   - then everyone + !announce               │
                     └─────────────────────────────────────────────┘
```

## Component 1 — Feature flags + kill switch (bot)

**Why this is the highest-leverage single piece:** it's the only
mechanism here that turns "I shipped a bug to everyone" into "I shipped
a bug to nobody, instantly, with zero redeploy." Every other component
reduces the *chance* of a bad deploy; this one caps the *blast radius*
of one that gets through anyway.

**Design:**
- New table in `database.py`:
  ```sql
  CREATE TABLE IF NOT EXISTS feature_flags (
      name            TEXT PRIMARY KEY,
      enabled         INTEGER NOT NULL DEFAULT 0,
      allowed_ids     TEXT DEFAULT '',   -- comma-separated discord_ids, empty = "everyone once enabled"
      updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
      updated_by      TEXT DEFAULT ''
  );
  ```
- New `database.py` functions: `is_feature_enabled(name, discord_id) -> bool`
  (checks `enabled` first; if `enabled=1` and `allowed_ids` is non-empty,
  further restricts to that allowlist — so "on for everyone" and "on for
  a beta squad" are the same mechanism, just an empty vs. populated list),
  `set_feature_flag(name, enabled, allowed_ids, updated_by)`,
  `list_feature_flags()`.
- New admin command `!flag` (subcommands: `!flag list`, `!flag enable
  <name>`, `!flag disable <name>`, `!flag beta <name> @user1 @user2`).
  Reuses the existing `manage_guild` permission check pattern already
  used by `!announce`/`!setlevel`/etc.
- **Usage pattern in code:** any new risky behavior gets wrapped:
  ```python
  if database.is_feature_enabled("new_thing", str(ctx.author.id)):
      ... new behavior ...
  else:
      ... old behavior, or a no-op ...
  ```
  This is a lightweight convention, not a framework — no dependency
  injection, no plugin system. Consistent with this codebase's existing
  style (plain functions, explicit imports, no magic).
- **Kill switch is the same mechanism, inverted**: `!flag disable
  <name>` on something already fully live instantly reverts everyone to
  the old/no-op path. No redeploy, no restart.
- Flags persist in the database (not memory), so they survive restarts
  — directly satisfies Requirement 4.3, and is a natural fit since this
  bot already treats SQLite as its single source of runtime truth (see
  the existing `settings` key-value table, which flags could arguably
  extend — but a dedicated table is clearer for `list_feature_flags()`
  and per-flag audit fields like `updated_by`).

## Component 2 — Pre-deploy snapshot + rollback (bot)

**Recovers and extends the stranded `scripts/backup.py`** (see
requirements.md's "real finding" section) rather than reinventing it.

**Design:**
- Phase 0 of `tasks.md`: open a PR containing exactly the 2 stranded
  commits (`7f685f1`, `5829134`), rebased onto current `main`, verified
  clean (tests pass, no conflicts with PR #44/#10's later changes).
- Extend `backup.py` with a `--tag <label>` argument, so a pre-deploy
  snapshot is distinguishable from a routine nightly one:
  `python scripts/backup.py --tag pre-deploy-<git-sha>`.
- New `scripts/deploy.sh` (or a Python equivalent, matching this
  project's existing preference for Python over bash where either
  works): wraps the full deploy sequence into one command so "did I
  remember to back up first" stops being a thing a human has to
  remember:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  cd /opt/empire-english-bot
  GIT_SHA=$(git rev-parse --short HEAD)
  python3 scripts/backup.py --tag "pre-deploy-${GIT_SHA}"
  docker compose build --pull
  docker tag empire-english-bot-empire-english-bot:latest "empire-english-bot:${GIT_SHA}"
  docker compose up -d
  sleep 5
  python3 scripts/health_check.py || (echo "HEALTH CHECK FAILED — see rollback.sh" && exit 1)
  ```
- New `scripts/rollback.sh`: `docker tag empire-english-bot:<previous-sha>
  empire-english-bot-empire-english-bot:latest && docker compose up -d`
  plus, if the database itself needs reverting (not just code), a
  documented `cp` from the tagged backup file back into the Docker
  volume. This directly satisfies Requirement 3.3's "single documented
  command sequence."
- **Image retention:** keep the last 5 tagged images (`docker image
  prune` filtered to keep tagged ones, drop untagged dangling layers) —
  cheap on disk, makes "go back two deploys" possible without a rebuild.

## Component 3 — Automated health check (bot)

**Design:** `scripts/health_check.py`, callable both from `deploy.sh`
and on a schedule (cron, or a new lightweight `@tasks.loop` inside the
bot itself posting to a private channel). Checks concrete, specific
facts — directly satisfying Requirement 2.4's explicit rejection of
"container is running" as sufficient evidence:
- Curriculum loaded: exactly 38 weeks, all 4 levels present (mirrors
  what we manually grepped from logs during yesterday's PR #44 deploy).
- Command count: at least N commands registered (catches an import
  error that silently drops a whole command's registration).
- Database reachable: a trivial `SELECT 1` and `member_count()` call
  succeed.
- Discord gateway connected: `bot.is_ready()` true within a timeout.
- Exit code 0 = healthy, non-zero = not, with a human-readable summary
  printed either way (so `deploy.sh` can gate on it, and a human running
  it manually gets useful output either way).

## Component 4 — The "student journey" simulation (bot, CI)

**Design:** `tests/test_student_journey.py` — not unit tests of
individual functions (already well covered by the 281-test suite), but
one **end-to-end scripted scenario** run against a fresh temp SQLite DB
per CI run:
1. `!join` a synthetic member.
2. Simulate 8 days of `!done <task>` across all 7 daily tasks (crossing
   at least one streak-bonus threshold from `STREAK_BONUS_POINTS`).
3. Run the weekly assessment flow (`!assess`) and confirm the score
   lands in the database with the correct upsert-once-per-week behavior
   (already covered by unit tests, but re-verified here in the context
   of a full journey, not in isolation).
4. Drive a full advancement-exam submission through to `!examresult
   ... pass`, confirming the member's level actually changes and a role
   reassignment call fires (mocked Discord API, per existing test
   conventions).
5. Assert final invariants: total_points matches a hand-computed
   expected value, `longest_streak` matches, no `daily_submissions` rows
   are missing for any of the 8 simulated days.

This is the mechanism that would have caught something like a points
double-award or a broken streak-carry bug *before* merge, not after a
real student's numbers looked wrong. Runs in the same GitHub Actions
workflow that already exists (`.github/workflows/learning-bot-test.yml`)
— no new CI system, just a new test file the existing workflow already
picks up.

## Component 5 — empire-dojo: formalize the free staging that already exists

**Realization:** Cloudflare Pages already generates a unique preview
URL for every PR/branch (visible in past PR comments in this project's
own history, e.g. PR #7's `feat-bilingual-ui-labels.empire-practice.pages.dev`).
This has been happening automatically and ignored. Formalize it into a
hard rule, add automation around it:
- New GitHub Actions workflow `.github/workflows/dojo-verify.yml`: on
  every PR, runs `scripts/generate.py` fresh and then a Python
  `html.parser`-based sweep (the exact verification method used
  manually during the 2026-07-13 XSS fix) over every generated page,
  failing the check if any page fails to parse or if any known
  injection-shaped substring (`<script`, `javascript:`, `onerror=`)
  survives unescaped outside of an intentionally-escaped context.
  Directly satisfies Requirement 5.2.
- New steering note (append to existing `project-rules.md`): "never
  merge an empire-dojo PR without clicking through its Cloudflare
  preview URL first" — codifies what should already be habit into an
  explicit, written rule a future session will actually see.
- **Creative addition — automated diff-against-live**: a small script
  (`scripts/diff_against_live.py`) that fetches N representative pages
  (one per level, a mix of accent/vocab/listening/shadowing page types)
  from both the live domain and the PR's preview URL, and prints a
  unified diff. Turns "did I accidentally change something I didn't
  mean to" from a manual spot-check into a one-command report. Directly
  satisfies Requirement 5.3.

## Component 6 — The "ghost bot" (creative option, Phase 2+)

**The idea:** a second, free Discord bot application (new token, $0
cost — Discord doesn't charge per bot), invited into the **real**
production guild, but restricted via Discord's own permission system to
only see a new, hidden, admin-only channel category. Because it lives
in the real guild, it automatically inherits the real role hierarchy and
channel structure — which is exactly what's drifted out of sync before
in this project's history (the `setup_server.py` permission-drift bug
found and fixed in session 7). A synthetic "test student" account (or
even the operator's own second Discord account) can run real commands
against this ghost bot, in the real environment, with zero risk to real
students, since it's a completely separate bot identity with its own
database file.

**Why Phase 2, not Phase 0:** genuinely useful, but it's the most
operationally novel piece (new bot application registration, a second
`.env`, a second container) — sequenced after the higher-leverage, lower-effort
pieces (flags, backups, CI) exist and are proven, per the ranking
already discussed with the user.

## Component 7 — Deploy-time presence + dev-log channel (creative, cheap, do early)

**Design, both trivially cheap:**
- `deploy.sh`'s wrapper (or the bot itself, via a tiny admin command
  `!maintenance on|off`) sets `await bot.change_presence(activity=discord.Game
  (name="🔧 Updating... / بيتم التحديث"))` immediately before a deploy,
  and restores the normal presence after the health check passes. Reads
  as deliberate, not broken, to anyone glancing at the bot's status
  during the few seconds of a restart.
- A new private `#dev-log` channel (admin-only, created via
  `setup_server.py` alongside existing categories) gets one line
  auto-posted by `deploy.sh` on every deploy: git SHA, one-line summary
  (pulled from the commit message), timestamp. Turns "does this weird
  behavior correlate with something I shipped" from a manual git-log
  dig into an instant visual check.

## Component 8 — Turning safety into a marketing signal (Requirement 6)

**Design:** no new code, a **process rule**: once a feature has been
flag-enabled for everyone and verified stable for a day or two, post a
bilingual announcement via the *existing* `!announce` command, framed as
"here's what's new for you" rather than "here's what we changed."
Costs nothing, reuses what's already built, and turns every safe rollout
into a visible trust-building moment for paying students — the same
instinct already validated by this project's bilingual-UI work (session
6), just applied to the release process itself.

For the "publicly viewable status artifact" (Requirement 6.2): the
cheapest true option is a public, read-only Discord command
(`!systemstatus`, distinct from the existing admin-only `!status`) that
any member can run, showing something like "✅ All systems operational
· Last verified: 4 minutes ago" — sourced from Component 3's health
check writing its last-good timestamp into the `settings` table. No new
service, no new page, reuses infrastructure that will already exist
from Component 3.

## What this design deliberately does NOT do

- No Kubernetes, no blue/green load balancer, no second VPS — none of
  that is proportionate to a $7/mo, 16-student system, and would
  introduce exactly the kind of ongoing operational toil this project's
  own steering explicitly warns against.
- No new SaaS dependency for status pages, feature flags, or CI beyond
  what's already free and in use (GitHub Actions, Cloudflare Pages).
- Does not touch `empire-oracle`/`empire-annex`/other repos — scoped
  strictly to `empire-nexus`'s `discord-learning-bot` and `empire-dojo`,
  per the user's explicit framing of "the project we were working on."

## Open design questions (flag to user, don't guess)

1. **Ghost bot (Component 6):** worth building at all before real
   students exist, or genuinely wait until there's a "beta squad" of a
   few friendly real students to test features on directly? Both are
   reasonable; the user should pick based on how much they trust
   synthetic data vs. wanting real (if small-scale) signal.
2. **`#dev-log` channel placement:** new dedicated category, or fold
   into the existing `ADMIN` category from `setup_server.py`? Low
   stakes, flagged only so it's a deliberate choice, not an accident.
