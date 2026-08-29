# Ijtihad (اجتهاد) — Effort Economy

> **Status: PROPOSAL — awaiting owner approval. No code written.**
> Initiative name: *Ijtihad* = diligent striving/effort. The point of the whole
> redesign is to reward striving, not seniority.

---

## 1. The problem, stated as arithmetic (not opinion)

The owner's observation — *"XP rewards whoever joined earlier and whoever spends
time, not whoever really works"* — is structurally true. Evidence from the code:

**Rank is a lifetime integral.** `database.leaderboard()` is
`ORDER BY total_points DESC` over `members.total_points`, a column that only ever
increases. There is no decay, no period scoping, no reset anywhere in the codebase.
Rank therefore approximates *tenure × minimum activity*.

| Student | Behaviour | Lifetime points |
|---|---|---|
| Veteran, 6 months, coasting | 2 tasks/day + accumulated streak bonuses | **~14,500** |
| Newcomer, 1 month, flawless | 7/7 every single day + streak bonuses | **~7,750** |

A newcomer doing **perfect work every day** needs roughly **10 weeks of
flawlessness** to overtake a veteran doing *the bare minimum*.
(Assumptions: `POINTS_PER_TASK=15`, `POINTS_ALL_TASKS=100`, `STREAK_BONUS_POINTS`
as configured; veteran holds a 100+ day streak.)

**Achievement pays exactly zero.** These constants exist and are **never called**
from any production module:

| Constant | Value | Reality |
|---|---|---|
| `POINTS_ASSESSMENT` | 50 | Passing the weekly mastery test awards **0** |
| `POINTS_ADVANCEMENT` | 500 | Being promoted A1→A2 awards **0** |
| `POINTS_PEER_FEEDBACK` | 15 | Never awarded |

Scoring a 90%+ distinction also awards **0**. Meanwhile pure attendance pays
105–205 points/day. **The economy cannot express "this student improved."**

**All work is worth the same.** `POINTS_PER_TASK = 15` is paid for a submission
existing. Difficulty, accuracy, score and CEFR level multiply the award by exactly
**1.0** — a C1 student writing a 200-word argument and an A1 student typing three
words both earn 15.

**Trying harder is punished.** When `adaptive_engine` promotes a student to
*Challenging*, their tasks get longer and faster — for the same 15 points as
*Easy* mode. A points-maximising student should deliberately score badly.

**Streaks reward logging in.** `_recompute_streak()` counts any day with
`tasks_completed > 0`. **One task keeps a streak alive exactly as well as 7/7.**
The nightly public `#streak-tracker` post — the most frequent public ranking in
the system, and behind no feature flag — sorts by precisely this number and names
up to 15 students.

**Streak bonuses are a tenure ladder.** `{7:200, 14:400, 30:1000, 60:2500,
100:5000}`. The day-100 bonus alone equals **333 completed tasks**. A three-week-old
student is structurally capped at 200.

**The smoking gun.** `api_server.py` computes `xp_in_level = total_points −
level_threshold` with **no zero floor**. Because promotion is exam-gated and never
awards points, a student who advances *faster than they accumulate points* — the
hardest-working, highest-scoring student — is shown a **negative progress bar**
(e.g. −40%). The system's own maths punishes excellence.

## 2. What already exists and is switched off

The cure is substantially built:

- **`narrative_engine.momentum_score()`** — `streak(40) + 7-day completion(40) +
  improvement trend(20)`. Recency-based, **completely tenure-blind**, already
  unit-tested, already rendered in `!progress` and `/api/dashboard`. Flag
  `masar_momentum_score` = **OFF**. Its own comment says it was written to replace
  the XP bar.
- **`points_log` already timestamps every award** (`logged_at`, indexed) — period
  scoping is a query, not a migration.
- **Content is already rolling-enrollment aware**: `level_anchor_iso()` /
  `member_week_number()` give every student a personal "Week N" from their own
  join date. *The curriculum already knows how to be fair across join dates;
  only the scoring doesn't.*
- Also OFF: `itqan_weekly_assessment` (the achievement engine),
  `tatawwur_pronunciation`, `tatawwur_adaptive`, `masar_growth_letter`.

## 3. Owner decisions (2026-08-29)

| # | Question | Decision |
|---|---|---|
| 1 | Veterans' history | **Honour it in a separate track** (never erased) |
| 2 | Does XP unlock anything? | **No — purely motivational** |
| 3 | Enable the quality engines? | Agent's judgement (see design §7 sequencing) |
| 4 | Re-baseline the 17 students? | **Allowed** |
| 5–7 | Public ranking / busy adults / grit | Agent's recommendation (design §4, §3.2, §5) |

## 4. Goals

- **G1** A student who works hard *this week* can be visibly recognised within
  days, regardless of join date.
- **G2** Harder and better work earns more than easier work.
- **G3** Achievement (mastery, distinction, promotion) becomes the largest reward
  in the economy, not the smallest.
