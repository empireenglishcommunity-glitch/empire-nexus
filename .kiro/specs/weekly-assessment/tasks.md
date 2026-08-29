# Implementation Plan — Weekly Assessment ("Itqan")

## Status — BUILT, DEPLOYED AND LIVE (header added 2026-08-29)

> 🔴 **All 45 boxes below are unticked and that is WRONG — Itqan is live.** Added
> after the 2026-08-29 audit found this spec reading 0% complete while
> `empire-chronicle`'s `SYSTEM-MAP.md` §11 documents the same system as built
> across 12 owner-merged phases, deployed, live-verified, with both flags ON for
> all 16 students and 0 lockouts. **Do not rebuild any of this.**
>
> **Evidence** (verified 2026-08-29):
> - `src/assessment.py` (2,355 lines — the engine) and `src/itqan_outcomes.py`
>   (482 lines — the consequences)
> - flags `itqan_weekly_assessment` + `itqan_progression_gate` registered under
>   initiative `itqan`
> - tables `assessment_attempts`, `assessment_items`, `week_mastery`,
>   `assessment_recordings` all in `database.py`'s `_SCHEMA`
> - scheduled loops `itqan_weekly_report` + `itqan_due_nudge` in `bot.py`
> - the practice-site surface exists at `empire-dojo/site/assessment/`
>
> ⚠️ **One real discrepancy to resolve before touching this:** both flags are
> `default_enabled=False` in `flag_registry.py`, while `SYSTEM-MAP.md` §4 records
> them as **ON for all 16 students**. Flags fail closed when unset, so a restored
> database would boot with Itqan **off**. **Read the live `feature_flags` table
> first** — do not "fix" the registry from the docs or the docs from the registry.
>
> Later refinements are recorded in `SYSTEM-MAP.md` §11, not here — notably that
> `itqan_progression_gate` is now **SOFT** (it never freezes daily tasks; the old
> `gate_locked` day-freeze was removed from `darb.py`), and that abandoned or
> timed-out attempts are **voided** with no score, fail or cooldown. Anything
> below that contradicts §11 is superseded.

Build order. **Every phase is its own owner-merged PR, fully tested, and
deployed + live-verified with zero disruption to the 16 students.** Everything
is behind the `itqan_weekly_assessment` flag (OFF) until Phase 9, so nothing is
visible to students until we deliberately turn it on — and even then, to a pilot
first.

Legend: **[nexus]** = bot/API repo · **[dojo]** = practice site repo.

---

## Phase 0 — Foundations (flag + data + config) · [nexus]
- [ ] Register `itqan_weekly_assessment` flag in `flag_registry.py` (default OFF).
- [ ] Create tables: `assessment_attempts`, `assessment_items`, `week_mastery`
      (schema per design §2), with indexes.
- [ ] Add owner-tunable config keys in `settings` with defaults (thresholds,
      cooldown, spiral weight, time limit) + getters.
- [ ] Unit tests: schema creates cleanly; config defaults/overrides read back.
- **Verify:** tests green; no behavior change in prod (flag off, tables unused).

## Phase 1 — Generation engine (spiral) · [nexus]
- [ ] `assessment.generate_blueprint(discord_id, level, week)` — item budget,
      65/35 recent/prior split, prior items from SRS weak-queue, sources from
      `curriculum.py`; deterministic-per-attempt seed, re-draw per new attempt.
- [ ] Unit tests: correct split/counts; prior items favor weak queue; length
      stays bounded as week grows; reproducible per seed, differs per attempt.
- **Verify:** tests green; pure logic, nothing wired to users yet.

## Phase 2 — Scoring engine · [nexus]
- [ ] Objective scoring (listening, vocab) reusing existing verification helpers.
- [ ] Pronunciation via Whisper (reuse `pronunciation_scorer`), lenient bands.
- [ ] Speaking: Whisper transcript → AI check (target-content use + attempt),
      kind grading. Writing: Groq feedback + band.
- [ ] Two-dimension pass logic (consistency from existing tracking + mastery),
      distinction, **borderline → flagged**, **AI failure → flagged + graceful**.
- [ ] Unit tests incl. borderline flagging and AI-failure fallback (mocked).
- **Verify:** tests green.

## Phase 3 — API + attempt lifecycle (anti-cheat server side) · [nexus]
- [ ] `/api/assessment/status`, `/start`, `/item`, `/finish` (session-gated).
- [ ] Server enforcement: unlock check, one in-progress attempt, time limit,
      cooldown, pool re-draw, integrity-flag capture.
- [ ] Tests: unlock gating, cooldown, single-attempt, timer auto-finish,
      scoring end-to-end (mocked AI).
- **Verify:** tests green; endpoints reachable but flag-gated (404/again disabled
      when flag off).

## Phase 4 — Calendar unlock + marker · [nexus] + [dojo]
- [ ] `darb.build_calendar`: add per-week assessment stop + unlock rule (all 7
      days completed ≥ once) + per-week state.
