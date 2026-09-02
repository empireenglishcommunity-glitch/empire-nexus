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
- **Repository:** `empireenglishcommunity-glitch/empire-nexus` (consolidated
  monorepo). *(Corrected 2026-08-29: this said `empire-english-community`, a name
  this repo has never had. It was `EEC-REPO` until the 2026-07-12 org-wide rename,
  and `empire-nexus` since.)*
- **Levels:** the **six CEFR levels A1–C2**, 90 curriculum weeks. The home-grown
  `L0`–`L3` model was retired in 2026-08 and its content deleted on 2026-08-25.
  Student-facing wording is always **"CEFR-aligned, not certified."**

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

> **Corrected 2026-08-29.** This tree previously showed `workers/`, `apps/`
> (`mobile/` + `web/`), `infrastructure/` and `bots/telegram-sales-bot/`. **None of
> them exist in this repo** — `infrastructure/` moved to `empire-server-forge` in
> the 2026-07-12 restructure, and the others are gone. `README.md` and
> `empire-chronicle/SYSTEM-MAP.md` §7 carried the same phantom tree and were fixed
> in the same pass. Verified by `ls`; 942 tracked files total.

```
empire-nexus/
├── README.md                    ← Project index
├── PROJECT_STATUS.md            ← ⚠️ STALE (2026-07-11), historical record only
├── REPOSITORY_AUDIT.md          ← ⚠️ STALE (2026-06-27), historical record only
├── .kiro/
│   ├── steering/                ← AI agent rules (this file)
│   └── specs/                   ← 24 initiative specs. ⚠️ tasks.md checkboxes are
│                                   NOT a reliable progress signal — read each
│                                   spec's status header instead.
├── .github/workflows/           ← learning-bot-test · deploy-learning-bot
│                                   · challenge-bot-test
├── bots/
│   ├── discord-learning-bot/    ← THE PRODUCT (Python/Docker, auto-deploys)
│   │   ├── src/                 ← 35 modules, ~29,600 lines
│   │   ├── content/{a1..c2}/    ← accent · grammar · reading · mediation · broadcast
│   │   ├── content/cefr/        ← can_do.json · grammar_syllabus.json
│   │   │                          · {LEVEL}-ALIGNMENT.md (owner sign-off)
│   │   │                          · authentic_audio.json
│   │   ├── content/placement/   ← placement test content
│   │   ├── data/                ← 90 × {level}_week{n}.json
│   │   ├── tests/               ← 89 files → 2,044 passing / 2 skipped
│   │   └── scripts/             ← ops, migration + verification tooling
│   └── discord-challenge-bot/   ← separate 30-day challenge bot (own project)
├── services/
│   └── nutq-scorer/             ← self-hosted pronunciation scorer (own container)
├── content/                     ← marketing/brand: telegram-posts · build-kit · brand
├── docs/                        ← ⚠️ largely HISTORICAL. strategy · specs
│                                   · operations · business · infrastructure
│                                   · checkpoints. Several files still say L0–L3.
└── scripts/fix_quiz.py          ← one-off
```

**Current cross-project state lives in the private `empire-chronicle`**, not here:
`STATUS.md` (read first), `SYSTEM-MAP.md`, and
`audits/2026-08-29-ECOSYSTEM-AUDIT.md`.

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

### Discord admin commands are SLASH (`/`); `!` is for students
Owner decision: admins drive the bot with **slash commands**, students keep `!`.
When telling the owner/team to run an admin action, ALWAYS phrase it as `/` —
`/setupgate`, `/checkchannels`, `/onboard`, `/setlevel`, `/status`, `/flag …` —
never `!setupgate` etc. (writing the `!` form is a documentation slip that keeps
happening; don't).
- 9 admin commands have first-class native slash versions (`/onboard`,
  `/setlevel`, `/find`, `/reset-student`, the `/itqan-*` set) + the `/nutq` group.
- EVERY other admin command is reachable through the generic bridge
  **`/admin command:<name> args:<rest as typed after !>`** — it re-dispatches to
  the exact same prefix-command code via `get_context()`/`bot.invoke()`, so `/`
  and `!` behave identically. Add new admin commands as normal `@bot.command`
  with a `has_permissions` check and they appear in `/admin` automatically.
- Why not `!` for admins: in the private `#admin-commands` channel, Discord's
  native `@`-picker can't list students (they can't see the channel). Slash
  pickers are bot-supplied, so they always work there.
- Onboarding is team-run (`manual_onboarding` flag ON): students do NOT
  self-onboard. Use **`/onboard`** — it grants the gateway role + level role +
  registers + adds community-pings in one idempotent step.

