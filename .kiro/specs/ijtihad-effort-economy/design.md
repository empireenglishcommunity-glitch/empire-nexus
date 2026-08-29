# Ijtihad — Design

> **Status: PROPOSAL — awaiting owner approval. No code written.**
> Read `requirements.md` first for the evidence and the requirements being satisfied.

---

## 1. Core idea: three currencies, not one number

The whole defect is that `total_points` simultaneously means *"how hard are you
working"*, *"what have you achieved"* and *"how long have you been here"*. Any
formula over one number will keep trading these against each other. So we split them.

| Currency | Question it answers | Lifespan | Who wins it |
|---|---|---|---|
| **Ijtihad Points (IP)** | *Are you working, now?* | **Resets every 4-week season** | Whoever works hardest this season — a 5-day-old student can lead |
| **Sijil (سجل — Record of Honour)** | *What have you accomplished?* | **Permanent, never resets** | Veterans, legitimately and exclusively |
| **Growth** | *Are you improving vs your own past?* | Rolling, personal | Anyone improving, regardless of absolute level |

This satisfies R1 and resolves the owner's tension directly: **veterans keep
everything (Sijil) without out-ranking newcomers on current effort (IP).**

---

## 2. Ijtihad Points (IP) — the seasonal effort score

### 2.1 Seasons (R2)
A season is **4 weeks**, fixed calendar windows for everyone (not per-student), so
the community shares a rhythm and boards are comparable.

```
season = (id, label, started_on, ends_on)
```

**Key architectural choice — no data migration.** Seasonal IP is *derived* by
summing `points_log` inside the season's date window. `points_log.logged_at` already
exists and is indexed. Consequences:
- No new points column, no rewriting history.
- All pre-Ijtihad points fall outside every season window, so they naturally
  become legacy-only and appear in Sijil, not in any season board.
- Fully reversible: disable the flags and `total_points` still behaves exactly as
  it does today.

### 2.2 Daily effort
```
task_ip       = BASE_IP × difficulty_mult × quality_mult
full_day_bonus = FULL_DAY_IP   (only when tasks_today >= personal_daily_target)
```

Proposed starting values (all owner-tunable in the `settings` table, per existing
Itqan/Taqdeem convention — never hardcoded thresholds):

| Parameter | Value | Note |
|---|---|---|
| `BASE_IP` | 10 | per completed task |
| `FULL_DAY_IP` | 25 | met your own target |
| `difficulty_mult` | Easy 1.0 · Standard 1.25 · Challenging 1.5 | **×1.0 when `tatawwur_adaptive` OFF** (R4) |
| `quality_mult` | 1.0 → 1.3 | **never below 1.0**; ×1.0 when no score available |

`quality_mult` is a **bonus-only** band (R4): trying and doing badly still earns
full base points. This is deliberate — punishing low scores would hit exactly the
struggling-but-persistent students we want to keep (G7).

`difficulty_mult` fixes the perverse incentive: attempting *Challenging* content
now pays 50% more, so improving is rational.

### 2.3 Personal Daily Target (PDT) — the busy-adult answer (R3, G6)
Each student has a target of **3, 5, or 7** tasks/day.
- Default **5**; set during onboarding; changeable **once per season** (life
  changes yes, gaming no).
- Meeting your target = a **Full Day** → counts for streaks, consistency, and
  `FULL_DAY_IP`.
- **Absolute IP still scales with real volume**: 7 tasks earns 70 base IP, 3 earns
  30. So a 7/7 student still out-earns a 3/3 student (G2), while the 3/3 student
  keeps dignity, streaks and consistency credit (G6).
- Raising your target raises your ceiling — ambition is rewarded, not penalised.

### 2.4 Achievement payouts (R5) — the biggest awards in the economy
| Event | IP | Sijil entry |
|---|---|---|
| Weekly mastery pass | **+150** | ✅ Week mastered |
| Weekly mastery **distinction** (≥90%) | **+250** (replaces the 150) | ✅ Distinction |
| Monthly review pass | **+300** | ✅ Review passed |
| Level promotion (A1→A2 …) | **+500** | ✅ Level earned (permanent) |

For scale: +500 for a promotion ≈ 50 tasks. Achievement finally outweighs
attendance, which is the single biggest inversion this design makes.

### 2.5 Seasonal streak bonuses (R6) — bounded, not a tenure ladder
Full-day streaks **within the season only**:

| Full-day streak | IP |
|---|---|
| 7 | +100 |
| 14 | +200 |
| 21 | +350 |
| 28 (perfect season) | +600 |

