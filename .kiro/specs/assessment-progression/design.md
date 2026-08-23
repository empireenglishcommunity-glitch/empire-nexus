# Design — Assessment Progression (Monthly Review + Level Advancement)

The two new layers of the assessment pyramid, building on the live Itqan
infrastructure. Professional, kind, retention-focused, production-heavy.

## Architecture principle: Reuse Itqan, extend it

Both new assessments reuse the existing infrastructure:
- Same practice-site page (`/assessment/`) with a `type` parameter
  (`weekly`, `monthly`, `advancement`)
- Same `assessment.py` engine (generate → score → deliver outcomes)
- Same `assessment_attempts` / `assessment_items` tables (with a `type` column)
- Same API endpoints (extended: `/api/assessment/start?type=monthly`)
- Same recording infrastructure, TTS, anti-cheat, timer
- Same flag/config/settings pattern

What's NEW is the content selection logic, scoring dimensions, Part B
(integrated task), and the promotion automation.

---

## Component Design

### 1. Content Selection

**Monthly Review:**
```
generate_monthly_blueprint(discord_id, level, weeks_covered=[1,2,3,4]):
  - Equal weight across all weeks_covered (not recency-biased)
  - SRS-weighted: prioritize items the student got wrong historically
  - Production-heavy: speaking + writing ≥ 50%
  - ~15-18 items, 20 min
```

**Advancement Exam Part A:**
```
generate_advancement_blueprint_a(discord_id, level):
  - Full level coverage (all weeks)
  - 5 skills × 3-4 items = ~18 items
  - SRS-weighted toward weak areas
  - 20 min
```

**Advancement Exam Part B:**
```
generate_advancement_blueprint_b(discord_id, level):
  - Single integrated task (configurable per level)
  - L0: self-introduction (60s recording)
  - L1: picture description (45s recording)
  - L2: situational prompt (60s recording)
  - L3: mini-presentation (90s recording)
  - 10 min (includes prep time + recording)
```

### 2. Scoring

**Monthly Review:**
- Single dimension: Retention Score = weighted average of item scores
- Pass: ≥ 65%
- Skill breakdown for the student (diagnostic value)
- AI grading same as Itqan (Whisper for speech, Groq for text feedback)

**Advancement Exam:**
- Part A: per-skill scores (5 skills, each 0–100%)
- Part B: 4 sub-scores × 25 = 100 (fluency, accuracy, vocab range, pronunciation)
- Overall = Part A (60%) + Part B (40%)
- Pass: overall ≥ 75% AND each skill in Part A ≥ 60% AND Part B ≥ 50%

**Part B scoring (AI-graded):**
```
Whisper transcription → Groq evaluation prompt:
  "Score this 60-second self-introduction by an L0 Arabic speaker.
   Score 0-25 on each:
   - Fluency: smoothness, pace, minimal hesitation
   - Accuracy: grammar correctness for L0 level
   - Vocabulary range: uses words from multiple topics (family, daily routine, etc.)
   - Pronunciation clarity: would a native speaker understand?
   Be kind to beginners. 15/25 per category = solid L0 performance."
```

### 3. Database extensions

```sql
-- Extend assessment_attempts with a type column (migration)
-- type: 'weekly' (default, backwards-compatible), 'monthly', 'advancement'
ALTER TABLE assessment_attempts ADD COLUMN type TEXT NOT NULL DEFAULT 'weekly';

-- Monthly review tracking
CREATE TABLE IF NOT EXISTS monthly_reviews (
    discord_id    TEXT NOT NULL,
    review_number INTEGER NOT NULL,  -- 1st, 2nd, etc. for this level
    attempt_id    INTEGER NOT NULL,  -- FK to assessment_attempts
    passed        INTEGER NOT NULL DEFAULT 0,
    retention_score REAL,
    skill_breakdown TEXT,  -- JSON: {listening: 72, vocab: 85, ...}
    reviewed_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (discord_id, review_number),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);

-- Advancement exam tracking
CREATE TABLE IF NOT EXISTS advancement_exams (
    discord_id    TEXT NOT NULL,
    level         TEXT NOT NULL,     -- the level being tested (e.g. 'L0')
    attempt_num   INTEGER NOT NULL,  -- 1, 2, 3...
    attempt_id    INTEGER,           -- FK to assessment_attempts (Part A)
    part_b_recording TEXT,           -- path/URL to the Part B recording
    part_a_score  REAL,
    part_b_score  REAL,
    overall_score REAL,
    skill_mins    TEXT,              -- JSON: per-skill scores for min check
    passed        INTEGER NOT NULL DEFAULT 0,
    attempted_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (discord_id, level, attempt_num),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
```

