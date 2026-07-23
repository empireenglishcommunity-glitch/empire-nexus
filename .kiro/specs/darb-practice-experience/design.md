# Darb (درب) — Design

> Read `requirements.md` first. This document explains the architecture,
> the data model, the exact request flows, and the deliberate
> non-goals. It is written so a future session (or a different agent)
> can implement it without re-deriving anything.

## Architecture at a glance

```
                          ┌─────────────────────────────────────────┐
   Discord  ──!link──▶    │  BOT (empire-nexus) — aiohttp API :8099  │
                          │  bot.empireenglish.online (CF Tunnel)     │
   student                │  • issues one-time claim codes            │
      │                   │  • consumes code → mints signed session   │
      │                   │  • records completion + mastery (truth)   │
      │                   │  • SQLite: members, submissions,          │
      │                   │    claim_codes, device_sessions,          │
      │                   │    practice_mastery, token_ip_log         │
      │                   └───────────────▲───────────────────────────┘
      │ enters claim code                 │  signed-session verify (shared HMAC secret)
      ▼                                   │  + completion/calendar API calls
┌──────────────────────────────────────────────────────────────────┐
│  PRACTICE PLATFORM (empire-dojo) — Cloudflare Pages                 │
│  practice.empireenglish.online                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Pages Functions middleware  (site/functions/_middleware.js) │   │
│  │  • runs on EVERY request, at the edge                        │   │
│  │  • no valid empire_session cookie  → serve gate.html only    │   │
│  │  • valid cookie, wrong level for path → deny                 │   │
│  │  • valid cookie, right level → serve the static asset        │   │
│  └────────────────────────────────────────────────────────────┘   │
│  static content (1,330 pages + audio) served ONLY past the gate     │
└──────────────────────────────────────────────────────────────────┘
```

Key idea: **the Cloudflare Pages Functions middleware is the real gate.**
It lives in the same repo, deploys with the site (no separate Worker, no
new vendor), and runs before any file is served. Content that isn't
served can't be stolen.

## The session token (how the edge trusts without calling the bot)

- On claim, the bot mints a compact **HMAC-SHA256-signed** token:
  `base64url({discord_id, level, device_id, iat, exp}) + "." + HMAC`.
- The token is set as cookie **`empire_session`** on the parent domain
  `Domain=.empireenglish.online`, `Secure`, `SameSite=Lax`, long
  `Max-Age`. Parent-domain scope means the cookie is sent to BOTH
  `practice.` (for the middleware) and `bot.` (for API calls).
- The middleware verifies the signature with the **shared secret**
  (`DARB_SESSION_SECRET`, in the bot `.env` AND the Pages project env
  vars — never in git). No per-request bot call needed for authenticity
  or level — fast and resilient (R3.4).
- **Revocation (R6.4):** signed tokens are otherwise valid until `exp`.
  To support instant revocation without a per-request DB hit, the
  middleware does a **cached** revocation check: it calls the bot's
  `/api/session-status` at most once per session per short TTL (via the
  Cloudflare Cache API keyed by `device_id`), and on a revoked result
  serves the gate. Trade-off documented: revocation takes effect
  within the cache TTL (minutes), which is acceptable for this scale.
  (If we later want instant revocation, the middleware can check every
  request — fine at 15-student traffic — this is a tunable.)

## Data model (new SQLite tables + one extension)

