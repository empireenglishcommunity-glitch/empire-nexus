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

## Phase 3 — Achievement payouts (the key inversion) ✅ DONE

- [x] **3.1** `ijtihad.award_week_mastery()` — 150 for a mastery pass, 250 for a
      distinction. Wired into `itqan_outcomes.deliver_outcome`, computed *before*
      the celebration so the Week Champions post can show it.
- [x] **3.2** `ijtihad.award_monthly_review()` — 300, wired into
      `monthly_outcomes.deliver_monthly_outcome` on a pass.
- [x] **3.3** `ijtihad.award_promotion()` — 500, wired into
      `advancement_outcomes._promote_and_celebrate`. The single biggest milestone
      in the programme previously awarded nothing.
- [x] **3.4** Dedup via `database.ijtihad_award_once()` + `ijtihad_already_awarded()`,
      using the same points_log reason-dedup pattern that fixed the 7×200
      streak-bonus double-award. Keys include the level (week 1 of A2 ≠ week 1 of
      A1); promotion is keyed on the level *left behind*. The mastery→distinction
      order is handled precisely: mastering (150) then later re-passing with
      distinction pays only the **100 difference**, so the week converges on 250
      and can never pay 400 — and distinction-first cannot then also collect the
      base. Both directions tested.

*Sijil entries need no separate write: Sijil is a read-model over `week_mastery`,
`advancement_exams` and `monthly_reviews`, so an achievement appears there the
moment the underlying feature records it (Phase 1 design).*

*Phase 3 result: 21 tests, full suite 2,204 passed / 2 skipped, ledger 9866/9866/0.*

**Award amounts are owner-tunable** (`ijtihad_ip_mastery` / `_distinction` /
`_monthly` / `_promotion` via `get_ijtihad_config()`), never hardcoded.

**Note on what is live:** two of the three triggers are dormant until their own
features are enabled (`itqan_weekly_assessment` and `assessment_monthly_review`
are both OFF). **Promotion is live today**, so enabling
`ijtihad_achievement_awards` makes the next real promotion pay 500.

## Phase 4 — Personal Daily Target + streak reform ✅ DONE (points deferred)

- [x] **4.1** `student_targets` (3/5/7, default 5, **one change per season**) +
      `ijtihad_get_target()` / `ijtihad_set_target()` / `ijtihad_target_is_set()`.
      Choices are deliberately coarse rather than free text: an arbitrary number
      invites optimising the denominator instead of doing the work.
      `!target` (alias `!هدفي`) views or sets it.
- [x] **4.2** Full Day = `tasks_today >= target` (`ijtihad_is_full_day`), judged
      against the target in force **that day**, so raising your target later
      cannot retroactively delete past Full Days.
      🔸 **`FULL_DAY_IP` deliberately NOT implemented here.** Adding a new
      "you finished your day" award alongside the existing `POINTS_ALL_TASKS`
      (100 at 7/7) would create two overlapping bonuses for the same idea —
      exactly the double-award inconsistency Phase 0.2 just removed. Full Day
      grants **status** (streak, consistency, eligibility) in this phase; the
      award-table restructure (BASE_IP/FULL_DAY_IP replacing 15/100) belongs in
      one coherent change, together with Phase 7's multipliers.
- [x] **4.3** `ijtihad_full_day_streak()` — consecutive Full Days.
      **Additive, not a rewrite:** `members.current_streak` and the legacy
      `_recompute_streak` are untouched, because DMs, alerts, bonuses and the
      nightly post all still read them. Two coexisting notions is deliberate — a
      gentle "you showed up" streak may exist, it just must not be what we
      publicly rank. Pinned by a test: 1 task keeps the legacy streak alive and
      leaves the full-day streak at 0.
      🔸 The **seasonal streak-bonus table** is deferred with `FULL_DAY_IP` for
      the same reason (it would overlap the live `STREAK_BONUS_POINTS` ladder).
- [x] **4.4** `streak_freezes` — 2/season, **persisted on first use** so
      recomputation is stable and a streak never flickers. Maintenance days
      bridge for free (server downtime is our fault, not the student's). Never
      spent before a streak exists. `!target` surfaces how many remain.
- [x] **4.5** Flag `ijtihad_personal_target` default **OFF**. 34 tests.

*Phase 4 result: full suite 2,238 passed / 2 skipped (+34), ledger 9866/9866/0.*

**Two real bugs the tests caught** (both genuine design gaps, not test mistakes):
1. *Streak history predates Season 1*, so a bridged day can belong to **no**
   season. The first implementation required the gap day to have a season and so
   silently ended every streak at the season boundary. Freezes are a **current**
   allowance, so such a day is now charged to the current season — otherwise
   pre-season gaps would bridge for free, without limit.
2. *Freezes were burned on prehistory* — after fixing (1) the walk marched back
   through empty days from before the student joined. A freeze now only bridges a
   **genuine gap between two worked days**: the algorithm probes the run of missed
   days and bridges only if a Full Day sits on the far side, within budget.

The freeze tests were also made date-independent; they had been implicitly
depending on which weekday the suite ran on, which is how bug (1) stayed hidden.

## Phase 5 — Boards ✅ DONE

- [x] **5.1** `!season` (alias `!الموسم`) — season effort board, capped at top 5,
      listing only students who earned something. The caller's own rank is
      appended to the reply *they* asked for rather than published in a ranked
      list naming everyone.
- [x] **5.2** `!peers` (alias `!زمايلي`) — `ijtihad_journey_peers()` compares
      students within ±2 of your **personal week number**, the fair unit under
      rolling enrolment. Degrades `journey (min 3) → CEFR level → community`,
      because a one-person "ranking" is worse than no ranking. The rendered board
      **states which scope it used** — a ranking whose basis is hidden is just a
      number someone asserts.
- [x] **5.3** `!consistency` (alias `!استمرارية`) — `ijtihad_consistency_board()`
      ranks current full-day streaks. Computed per member (a full-day streak
      depends on each student's own target and freeze history), and passes
      `consume_freezes=False`: merely **looking** at a leaderboard must never
      spend a student's allowance. A student on a target of 3 can top it.
- [x] **5.4** Nightly `#streak-tracker` reformed into a **roll**, not a ranking —
      `ijtihad_full_days_on()` + `format_full_day_roll()`. No positions, so nobody
      can appear in a losing one; a small top-3 of runs is appended for
      aspiration. The legacy path is kept verbatim for when the flag is off (it
      previously had **no flag at all**).
- [x] **5.5** Flag `ijtihad_boards` default **OFF**. 30 tests covering the cap,
      the "only students who earned something" rule, the caller-sees-own-rank
      rule, cohort degradation at N=0/1, scoped boards, the freeze-safety of
      board building, roll wording (singular/plural/empty), and discriminator
      stripping.

- [x] **5.6** *(added)* `!top` redirects to the season board with a one-line
      explanation instead of being silently redefined or removed. It has always
      meant "lifetime ranking" — the very thing that rewarded seniority over work
      — so it neither lies nor dies.
- [x] **5.7** *(added)* `!ijtihad-config` (admin) to view/set the tunables.
      Needed because the Season 1 start date must be set **before** the seasons
      flag is enabled, and hand-editing settings on the server is exactly the
      step that gets skipped or mistyped.

*Phase 5 result: full suite 2,268 passed / 2 skipped (+30), ledger 9866/9866/0.*

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
