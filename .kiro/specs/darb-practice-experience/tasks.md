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

- [ ] **2.1** Homepage becomes the **calendar**: render from
  `/api/calendar` — real dates, today (yellow+dot), done (green), locked
  ("opens {date}"), missed (amber/catch-up), level_complete. (R7)
- [ ] **2.2** Remove the level switcher; show only the session's level.
  (R4.2)
- [ ] **2.3** Future-day lock enforced in UI (locked cells not openable).
  (R7.5)
- [ ] **2.4** Mastery colors: exercise pages + calendar cells show the
  tier (Bronze→Diamond) from the server; "Done" control calls
  `/api/practice-complete` and paints the returned tier; same-day repeat
  shows "come back tomorrow". (R9)
- [ ] **2.5** Completion is server-backed (green persists cross-device);
  localStorage is cache-only. (R8, C5)
- [ ] **2.6** Deploy + live-verify with a ghost account across two
  browsers/devices: dates correct vs join date, today highlighted,
  complete → green everywhere, tier increments only once/day, catch-up a
  past day works, future locked.
- [ ] **2.7** PR merged + deployed + verified. Update STATUS.md.

---

## Phase 3 — True edge gating (Cloudflare Pages Functions middleware)

Goal: content never served without a valid session. This is the switch
that makes it genuinely paid/gated. Do it only after Phases 1–2 are
proven, so the claim→session→calendar path already works.

- [ ] **3.1** Add `site/functions/_middleware.js`: verify `empire_session`
  HMAC (shared secret from Pages env), check expiry + path-level match,
  cached revocation check via `/api/session-status`; serve `gate.html`
  otherwise. (R3, R4.3)
- [ ] **3.2** Build `gate.html`: single clean bilingual claim page (enter
  code → `/api/claim` → set parent-domain cookie → redirect to calendar).
  Remove the old per-page JS gate overlay entirely. (R2.2, Flow A)
- [ ] **3.3** Set `DARB_SESSION_SECRET` in the Cloudflare Pages project
  env (matching the bot). (C3)
- [ ] **3.4** Level enforcement at edge: Lx session cannot fetch other
  levels' paths. (R4.3)
- [ ] **3.5** Watermark: inject per-student faint name overlay post-gate.
  (R6.3)
- [ ] **3.6** Owner alerts + revocation: wire 3rd-device / anomaly alerts
  to the Telegram ops path; add an owner command/way to revoke a
  student's sessions. (R6.2, R6.4)
- [ ] **3.7** **Safety-critical live verification** with a ghost account:
  (a) no session → only gate served, view-source shows no content;
  (b) valid session → content served, no flash; (c) wrong-level path
  denied; (d) revoke → locked within TTL. Confirm a REAL current student
  is not locked out (test the migration path — see 3.8).
- [ ] **3.8** **Migration of the 15 live students:** decide + execute how
  existing students get their first session without disruption (e.g., a
  one-time "your access was upgraded, tap here / run `!link`" DM, or
  honor existing saved tokens for a grace window). Documented, reversible.
- [ ] **3.9** Rollback rehearsed: removing `_middleware.js` + redeploy
  instantly reverts to open serving if a gate bug appears. Documented.
- [ ] **3.10** PR merged + deployed + verified. Update STATUS.md.

---

## Phase 4 — Record → #showcase + auto-complete (isolated / optional)

Goal: one-tap record→Discord. Isolated so any device flakiness can't
block earlier phases. (R10)

- [ ] **4.1** `POST /api/submit-recording` (multipart) → bot posts the
  audio to the student's `#lN-showcase` with their name. (R10.2)
- [ ] **4.2** Auto-complete on send (reuses Flow D path); `!done`
  afterward returns "already done today". (R10.3–10.4)
- [ ] **4.3** Practice-page "Send to Discord" button next to the existing
  recorder. (R10.1–10.2)
- [ ] **4.4** Live-verify on real target devices (esp. iOS Safari audio
  format). If infeasible, defer per R10.5 and document.
- [ ] **4.5** PR merged + deployed + verified. Update STATUS.md.

---

## Phase 5 — Full progress-chain verification

Goal: prove the bot follows progress 100%. (R11)

- [ ] **5.1** Ghost-account end-to-end script: practice-complete (page) +
  `!done` (Discord) + record→showcase → assert `practice_mastery`,
  `daily_submissions`, streak, points, calendar state, and tier all
  agree, including catch-up and duplicate cases. (R11.1)
- [ ] **5.2** Run live, zero residue on real data, documented. (R11.2)
- [ ] **5.3** Fix + re-verify any defect found. (R11.3)
- [ ] **5.4** Final STATUS.md update: Darb complete.

---

## Cross-cutting bookkeeping

- After each phase: `empire-chronicle/STATUS.md` updated (R12.2), PR
  linked, live-verification evidence noted.
- SSH keys are ephemeral — request a fresh one per session that needs the
  server; never reuse.
- `empire-dojo` has no CI/CD — every deploy is manual `wrangler` + live
  re-check (C6).
- Keep `DARB_SESSION_SECRET` out of git; it lives only in the server
  `.env` and the Cloudflare Pages env.