The old `{…100: 5000}` ladder disappears from the seasonal economy. Long-run
streaks are honoured permanently in Sijil instead (§3), so nothing is lost — it
just stops crushing newcomers.

**Streak freezes:** 2 per season, consumed automatically on a missed day
(announced to the student, not silent). Existing maintenance-day bridging is kept.
Rationale: loss aversion motivates, but an unforgiving streak converts one sick
day into a quit.

---

## 3. Sijil (سجل) — the permanent Record of Honour (R10, G4, decision 1)

Never resets. Never decays. Derived from data we already store, so this is mostly
a *presentation* layer rather than new accounting:

- **Legacy XP** — the student's pre-Ijtihad `total_points`, preserved verbatim and
  labelled as historical.
- **Weeks mastered** and **distinctions** (`week_mastery`).
- **Levels earned**, with dates (`advancement_exams`, `level_started_at`).
- **Longest streak ever** (`members.longest_streak` — already permanent).
- **Lifetime tasks completed** (`daily_submissions`).
- **Seasons completed**, and best season IP.

Veterans dominate this board and always will — correctly. It answers *"who has
built the most here"* while IP answers *"who is working right now."*

---

## 4. Boards (R7, R8, N3) — replace the god-board

With ~17 active students, a top-10 board names most of the community and tells
half of them they are losing. **Design rule: publish the top 3–5 only; everyone
sees their own standing privately.**

| Surface | Sorts by | Resets | Who can realistically win |
|---|---|---|---|
| **Season Effort** | Season IP | every 4 weeks | Hardest worker this season (any join date) |
| **Journey-Stage Peers** | Season IP within ±2 personal weeks | seasonal | Best among true peers |
| **Most Improved** | Growth vs own baseline | weekly | Anyone improving — often a beginner |
| **Consistency** | Current full-day streak | seasonal | The reliable, even if slow |
| **Hall of Honour (Sijil)** | Permanent achievements | never | Veterans |
| **Weekly Spotlight** | *rotating metric* | weekly | Different person almost every week |

**Journey-stage cohorts (R8).** Peers = students within ±2 of your personal week
number. Graceful degradation is mandatory at this community size:
`journey cohort (min 3 members)` → `same CEFR level` → `whole community`. Never
render a one-person ranking.

**Weekly Spotlight (G5).** Each week the bot highlights a *different* dimension —
biggest improvement · most consistent · best comeback · hardest difficulty
sustained · most weeks mastered this season · newcomer of the week. Recognition
circulates by construction instead of ossifying.

**Reform the nightly `#streak-tracker`.** Today it ranks ≥1-task streaks and names
15 students — the most public surface is the one least connected to effort, and it
is behind no flag. Change it to celebrate **who completed a Full Day today**
(a roll, not a ranking), plus top 3 full-day streaks. Same warmth, no bottom-half
shaming, and it finally measures work.

---

## 5. Growth and grit (R9, G7)