### `!setupgate` / channel-security contract (do NOT reintroduce leaks)
Channel visibility is enforced by Discord permission **overwrites**, set once by
`scripts/setup_server.py` and re-asserted by `/setupgate` (`role_gate.cmd_setupgate`).
`/setupgate` used to blanket-grant the shared `✅ Student | طالب` gateway role
`view_channel=True` on **every** non-`#rules`/`#welcome` channel — which twice
caused real security leaks:
1. students could see **admin channels** (fixed: PR #469), and
2. students could see **every level's zone**, not just their own (fixed: PR #474).

The permanent rules `/setupgate` now enforces — keep them:
- The gateway role unlocks **SHARED** channels only (community, resources,
  accountability, feedback, system). It must **NEVER** be granted view on:
  - **admin/hidden channels** — detected by `role_gate.is_admin_only_channel()`
    (the 🔒 ADMIN + 👻 Ghost categories; `admin-chat`, `mod-actions`,
    `member-notes`, `bot-logs`, `dev-log`, `ghost-*`). Deny it there.
  - **per-level zones** — detected by `role_gate.level_zone_of()` (slug-prefixed
    `a1-…c2-` channels / the `<lvl> ZONE` categories). Each zone is visible to
    its OWN level role only; every other level role AND the gateway role denied.
- `setup_server.py` also denies the gateway role on those categories
  (`STUDENT_GATEWAY_ROLE_NAME` — keep it in sync with `role_gate.STUDENT_ROLE_NAME`).
- If you add a NEW channel type that should be private/segmented, teach BOTH
  `setup_server.py` (the overwrites) AND `/setupgate`'s special-casing — do not
  rely on the blanket "student channel" branch, which grants the shared gateway
  role.
- **Guardrail:** `/checkchannels` (and the daily loop via
  `run_admin_exposure_check` + `run_level_isolation_check`) audits both admin
  exposure and level isolation and alerts Empire Ops on any leak. After any
  change to channels/roles/`/setupgate`, run `/checkchannels` and confirm
  "all … hidden" + "all … isolated".

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
- 🔴 **`default_enabled` is a SHIP STATE, not a mirror of production. Do not
  "sync" it to the live table.** *(Rule corrected 2026-08-29 — the previous
  wording was itself the bug.)*

  This rule used to say: when you enable a flag, flip `default_enabled` to True in
  the same commit, "so `default_enabled` always reflects the intended production
  state." **That instruction is wrong and cannot be followed**, because four tests
  deliberately assert the opposite, with docstrings explaining why:

  | Test | Asserts |
  |---|---|
  | `test_community_phase0::test_majlis_flags_default_off` | *"never accidentally active"* |
  | `test_itqan_phase0::test_flag_registered_and_off_by_default` | *"must default OFF"* |
  | `test_taqdeem_phase0` | `assessment_monthly_review` default False |
  | `test_motivation` | `hafiz_motivation` *"default off until verified"* |

  Following the old rule would have meant deleting those tests. **The tests are
  right.** For a system with 17 live students, a restored database coming up
  **inert** is the correct failure mode: an operator noticing "nothing is running"
  is far safer than students silently receiving half-configured features during a
  recovery.

  So `default_enabled` answers *"what does a FRESH database do?"* — nothing else.
  Reading it as production state is what made four separate documents wrong; the
  live table was finally read on 2026-08-29 and **16 of 51 flags** differ from
  their default.

  **What to do instead when you flip a flag:**
  1. Flip it live (`!flag enable <name>`, or Telegram `/flag`).
  2. **Record it in `empire-chronicle/docs/PRODUCTION-FLAG-STATE.md` in the same
     session.** A flag flip is a release. That file is the only place production
     state is written down — `updated_by` in the DB is a breadcrumb that happened
     to survive, not documentation.
  3. Leave `default_enabled` alone unless you are genuinely changing what a fresh
     install should do.

  **Consequence to remember:** `sync_flag_registry()` only INSERTs and never
  updates, so after a DB restore the ON rows must be re-applied deliberately from
  that file.

- **A new flag MUST be added to `src/flag_registry.py` in the SAME commit that
  creates it** — with its name, description, initiative and (default-OFF)
  `default_enabled`. Never as a separate PR or afterthought. The registry is what
  `!flag list` renders, so an unregistered flag is invisible to the owner. The registry is the source of truth for what flags
  exist, what they do, and which initiative they belong to. When adding
  a flag: add the REGISTRY entry with its name, description, initiative,
  and default_enabled state in the same commit. When enabling a flag
  that was previously default_enabled=False (e.g. after testing): update
  the registry's default to True in the same commit. This ensures
  `!flag list` always shows accurate descriptions and `default_enabled`
  always reflects the intended production state.

### Arabic/English mixed-direction (bidi) text — Sahin standing rule
Found live during Sahin Phase 1 (2026-07-17): an Arabic (RTL) line
containing **two or more** separate embedded English/code tokens
(e.g. two different `` `#channel-name` `` references joined by an
Arabic connector word like "أو"/"ثم") produces genuinely disorienting
reading order — the eye must jump between RTL and LTR runs multiple
times in an order that doesn't match the logical/typed order. This is
a real property of the Unicode Bidirectional Algorithm every modern
text renderer (including Discord's client) follows — not a wording
mistake specific to any one line.

**Rule going forward: never write an Arabic sentence/line containing
2+ separate embedded LTR tokens (channel names, commands, English
words).** Fix pattern, in order of preference:
1. Split into separate lines, one embedded LTR token per line, so
   each line has at most one RTL→LTR transition and nothing Arabic
   trails after the token on that same line.
2. If several tokens genuinely belong together (e.g. a list of
   commands), move them onto their OWN line with zero Arabic on that
   line (pure LTR content has no direction to alternate with, so it's
   never a bidi issue on its own) — join with a direction-neutral
   separator (`—`, `←`, `·`) rather than an Arabic connector word.

**Before shipping any new Arabic content with inline
channel/command/English references**, run
`bots/discord-learning-bot/scripts/bidi_check.py` (or import
`find_bidi_issues()`/`find_bidi_issues_in_dict()` from it directly) —
it flags every line with 2+ embedded LTR islands. A regression test
(`tests/test_bidi_check.py::test_real_channel_guides_have_zero_bidi_issues`)
already locks this in for `channel_guides.py`; extend that pattern to
any NEW Arabic content map added to this codebase, don't invent a
separate check per file.

### Audio-upload API endpoints — Taqdeem standing rule
Found live on 2026-08-29: a student (Mai) was stuck on the Monthly
Review — every Speaking item showed *"Couldn't save that answer — check
your connection"* and retrying never worked. It was **not** a
connection problem. The `/api/assessment/monthly/item` and
`/api/assessment/advancement/item` handlers parsed the request with
`await request.json()` **only**. But a pronunciation/speaking answer is
always sent as **multipart/form-data** with an `audio` blob, so
`request.json()` raised, the handler returned
`{"ok": false, "error": "bad_json"}`, and the client rendered its
generic save-failed message. The audio recorded and played back fine on
the device — it just could never reach the server. Only the *weekly*
endpoint parsed multipart. The three endpoints had silently drifted:
weekly correct, monthly + advancement broken.

**Rule going forward: any API endpoint that can receive a student
recording MUST parse BOTH `multipart/form-data` (audio) AND JSON (text),
never JSON-only.** In `discord-learning-bot/src/api_server.py` the
canonical way is the shared helper **`_read_item_submission(request)`** —
route every assessment item endpoint (weekly / monthly / advancement,
and any future exam family) through it and pass its `audio_bytes` /
`audio_filename` into `assessment.submit_item(...)`. Do **not** write a
new endpoint that calls `request.json()` directly for a submission that
might carry audio, and do **not** clone the multipart-parsing block into
yet another divergent copy — reuse the one helper so the three (soon
four) endpoints can never drift apart again.

- The regression is locked by
  `tests/test_assessment_item_submission.py` (multipart audio is parsed,
  filename-by-content-type, JSON text still works, and the error paths).
  When adding a new recording endpoint, extend that test file — do not
  ship an audio endpoint with no multipart test.
- `/api/placement/speaking` and `/api/submit-recording` (Nutq daily
  practice) already accept multipart correctly; `/api/placement/speaking`
  still has its own inline copy of the parse and is a candidate to fold
  onto `_read_item_submission` if it is touched again.
- Client side: a save failure currently surfaces as *"check your
  connection"* even for a server-side 400. If you touch
  `empire-dojo/site/js/assessment.js`, prefer distinguishing a real
  network error from a server rejection so a future backend bug is not
  again misread as a connectivity problem by the student and the owner.

### General
- Commit messages: `type(scope): description`
- Branch naming: `component/description`
- Always push to a branch, never directly to main (create PR)
- Arabic text: use Egyptian dialect, warm tone, consistent emojis —
  **EXCEPTION: `discord-learning-bot/scripts/channel_guides.py`'s
  per-channel guides deliberately use Modern Standard Arabic (فصحى)
  instead, per an explicit 2026-07-17 owner decision (Sahin Phase 1) —
  see that file's own module docstring for the full reasoning. This
  is a scoped exception, not a project-wide dialect change; new
  Arabic content elsewhere should still default to Egyptian dialect
  unless explicitly told otherwise.**

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
