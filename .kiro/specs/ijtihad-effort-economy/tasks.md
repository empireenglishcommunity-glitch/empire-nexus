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

## Phase 0 — Preconditions (no behaviour change, no flag needed) ✅ DONE

- [x] **0.1** Clamped the dashboard progress bar at ≥0. Extracted the arithmetic
      into `api_server._level_progress()` so it is unit-testable, and documented
      that the *root* cause (promotion awarding nothing) is Phase 3's job — after
      which this bar is superseded outright. 10 tests incl. a promoted student
      with low lifetime points, every CEFR level at 0 points, the C2 top of the
      ladder, legacy L0–L3 keys and a missing level.
- [x] **0.2** `/api/complete-exercise` now routes through
      `tasks.process_submission` — the same single path as Discord `!done` and
      `/api/practice-complete`. It previously awarded points but **never called
      `update_streak`**, so the identical action scored differently on web vs
      Discord; its own spec (ecosystem-harmony W2.1) always said it should behave
      "exactly like `!done`". Verified the Dubai-date audit fix is preserved:
      `tasks.today_str()` is the canonical logging date that every reader compares
      against (per `database._today_local()`'s docstring), so this is *more*
      correct, not a regression. The `/api/practice-complete` weekly branch keeps
      its deliberate bypass (documented: logging a weekly exercise as a daily
      submission would hand out the all-7 bonus unearned).
- [x] **0.3** Deleted `POINTS_PEER_FEEDBACK` (never awarded; no peer-feedback
      award exists in the approved design). **Kept** `POINTS_ASSESSMENT` and
      `POINTS_ADVANCEMENT` with the comment rewritten so they are unawarded *by
      schedule* (Phase 3), not by neglect — the previous comment's "do not leave
      these in a third state" warning is now satisfied by an explicit decision.
- [ ] **0.4** ⏳ **OWNER ACTION** — enable `masar_momentum_score` (already built,
      already tested, tenure-blind; zero new code). Run `!flag enable
      masar_momentum_score` in Discord, then record the flip in
      `empire-chronicle/docs/PRODUCTION-FLAG-STATE.md`. Agent has no standing
      server access, so this one cannot be done from the sandbox.

*Phase 0 result: full suite 2,130 passed / 2 skipped (+17 new tests), coverage
ledger 9866/9866/0.*

## Phase 1 — Sijil, the Record of Honour (additive, read-only) ✅ DONE

- [x] **1.1** `database.sijil_record()` — read-model returning Legacy XP, weeks
      mastered, distinctions, monthly reviews passed, levels earned by exam,
      perfect (7/7) days, active days, lifetime tasks and longest-ever streak.
      Cross-level (promotion never hides history) and **writes nothing** — locked
      by a test that snapshots four tables before/after and asserts equality.
- [x] **1.2** `!sijil` (aliases `!honour`, `!honor`, `!سجل`) renders a student's
      own record, in `src/sijil.py`.
- [x] **1.3** `!hall` (alias `!قاعة-الشرف`) + `database.sijil_hall_of_honour()` —
      ranked by **weeks mastered → distinctions → levels earned**, explicitly
      *not* by points or tenure, and it excludes students with no achievement so
      it can never quietly become a seniority ladder. The board states its own
      ranking basis out loud ("not by how long anyone has been here").
- [x] **1.4** Flag `ijtihad_sijil` registered default **OFF** in the same commit.
      28 tests, including the empty state (a new student gets an encouraging
      "your record starts now" that explains *work* earns this page, never a wall
      of zeros), zero-row omission, an unknown member id, and the core inversion:
      a newcomer who masters 3 weeks outranks a 50,000-point veteran with no
      mastery.

*Phase 1 result: full suite 2,158 passed / 2 skipped (+28), ledger 9866/9866/0.
`bot.py` verified to import with both commands registered and Arabic aliases live.*

**Owner action after merge:** `!flag enable ijtihad_sijil` (then record it in
`PRODUCTION-FLAG-STATE.md`). Safe to enable immediately — it is read-only and
additive; it shows students a record they already earned.

## Phase 2 — Seasons (the accounting) ✅ DONE

> **Scope note:** Phase 2 deliberately ships **no new points maths**. Time-scoping
> alone breaks the lifetime integral that made rank ≈ tenure, so it is the
> highest-value, lowest-risk increment available — and it is fully reversible
> because no award value and no stored row changes. `BASE_IP` / `FULL_DAY_IP` /
> multipliers moved to the phases that actually consume them (4 and 7) rather
> than being added here as unused settings, which would have recreated exactly
> the "declared but never used" state Phase 0.3 just cleaned up.

- [x] **2.1** `seasons` table + resolution helpers:
      `ijtihad_ensure_seasons()` (idempotent; creates and backfills so a long
      offline gap still yields a contiguous history, never one giant window),
      `ijtihad_current_season()`, `ijtihad_season_for_date()` (pure read — never
      creates), `ijtihad_all_seasons()`. Seasons start on a **Saturday** to match
      the curriculum's own week boundary (Sat=0), and the chosen anchor is
      **persisted on first use** so boundaries can never silently shift under
      students later.
- [x] **2.2** Season effort **derived** from `points_log` date windows —
      `ijtihad_season_points()`, `ijtihad_season_leaderboard()`,
      `ijtihad_season_rank()`. No new column, no history rewrite, no second
      ledger to disagree with the first. All pre-Ijtihad points fall outside
      every window and so become legacy-only (they appear in Sijil, never on a
      season board). The board excludes anyone with zero season activity, so it
      can never publish a bottom half (R7/N3), and rank is returned for private
      display rather than published.
- [x] **2.3** ~~Moved to Phases 4 and 7~~ — see scope note. Season *length* is
      owner-tunable now (`ijtihad_season_weeks`, default 4) along with
      `ijtihad_season1_start`, via `get_ijtihad_config()`/`set_ijtihad_config()`
      mirroring the Itqan convention (blank/invalid values fall back to default;
      unknown keys are rejected so typos can't write junk settings).
- [x] **2.4** Flag `ijtihad_seasons` registered default **OFF**. 25 tests:
      Saturday anchoring, mid-week start, 4-week inclusive span, anchor
      persistence, idempotency, rollover contiguity, multi-month offline
      backfill, future anchor (no current season), invalid anchor fallback,
      inclusive window boundaries, legacy points excluded, empty/limited boards,
      inactive members excluded, missing-season tolerance, and a
      non-destructiveness check that `total_points`/`points_log` are untouched.

*Phase 2 result: full suite 2,183 passed / 2 skipped (+25), ledger 9866/9866/0.
Verified on a fresh database: Season 1 = 2026-08-29 → 2026-09-25, anchor
persisted, idempotent.*

**Headline test** (`test_a_newcomer_can_outrank_a_veteran_in_the_same_season`):
a veteran with **50,000 lifetime points** who coasts is ranked **below** a
newcomer who joined this season and worked — on the season board. That is the
owner's complaint, fixed, as an executable assertion.

**Owner decisions needed BEFORE enabling** (this is the first phase that changes
what a number *means*): the Season 1 start date, and the announcement wording.

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
