# Design — Masar (مسار): Personal Growth Narrative

## Architecture: One Narrative Engine, Two Surfaces

```
                    ┌───────────────────────────┐
                    │   Existing SQLite tables   │
                    │  nour_memories             │
                    │  ability_milestones         │
                    │  pronunciation_scores       │
                    │  vocab_srs                  │
                    │  members.difficulty_level   │
                    │  nour_conversations          │
                    │  (all pre-existing, no      │
                    │   new tables for THIS data) │
                    └────────────┬────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │  narrative_engine.py (NEW)  │
                    │  - gather_signals()         │
                    │  - build_growth_letter()    │
                    │  - build_milestone_moment()  │
                    │  - build_difficulty_note()  │
                    │  - momentum_score()         │
                    │  (uses existing ai_engine /  │
                    │   nour_concierge AI chain)   │
                    └──────┬──────────────┬────────┘
                           │              │
                ┌──────────▼───┐   ┌──────▼──────────┐
                │  Discord DM  │   │  New table:      │
                │  (existing   │   │  nour_growth_    │
                │   send path) │   │  letters (cache) │
                └──────────────┘   └──────┬───────────┘
                                          │
                               ┌──────────▼───────────┐
                               │  /api/growth-letter  │
                               │  (new, reads cache)  │
                               │  /api/momentum       │
                               │  (new, computed live)│
                               └──────────┬───────────┘
                                          │
                               ┌──────────▼───────────┐
                               │  /dash/ dashboard     │
                               │  (Masar cards replace │
                               │   the old tips/XP-bar │
                               │   cards)              │
                               └───────────────────────┘
```

**Key decision: one shared "narrative engine" module, not four
separate features bolted on independently.** `narrative_engine.py` is
the single place that knows how to turn raw signals into Nour-voiced
text, reused by the weekly letter, milestone moments, and difficulty
notes alike. This avoids each feature re-implementing its own
prompt-building and its own fallback logic (the exact kind of
duplication that made D020's gap invisible for so long — nobody owned
the "does this actually run" question for the tips engine specifically).

---

## Component 1 — `narrative_engine.py` (new module, shared foundation)

### `gather_signals(discord_id) -> dict`
Pulls together everything Masar's features need from existing tables,
in one place, so every feature reads the SAME snapshot of a student's
state rather than each re-querying slightly differently:
```python
{
    "memories": [...],           # from nour_memories, most recent N
    "milestones_recent": [...],  # ability_milestones, last 14 days
    "pronunciation_trend": {...},# from pronunciation_scores, 14d
    "srs_state": {...},          # due/mastered/accuracy from vocab_srs
    "difficulty_level": int,
    "streak": int,
    "conversation_themes": [...],# recent nour_conversations, summarized
}
```
This function is the ONE place that knows how to read "everything
about this student" — reused by every feature below, and testable on
its own (unlike D020's engine, which had no generation function to
test at all).

