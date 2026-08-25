# Design — CEFR Curriculum ("Mi'yar")

Rebuild Empire English's curriculum to be **100% CEFR-aligned across six
levels (A1–C2)**, reusing the existing engine, with a **silent, zero-loss
migration** of current students as the non-negotiable safety constraint.

## Guiding principles

- **Reuse, retarget — don't rebuild.** The daily 7-task loop, practice site,
  Taqdeem assessment engine, SRS, recordings, flags/config all stay. Only the
  *content* and the *level model* change, authored to CEFR.
- **CEFR is the source of truth.** Levels = the six CEFR bands. Learning
  objectives = official can-do descriptors. Grammar/vocab = CEFR-band-anchored.
- **Never disturb the living system.** Everything new is built behind a flag
  and enabled level-by-level after the owner's approval. Migration is
  snapshotted, dry-run on a clone, verified per-student, reversible.
- **Curated + auditable.** Each level authored against official CEFR sources
  with an owner approval gate + a written alignment rationale.
- **Truth in labelling.** "CEFR-aligned", never "CEFR-certified" (see R0).

## Sources (all free / public — we build our OWN lists)

- **Council of Europe CEFR Companion Volume (2020)** — the official can-do
  descriptor scales (reception, production, interaction, mediation). Freely
  published.
- **English Grammar Profile (concepts)** — public reference for which grammar
  appears at which CEFR level. We author our own grammar descriptions.
- **CEFR-mapped vocabulary references** (Oxford 3000/5000 CEFR tags; English
  Vocabulary Profile is browsable) — used only to *decide banding*; the stored
  wordlist is our own (word, band, POS, AR gloss, pronunciation, example).

---

## The level model

### Six CEFR levels

| Code | CEFR | English name | Arabic | Weeks (proposed) |
|------|------|--------------|--------|------------------|
| A1 | Breakthrough | Beginner | مبتدئ | 10 |
| A2 | Waystage | Elementary | أساسي | 12 |
| B1 | Threshold | Intermediate | متوسط | 14 |
| B2 | Vantage | Upper-Intermediate | فوق المتوسط | 16 |
| C1 | Effective Operational Proficiency | Advanced | متقدّم | 18 |
| C2 | Mastery | Proficiency | إتقان | 20 |

Week counts anchored to CEFR guided-hour ratios (each level longer than the
last), fixed per level at design sign-off (R13).

### Level config (`config.py`)

Replace the L0–L3 `LEVELS` dict with a CEFR-keyed model (keys: `A1`…`C2`),
each carrying: `cefr`, `name`, `name_ar`, `title` (official CEFR title),
`emoji`, `color`, `weeks`, `order` (0–5). A `LEGACY_LEVEL_MAP =
{"L0":"A1","L1":"A2","L2":"B1","L3":"B2"}` supports migration + backwards reads.

`curriculum.LEVEL_WEEK_COUNTS` becomes CEFR-keyed.

---

## Content data model

Keep the existing per-week JSON shape (proven, drives the daily loop) and
**extend** it with CEFR fields. Files renamed to CEFR keys:
`data/a1_week1.json`, … `data/c2_week20.json`.

```jsonc
{
  "level": "A1",
  "cefr": "A1",
  "week": 1,
  "theme": "Greetings & Introductions",
  "can_do": [                         // NEW — the week's CEFR objectives
    {"code": "A1.SI.1", "mode": "spoken_interaction",
     "en": "Can introduce themselves and use basic greetings.",
     "ar": "يقدر يعرّف نفسه ويستخدم تحيّات بسيطة."}
  ],
  "grammar_point": {                  // NEW structured (was a bare string)
    "cefr": "A1", "title": "Present simple: to be",
    "en": "...", "ar": "..."
  },
  "phoneme_focus": "…",
  "vocabulary": [
    {"word": "hello", "cefr": "A1", "pos": "exclam",
     "arabic": "أهلاً", "pronunciation": "/həˈloʊ/",
     "example": "Hello, my name is Sara."}   // NEW example sentence
  ],
  "speaking_missions": { "Saturday": "…", … },
  "writing_prompts": [ "…" ],
  "listening": [ … ]                  // NEW explicit listening items where needed
}
```

Backwards compatibility: `curriculum.load_all()` reads both legacy (`l0_*`) and
CEFR (`a1_*`) files; a loader shim maps legacy → CEFR keys during the
transition so nothing breaks between phases.

