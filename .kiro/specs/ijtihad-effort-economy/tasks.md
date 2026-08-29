# Ijtihad — Implementation Plan

> **Status: NOT STARTED — awaiting owner approval of `requirements.md` +
> `design.md`. No code has been written. Nothing below has begun.**
>
> Ordering rationale: Phase 0 removes defects that would corrupt seasonal maths;
> Phase 1 is purely additive and safe (it only *reads* existing data), so veterans
> gain their honour track **before** anything resets. Effort seasons come after
> that, so no student ever experiences a reset without first seeing their record
> preserved.

---

## Phase 0 — Preconditions (no behaviour change, no flag needed)

- [ ] **0.1** Clamp the dashboard progress bar at ≥0, and stop deriving it from
      `CEFR_XP_THRESHOLDS` (which real progression ignores). Fixes the negative
      bar shown to the fastest-advancing students. Regression test for a promoted
      student with low lifetime points.
- [ ] **0.2** Consolidate the three award paths (`tasks.process_submission`,
      `/api/complete-exercise`, `/api/practice-complete` weekly branch) into one
      awarding function, preserving today's amounts exactly. Tests proving Discord
      and web award identically.
- [ ] **0.3** Resolve dead constants: wire up `POINTS_ASSESSMENT` +
      `POINTS_ADVANCEMENT` (Phase 3 uses them) and delete `POINTS_PEER_FEEDBACK`.
      No third state between feature and dead code.
- [ ] **0.4** Enable `masar_momentum_score` (already built + tested; tenure-blind).
      Owner flips the flag; record in `PRODUCTION-FLAG-STATE.md`.

## Phase 1 — Sijil, the Record of Honour (additive, read-only)

- [ ] **1.1** Read-model computing Legacy XP, weeks mastered, distinctions, levels
      earned, longest-ever streak, lifetime tasks. Pure reads — writes nothing.
- [ ] **1.2** `!sijil` (+ Arabic alias) rendering a student's own record.
- [ ] **1.3** Hall of Honour surface (top permanent achievements).
- [ ] **1.4** Flag `ijtihad_sijil`; tests incl. a brand-new student (empty record
      must render gracefully, never an error or an insulting blank).

## Phase 2 — Seasons and Ijtihad Points

- [ ] **2.1** `seasons` table + season resolution helpers (current season, window
      for a date, boundaries).
- [ ] **2.2** Season IP derived by summing `points_log` within the window. No
      schema change to `points_log`; no history rewrite.
- [ ] **2.3** `BASE_IP` / `FULL_DAY_IP` and all multipliers as owner-tunable
      `settings` rows (never hardcoded), mirroring the Itqan/Taqdeem convention.
- [ ] **2.4** Flag `ijtihad_seasons`; tests for season rollover, a student joining
      mid-season, and a season with zero activity.

## Phase 3 — Achievement payouts (the key inversion)

- [ ] **3.1** Award IP + Sijil entry on weekly mastery pass / distinction.
- [ ] **3.2** Award IP + Sijil entry on monthly review pass.
- [ ] **3.3** Award IP + permanent Sijil entry on level promotion.
- [ ] **3.4** Dedup guarantees (an achievement pays once, ever) with tests —
      mirroring the existing streak-bonus dedup pattern.

## Phase 4 — Personal Daily Target + streak reform

- [ ] **4.1** `student_targets` (3/5/7, default 5, one change per season).
- [ ] **4.2** Full Day = `tasks_today >= target`; `FULL_DAY_IP` on Full Days.
- [ ] **4.3** Full-day streak computation replacing the ≥1-task rule, with the
      seasonal bonus table.
- [ ] **4.4** `streak_freezes` (2/season), consumed automatically and **announced**
      to the student, never silently.
- [ ] **4.5** Flag `ijtihad_personal_target` + `ijtihad_streak_reform`. Tests:
      target 3 met = Full Day; 3 of target 7 = not; freeze consumption; existing
      maintenance-day bridging still honoured.

## Phase 5 — Boards

- [ ] **5.1** Season Effort board (top 3–5 only; own standing shown privately).
- [ ] **5.2** Journey-Stage peer view with degradation
      `journey cohort (min 3) → CEFR level → whole community`.
- [ ] **5.3** Consistency board (full-day streaks).
- [ ] **5.4** Reform nightly `#streak-tracker`: celebrate today's Full Days as a
      roll + top 3 streaks; stop naming the bottom half. **Put it behind a flag**
      (it currently has none).
- [ ] **5.5** Flag `ijtihad_boards`. Tests for tiny cohorts (N=0,1,2) and for the
      "never publish bottom half" rule.

## Phase 6 — Growth, grit, spotlight

- [ ] **6.1** Par = trailing 14-day median daily IP; growth = weekly delta vs par.
- [ ] **6.2** Most Improved board (requires ≥7 days history; newcomers routed to
      Newcomer of the Week instead of being excluded).
- [ ] **6.3** `recognition_log` + the five grit recognitions (Personal Best,
      Persistence, Comeback, Uphill, Refinement), each firing once.
- [ ] **6.4** Weekly Spotlight rotating its metric each week.
- [ ] **6.5** Flag `ijtihad_growth_recognition`; tests proving recognitions are
      independent of absolute skill (a low-scoring persistent student is eligible).

## Phase 7 — Quality multipliers (as engines come online)

- [ ] **7.1** `difficulty_mult` from `adaptive_engine` tiers; ×1.0 when
      `tatawwur_adaptive` is OFF.
- [ ] **7.2** `quality_mult` bonus band (1.0→1.3, **never below 1.0**) from
      pronunciation/assessment scores; ×1.0 when unavailable.
- [ ] **7.3** Flag `ijtihad_quality_multipliers`; tests proving graceful ×1.0
      degradation with every engine OFF.

## Phase 8 — Migration, launch, measurement

- [ ] **8.1** Dry-run report: every current student's computed Sijil + what their
      Season 1 start looks like. Owner reviews **before** anything goes live.
- [ ] **8.2** Bilingual announcement framing this as *addition, not reset*:
      permanent record + a fresh, winnable season.
- [ ] **8.3** Capture baseline values for the §9 metrics before enabling.
- [ ] **8.4** Staged enable: owner-only beta (per-member allowlist) → whole
      community, recording each flip in `PRODUCTION-FLAG-STATE.md`.
- [ ] **8.5** Review after one full season against §9, explicitly including the
      guard metric (veteran active-days must not drop).

---

## Decisions still needed before Phase 2

See `design.md` §11: season length (4 weeks proposed), season naming, PDT default
(5 proposed), season-end ritual, and whether `!top` keeps its name.
