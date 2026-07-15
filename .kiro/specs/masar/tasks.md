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

- [ ] **M0.1** Write `narrative_engine.py` with `gather_signals(discord_id)`
  — pulls from `nour_memories`, `ability_milestones` (last 14 days),
  `pronunciation_scores` (14d trend), `vocab_srs` (due/mastered/accuracy),
  `members.difficulty_level`, `members.current_streak`, and a summary
  of recent `nour_conversations` themes, into one dict. Unit-testable
  on its own (a real gap D020 had — no generation function existed to
  test at all).
- [ ] **M0.2** Wire the AI-chain calls (`build_growth_letter`,
  `build_milestone_moment`, `build_difficulty_note` — stub bodies for
  now, full prompts come in M2-M4) to reuse the SAME Groq→Gemini
  fallback pattern already proven working in `nour_concierge._generate_response()`
  (confirmed via Hisn H4.1). Confirm via a live test (same methodology
  as Hisn H4.1: simulate Groq-fail/Gemini-succeed, simulate both-fail)
  that each of the 3 functions falls back correctly and NEVER returns
  `None`/silence — this is the exact class of gap that made D020
  invisible for so long; each function must have a working, verified
  non-AI fallback before any real feature is built on top of it.
- [ ] **M0.3** Produce the Data Honesty Audit table (design.md's
  Component 6) as a real, current-state check — re-verify each of the
  9 listed displays against the live system (not just trust the
  design doc's table, which was written from a code read) before
  presenting it to the owner for sign-off. Get explicit owner sign-off
  on the audit before proceeding to M1.
- [ ] **M0.4** Create the `nour_growth_letters` table (schema in
  design.md Component 2) via a normal `database.py` schema migration,
  consistent with every other table in this codebase. Confirm it's
  created correctly on both a fresh DB and an existing production-like
  DB (use the Hisn H5 DB clone methodology — a real clone, never
  production directly — to test the migration path safely).

## Phase M1 — Momentum Score (fixes D012)

- [ ] **M1.1** Implement `narrative_engine.momentum_score(discord_id)`
  per design.md's Component 3 formula (streak/completion/trend
  weighted average → score + label). Pure computation, no AI, unit
  tested directly against known input combinations (e.g. confirm a
  0-streak/0-tasks member scores in the "restarting" band, a
  full-streak/full-completion/improving-trend member scores "strong").
- [ ] **M1.2** Wire `momentum_score()` into the dashboard's existing
  `level-progress` bar element — replace the fill-%/label source, keep
  the existing CSS/markup, change only what data feeds it and its
  displayed label text (bilingual, per constraints). Confirm via a
  live dashboard load (same Ghost-Testing-member methodology as Hisn
  H2.3) that the bar now shows momentum, not points-vs-threshold.
- [ ] **M1.3** Add the Momentum Score as a new line in `!progress`'s
  Discord output, alongside (not replacing) the existing level badge
  line. Confirm via direct command-callback invocation (same harness
  pattern as Hisn H1.1) that both surfaces show the same score for the
  same member at the same moment (design.md's R2 consistency
  requirement).
- [ ] **M1.4** Add `masar_momentum_score` feature flag (default OFF),
  gate both M1.2 and M1.3 behind it. Flip to ON only after M1.2/M1.3
  are both live-verified.
- [ ] **M1.5** **Live verification (repeat before marking M1 done):**
  toggle the flag on in production, confirm both the dashboard and
  `!progress` reflect a real test member's momentum score correctly,
  confirm the flag correctly gates both surfaces off when disabled
  (same D010-style flag-gate discipline). Only then mark D012 as
  Resolved in Hisn's `defect_log.md` (cross-reference, since D012 was
  found there).

## Phase M2 — Nour's Weekly Growth Letter (fixes D020) — the flagship deliverable

- [ ] **M2.1** Implement `narrative_engine.build_growth_letter(signals)`
  fully — real AI prompt construction from `gather_signals()`'s output,
  Nour-voice system prompt (reuse/adapt the existing personality
  definition from `nour_personality.py`/`nour_concierge.py`, do not
  invent a new voice), and the template-based fallback described in
  design.md (personal-feeling, built from real signals, not generic).
- [ ] **M2.2** Write the new scheduled task
  `nour_growth_letter_task()`. Before choosing its exact time, extract
  the FULL current schedule (same regex/manual-extraction method as
  Hisn H4.6) and pick a time with zero collisions against any existing
  `@tasks.loop` — do not repeat D022's mistake. Document the chosen
  time and why it doesn't collide, in this task's completion note.
- [ ] **M2.3** Store each generated letter in `nour_growth_letters`,
  DM it to the student, and confirm delivery the same way Hisn's H3.2
  did (check real Discord/Telegram-equivalent delivery logs, not just
  "the function returned without error").
- [ ] **M2.4** Add `GET /api/growth-letter` endpoint (reads the cached
  latest letter for the token's member) — apply the EXACT flag-gating
  pattern already correctly used elsewhere (confirmed via Hisn D010's
  fix) so this endpoint cannot repeat that exact class of bug.
- [ ] **M2.5** Update the dashboard: remove/replace the old "Nour's
  Study Tips" 3-bullet card with a single Growth Letter card reading
  from M2.4's endpoint. Confirm old dead code path (`/api/nour-tips`,
  `_generic_tips_for_level()`) is either removed or explicitly and
  intentionally left as a documented legacy fallback — no silent
  half-migration.
- [ ] **M2.6** Add `masar_growth_letter` feature flag (default OFF).
- [ ] **M2.7** **Live verification (the single most important task in
  this entire spec, directly closing D020's original gap):** trigger
  the real task against production (or the H5 DB clone first, if a dry
  run is preferred), inspect the resulting letter for a REAL student
  and confirm it references at least one genuine signal specific to
  that student (not a generic sentence that could apply to anyone).
  Confirm both delivery surfaces (Discord DM + dashboard) show
  consistent content. Only after this passes, flip the flag on and
  mark D020 as Resolved in Hisn's `defect_log.md`.

## Phase M3 — Milestone Moments (optional polish, independently skippable)

- [ ] **M3.1** Implement `narrative_engine.build_milestone_moment()`
  fully (AI prompt + milestone-specific template fallback).
- [ ] **M3.2** Hook into the real `complete_milestone()` call site(s)
  — confirm via code search exactly where this is called from in the
  live codebase (design.md flags this as "to be confirmed at
  implementation time," do that confirmation here, don't assume).
  Add the notification call, gated by the existing `celebrations`
  preference and quiet-hours check.
- [ ] **M3.3** Add `masar_milestone_moments` feature flag (default OFF).
- [ ] **M3.4** **Live verification:** trigger a real milestone unlock
  for a Ghost Testing member (same convention as Hisn's `GHOST_TEST_`
  IDs), confirm the personalized message sends correctly, confirm it
  correctly does NOT send when `celebrations` is off or during quiet
  hours (test both gates explicitly, don't assume they work because
  the code calls them).

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