### `build_growth_letter(signals) -> str` (R3)
Calls the existing AI chain (same Groq→Gemini pattern already used in
`nour_concierge._generate_response()`), with a prompt built from
`signals`, asking for a short (3-5 sentence), specific, warm message
in Nour's established voice. Falls back — if BOTH providers fail — to
a template-based letter built directly from `signals` (e.g. "Your
streak is now N days and you just unlocked [milestone] — that's real
progress ") rather than a generic non-personal string. This
fallback is itself personal (built from real signals, just not
AI-phrased), which is a stronger fallback than anything currently in
the codebase.

### `build_milestone_moment(discord_id, milestone_id, signals) -> str` (R4)
Same AI-chain pattern, prompted specifically about the milestone just
unlocked plus whatever signals are relevant (how long it took, related
memory). Falls back to a milestone-specific (not generic) template.

### `build_difficulty_note(discord_id, direction, signals) -> str` (R5)
Same pattern, for a difficulty change. `direction` is `"up"` or
`"down"`; the prompt/template explicitly frames both directions
positively per R5's acceptance criteria.

### `momentum_score(discord_id) -> dict` (R2)
Pure computation, no AI call needed (unlike the above three) — reads
`signals` and returns:
```python
{"score": 0-100, "label": "building"|"steady"|"strong"|"restarting",
 "basis": "7-day streak + task completion + pronunciation trend"}
```
Deterministic and fast enough to compute live on every API/`!progress`
call — no caching table needed for this one, unlike the growth letter.

---

## Component 2 — Nour's Weekly Growth Letter (R3)

### New scheduled task: `nour_growth_letter_task()`
- Runs weekly, **staggered against every existing `@tasks.loop` time**
  per the D022 lesson from Hisn (exact minute TBD at implementation
  time by checking the full current schedule table, not assumed here).
- For each active member: `gather_signals()` → `build_growth_letter()`
  → store in a new `nour_growth_letters` table → DM the student →
  (same content available to the dashboard via API, no duplicate
  generation).
- Replaces the currently-dead weekly tip generation entirely — this
  IS the fix for D020, not an addition alongside a separate patch to
  the old broken path.

### New table:
```sql
CREATE TABLE IF NOT EXISTS nour_growth_letters (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    letter_text     TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'ai',  -- 'ai' or 'template_fallback'
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    week            INTEGER NOT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_growth_letters ON nour_growth_letters(discord_id, week);
```
(This directly replaces `nour_study_tips` in practice — the old table
can be dropped or left inert once this ships; exact migration decided
at implementation time, not a requirements-level concern.)

### New API endpoint:
```
GET /api/growth-letter?token=<token>
  → { letter: "...", generated_at: "...", source: "ai"|"template_fallback" }
```
Replaces `/api/nour-tips` on the dashboard (that endpoint's D010 fix
from Hisn — the flag-gating bug — stays correct and reusable; Masar
just changes what's being served through a gated endpoint, from dead
generic tips to a real generated letter).

### Verification requirement (carries R3's "not just code-reviewed" clause):
Before this is marked complete, the task must be triggered live
against production (or the H5 DB clone, if a dry run is preferred
first) and the resulting letter inspected for: (a) it exists, (b) it
references at least one real signal from that specific student, (c)
delivery succeeded (Discord DM + dashboard both show it). This is the
exact test methodology Hisn used throughout — apply it here too,
before declaring success.

---

## Component 3 — Momentum Score replaces/clarifies the XP bar (R1, R2)

### Where it appears:
- **Dashboard** (`/dash/`): replaces the current `level-progress`
  bar's display (the bar itself can stay visually — same CSS — but its
  fill % and label now come from `momentum_score()`, explicitly
  labeled "Momentum This Week" / "نشاطك الأسبوعي", never "% to next
  level").
- **`!progress` Discord command**: same score, same label, added as a
  new line — the level badge output is unchanged (per R1's constraint
  that level itself must not be touched).

### Design choice on R1's fork (relabel vs. replace):
Chosen: **replace**, not just relabel. A relabeled-but-still-points-
based bar would still mislead by implying "more points = closer to
something," when points and level aren't actually linked (per D012's
original finding). A recency-weighted momentum score is honest about
being about THIS WEEK, not a lifetime total, and naturally resets in
a way a points bar never does — closing the exact ambiguity D012
found, not just papering over it with a new label.

### Computation (deterministic, per Component 1):
```
score = weighted_avg(
    streak_component,      # min(current_streak / 7, 1.0) * 40
    completion_component,  # (tasks_this_week / 28) * 40
    trend_component,       # pronunciation trend: improving=20, stable=10, declining=0, no_data=10
)
label = "restarting" if score < 25 else "building" if score < 50
        else "steady" if score < 75 else "strong"
```
(Exact weights are a design-time placeholder, tunable at
implementation without changing the requirement — the REQUIREMENT is
"one honest, clearly-labeled, recency-based signal," not these exact
numbers.)

---

## Component 4 — Milestone Moments (R4)

### Hook point: `database.complete_milestone()`
Currently this function only writes to `ability_milestones` and
returns a bool. Add a thin wrapper (or a call site right after,
depending on where `complete_milestone()` is actually invoked from —
to be confirmed at implementation time) that, on a genuinely NEW
unlock (not a repeat call), invokes `build_milestone_moment()` and
sends the result as a DM — gated by the existing `celebrations`
notification preference and existing quiet-hours check, per R4's
constraint.

No new table needed — `ability_milestones.completed_at` already
provides the "when" for future reference by `gather_signals()`.

---

## Component 5 — Adaptive Difficulty Transparency (R5)

### Hook point: `adaptive_engine.py`'s difficulty-adjustment call site
(the exact function that calls `database.update_member(discord_id,
difficulty_level=level)` — confirmed to exist at line ~178 in the
current codebase). Add a check: if the new level differs from the
previous level, call `build_difficulty_note()` and DM the result.