```sql
-- One-time claim codes (R5.1–5.3)
CREATE TABLE claim_codes (
  code         TEXT PRIMARY KEY,      -- short, unguessable
  discord_id   TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at   TEXT NOT NULL,         -- e.g. +15 min
  consumed_at  TEXT DEFAULT NULL,     -- set when claimed (never reusable)
  FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
-- Only one UNCONSUMED code per student at a time: issuing a new one
-- deletes/expires the prior unconsumed code (R5.2).

-- Durable device sessions (R5.3–5.5, R6)
CREATE TABLE device_sessions (
  device_id    TEXT PRIMARY KEY,      -- random per device
  discord_id   TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen_at TEXT,
  created_ip   TEXT,
  user_agent   TEXT,
  revoked      INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
-- Max 2 non-revoked sessions per student; 3rd claim revokes the oldest
-- and alerts the owner (R5.5, R6.2).

-- Content-day-aware completion + mastery (R8, R9) — the heart of it
CREATE TABLE practice_mastery (
  discord_id            TEXT NOT NULL,
  level                 TEXT NOT NULL,   -- L0..L3
  week                  INTEGER NOT NULL,
  day                   INTEGER NOT NULL, -- 1..7
  exercise              TEXT NOT NULL,   -- accent|vocab|shadow|listening
  completion_count      INTEGER NOT NULL DEFAULT 0, -- mastery tier driver (cap 5)
  first_completed_date  TEXT,
  last_completed_date   TEXT,            -- gate for once-per-day increment
  PRIMARY KEY (discord_id, level, week, day, exercise),
  FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
```

`daily_submissions` (existing) is **kept** and still drives streaks/points
and the recording/verification accountability loop. `practice_mastery` is
the new content-day truth for the calendar + tiers. Both are written on
every completion so they never diverge (see flows).

## Request flows

### Flow A — Claim (unlock)
1. Student runs `!link` in Discord.
2. Bot deletes any prior unconsumed code for them, inserts a fresh
   `claim_codes` row (expires +15 min), DMs the code + the gate URL.
3. Student opens `practice.empireenglish.online` → middleware sees no
   session → serves `gate.html` (a single clean page: "enter your code",
   bilingual, plus "type `!link` in #bot-commands to get one").
4. Student enters code → `gate.html` POSTs to bot `/api/claim`
   `{code, device_id}` (device_id generated + stored locally if absent).
5. Bot validates code (exists, unexpired, unconsumed), marks it consumed,
   enforces the 2-session cap (revoke oldest + alert if exceeded), inserts
   a `device_sessions` row, logs IP/UA, and returns the signed session
   token + the student's level.
6. `gate.html` sets the `empire_session` cookie (parent-domain) and
   redirects to the student's calendar. No flash: they never see a
   content page locked; they see the gate, then their calendar.

### Flow B — Normal page load (returning student)
1. Browser sends `empire_session` cookie automatically.
2. Middleware verifies signature + expiry + that the requested path's
   level matches the session level; (cached) revocation check.
3. Valid → serve the static asset directly. **No overlay, no flash, no
   JS gate.** (The old per-page JS gate overlay is removed entirely.)
4. Invalid/space wrong level → serve `gate.html` (or redirect to the
   student's own level root).

### Flow C — Completing an exercise on the practice page
1. Student finishes, e.g., accent for their current day, taps "Done".
2. Page POSTs `/api/practice-complete` `{level, week, day, exercise}`
   (session cookie identifies the student; the page knows week/day from
   the calendar it rendered).
3. Bot:
   - Upserts `practice_mastery`: if `last_completed_date < today` →
     `completion_count = min(count+1, 5)`, set dates; if `== today` →
     no increment (returns "come back tomorrow").
   - Logs a `daily_submission` for today's date + task (so streak/points
     update and the bot "follows progress").
   - Returns the new exercise tier + the day tier (min across 4).
4. Page paints the exercise/day the returned tier color. Calendar day
   goes green once all 4 exercises have `count>=1`.

### Flow D — Completing via Discord (`!done`) or record→showcase
- `!done <task>` (or the record→showcase auto-complete) writes the same
  `daily_submission` (as today) AND upserts `practice_mastery` for the
  student's **current scheduled** (week, day) computed from join date.
- Duplicate (already done today) → the existing `UNIQUE` constraint makes
  it a no-op → bot replies "already done today" (R10.4). No double-count.