- **G4** Veterans keep a permanent, prestigious record of everything they have done.
- **G5** Recognition **circulates** among students instead of ossifying around the
  same 2–3 names.
- **G6** A student who is genuinely busy can rank well by doing *their* realistic
  best consistently.
- **G7** A student with weak absolute English but real persistence gets genuine,
  visible recognition.

## 5. Non-goals (explicit)

- **N1** XP will **never** gate or unlock content. Access stays free of scoring.
- **N2** No real-world prizes or monetary value attached (per decision 2), so
  anti-gaming needs to be *reasonable*, not adversarial.
- **N3** No public ranking of the bottom half. With ~17 active students a top-10
  board names most of the community and tells half of them they are losing.
- **N4** No deletion or decay of anyone's existing history.
- **N5** Not a curriculum or assessment redesign. Enabling the weekly assessment
  is a **separate product decision** (design §7), not smuggled in here.

## 6. Requirements

### R1 — Separate the three things currently conflated
`total_points` currently means "effort", "achievement" and "seniority" at once,
which is why it fails. The system MUST track three distinct measures:
**Effort** (renewable, seasonal), **Honour** (permanent), **Growth** (personal).
*Acceptance:* each has its own surface; no single number mixes tenure with
current effort.

### R2 — Effort is seasonal
Effort resets on a fixed cadence (4 weeks). Joining mid-season MUST NOT be a
permanent handicap.
*Acceptance:* at the start of each season every active student's effort score is 0.

### R3 — Effort is measured against personal capacity
A student's daily completion credit is judged against a **Personal Daily Target**
they own, not a fixed 7.
*Acceptance:* a student whose target is 3 and who completes 3 receives full
"complete day" status for streak/consistency purposes; a student who completes 3
of a target of 7 does not. Absolute effort points still scale with real volume, so
7/7 earns more points than 3/3 (G2 and G6 both hold).

### R4 — Quality and difficulty multiply effort
Effort points MUST scale with difficulty tier and demonstrated quality when those
signals are available, and MUST degrade gracefully to ×1.0 when the relevant
engine is disabled.
*Acceptance:* with all quality engines OFF the system still functions; multipliers
are never below ×1.0 (quality is a bonus, never a penalty — trying is never
punished).

### R5 — Achievement becomes the biggest award
Passing the weekly mastery test, earning a distinction, passing the monthly review
and being promoted a level MUST each award substantial effort points **and** a
permanent Honour entry.
*Acceptance:* `POINTS_ASSESSMENT`/`POINTS_ADVANCEMENT`/`POINTS_PEER_FEEDBACK` are
either wired up or deleted — no third state between "feature" and "dead code".

### R6 — Streaks measure work, not attendance
A streak day MUST require meeting the student's Personal Daily Target, not ≥1 task.
Streak protection (freezes) MUST exist so illness or travel does not destroy
months of motivation.
*Acceptance:* a 1-task day no longer extends a full-day streak; each student has a
small number of freezes per season.

### R7 — Replace the single global board
The one lifetime board MUST be replaced by several surfaces on which different
kinds of students can lead: season effort, journey-stage peers, most improved,
consistency, and a permanent Hall of Honour.
*Acceptance:* a student in their first fortnight can legitimately top at least one
surface; no surface publicly ranks the bottom half (N3).

### R8 — Compare like with like
Peer comparison MUST be scoped by **journey stage** (personal week number), not
calendar tenure, and MUST degrade gracefully when a cohort is too small (→ level
cohort → whole community).
*Acceptance:* with 17 students and sparse cohorts, no surface renders an empty or
one-person "ranking".

### R9 — Recognise growth and grit explicitly
The system MUST detect and celebrate: personal bests, improvement over one's own
baseline, retrying after a failure and improving, and returning after an absence.
*Acceptance:* these fire independently of absolute skill, so a low-scoring
persistent student can be celebrated (G7) — via recognition, not by inflating the
effort score above stronger students.

### R10 — Veterans' legacy is preserved and honoured
Existing lifetime points, longest streaks, weeks mastered and levels earned MUST
be carried into the permanent Honour track. Nothing is deleted.
*Acceptance:* after migration every current student can see a record of everything
they achieved before the change (decision 1).

### R11 — Fix the existing defects as a precondition
The negative progress bar, the three inconsistent award paths (Discord vs
web-daily vs web-weekly), and the dead constants MUST be resolved before
period-scoped scoring is introduced, or the new boards will disagree with each
other.
*Acceptance:* one award path; progress percentages clamped ≥0; no dead points
constants remain.

### R12 — Flag-gated, reversible, measured
Every behaviour change ships behind a default-OFF feature flag registered in
`flag_registry.py` in the same commit, and the rollout defines how we will know it
worked (design §8).
*Acceptance:* the whole initiative can be switched off without a redeploy, and
existing data is never rewritten destructively.