### 4. Flags and config

**Flags (2 new, default OFF):**
- `assessment_monthly_review` — the monthly review feature
- `assessment_advancement_exam` — the advancement exam feature

**Config (in settings, owner-tunable):**
```
PROGRESSION_CONFIG_DEFAULTS = {
    "monthly_pass_pct": 65,
    "monthly_retake_cooldown_hours": 72,
    "monthly_weeks_per_review": 4,
    "advancement_pass_pct": 75,
    "advancement_skill_min_pct": 60,
    "advancement_part_b_min_pct": 50,
    "advancement_part_a_weight": 0.6,
    "advancement_part_b_weight": 0.4,
    "advancement_retake_cooldown_days": 7,
    "advancement_time_limit_part_a_min": 20,
    "advancement_time_limit_part_b_min": 10,
}
```

### 5. Calendar integration

The calendar (`darb.build_calendar`) gains two new stop types:
- **Monthly Review stop** — appears after week 4, week 8 (for L0)
  States: locked (not enough weeklies passed) → available → passed ✅ / retake 🔁
- **Advancement Exam stop** — appears after the final week
  States: locked (need all weeklies + ≥1 monthly) → available → passed 🎓 / retake 🔁

### 6. Automatic promotion (on advancement pass)

```python
async def promote_student(discord_id, from_level, to_level):
    # 1. Update member level
    database.set_level(discord_id, to_level)  # sets level + level_started_at
    # 2. Generate certificate (reuse existing)
    # 3. DM the student (private congratulation + certificate link)
    # 4. Post to Champions (public celebration)
    # 5. Notify owner via ops channel
    # 6. Log the promotion event
```

### 7. Outcomes delivery

**Monthly pass:**
- Private DM: "🌟 مراجعتك الشهرية — نتيجتك X%! [skill radar] [trajectory]"
- Optional: Monthly Star in Champions (flag-gated)

**Monthly not-pass:**
- Private DM: "📊 مراجعتك — X%. [breakdown] [specific review list] [retake in 72h]"
- After 2 fails: owner alert

**Advancement pass:**
- Private DM: "🎓 مبروك! اتقبلت في المستوى التالي! [certificate link]"
- Public Champions post: "🎓 [name] advanced to Level 1!"
- Auto-promote

**Advancement not-pass:**
- Private DM: "📊 نتيجتك X% — محتاج 75%. [per-skill breakdown] [review in 7 days]"
- Owner notified

### 8. Part B integrated task — page UX

A new section in the assessment page for Part B:
1. Instructions screen: "You'll now record a 60-second self-introduction..."
2. Preparation timer (60s): student sees the prompt, thinks/notes
3. Recording: big Record button, 60s max, visual timer
4. Review + submit (can re-record once)
5. "Part B complete — results will be ready shortly"

Scoring is async (Whisper + Groq takes a few seconds); the page polls
for results like the existing Itqan scoring flow.

---

## Key flows

### A. Monthly Review flow
1. Student passes 4th weekly → monthly review unlocks on calendar
2. Student opens it → instructions page (Arabic-first, "this tests your memory across 4 weeks")
3. Timer starts (20 min) → 15-18 items, one at a time
4. Finish → score → outcome delivered (pass: congrats + radar; not-pass: review list)

### B. Advancement Exam flow
1. All weeklies passed + ≥1 monthly passed → advancement unlocks
2. Student opens it → two-part instructions ("Part A: skills test, Part B: speak freely")
3. Part A: 18 items, 20 min (same UX as Itqan)
4. Part B: prompt → prep time → record → submit
5. Scoring (async) → overall calculation → pass/fail determination
6. Pass → auto-promote + celebrate. Not-pass → private feedback + 7-day cooldown.

---

## Guardrails

- Both behind their own flag (OFF by default); with flags OFF = today's behavior
- Manual `!setlevel` always works (owner override path preserved)
- Retake cooldowns enforced server-side (can't circumvent via page refresh)
- Part B recordings retained 14 days (owner-only, same as Itqan recordings)
- All AI scoring: borderline → flagged, AI-error → flagged (never auto-fail)
- Graceful: if monthly not taken, student can still do daily+weekly normally;
  advancement is just locked until the monthly prerequisite is met

## Out of scope (for now)
- Live oral exam with the owner (could be a Phase N add-on)
- Cross-level comparisons / cohort ranking
- Adaptive difficulty adjustment based on monthly results (separate spec: Tatawwur)
- L1/L2/L3 Part B task design (focus on L0 first; others configurable later)