- Catch-up of a *past* day is done **on the page** (Flow C, explicit
  week/day), which is where the calendar's catch-up affordance lives — so
  Discord `!done` only ever needs to handle "today", keeping it simple.

### Flow E — Record → #showcase (Phase 4)
1. Page records audio (existing `Recorder`), shows playback/download.
2. "Send to Discord" → POST audio blob to `/api/submit-recording`
   `{level, week, day, exercise}` (multipart; session cookie identifies
   student).
3. Bot posts the file into the student's `#lN-showcase` channel with
   their name, then runs the same completion path as Flow D (auto-mark).
4. Returns success; page shows "sent ✅ + marked done".

## Calendar computation (server-side, R7)

A single endpoint `/api/calendar` returns everything the page renders, so
the browser never computes dates or "today" (avoids timezone drift):

```jsonc
{
  "level": "L0",
  "join_date": "2026-07-20",
  "today_index": 3,                 // 1-based, Asia/Dubai
  "level_total_days": 56,           // L0 = 8 weeks
  "days": [
    { "index":1, "date":"2026-07-20", "week":1, "day":1,
      "state":"done", "day_tier":2,
      "exercises":[{"id":"accent","tier":3},{"id":"vocab","tier":2}, ...] },
    { "index":3, "date":"2026-07-22", "week":1, "day":3,
      "state":"today", "day_tier":0, "exercises":[...] },
    { "index":4, "date":"2026-07-23", "week":1, "day":4,
      "state":"locked", ... },
    { "index":2, "date":"2026-07-21", "week":1, "day":2,
      "state":"missed", ... }
  ]
}
```

- `state` ∈ `done | today | locked | missed | level_complete`.
- Computed from: `join_date`, server "today" (Asia/Dubai), and
  `practice_mastery`. The page is a pure renderer.

## Daily message redesign (R1) — shape

```
🌅 مهام اليوم / Today's tasks — Week 1 · Day 3

🌐 على منصة التمرين / On the practice platform:
   practice.empireenglish.online
   🎯 النطق · 📖 المفردات · 🎧 المحاكاة · 👂 الاستماع

💬 هنا في Discord / Here on Discord:
   🎙️ المحادثة (speaking) · ✍️ الكتابة (writing) · 🤝 المجتمع (community)

سجّل إنجازك بكتابة !done ... / log each with !done ...
```

One link. Two groups. No per-task deep links.

## Anti-abuse (R6)

- **IP/device logging:** extend the existing `token_ip_log` / device
  session rows on every claim + `/api/session-status` hit.
- **Owner alerts:** reuse the existing Telegram alert path (Markaz ops
  bot) — fire on: 3rd-device claim, revocation events, and access from a
  new country/IP cluster.
- **Watermark:** the middleware (or a tiny always-present snippet injected
  post-gate) renders a fixed, low-opacity overlay with the student's name
  — a social deterrent that survives screenshots.
- **Rate limit:** `!link` limited (e.g., ≤ N codes / hour / student).

## What this deliberately does NOT do (non-goals)

- No second server, no Kubernetes, no paid auth vendor, no database
  migration off SQLite.
- No account passwords / email login — Discord remains the identity
  root; the claim code is the bridge.
- No change to the curriculum content, the 7-task model, or the level
  advancement/exam flow (those stay in Discord).
- No attempt at DRM-grade protection (impossible for web content); the
  goal is genuine gating + strong sharing deterrence proportional to a
  small paid community, not defeating a determined pirate.
- Does not touch Nour / Aql (still paused).

## Rollout safety (C1)

- Phases 0–2 do not remove the current access path until the new one is
  proven; the edge gate (Phase 3) is switched on only after claim +
  sessions (Phase 1) and the calendar (Phase 2) are live and verified.
- Every `empire-dojo` deploy is verified live per C6.
- A documented rollback exists for each phase (revert PR + redeploy; the
  middleware can be disabled by removing `_middleware.js` and
  redeploying, instantly reverting to open serving if a gate bug locks
  real students out).
