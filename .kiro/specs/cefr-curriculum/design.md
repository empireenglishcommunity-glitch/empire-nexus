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