### Can-Do descriptor library (`content/cefr/can_do.json`)

A curated, bilingual library of the official CEFR can-do descriptors, keyed by
level + mode, from which weeks draw their objectives and exams draw their test
targets. Single source of truth for "what this level means."

### Grammar syllabus (`content/cefr/grammar_syllabus.json`)

Per-level ordered list of grammar points (title, CEFR band, explanation EN/AR,
examples), authored against the English Grammar Profile concepts.

### Vocabulary bands (`content/cefr/vocab/<level>.json`)

Our own CEFR-banded wordlists per level (word, band, POS, AR, pronunciation,
example). Feeds weeks + SRS + assessments.

---

## Assessments (reuse Taqdeem, retarget to CEFR)

- **Weekly (Itqan):** tests the week's can-do objectives + that week's
  vocab/grammar. Blueprint generator reads the CEFR week file (already
  compatible — it reads vocabulary + speaking/writing).
- **Monthly (retention):** unchanged mechanism; draws across the level's weeks.
- **Level exit exam (advancement):** retargeted as the **CEFR level test** —
  Part A across the level's skills/can-dos, Part B a level-appropriate
  production task (A1 self-intro … C2 argue a nuanced position). Pass →
  certify at that CEFR level + promote.
- **Part B prompts** already scale per level (extend `_PART_B_PROMPTS` from L0–L3
  keys to A1–C2 keys, authored per CEFR production descriptors).
- **Certificate** page: show the CEFR level + can-do checklist + compliant
  wording.

No engine changes — only the content the engine reads, plus the level keys.

---

## Migration engine (the critical safety piece)

A dedicated, reversible, idempotent migration in `database.py` +
a one-shot admin command, gated + dry-runnable.

### What it does (per student)
1. **Snapshot** the member's full record (reuse `snapshot_member_data`) →
   stored in a `cefr_migration_log` table (reversible).
2. **Remap `level`** via `LEGACY_LEVEL_MAP` (L0→A1, …). All 16 are L0→A1.
3. **Preserve** everything else as-is: `level_started_at` (calendar anchor
   stays → same week position), streak, points, `week_mastery` rows (week
   numbers carry over 1:1 since A1 ≥ L0 week count), SRS, tokens, prefs.
4. **Verify**: read back the member; confirm level remapped, counters equal to
   snapshot, calendar (week,day) resolves to the same position.
5. Write a per-student line to the migration report.

### Safety protocol
- **Dry-run mode** (`migrate_to_cefr(dry_run=True)`): computes + reports every
  change without writing. Run first, owner reads the report.
- **Ghost/clone test:** run the real migration against a DB copy first; verify.
- **Idempotent:** re-running detects already-migrated members (level already
  A1–C2) and no-ops them.
- **Per-student rollback:** `rollback_cefr_migration(discord_id)` restores from
  the snapshot.
- **Timing:** run in a low-activity window; students see continuity.

### Why it's zero-loss
Because L0 maps directly to A1 and the **week number is preserved** (A1 has ≥
as many weeks as L0), a student mid-way through L0 week 5 simply continues at
A1 week 5. Weeks they already mastered stay mastered (same week numbers). New
A1 content only differs for weeks they haven't reached yet — and even there,
it's the same daily mechanism. No reset, no logout, no lost streak.

---

## Rollout sequence (level-by-level, never disturbing the live system)

```
Phase 0  Framework foundation (level model, can-do library skeleton,
         data-model extension, migration engine — all behind cefr flag, OFF)
Phase 1  Author + approve + ship A1 content (10 weeks, full skills)
Phase 2  SILENT MIGRATION of current students L0→A1 (snapshot, dry-run,
         ghost test, execute, verify) — only after A1 content is live
Phase 3  A2 content   Phase 4  B1   Phase 5  B2   Phase 6  C1   Phase 7  C2
Phase 8  CEFR placement test + certificates + level exit exams wired per level
Phase 9  Guides + transparency (can-do checklists in !progress + site)
Phase 10 Final verification + turn the cefr flag fully on
```

Each content phase = author → owner approval gate → deploy → verify.

---

## Feature flag & config

- Flag: `cefr_curriculum` (default OFF). With it off, legacy L0–L3 behaviour is
  unchanged. Turned on per-level as content ships (allowlist or full).