- [ ] `empire-dojo` calendar render: show the assessment stop (locked → "finish
      Day X", available, mastered 🏅, not-yet 🔁).
- [ ] Tests: unlock only when all days done; states correct.
- **Verify:** tests green; deploy dojo; with flag off it shows nothing new.

## Phase 5 — The assessment page · [dojo]
- [ ] `site/assessment/` page + `js/assessment.js`: intro (Arabic + sample),
      one-at-a-time runner, timer, Kokoro audio, recording (`RecorderUI`),
      results screen with per-item feedback.
- [ ] Client anti-cheat: disable copy/paste + context menu; tab-away counting via
      Page Visibility API → sent as integrity flags.
- [ ] Verify end-to-end against a pilot/test account on the real API.
- **Verify:** manual run-through on phone + desktop; deploy dojo.

## Phase 6 — Outcomes (badge, celebrate, support, retake, re-inject) · [nexus]
- [ ] On mastered: upsert `week_mastery`, badge, post to `🏅 Week Champions`
      (create channel once; store id in config), streak/progress update.
- [ ] On not-yet: private encouraging DM + review list + cooldown; **daily tasks
      untouched**; re-inject weak items into SRS/daily queue.
- [ ] On flagged: owner notification via Empire Ops.
- [ ] Tests: correct routing (mastered/not-yet/flagged), no public non-pass,
      no daily-flow mutation on not-yet.
- **Verify:** tests green; live-verify a pass posts to Champions and a not-yet
      DMs privately.

## Phase 7 — Owner report + overrides · [nexus]
- [ ] Weekly Empire Ops summary + on-demand `!itqan` / `/itqan` (pass/not-yet/
      flagged, both scores, most-missed items).
- [ ] `!itqan-pass` / `!itqan-reset` admin commands (admin-channel-gated).
- [ ] Tests: report aggregation; overrides update `week_mastery`/attempts.
- **Verify:** tests green; live-verify report + overrides.

## Phase 8 — Motivation & progression · [nexus] + [dojo]
- [ ] Weeks-mastered streak; progress map on dashboard + calendar.
- [ ] Level-completion certificate (render via existing `html2img`, deliver via
      DM + page download).
- [ ] (Optional) champion teaching-clip invite + post.
- [ ] Tests: streak/progress math; certificate triggers only on full-level
      mastery.
- **Verify:** tests green; deploy; live-verify certificate on a completed level
      (test account).

## Phase 9 — Calibration & rollout · [nexus]
- [ ] Enable `itqan_weekly_assessment` for a **pilot allowlist** (owner/test
      account + 1–2 willing students).
- [ ] Run real weeks; tune thresholds (70/70/90) from actual results; sanity-check
      AI fairness + flag rate.
- [ ] Roll out to all 16; announce; keep the owner report as the ongoing health
      check.
- **Verify:** pilot results reviewed with owner before full rollout.

---

## Guardrails (apply to every phase)
- Full test suite green before every push; owner merges every PR.
- Deploy order when a phase spans both repos: **dojo before bot** if a client
  change could otherwise outrun the API (and vice-versa — never leave a gap that
  breaks a live student).
- Flag stays OFF through Phase 8; nothing student-visible ships until Phase 9.
- After each merge: deploy + **live-verify** (never assume green = shipped).
- Update `SYSTEM-MAP.md` and checkpoint `empire-chronicle` at the end.


---

## Phase 10 — Owner polish (post-pilot) · [nexus]
From the live pilot. Lean, non-disruptive, all owner-facing.
- [ ] Flagged Telegram alert: paste-ready `!` commands (discord id + week +
      attempt id) + clear `!` vs `/` note; add a **success log** to the flagged
      notify so sends are verifiable.
- [ ] **Manual pass celebrates (A2):** `!itqan-pass` / `/itqan-pass` notify +
      celebrate the student like an earned pass (DM + Champions + certificate if
      the level is complete).
- [ ] **`/itqan-due` + `!itqan-due`** full status report (R17.1): per student —
      current week, days-done, state (locked/due/passed/not_yet/flagged), DUE
      highlighted.
- [ ] **Arabic due-assessment nudge (R17.2):** daily job DMs DUE students once
      per due week (guarded).
- [ ] Tests (report states, due detection, nudge-once guard, manual-pass
      celebration). **Verify:** suite green; deploy; live-check the report + a
      manual pass celebrating.

## Phase 11 — Mastery-based progression gate (R16) · [nexus] + [dojo]
The one change that governs the daily flow — spec'd, gated, migrated.
- [ ] `itqan_progression_gate` config/flag (default OFF).
- [ ] `darb.build_calendar`: highest-unlocked-week = week 1 + every subsequent
      week whose predecessor is `mastered`; future weeks `gate-locked` with an
      Arabic-first reason. **Grandfather** existing students via a one-time
      baseline stamp so nobody is locked out of content already reached.
- [ ] A pass (earned or manual `!itqan-pass`) immediately opens the next week.
- [ ] dojo calendar renders the gate-locked reason ("pass Week W's test to open
      Week W+1"), bilingual.
- [ ] Tests: gate locks W+1 until W passed; pass opens W+1; grandfather baseline
      never locks reached weeks; gate OFF = today's behavior; safety valves
      (retake/override) still open progression.
- [ ] **Verify:** suite green; deploy (dojo + bot); enable for the pilot
      allowlist first; confirm no existing student is locked out; then roll out.

## Guardrails (unchanged)
- Full suite green before every push; owner merges every PR; deploy + live-verify;
  flag/gate stays pilot-allowlisted until the owner okays full rollout.
