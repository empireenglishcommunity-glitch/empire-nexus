# Requirements — Assessment Progression (Monthly Review + Level Advancement)

> **Codename: Taqdeem (تقديم)** — Arabic for "advancement / moving forward."
> The complete assessment pyramid: Daily Practice → Weekly Mastery (Itqan, live)
> → **Monthly Progress Review** → **Level Advancement Exam**. This spec covers
> the two new layers. Directory: `assessment-progression`.

## Origin

Empire English has 16 Arabic-speaking students (all L0 today) doing a 7-task
daily loop + a weekly mastery test (Itqan, live since session 33). The weekly
test proves "did you learn THIS week" — but a dangerous gap exists: a student
can pass 8 weekly tests one-by-one yet forget week 1 content by week 8. That's
the **retention problem**. And advancement from L0→L1 is currently manual
(`!setlevel`) with no objective gate — the owner decides by feel.

The owner wants:
- A **Monthly Progress Review** that catches retention gaps before they compound
- A **Level Advancement Exam** that makes "Empire English Level 1" mean something
  real — an objective, comprehensive, production-heavy gate that the student
  earns through demonstrated ability

Both must feel professional (like Cambridge/IELTS adapted for beginners), be
kind to learners, never break the daily flow, and give the owner actionable
intelligence.

## Constraints

1. **Zero disruption to the live daily flow.** Daily tasks, streaks, points,
   the calendar, weekly assessments — all keep working exactly as today.
2. **Budget:** same server, free/cheap AI (Groq Whisper for speech→text,
   Groq/Gemini for text feedback, Kokoro for TTS). No new paid services.
3. **Graceful degradation:** if AI/scoring is down, assessments degrade to
   template scoring + owner flag, never crash.
4. **Bilingual, Arabic-first.** All student-facing copy.
5. **Owner stays in control:** manual override for edge cases; human is the
   final authority on advancement decisions.
6. **Kind to beginners:** private not-pass; never public failure; specific
   actionable feedback; reasonable thresholds.
7. **Professional integrity:** anti-gaming (cooldowns, production-based items,
   owner notification); advancement means something real.
8. **Builds on Itqan:** reuses the existing assessment page, scoring engine,
   recording infrastructure, SRS data, curriculum data, and the flag/config
   pattern.

## Glossary

- **Monthly Review:** a retention-focused assessment that fires after every 4
  weekly assessments passed. Diagnostic + trajectory, not a daily-task gate.
- **Advancement Exam:** the definitive level-up gate. Two parts: structured
  skills + an integrated production task.
- **Retention Score:** single-dimension 0–100% measuring how well a student
  retained content from earlier weeks (SRS-weighted).
- **Integrated Task:** a real-world production scenario (Part B of the
  advancement exam) — e.g. a 60-second self-introduction recording.
- **Skill minimum:** the per-skill floor (60%) that must be crossed on the
  advancement exam (no zero-skill advancement).

---

## Requirements — Monthly Progress Review

### R1 — Trigger and unlock
**User story:** As a student, I want the monthly review to appear naturally
after I've proven myself across 4 weeks, not on an arbitrary calendar date.

Acceptance criteria:
1. THE SYSTEM SHALL unlock a Monthly Review after the student passes their
   **4th, 8th** (etc.) weekly assessment — i.e. after every 4 Itqan passes.
2. THE SYSTEM SHALL show the Monthly Review as a distinct stop on the calendar
   (separate from weekly tests), labeled clearly ("مراجعة شهرية / Monthly Review").
3. THE SYSTEM SHALL NOT lock daily tasks or weekly assessments while a Monthly
   Review is pending — it is available, not mandatory for daily progress.
4. THE SYSTEM SHALL require **at least 1 Monthly Review passed** before the
   Level Advancement Exam can unlock (retention must be proven).

### R2 — Content and format
**User story:** As a student, I want the monthly review to test whether I still
remember content from all the weeks I've completed, not just the latest one.

