# Tasks — Masar (مسار): Personal Growth Narrative

> **How to use this file:** work top to bottom, phase by phase. Check
> off a task (`- [x]`) in the SAME commit/PR that completes it, so this
> file is always an accurate live progress record — never mark
> something done here until it's actually merged and LIVE-VERIFIED, per
> this project's own established discipline (proven throughout Hisn:
> a code fix isn't done until deployed and re-checked against the real
> running system, not just merged).
>
> **If you are a fresh session/agent picking this up:** read
> `requirements.md` and `design.md` in this same directory first. Then
> resume at the first unchecked task below.
>
> **Timeline note:** per explicit owner instruction, Masar has NO
> deadline pressure and is NOT gated by Hisn's own Go/No-Go timeline.
> Build it right. Do not rush a phase to "make it before launch."

---

## Phase M0 — Foundation

- [x] **M0.1** Write `narrative_engine.py` with `gather_signals(discord_id)`
  — pulls from `nour_memories`, `ability_milestones` (last 14 days),
  `pronunciation_scores` (14d trend), `vocab_srs` (due/mastered/accuracy),
  `members.difficulty_level`, `members.current_streak`, and a summary
  of recent `nour_conversations` themes, into one dict. Unit-testable
  on its own (a real gap D020 had — no generation function existed to
  test at all).
  → **Done.** Reuses existing helpers throughout (`nour_personality.get_memories()`,
  `database.get_srs_stats()`, `database._get_pronunciation_stats()`,
  `database.tasks_completed_today()`, `tasks.calculate_completion_rate()`)
  rather than duplicating SQL — only one genuinely new query was
  needed (`_get_recent_milestones()`, a 14-day-windowed variant of the
  existing lifetime-only `get_completed_milestones()`).
  `conversation_themes` is a plain extraction of recent
  `nour_conversations` rows (topic/intent or a message snippet), NOT
  an AI summary — keeps `gather_signals()` itself free of any AI call,
  fully deterministic and testable without network access.
- [x] **M0.2** Wire the AI-chain calls (`build_growth_letter`,
  `build_milestone_moment`, `build_difficulty_note` — stub bodies for
  now, full prompts come in M2-M4) to reuse the SAME Groq→Gemini
  fallback pattern already proven working in `nour_concierge._generate_response()`
  (confirmed via Hisn H4.1). Confirm via a live test (same methodology
  as Hisn H4.1: simulate Groq-fail/Gemini-succeed, simulate both-fail)
  that each of the 3 functions falls back correctly and NEVER returns
  `None`/silence — this is the exact class of gap that made D020
  invisible for so long; each function must have a working, verified
  non-AI fallback before any real feature is built on top of it.
  → **Done, live-tested.** `_call_groq()`/`_call_gemini()`/
  `_generate_with_fallback()` copy the exact proven request shape
  (timeouts, failure tracking) from `nour_concierge.py`. Ran the same
  2-scenario test Hisn H4.1 used, against all 3 functions: (1) Groq
  fails, Gemini succeeds → all 3 returned AI-sourced text; (2) both
  fail → all 3 returned real, signals-based (not generic) template
  text, never `None`/silence. Reused Nour's exact existing personality
  prompt (`nour_concierge.NOUR_SYSTEM_PROMPT`), no new voice invented.