### Throttling (per R5's anti-spam acceptance criterion):
Track `last_difficulty_notification_at` per member (reuse the
existing `notification_log` table with a new `notification_type` value
`"difficulty_change"`, same pattern as every other notification type
in this codebase — no new table needed) and only send if none was
sent in the last 7 days, even if the engine adjusts more than once in
that window. The adjustment itself still happens immediately; only
the NOTIFICATION is throttled.

---

## Component 6 — Data Honesty Audit (R6)

This is a design-phase deliverable, not code. Produced as a table in
this document, reviewed with the owner before implementation begins on
Phases M2+:

| Display | Current meaning | Honest? | Action |
|---|---|---|---|
| Level badge (`!level`, dashboard) | Assessment-based skill tier | ✅ Yes | No change |
| XP/points bar (dashboard) | Raw points vs. flat threshold, implies level-up | ❌ No (D012) | Replaced by Momentum Score (Component 3) |
| Milestone grid (dashboard) | Real unlock status, `ability_milestones` | ✅ Yes | No change to the grid; unlock MOMENT gets richer (Component 4) |
| "Nour's Study Tips" card (dashboard) | Was meant to be AI-generated, never was (D020) | ❌ No | Replaced by Growth Letter (Component 2) |
| Leaderboard rank | Real, live-computed rank | ✅ Yes | No change |
| Streak counter | Real, DB-backed | ✅ Yes | No change |
| SRS due/mastered counts | Real, DB-backed | ✅ Yes | No change |
| Pronunciation trend/average | Real, computed from real scores | ✅ Yes | No change |
| `!progress` Discord output | Mirrors dashboard fields | ✅ Yes (once Momentum Score is added consistently) | Add Momentum Score line (Component 3) |

Only 2 of 9 existing displays failed the honesty check — both are
exactly D012 and D020, confirming the initial framing was correctly
scoped, not artificially inflated to justify a bigger initiative.

---

## Implementation Priority (Phases)

| Phase | What | Depends on | Risk if skipped |
|---|---|---|---|
| **M0** | `narrative_engine.py` foundation (`gather_signals`, AI-chain wiring, fallback discipline) + Data Honesty Audit sign-off with owner | Nothing new — reads existing tables only | Every later phase needs this; must be solid first |
| **M1** | Momentum Score (R1, R2) — dashboard + `!progress` | M0 | Fixes D012; lowest-risk phase (pure computation, no AI, no new scheduled task) |
| **M2** | Nour's Weekly Growth Letter (R3) — the flagship fix for D020 | M0 | The core deliverable; highest value |
| **M3** | Milestone Moments (R4) | M0 | Nice-to-have polish; independently skippable |
| **M4** | Adaptive Difficulty Transparency (R5) | M0 | Nice-to-have polish; independently skippable |
| **M5** | Live verification pass (repeat Hisn-style live testing on M1-M4, all together) + final Data Honesty Audit re-check | M1-M4 | Without this, Masar risks becoming "D020 again" — declared done without live proof |

M1 and M2 are the two REQUIRED phases (they directly resolve D012 and
D020). M3/M4 are valuable but explicitly skippable if priorities
shift — flagged as such so a future session doesn't treat their
absence as an incomplete initiative. M5 is non-negotiable: per this
whole campaign's own standing discipline, nothing is "done" until
live-verified, not just code-reviewed.

---

## Feature Flags

| Flag | Description | Default |
|---|---|---|
| `masar_momentum_score` | Enable Momentum Score on dashboard + `!progress` | OFF until M1 ships, then ON |
| `masar_growth_letter` | Enable Nour's Weekly Growth Letter (task + API + dashboard card) | OFF until M2 ships, then ON |
| `masar_milestone_moments` | Enable personalized milestone unlock DMs | OFF until M3 ships, then ON |
| `masar_difficulty_notes` | Enable adaptive difficulty transparency DMs | OFF until M4 ships, then ON |

Each phase ships behind its own flag, consistent with this codebase's
established pattern (confirmed working throughout Hisn — flags gate
new surfaces cleanly) — allows instant rollback of any one phase
without affecting the others.

---

## Explicit Non-Goals (reiterated from requirements, for design clarity)

- No new chat surface, no changes to Nour's core conversational
  personality — only new places her existing voice appears.
- No changes to milestone definitions, adaptive algorithm internals,
  or level/assessment computation.
- No new authentication, no new infrastructure, no new AI providers.