**Par (personal baseline).** `par` = trailing **median** of the student's last 14
days of daily IP (median, so one heroic or one sick day doesn't distort it).
Median needs ≥7 days of history; before that a student is surfaced through
*Newcomer of the week* instead of being excluded.

```
growth = (this_week_IP − par_week_IP) / max(par_week_IP, floor)
```

**Grit recognitions** — event-based, each fires once and is recorded in a
`recognition_log` (which also prevents duplicates):

| Recognition | Trigger |
|---|---|
| **Personal Best** | Best-ever week IP, or best score on a skill |
| **Persistence** | Retried a failed assessment **and** improved |
| **Comeback** | Returned after ≥3 days away and completed a Full Day |
| **Uphill** | Sustained Full Days while on *Challenging* difficulty |
| **Refinement** | Improving scores across ≥3 attempts at the same content type |

Crucially these are **recognition, not IP inflation** — so a weaker student is
genuinely celebrated (G7) without being placed above a stronger student on the
effort board. That was the trap in question 7, and this is how it's avoided.

---

## 6. Data model

Additive only. No destructive rewrite (R12).

```sql
seasons(id, label, started_on, ends_on)
student_targets(discord_id, season_id, target, set_at)      -- PDT, 1 change/season
streak_freezes(discord_id, season_id, used_on)
recognition_log(discord_id, kind, period_key, detail, created_at)  -- dedup + history
```

Everything else is **derived** from existing tables:
- Season IP → `SUM(points_log.points)` within the season window
- Full Day → `streaks.tasks_completed >= student_targets.target`
- Sijil → `week_mastery`, `advancement_exams`, `members.longest_streak`,
  `daily_submissions`, legacy `total_points`

`members.total_points` keeps accumulating (harmless, and it *is* Legacy XP).

---

## 7. Preconditions and engine sequencing (R11, decision 3)

**Precondition fixes, before any seasonal scoring (R11):**
1. Clamp the progress bar at ≥0 **and** stop deriving it from XP thresholds that
   progression ignores (this is what produces −40% for the best students).
2. Consolidate the **three award paths** (`tasks.process_submission`,
   `/api/complete-exercise`, `/api/practice-complete` weekly branch) into one, or
   season sums will disagree between Discord and web.
3. Resolve the dead constants: wire up (`POINTS_ASSESSMENT`, `POINTS_ADVANCEMENT`)
   or delete (`POINTS_PEER_FEEDBACK`).

**Quality-engine order — my recommendation on decision 3.** The design works with
all of these OFF (multipliers = 1.0), so none is a blocker; each is enabled as its
own decision, and each makes IP smarter:

1. **`masar_momentum_score` → turn ON early.** Already built, tested, tenure-blind.
   Zero new code. It is the honest replacement for the XP bar.
2. **`tatawwur_pronunciation`** — produces the score signal that feeds
   `quality_mult` and the improvement trend.
3. **`tatawwur_adaptive`** — produces difficulty tiers, enabling `difficulty_mult`
   and fixing the "score badly" incentive.
4. **`itqan_weekly_assessment` — a separate product decision, NOT bundled here.**
   It unlocks the achievement payouts that make §2.4 meaningful, but it introduces
   a *timed test* to students. That is a teaching change, not a scoring change, and
   deserves its own rollout and its own conversation (N5).

Until #4, achievement payouts simply have nothing to fire on — the rest of the
system still works.

---

## 8. Migration for the current 17 students (decision 4)

1. Compute each student's Sijil from existing data (nothing is written to
   `points_log`; Sijil is a read-model).
2. Preserve `total_points` verbatim as **Legacy XP**, shown in Sijil.
3. Season 1 starts with **IP = 0 for everyone** — the approved re-baseline.
4. Announce it as *addition*, not reset: "your record is permanent, and a fresh
   season starts for everyone." Veterans gain a trophy case; newcomers gain a
   winnable race.

Rollback: disable the flags. Nothing was rewritten, so the old behaviour returns
exactly.

---

## 9. How we'll know it worked (R12)

Measured before/after, from data already collected:

| Metric | Target direction |
|---|---|
| A student <14 days old appearing in any board's top 3 | should become possible and actually happen |
| Distinct students publicly celebrated per month | **up** (G5 — recognition circulating) |
| Full-Day rate per active student | **up** |
| 7-day active rate (retention) | **up or flat** |
| **Guard metric:** veteran active-days | **must not drop** — if it does, Sijil isn't doing its job |
| Median days between a student's first task and first public recognition | **down** |

---

## 10. Feature flags (R12)

All default **OFF**, all registered in `flag_registry.py` in the same commit that
creates them (per project convention), all recorded in
`empire-chronicle/docs/PRODUCTION-FLAG-STATE.md` when flipped live.

| Flag | Gates |
|---|---|
| `ijtihad_seasons` | season windows + seasonal IP accounting |
| `ijtihad_personal_target` | Personal Daily Target + Full Day definition |
| `ijtihad_streak_reform` | full-day streaks, seasonal bonuses, freezes |
| `ijtihad_boards` | the new board set + reformed `#streak-tracker` |
| `ijtihad_sijil` | Hall of Honour surface |
| `ijtihad_growth_recognition` | growth, grit recognitions, weekly spotlight |
| `ijtihad_quality_multipliers` | difficulty/quality multipliers on IP |

---

## 11. Open design questions for the owner

1. **Season length** — 4 weeks proposed. It aligns with the monthly review cadence
   (`progression_monthly_weeks_per_review = 4`). Prefer 2 weeks (faster fresh
   starts) or 6–8 (less churn)?
2. **Season naming** — numbered ("Season 3") or themed?
3. **PDT default** — 5 proposed. Should returning-from-absence students be offered
   a lower target as a soft landing?
4. **Does anything visible happen at season end** — a closing summary DM, a
   podium post, a Sijil stamp for the winner? (Recommended: yes, a Sijil stamp —
   it converts a seasonal win into permanent honour.)
5. **Do we keep `!top` as a command name** (pointing at the new season board), or
   rename to something that signals "this season"?
