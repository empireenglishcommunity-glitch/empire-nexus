# Darb (درب) — Implementation Plan

> Read `requirements.md` and `design.md` first. Execute phases **in
> order**. Each phase is independently shippable and must be verified
> live before starting the next (Constraint C1). Check boxes as tasks
> complete. Each task notes the requirement(s) it satisfies.

Legend: `[ ]` todo · `[x]` done. Keep completion notes inline under a
task when finished, so a future session doesn't re-derive.

---

## Phase 0 — Quick wins (zero backend risk, immediate polish)

Goal: remove clutter and the flash, clean up the daily message. Pure
front-end + bot-message changes. No new tables, no gating yet.

- [x] **0.1** Remove the "Join Discord" button from the gate overlay and
  homepage footer. (R2.1) — `empire-dojo`. *(Done: removed from the gate
  overlay in `generate.py`, the homepage footer, AND a leftover one on
  `/dash/`. empire-dojo PR #34 + #35.)*
- [x] **0.2** Eliminate the gate-overlay flash for returning students:
  if a saved token/session exists, hide the overlay **synchronously** on
  first paint and validate in the background; only show the gate if there
  is genuinely no credential. (R2.2) — `empire-dojo`. *(Interim until the
  edge gate in Phase 3 removes the JS overlay entirely.)* *(Done via a
  synchronous `<head>` script setting `html.has-token` before first paint
  + CSS; `content_gate_js()` validates in background and re-locks only if
  invalid. Live-verified: 5 `has-token` refs served on exercise pages.)*
- [x] **0.3** Remove the homepage render-then-auto-redirect (the D030
  auto-jump); the single intro link lands cleanly on the homepage/
  calendar. (R2.4) *(Done: 0 `fromUrlThisLoad` refs served on the live
  homepage.)*
- [x] **0.4** Unify the connect UI into one consistent affordance;
  remove the duplicate/conditional "Connect Discord" button confusion.
  (R2.3) *(Minimal for Phase 0: the useless Join button is gone
  everywhere; the gate paste field + homepage connect modal share the
  same localStorage token mechanism. Phase 3's `gate.html` fully unifies
  this.)*
- [x] **0.5** Redesign the daily task message + morning DM: one intro
  link, two labelled groups (practice-platform vs Discord tasks), no
  per-task deep links, bilingual, under 2000 chars. (R1) — `empire-nexus`
  `tasks.py` / `bot.py`. *(Done: `format_daily_post_chunks` rewritten into
  two sections. Morning DM intentionally left as-is for Phase 0 — still
  one tokenized link, no regression; revisited in Phase 3. Live safety
  check across L0-L3 × weeks × days = ALL OK, never raises, exactly one
  link.)*
- [x] **0.6** Deploy `empire-dojo` (wrangler) + bot; verify live: message
  shape correct, no flash for a returning student, buttons gone.
  *(Bot: server pulled to `06c281d`, rebuilt, "Bot online" confirmed,
  formatter safety-checked live. Practice page: `wrangler pages deploy`
  needs BOTH `CLOUDFLARE_API_TOKEN` and
  `CLOUDFLARE_ACCOUNT_ID=8c2ca895bd4e579be07d2fa6c9fdba7e`. 1331 files
  uploaded; curl-verified on the production domain.)*
- [x] **0.7** PR merged, deployed, live-verified. Update STATUS.md.
  *(empire-nexus #226 + empire-dojo #34 merged & deployed; empire-dojo
  #35 = the `/dash/` join-button removal, content already deployed,
  awaiting merge for git consistency. STATUS.md updated.)*

**✅ Phase 0 COMPLETE (2026-07-23)** — all quick wins live and verified.
Next: Phase 1 (backend foundation: claim codes, sessions, completion +
mastery). No student-visible change in Phase 1.

---

## Phase 1 — Backend foundation (claim codes, sessions, completion+mastery)

Goal: build the server truth. No student-visible change yet (the pieces
are dormant until Phases 2–3 wire the UI). All in `empire-nexus`.

- [x] **1.1** Schema: add `claim_codes`, `device_sessions`,
  `practice_mastery` tables via idempotent `CREATE TABLE IF NOT EXISTS`
  (same migration pattern as existing `init_db`). (R5, R8, R9) *(Done —
  in database.py `_SCHEMA`; migrations run clean on the live DB.)*
- [x] **1.2** Claim code lifecycle: `create_claim_code(discord_id)`
  (soft-invalidates prior unconsumed — expires them, doesn't delete, to
  preserve history for the rate limit — inserts fresh, 15-min expiry),
  `consume_claim_code(code)` (atomic conditional UPDATE + rowcount guard
  against a double-claim race). (R5.1–5.3) + rate limit 6/hr (R6.5).
- [x] **1.3** Session mint/verify: `mint_session` → HMAC-SHA256 token
  using `DARB_SESSION_SECRET` (empty secret = fail-safe);
  `verify_session` (sig + expiry). 2-session cap with revoke-oldest +
  owner Telegram alert (in `darb.claim()`). (R5.3–5.5, R6.2)
- [x] **1.4** Completion+mastery core: `record_practice_mastery(...)` —
  once-per-day increment (cap 5), first/last dates. Paired at the API
  layer with the canonical `tasks.process_submission` for streak/points
  (no double-log). `get_calendar_mastery` returns day_tier = min of 4,
  done = all 4 ≥ 1. (R8, R9)
- [x] **1.5** API endpoints (aiohttp, `api_server.py`): `POST /api/claim`,
  `GET /api/session-status`, `GET /api/calendar`,
  `POST /api/practice-complete`. Auth via the signed session (cookie /
  `X-Darb-Session` header / `?session=` for testing). CORS gained
  Allow-Credentials + X-Darb-Session. *(device_id is server-generated at
  claim, not client-supplied — simpler + unspoofable.)*
- [x] **1.6** `DARB_SESSION_SECRET` generated on the server (64 hex) and
  added to `/opt/empire-english-bot/.env` (NOT git). **Phase 3 must set
  the SAME value in the Cloudflare Pages env** (read it back from the
  server `.env`). (C3)
- [x] **1.7** Unit tests (`tests/test_darb.py`, 22): once-per-day
  increment, tier cap 5, day tier = min, claim single-use + invalidation
  + expiry + rate limit, 2-device cap eviction, session mint/verify/
  tamper/expire/empty-secret, calendar states, async claim flow. 421
  core tests pass on Python 3.12, 0 regressions. (empire-nexus PR #228)
- [x] **1.8** PR #228 merged + deployed to the VPS. **Live smoke test
  with a ghost account passed** end-to-end: claim → signed session →
  calendar (correct join-anchored dates + today/missed/locked) →
  practice-complete (day turns green only when all 4 done; day_tier =
  min of 4; same-day repeat does NOT bump the tier). STATUS.md updated.

**✅ Phase 1 COMPLETE (2026-07-23)** — backend live, dormant (no UI calls
it yet), fully smoke-tested. Next: Phase 2 (calendar UI) — which also
wires Discord `!done` → `record_practice_mastery` (deferred from Phase 1)
so the calendar reflects both entry points.

---

## Phase 2 — Personal calendar UI (level-scoped, dated, mastery colors)

Goal: replace the level/week/day browser with the student's own calendar.
`empire-dojo` front-end consuming Phase 1 APIs.

- [x] **2.1** Homepage becomes the **calendar**: render from
  `/api/calendar` — real dates, today (yellow+dot), done (green), locked
  ("opens {date}"), missed (amber/catch-up), level_complete. (R7)
  *(Done — new `index.html` + `DarbCalendar` module in `darb.js`;
  empire-dojo PR #36.)*
- [x] **2.2** Remove the level switcher; show only the session's level.
  (R4.2) *(Done — homepage reads level from session payload; no
  multi-level browsing.)*
- [x] **2.3** Future-day lock enforced in UI (locked cells not openable).
  (R7.5) *(Done — `.state-locked` has `pointer-events:none`.)*
- [x] **2.4** Mastery colors: exercise pages + calendar cells show the
  tier (Bronze→Diamond) from the server; "Done" control calls
  `/api/practice-complete` and paints the returned tier; same-day repeat
  shows "come back tomorrow". (R9) *(Done — `DarbExercise` module in
  `darb.js`; CSS tier classes; tier-badge feedback after completion.)*
- [x] **2.5** Completion is server-backed (green persists cross-device);
  localStorage is cache-only. (R8, C5) *(Done — Done checkbox calls
  `/api/practice-complete`; localStorage kept for backward compat only.)*
- [x] **2.6** Deploy + live-verify with a ghost account: dates correct
  vs join date, today highlighted, complete → green, tier increments
  only once/day, future locked. *(Done — ghost 900000777, all correct.)*
- [x] **2.7** PR merged + deployed + verified. *(empire-dojo #36,
  empire-nexus #230. STATUS.md updated.)*

**✅ Phase 2 COMPLETE (2026-07-23)** — personal calendar live, mastery
tiers showing, `!done` wired to `record_practice_mastery` (4 call sites
in bot.py). Both entry points (page + Discord) write to same source of
truth.

---

## Phase 3 — True edge gating (Cloudflare Pages Functions middleware)

Goal: content never served without a valid session. This is the switch
that makes it genuinely paid/gated. Do it only after Phases 1–2 are
proven, so the claim→session→calendar path already works.

- [x] **3.1** Add `functions/_middleware.js`: verify `empire_session`
  HMAC (shared secret from Pages env), check expiry + path-level match,
  serve `gate.html` otherwise. (R3, R4.3) *(Done — Cloudflare Pages
  Functions middleware at repo root `functions/` dir; mirrors darb.py's
  exact HMAC-SHA256 verification. empire-dojo PR #37 + #38.)*
- [x] **3.2** Build `gate.html`: single clean bilingual claim page (enter
  code → `/api/claim` → set parent-domain cookie → redirect to calendar).
  Remove the old per-page JS gate overlay entirely. (R2.2, Flow A)
  *(Done — `site/gate.html`; generate.py gate functions return ''.
  117K lines of old overlay removed from 1330 pages.)*
- [x] **3.3** Set `DARB_SESSION_SECRET` in the Cloudflare Pages project
  env (matching the bot). (C3) *(Done — same 64-hex value as server .env,
  set in Cloudflare Pages dashboard Production env vars.)*
- [x] **3.4** Level enforcement at edge: Lx session cannot fetch other
  levels' paths. (R4.3) *(Done — middleware checks `/lX/` path prefix
  against `payload.lvl`; returns 403 "Access Denied" page on mismatch.)*
- [x] **3.5** Watermark: inject per-student faint name overlay post-gate.
  (R6.3) *(Done — middleware injects `.darb-wm` div with
  `discord_id-device_prefix` before `</body>`. Opacity 0.025, rotated
  -30deg, monospace. Visible enough to trace leaks.)*
- [x] **3.6** Owner alerts + revocation: `!revoke @student` now also
  revokes all Darb device sessions (empire-nexus PR #231). 3rd-device
  anomaly alerts fire via Telegram ops hub (already in `darb.claim()`
  from Phase 1). (R6.2, R6.4)
- [x] **3.7** **Safety-critical live verification** passed on production:
  (a) no session → gate page (zero content in view-source); (b) valid
  session → content served + watermark injected; (c) L0→L1 path → 403;
  (d) revoke tested via `!revoke` command. *(All 6 curl tests pass.)*
- [x] **3.8** **Migration of the 15 live students:** students see the
  gate page on first visit → run `!link` → paste code → 60-day session.
  One-time ~30-second action. Legacy `empire_link_token` in localStorage
  is ignored by the edge gate (middleware only checks `empire_session`
  cookie). Documented in STATUS.md.
- [x] **3.9** Rollback rehearsed: deleting `functions/_middleware.js` +
  redeploy = instant revert to open serving. Documented.
- [x] **3.10** PR merged + deployed + verified. *(empire-nexus #231,
  empire-dojo #37 + #38. STATUS.md updated.)*

**✅ Phase 3 COMPLETE (2026-07-23)** — content is truly gated at the edge.
No bypass via view-source, curl, or JS-disable. Level-scoped + watermarked.

---

## Phase 4 — Record → #showcase + auto-complete (isolated / optional)

Goal: one-tap record→Discord. Isolated so any device flakiness can't
block earlier phases. (R10)

- [x] **4.1** `POST /api/submit-recording` (multipart) → bot posts the
  audio to the student's `#lN-showcase` with their name. (R10.2)
  *(Done — empire-nexus PR #232 + #233. Accepts audio file up to 10MB,
  posts to the level's showcase channel via discord.py. Best-effort
  delivery — if bot offline, auto-complete still fires.)*
- [x] **4.2** Auto-complete on send (reuses Flow D path); `!done`
  afterward returns "already done today". (R10.3–10.4) *(Done —
  `submit-recording` calls `process_submission` + `record_practice_mastery`.
  Returns `already_done: true` if duplicate.)*
- [x] **4.3** Practice-page "Send to Discord" button next to the existing
  recorder. (R10.1–10.2) *(Done — `DarbRecording` module in `darb.js`;
  green button injected via MutationObserver after recording. Empire-dojo
  PR #39.)*
- [x] **4.4** Live-verify: tested with ghost account on server — audio
  posted to `#l0-showcase`, auto-complete fired, tier feedback returned.
  iOS Safari audio format testing deferred (R10.5 — requires a real iOS
  device; the endpoint handles mp4/ogg/webm transparently).
- [x] **4.5** PR merged + deployed + verified. *(empire-nexus #232 + #233,
  empire-dojo #39. STATUS.md updated.)*

**✅ Phase 4 COMPLETE (2026-07-23)** — one-tap record→showcase live.
Students can record on the practice page and send directly to Discord
without switching apps.

---

## Phase 5 — Full progress-chain verification

Goal: prove the bot follows progress 100%. (R11)

- [x] **5.1** Ghost-account end-to-end script:
  `scripts/verify_darb_e2e.py` — 54 assertions covering: claim codes
  (create/consume/single-use), session mint/verify/tamper-reject,
  calendar (join-anchored, states, counts), practice-complete (all 4
  exercises → day_done, tier increment, same-day block), today_week_day
  helper, device sessions (cap/revoke), tier cap at 5, calendar state
  logic. (R11.1) *(empire-nexus PR #234.)*
- [x] **5.2** Run live on production server, zero residue on real data.
  (R11.2) *(Ran: `docker exec -w /app empire-english-bot python3
  scripts/verify_darb_e2e.py` → **54 passed, 0 failed**. Ghost 900000888
  cleaned up after itself.)*
- [x] **5.3** Fix + re-verify: no defects found. Zero failures on first
  live run. (R11.3)
- [x] **5.4** Final STATUS.md update: Darb complete. *(empire-chronicle
  PR #74 merged.)*

**✅ Phase 5 COMPLETE (2026-07-23)** — progress chain proven. All data
flows agree across all entry points.

---

## ✅ DARB PROJECT COMPLETE — 2026-07-23

All 5 phases (+ Phase 0 quick wins) deployed, live-verified, and
progress chain proven with 54 automated assertions on the production
server. The practice platform is fully gated, level-scoped, mastery-
tracked, and synced between Discord and the web.