- Config keys (settings): per-level week counts, pass thresholds per level,
  Part B task per level — all owner-tunable.

## Guardrails / failure modes

- All flags OFF ⇒ identical to today.
- Loader reads legacy + CEFR files during transition (no gap).
- Migration: snapshot-first, dry-run, ghost-test, idempotent, per-student
  rollback, verified report. Never destructive.
- Content behind approval gate — nothing student-facing until the owner signs
  off that level.

## Out of scope (for now)

- External exam accreditation (Aptis/Linguaskill/Cambridge mapping) — a
  possible future add-on for third-party validation.
- Reading as a separate timed skill beyond current listening/vocab (can be a
  later enhancement; CEFR reception is covered via listening + vocab + can-dos).
- Live human oral examining (the AI-scored Part B stands; owner can spot-review).



---

# Phase 8 — detailed implementation design (added 2026-08-25)

> Written after direct investigation of the live code. This section is the
> buildable spec for R6 (placement), R7 (exit exams) and R8 (certificates).
> It supersedes the two-line sketch above where they differ.

## Guiding principle: criterion-referenced, not norm-referenced

CEFR is a **can-do** framework. The defensible way to "align" to it with a tiny
cohort is to assess against the level's **can-do descriptors** (criterion-
referenced), NOT to norm-rank students against each other. Every exit-exam item
and every placement task therefore traces to a `can_do.json` descriptor code
(e.g. `B1.P.3`), and passing means "demonstrated these descriptors."

## The honest validation boundary (must appear in the alignment doc + certs)

The Council of Europe's *Manual for Relating Examinations to the CEFR* has four
stages: **familiarisation → specification → standardisation → empirical
validation.** With 17 students we can do the first three rigorously and document
them; we **cannot** do the fourth — there is no sample to statistically
calibrate item difficulty or validate cut scores. Therefore:

- Item difficulty / cut scores are **expert-assigned, not empirically
  calibrated.**
- The defensible public claim is **"built to CEFR methodology, aligned by
  design, pending empirical validation"** — never "internationally certified."
- This sentence is written into `content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md`
  and the certificate footer, so no future session or marketing overstates it.

## Scope decision (explicit, so it is not read as an omission)

Phase 8 ships in **bot (empire-nexus) + practice site (empire-dojo)** — where
the students actually are (Discord + Darb). The separate **empire-oracle**
TOEFL/IRT product is **intentionally not integrated** this phase, because:
1. it is a standalone deployed app with its own Prisma DB and **no bridge** to
   the bot (building that integration is its own project);
2. its CEFR mapping is 4 coarse ambiguous bands (`A2-B1`, `C1-C2`) that cannot
   emit a single level;
3. a "real IRT" score implies a rigor the 17-student data cannot support, which
   would work against the truth-in-labelling rule.
The oracle IRT engine remains the future "full adaptive placement" option; a
revisit trigger is: a calibrated item bank + enough attempts to estimate
parameters.

---

## R6 — CEFR placement (self-contained, in the bot)

A short **adaptive-by-branching** placement that outputs a **per-skill CEFR
profile**, not one number — because CEFR is skill-differentiated and collapsing
it to a single score is a known misuse.

- **Skills probed:** Vocabulary/Grammar (objective, auto-scored), Listening
  (objective), Writing (AI-rated vs descriptors), Speaking (AI-rated vs
  descriptors). Reading folded into vocab/grammar for now (noted as a later
  enhancement).
- **Branching:** start at B1-level items; a running correct-rate steps the next
  block up/down one CEFR band (mirrors the IRT idea of routing to the ability
  region, without over-claiming calibration). Objective blocks of ~5 items per
  band; stop when two consecutive blocks agree on a band or bands exhausted.
- **Per-skill result:** each skill resolves to a CEFR band from its own items.
- **Overall placement level:** the **lower of** (rounded mean of skill bands)
  and (min skill band + 1) — CEFR practice places conservatively so a student
  is never dropped somewhere they cannot cope; start them where they can
  succeed, they advance fast if under-placed.
- **Slotting:** placement → `set_level(discord_id, level)` + start at **week 1**
  of that level (R6.2). Current students are never force-retested (R6.3);
  placement is opt-in via a command / the practice site.