Acceptance criteria:
1. THE SYSTEM SHALL draw items from **all weeks in the review period** with
   equal weight (not recency-biased like the weekly's 65/35 spiral).
2. THE SYSTEM SHALL bias item selection toward the student's **SRS weak items**
   (words/skills they've historically gotten wrong) — testing what they're most
   likely to have forgotten.
3. THE SYSTEM SHALL test all 5 skills, weighted toward **production** (speaking
   + writing ≥ 50% of items).
4. THE SYSTEM SHALL present ~15–18 items in **20 minutes** (longer than weekly).
5. THE SYSTEM SHALL use the same page-based experience as Itqan (practice site,
   timed, audio + recording, one item at a time).

### R3 — Scoring and output
**User story:** As a student, I want to understand exactly where I'm strong and
where I'm slipping, not just a pass/fail.

Acceptance criteria:
1. THE SYSTEM SHALL score a single dimension: **Retention Score** (0–100%).
2. THE SYSTEM SHALL pass at **65%** (lower than weekly's 70% — older content is
   harder to retain; we catch real gaps without over-punishing).
3. THE SYSTEM SHALL produce a **skill breakdown** (per-skill % for the student).
4. THE SYSTEM SHALL produce a **specific review list** (the items/weeks/days
   the student should revisit).
5. THE SYSTEM SHALL produce a **trajectory indicator** ("on track for
   advancement" / "needs attention in X skill").
6. THE SYSTEM SHALL use the same kind AI grading as Itqan (borderline → flagged
   to owner, AI-error → flagged, beginner-kindness).

### R4 — Outcomes (pass / not-pass)
Acceptance criteria:
1. ON PASS: THE SYSTEM SHALL record the Monthly Review as passed, update the
   calendar, and send a **private congratulation** with the skill radar.
   Optional: a "Monthly Star ⭐" acknowledgement in a Champions-like post.
2. ON NOT-PASS: THE SYSTEM SHALL send a **private** message with the skill
   breakdown + review list + "retake in 72 hours." Never public.
3. AFTER 2 consecutive not-passes on the same Monthly Review: THE SYSTEM SHALL
   notify the owner ("this student is struggling with retention — may need
   intervention").
4. THE SYSTEM SHALL NOT lock daily tasks or weekly assessments on not-pass.

### R5 — Owner report
Acceptance criteria:
1. THE SYSTEM SHALL provide a monthly cohort report (who's retaining, who's
   slipping, who's ready for advancement) via the owner's ops channels.

---

## Requirements — Level Advancement Exam

### R6 — Trigger and unlock
**User story:** As a student, I want to take my advancement exam only after
I've proven both weekly mastery AND monthly retention — so I know I'm ready.

Acceptance criteria:
1. THE SYSTEM SHALL unlock the Advancement Exam when the student has:
   (a) passed ALL weekly assessments for their current level (e.g. all 8 for
   L0), AND (b) passed at least **1 Monthly Review**.
2. THE SYSTEM SHALL show the Advancement Exam as a prominent stop on the
   calendar after the final week, labeled "🎓 اختبار الترقية / Advancement Exam."
3. THE SYSTEM SHALL NOT auto-start the exam — the student chooses when to take
   it (after review/preparation).

### R7 — Format: Part A (Structured Skills)
**User story:** As a student, I want the structured part to comprehensively test
everything I've learned across the entire level.

Acceptance criteria:
1. THE SYSTEM SHALL present **Part A: Structured Skills** — all 5 skills ×
   3–4 items each = ~18 items, covering the **full level** (all weeks, spiral
   weighted toward weak items).
2. THE SYSTEM SHALL time Part A at **20 minutes**.
3. THE SYSTEM SHALL use the same item types as Itqan (dictation for listening,
   recording for pronunciation/speaking, text input for writing/vocab).

### R8 — Format: Part B (Integrated Task)
**User story:** As a student, I want to prove I can actually USE English in a
real situation, not just answer quiz questions.

Acceptance criteria:
1. THE SYSTEM SHALL present **Part B: Integrated Task** — ONE real-world
   production scenario appropriate to the level.
2. For L0: THE SYSTEM SHALL use a **self-introduction recording** (60 seconds):
   "Tell me your name, where you're from, what you do, and why you're learning
   English." This covers vocabulary, grammar, pronunciation, and fluency using
   content from across all 8 weeks.
3. THE SYSTEM SHALL time Part B at **10 minutes** (includes preparation +
   recording).
4. THE SYSTEM SHALL score Part B on: **fluency** (0–25), **accuracy** (0–25),
   **vocabulary range** (0–25), **pronunciation clarity** (0–25) = 100 total.
5. For future levels (L1, L2, L3): THE SYSTEM SHALL support different integrated
   tasks (picture description, situational prompt, read-aloud + comprehension)
   — configurable per level.

### R9 — Scoring and pass criteria
Acceptance criteria:
1. THE SYSTEM SHALL combine Part A (weighted 60%) + Part B (weighted 40%) into
   an **overall advancement score** (0–100%).
2. THE SYSTEM SHALL require **75% overall** to pass (higher than weekly/monthly).
3. THE SYSTEM SHALL require a **minimum 60% on EACH skill** in Part A — no
   zero-skill advancement (a student can't advance with zero pronunciation but
   perfect vocab).
4. THE SYSTEM SHALL require **50% minimum** on Part B (the integrated task must
   be genuinely attempted, not silence).
5. IF a student passes overall but fails one skill minimum: THE SYSTEM SHALL
   treat it as not-pass with specific guidance ("overall great, but pronunciation
   needs to reach 60% — here's what to practice").

### R10 — Outcomes
Acceptance criteria:
1. ON PASS: THE SYSTEM SHALL:
   (a) **Automatically promote** the student to the next level (L0→L1, etc.).
   (b) Generate + DM a **Level Completion Certificate** (page already exists).
   (c) Post a public **🎓 Level Advancement** celebration in Champions.
   (d) Reset the student's calendar for the new level (`level_started_at`).
   (e) Notify the owner.
2. ON NOT-PASS: THE SYSTEM SHALL:
   (a) Send a **private, kind** message: overall score, per-skill breakdown,
       specific review list, "you're X% of the way there."
   (b) Enforce a **7-day cooldown** before retake (serious — not a quiz to
       retry until you luck through; gives real review time).
   (c) Notify the owner of every attempt (for 16 students, this is manageable).
3. THE SYSTEM SHALL NOT lock daily tasks or weekly assessments on not-pass.

### R11 — Anti-gaming
Acceptance criteria:
1. THE SYSTEM SHALL enforce a **7-day retake cooldown** on the advancement exam.
2. THE SYSTEM SHALL ensure Part B is **production-based** (can't be guessed or
   memorized — it's a recording of YOU speaking).
3. THE SYSTEM SHALL use a **large enough item pool** that retake Part A items
   differ meaningfully from the previous attempt.
4. THE SYSTEM SHALL notify the owner of **every advancement attempt** (pass or
   fail) — for 16 students this provides natural oversight.
5. THE SYSTEM SHALL support an owner override: `!advance @student` for manual
   promotion in special cases (the earned path is the standard, not the only path).

### R12 — Owner controls
Acceptance criteria:
1. THE SYSTEM SHALL expose commands (Discord admin + Telegram):
   - View monthly/advancement status for all students
   - Override: `!advance @student` (manual promotion)
   - Config: thresholds, cooldowns, Part B task per level
2. THE SYSTEM SHALL provide monthly cohort intelligence: who's on track, who's
   struggling, who's advancement-ready.
3. All thresholds and cooldowns SHALL be owner-tunable via settings (no redeploy).

### R13 — Graceful degradation
Acceptance criteria:
1. IF AI scoring fails during an assessment: THE SYSTEM SHALL flag the attempt
   for owner review (never auto-fail on infrastructure issues).
2. WITH all flags OFF: THE SYSTEM SHALL behave identically to today (manual
   advancement via `!setlevel` remains functional).
3. THE SYSTEM SHALL survive bot restarts mid-assessment (reuse Itqan's
   attempt-resume mechanism).

### R14 — Calendar integration
Acceptance criteria:
1. THE SYSTEM SHALL show Monthly Review stops on the calendar at the appropriate
   points (after week 4, after week 8 for L0).
2. THE SYSTEM SHALL show the Advancement Exam stop after the final week.
3. Calendar states: locked → available → in-progress → passed/not-passed.
4. THE SYSTEM SHALL integrate with the existing Itqan progression gate
   (advancement exam passed = gate fully satisfied for all weeks).