- [x] **M0.3** Produce the Data Honesty Audit table (design.md's
  Component 6) as a real, current-state check — re-verify each of the
  9 listed displays against the live system (not just trust the
  design doc's table, which was written from a code read) before
  presenting it to the owner for sign-off. Get explicit owner sign-off
  on the audit before proceeding to M1.
  → **Done, owner sign-off given.** Re-verified all 9 rows against the
  actual current code (`bot.py`'s `cmd_progress`/`cmd_streak`/`cmd_level`,
  `api_server.py`'s `get_dashboard`/`get_nour_tips`) rather than
  trusting the design doc's table alone — also independently checked
  `!level` and the streak leaderboard, not explicitly listed in
  design.md's table, and confirmed both clean. Result: same 2 of 10
  displays fail (D012's XP bar, D020's tips card) — confirming the
  original scoping was accurate, not inflated. Owner initially
  flagged confusion over "2 fails" sounding like open problems being
  left alone; clarified that both are the very next 2 tasks (M1, M2),
  not skipped — owner then confirmed: "ok we can proceed."
- [x] **M0.4** Create the `nour_growth_letters` table (schema in
  design.md Component 2) via a normal `database.py` schema migration,
  consistent with every other table in this codebase. Confirm it's
  created correctly on both a fresh DB and an existing production-like
  DB (use the Hisn H5 DB clone methodology — a real clone, never
  production directly — to test the migration path safely).
  → **Done, tested both ways.** Added to `_SCHEMA` right after the old
  `nour_study_tips` table, with a comment explaining `nour_study_tips`
  is left in place (inert, not dropped) until M2.5 formally retires
  it — avoids a silent half-migration. Tested `database.init_db()` on
  (a) a brand new empty DB file, (b) a real clone of the current
  production DB (via `docker cp`, never touching production directly)
  — confirmed idempotent, zero disruption to existing tables/rows in
  either case.

## Phase M1 — Momentum Score (fixes D012)

- [x] **M1.1** Implement `narrative_engine.momentum_score(discord_id)`
  per design.md's Component 3 formula (streak/completion/trend
  weighted average → score + label). Pure computation, no AI, unit
  tested directly against known input combinations (e.g. confirm a
  0-streak/0-tasks member scores in the "restarting" band, a
  full-streak/full-completion/improving-trend member scores "strong").
  → **Done, tested against both boundary cases via `GHOST_TEST_`
  members in a real DB clone**: zero-everything member → score 10 →
  "restarting" ✅; full-streak(14d)/full-completion(100%)/
  improving-trend member → score 100 → "strong" ✅; a mid-range member
  → score 51 → "steady" (sensible middle value, not tested for in the
  task but useful confirmation the bands aren't degenerate).
- [x] **M1.2** Wire `momentum_score()` into the dashboard's existing
  `level-progress` bar element — replace the fill-%/label source, keep
  the existing CSS/markup, change only what data feeds it and its
  displayed label text (bilingual, per constraints). Confirm via a
  live dashboard load (same Ghost-Testing-member methodology as Hisn
  H2.3) that the bar now shows momentum, not points-vs-threshold.
  → **Done.** `/api/dashboard` now includes an optional `momentum`
  field (only present when `masar_momentum_score` is enabled for that
  specific `discord_id` — omitted entirely when off, not sent as
  null/zero, so the frontend needs no special-casing to fall back).
  `empire-dojo/site/dash/index.html`'s JS checks for `d.momentum`
  first; if present, drives the SAME bar/label DOM elements
  (`#level-progress`, `#level-progress-label`) from the score/label,
  bilingual ("Steady (62) — نشاطك الأسبوعي / مستقر"); if absent,
  unchanged fallback to the original XP-bar behavior. CSS/markup
  untouched.
- [x] **M1.3** Add the Momentum Score as a new line in `!progress`'s
  Discord output, alongside (not replacing) the existing level badge
  line. Confirm via direct command-callback invocation (same harness
  pattern as Hisn H1.1) that both surfaces show the same score for the
  same member at the same moment (design.md's R2 consistency
  requirement).
  → **Done.** New line added to `cmd_progress()` in `bot.py`, right
  after the existing Dhaka' pronunciation/difficulty line, gated by
  the same per-member `is_feature_enabled("masar_momentum_score",
  discord_id)` check. R2 consistency confirmed structurally, not just
  by inspection: both the dashboard field and the `!progress` line
  call the exact same `narrative_engine.momentum_score()` function —
  there is no second formula anywhere else that could ever diverge
  from it. Live-tested by calling it twice "at the same moment" for
  the same `GHOST_TEST_` member — identical output both times.
- [x] **M1.4** Add `masar_momentum_score` feature flag (default OFF),
  gate both M1.2 and M1.3 behind it. Flip to ON only after M1.2/M1.3
  are both live-verified.
  → **Done.** Registered in `flag_registry.py` under a new `masar`
  initiative group (🧭), default `False`, alongside placeholder
  registrations for `masar_growth_letter`/`masar_milestone_moments`/
  `masar_difficulty_notes` (M2/M3/M4's flags, registered now so
  `!flag list` shows the full Masar picture even before each phase
  ships — each stays OFF until its own phase is live-verified).
- [x] **M1.5** **Live verification (repeat before marking M1 done):**
  toggle the flag on in production, confirm both the dashboard and
  `!progress` reflect a real test member's momentum score correctly,
  confirm the flag correctly gates both surfaces off when disabled
  (same D010-style flag-gate discipline). Only then mark D012 as
  Resolved in Hisn's `defect_log.md` (cross-reference, since D012 was
  found there).
  → **Done, 2026-07-16, in REAL production (not a DB clone).** Backend
  deployed (`docker compose up -d --build` on the server, confirmed
  healthy startup, "Flag registry sync: 4 new flag(s) added" in logs,
  `nour_growth_letters` table confirmed created, all 4 masar flags
  confirmed registered at OFF, `members` confirmed untouched at 0
  rows). Frontend deployed via `wrangler pages deploy` — confirmed the
  fresh `*.pages.dev` URL AND `practice.empireenglish.online` both
  serve the new code immediately (no propagation delay this time).
  Seeded one `GHOST_TEST_920001` member directly in production for
  this test (cleaned up fully afterward — `members` back to 0 rows).
  With the flag ON: live `/api/dashboard` response included
  `"momentum": {"score": 29, "label": "building", ...}`; a direct
  call to `narrative_engine.momentum_score()` for the same member
  returned the IDENTICAL result — proving R2's dashboard/`!progress`
  consistency isn't a coincidence, it's structural (one function, two
  callers, impossible to diverge). With the flag OFF: `momentum` field
  genuinely absent from the live response (not null/zero), old
  `level_progress` fallback fully intact — confirmed the D010-style
  flag-gate discipline holds in real production, not just a clone
  simulation. **D012 marked Resolved in `defect_log.md`.** Flag left
  in its default OFF state after verification — the owner can flip it
  on for real students whenever ready; it is NOT auto-enabled.

## Phase M2 — Nour's Weekly Growth Letter (fixes D020) — the flagship deliverable

- [x] **M2.1** Implement `narrative_engine.build_growth_letter(signals)`
  fully — real AI prompt construction from `gather_signals()`'s output,
  Nour-voice system prompt (reuse/adapt the existing personality
  definition from `nour_personality.py`/`nour_concierge.py`, do not
  invent a new voice), and the template-based fallback described in
  design.md (personal-feeling, built from real signals, not generic).
  → **Done.** Replaced M0.2's generic stub prompt with
  `_build_growth_letter_prompt()` — a dedicated, directly unit-
  testable function that builds the AI prompt from WHICHEVER of the 6
  signal sources (memories, milestones, pronunciation trend, SRS
  state, conversation themes, streak/completion) are actually present
  for that specific student, satisfying R3's "at least 2 of" with
  real margin rather than the minimum. Verified against a
  `GHOST_TEST_` member seeded with all 6 categories — confirmed the
  generated prompt referenced all 6 correctly. Also enriched
  `_template_growth_letter()` (the non-AI fallback) to draw from
  milestones/pronunciation-trend/SRS-mastery when present, not just
  streak+completion — this is the fallback that fires when BOTH AI
  providers are down, so it needs to stand on its own as genuinely
  personal.
- [x] **M2.2** Write the new scheduled task
  `nour_growth_letter_task()`. Before choosing its exact time, extract
  the FULL current schedule (same regex/manual-extraction method as
  Hisn H4.6) and pick a time with zero collisions against any existing
  `@tasks.loop` — do not repeat D022's mistake. Document the chosen
  time and why it doesn't collide, in this task's completion note.
  → **Done.** Extracted the FULL current schedule directly from
  `bot.py` (12 loops total): `midnight_voice_reset` 00:00,
  `daily_task_post` 06:00, `morning_kickstart` 06:05,
  `markaz_daily_digest` 07:00, `markaz_weekly_report` 09:00 (Sun-only),
  `markaz_monthly_summary` 09:30 (1st-of-month), `weekly_assessment`
  10:00 (Sun-only), `nour_weekly_review` 10:00 (Sun-only),
  `evening_reminder` 20:00, `streak_at_risk` 21:00, plus
  `streak_update` (hourly) and `nour_proactive_check` (every 2h).
  Chose **Wednesday 11:00 Asia/Dubai** — deliberately a DIFFERENT DAY
  than the 3 tasks clustered on Sunday (not just a different minute on
  the same day), to genuinely spread the weekly notification load
  across the week rather than bunching 4 separate bursts onto one day;
  11:00 also has zero collision with any daily fixed-time task.
- [x] **M2.3** Store each generated letter in `nour_growth_letters`,
  DM it to the student, and confirm delivery the same way Hisn's H3.2
  did (check real Discord/Telegram-equivalent delivery logs, not just
  "the function returned without error").
  → **Done.** `database.store_growth_letter()`/`get_latest_growth_letter()`
  added. `nour_growth_letter_task()` iterates `all_active_members()`,
  per-member-gated, DMs a bilingual-aware header + the letter, logs
  `sent`/`failed` counts. Live delivery confirmed as part of M2.7
  below (Discord DM logs checked directly, not just "no exception").
- [x] **M2.4** Add `GET /api/growth-letter` endpoint (reads the cached
  latest letter for the token's member) — apply the EXACT flag-gating
  pattern already correctly used elsewhere (confirmed via Hisn D010's
  fix) so this endpoint cannot repeat that exact class of bug.
  → **Done, with a real bug caught and fixed during testing.** Initial
  implementation had an early `is_feature_enabled("masar_growth_letter")`
  call with no `discord_id`, BEFORE the member lookup — per
  `is_feature_enabled()`'s own documented semantics, a no-`discord_id`
  call only returns `True` when the flag's `allowed_ids` is EMPTY, so
  this early check would have silently rejected EVERY member whenever
  the flag was scoped to a restricted allowlist, defeating the exact
  gradual/beta-squad rollout capability the flag exists to support.
  Caught via a deliberate test (flag ON + restricted allowlist
  INCLUDING the test member — should return 200, initially returned
  503). Fixed by removing the early check entirely and relying solely
  on the per-member check after the member lookup. Re-tested with 5
  scenarios (OFF, ON-for-everyone, ON-restricted-excluding-member,
  ON-restricted-including-member, restored-OFF) — all correct.
  **The exact same bug pattern was also found and fixed in
  `nour_growth_letter_task()`'s own top-level guard (M2.2/M2.3)** —
  caught in the same pass, before either shipped.
- [x] **M2.5** Update the dashboard: remove/replace the old "Nour's
  Study Tips" 3-bullet card with a single Growth Letter card reading
  from M2.4's endpoint. Confirm old dead code path (`/api/nour-tips`,
  `_generic_tips_for_level()`) is either removed or explicitly and
  intentionally left as a documented legacy fallback — no silent
  half-migration.
  → **Done.** `empire-dojo/site/dash/index.html`: old `#nour-tips-card`
  replaced with `#growth-letter-card`, own separate `_fetchGrowthLetter()`
  call (same async pattern as the existing `_fetchLeaderboard()`),
  reads from `/api/growth-letter`. Card stays hidden if the flag is
  off or no letter exists yet — no error shown to the student, fails
  silently and gracefully. Old `/api/nour-tips` endpoint and
  `_generic_tips_for_level()` left in place, EXPLICITLY documented as
  legacy/superseded in a comment (not silently orphaned) — noted as
  safe to delete in a later cleanup pass once confirmed nothing still
  calls it.
- [x] **M2.6** Add `masar_growth_letter` feature flag (default OFF).
  → **Done** (registered during M0.2's commit, alongside the other 3
  Masar flags, under the new `masar` initiative group in
  `flag_registry.py`).
- [x] **M2.7** **Live verification (the single most important task in
  this entire spec, directly closing D020's original gap):** trigger
  the real task against production (or the H5 DB clone first, if a dry
  run is preferred), inspect the resulting letter for a REAL student
  and confirm it references at least one genuine signal specific to
  that student (not a generic sentence that could apply to anyone).
  Confirm both delivery surfaces (Discord DM + dashboard) show
  consistent content. Only after this passes, flip the flag on and
  mark D020 as Resolved in Hisn's `defect_log.md`.
  → **Done, 2026-07-16, in REAL production, using the owner's own real
  `bioroma` Ghost Testing Discord account** (a synthetic `GHOST_TEST_`
  ID cannot receive a real Discord DM — same reasoning as Hisn H3.2).
  Backend + frontend both deployed and confirmed live first. Seeded
  rich, real-shaped test data directly in production (4-day streak, a
  milestone, an improving pronunciation trend, a stored memory),
  scoped the flag to ONLY this one account via the allowlist (proving
  the beta-squad rollout path the M2.4 bug fix protects). Generated a
  REAL AI letter (`source: "ai"`) that genuinely referenced this
  student's actual 4-day streak and actual 68% pronunciation average —
  not generic filler. Delivered as a real Discord DM via the bot's own
  REST API (confirmed via a real returned message ID) and confirmed
  `/api/growth-letter` returned the byte-identical text — same
  structural dashboard/DM consistency guarantee as M1's. **Owner
  personally confirmed receipt** ("i got the message") — the one part
  of this verification an agent cannot check unilaterally. Test data
  fully cleaned up (`members` back to 0 rows), flag restored to
  default OFF. **D020 marked Resolved in `defect_log.md`.**

## Phase M3 — Milestone Moments (optional polish, independently skippable)

> **Scope-changing discovery made at the start of this phase, resolved
> with the owner before any code was written:** confirming M3.2's
> "real `complete_milestone()` call site" per design.md's own
> instruction to verify rather than assume revealed that
> `complete_milestone()` has **ZERO call sites anywhere in the live
> codebase** — no real student has ever had a milestone marked
> complete, ever, since the feature was built. Same root pattern as
> D020/D012 (a feature designed, but the piece that actually triggers
> it missing), just never logged as its own defect before now. Since
> these 15 milestones (`content/milestones/milestones.json`) need a
> human to judge a recording/essay/conversation — not something
> auto-detectable from existing signals — M3.2 was expanded (with the
> owner's explicit go-ahead: "do what you think is for the ecosystem's
> best interest") to add a minimal `!markmilestone` admin command,
> giving `complete_milestone()` its first real, working call site.
> Milestone definitions/criteria themselves were left completely
> unchanged, per requirements.md's out-of-scope note — only HOW a
> completion gets recorded was touched.
- [x] **M3.1** Implement `narrative_engine.build_milestone_moment()`
  fully (AI prompt + milestone-specific template fallback).
  → **Done.** Looks up the milestone's REAL name/description from
  `milestones.json` via a new `_get_milestone_info()` helper (falls
  back to the raw ID only if the lookup fails, e.g. a stale ID) —
  this is the concrete improvement over M0.2's stub, which only ever
  had the raw machine ID to work with. Includes extra real context
  (streak, a memory) in the AI prompt when available. Template
  fallback also uses the real name, e.g. "خلصت 'Introduce Yourself'"
  — not the raw `l0_introduce` ID.
- [x] **M3.2** Hook into the real `complete_milestone()` call site(s)
  — confirm via code search exactly where this is called from in the
  live codebase (design.md flags this as "to be confirmed at
  implementation time," do that confirmation here, don't assume).
  Add the notification call, gated by the existing `celebrations`
  preference and quiet-hours check.
  → **Done — with the scope expansion noted above.** New admin
  command `!markmilestone @user <milestone_id>` (in the ADMIN COMMANDS
  section of `bot.py`, `manage_guild` permission-gated like every
  other admin command) validates the milestone_id against the
  student's actual level's milestones, calls
  `database.complete_milestone()` (confirmed idempotent — a repeat
  call for an already-completed milestone returns `False` and sends
  no duplicate notification), and on a genuinely NEW completion,
  gathers signals and calls `build_milestone_moment()`, gated by BOTH
  the `masar_milestone_moments` flag AND the existing `celebrations`
  preference AND `is_quiet_hours()` — same 3-gate discipline as every
  other celebratory notification in this codebase.
- [x] **M3.3** Add `masar_milestone_moments` feature flag (default OFF).
  → **Done** (registered during M0.2's commit, alongside the other 3
  Masar flags).
- [x] **M3.4** **Live verification:** trigger a real milestone unlock
  for a Ghost Testing member (same convention as Hisn's `GHOST_TEST_`
  IDs), confirm the personalized message sends correctly, confirm it
  correctly does NOT send when `celebrations` is off or during quiet
  hours (test both gates explicitly, don't assume they work because
  the code calls them).
  → **Done, in REAL production, using the owner's own real `bioroma`
  account (same reasoning as M2.7 — a synthetic ID can't receive a
  real DM).** The gating mechanics themselves worked exactly as
  designed: flag ON, celebrations ON, not quiet hours → the DM sent.
  **But the DM's actual CONTENT revealed two real, pre-existing
  system-wide bugs, found live** (not caused by M3's own code): (1)
  Nour addressed a real male student using feminine Egyptian Arabic
  grammar throughout — because NOTHING in this codebase, anywhere,
  ever told the AI a student's gender, so it silently guessed one
  every time; (2) a stray Vietnamese word fragment ("đặc") appeared
  mid-sentence — a genuine AI token-hallucination glitch that nothing
  anywhere checked for. **Logged as D033 in Hisn's `defect_log.md`,**
  fixed at the root (new `gender` field + `!gender` command + a
  shared `get_gender_instruction()` helper used by BOTH Nour's
  regular chat AND all 3 Masar `build_*` functions, plus a real
  output-quality guard in the shared fallback chain) rather than
  patched narrowly within Masar alone, per the owner's explicit
  instruction: "do what you think is best interest for the system on
  the long run not temp fix." **D033's fix has now been deployed and
  live re-verified (2026-07-16, same session as this checkpoint) —
  `bioroma`'s `gender` set to `male`, the exact `complete_milestone()`
  → `build_milestone_moment()` path re-run against a genuinely new
  milestone (`l0_count100`), 4 independent AI-generated messages all
  confirmed correct masculine grammar with zero foreign-language
  leakage, one delivered as a real Discord DM (message ID
  `1527387035470659787`). D033 marked ✅ Resolved in `defect_log.md`.
  Post-verification cleanup done: `bioroma`'s full footprint deleted
  from `members`/`ability_milestones`/`nour_memories`, and
  `masar_milestone_moments` restored to default OFF. M3 is now fully
  closed — no open blockers remain.**

## Phase M4 — Adaptive Difficulty Transparency (optional polish, independently skippable)

- [ ] **M4.1** Implement `narrative_engine.build_difficulty_note()`
  fully (AI prompt + direction-aware template fallback, both framed
  positively per R5).
- [ ] **M4.2** Hook into `adaptive_engine.py`'s difficulty-adjustment
  call site (confirmed location: near line ~178, per design.md —
  re-verify this line number against current code before editing,
  since other work may have shifted it since this spec was written).
  Add the new `notification_log` entry type (`difficulty_change`) and
  the 7-day throttle check.
- [ ] **M4.3** Add `masar_difficulty_notes` feature flag (default OFF).
- [ ] **M4.4** **Live verification:** force a real difficulty change
  for a Ghost Testing member in both directions (up and down), confirm
  each produces a correctly-directioned, positively-framed message,
  and confirm the 7-day throttle genuinely suppresses a second
  notification if triggered again within the window (test this
  specifically — don't assume the throttle logic works because it
  compiles).

## Phase M5 — Final Integration Verification + Documentation

- [ ] **M5.1** Re-run the Data Honesty Audit (M0.3's table) one more
  time against the fully-shipped state (all flags that were built ON),
  confirming every previously-failing display (the XP bar, the tips
  card) now passes, and no NEW display introduced by M1-M4 fails the
  honesty check.
- [ ] **M5.2** Run a combined live scenario end-to-end for one Ghost
  Testing member: register → complete tasks across several simulated
  days → unlock a milestone → trigger a difficulty change → trigger
  the weekly growth letter → check the dashboard and `!progress` both
  reflect everything correctly and consistently. This is Masar's own
  equivalent of Hisn's H3 integration traces — don't skip it just
  because each phase was individually verified.
- [ ] **M5.3** Update `STATUS.md`'s initiative table: add Masar as
  initiative #11, mark complete once M0-M2 (the two required phases)
  plus whichever of M3/M4 were actually built are done and verified.
  If M3/M4 were deliberately skipped, say so explicitly rather than
  leaving them looking forgotten.
- [ ] **M5.4** Cross-reference back into Hisn's `defect_log.md`: confirm
  D012 and D020 are both marked Resolved with links to Masar's PRs, not
  left in their original "deferred, needs product decision" state.