- **Output artifact:** a stored `placement_result` row + a profile shown to the
  student and owner (per-skill bands + recommended level + the can-do overview
  for that level).

## R7 — CEFR level exit exam (retarget the advancement exam)

Reuse the existing two-part advancement machinery; retarget and descriptor-link
it. **No engine rewrite** — content + keys + an AI rater.

- **Keys A1–C2.** Extend `_PART_B_PROMPTS` from `L0–L3` to `A1–C2` (authored
  from each level's **production** descriptors). Keep legacy keys as aliases so
  nothing breaks.
- **Part A (structured, objective + short production):** `generate_advancement_
  blueprint_a` already spreads items across 5 skills; add a `can_do` code tag to
  each item so the exam demonstrably samples that level's descriptors across
  reception/production/interaction. Coverage rule: every skill family present;
  ≥1 item per production descriptor group.
- **Part B (integrated production task):** the per-level speaking/writing prompt,
  authored to the level's top production descriptors (A1 self-intro … C2 argue
  a nuanced position, concede then rebut).
- **AI rating (option c):** replace/augment the rule-based `score_part_b` with an
  **AI rater that scores against the level's descriptors** on the existing
  fluency/accuracy/vocab-range/pronunciation axes (0–100), returning a per-axis
  score + which descriptors were evidenced + a confidence. Reuse
  `ai_engine._call_llm`. Deterministic rule-based path stays as the fallback if
  the LLM is unavailable (never block a student on an API outage).
- **Boundary human-review queue:** if the total lands within a **±review-band**
  of the pass cut (default ±7, reuse the Itqan near-miss idea) OR the AI rater
  flags low confidence, the attempt is **not auto-decided** — it goes to an
  owner review queue (`exit_exam_reviews`) with paste-ready
  `!exam-pass`/`!exam-fail` commands, exactly like the Itqan flagged-review flow.
  Clear passes/fails auto-resolve.
- **Pass → certify + promote:** on pass, `deliver_advancement_outcome` promotes
  (already CEFR-aware via `next_cefr_level`) and issues the certificate (R8).
- **Cut scores (expert-assigned):** Part A ≥ 65% AND Part B ≥ 60/100 for A1–A2;
  the Part B weight and threshold rise with level (B1–B2 65, C1–C2 70) per R7.2.
  All thresholds live in one config block, documented as expert-set.
- **Flag:** stays behind `assessment_advancement_exam` (OFF) until owner enables.

## R8 — CEFR certificate (extend, don't replace)

- `itqan_certificate_data` gains an **exam-based** path: when a level exit exam
  is passed, the certificate reflects *"demonstrated proficiency at CEFR Level
  X"* + the **can-do checklist** the exam evidenced (from the tagged items) +
  date + distinction if Part B ≥ 90.
- Keep the existing completion-based certificate too; the exam-based one is the
  stronger credential. Both use `config.level_info` (already CEFR-safe).
- **dojo page:** add the can-do checklist block + the compliant footer
  (*"CEFR-aligned; not an accredited CEFR examination."*), bilingual.
- Wording obeys R0 everywhere: **"CEFR-aligned," never "CEFR certified."**

## Data model (new, all behind the existing flags)

- `placement_result(discord_id, taken_at, overall_level, skill_bands_json,
  recommended_week, source)` — one row per placement.
- `exit_exam_reviews(id, discord_id, level, attempt_ref, part_a, part_b,
  ai_confidence, status[pending|passed|failed], created_at, resolved_at,
  resolved_by)` — the boundary queue.
- Reuse existing `advancement_exams` for the attempt/outcome record.

## Test plan (what Task 6 must prove)

1. Placement emits a **per-skill profile** and a single conservative level;
   boundary maths (lower-of rule) unit-tested.
2. Exit-exam blueprint for every level A1–C2 tags items to real `can_do` codes;
   `_PART_B_PROMPTS` has A1–C2 keys; legacy keys still resolve.
3. AI rater returns the schema; rule-based fallback triggers when the LLM path
   is stubbed (no network dependence in tests).
4. Boundary queue: a near-cut result goes to `exit_exam_reviews` (pending), a
   clear pass auto-promotes, a clear fail does not.
5. Certificate: exam-based path shows the can-do checklist + compliant footer;
   `config.level_info` drives the label.
6. Full suite green; no student-facing behaviour changes while flags are OFF.
