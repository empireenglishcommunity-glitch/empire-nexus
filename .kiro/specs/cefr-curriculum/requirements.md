# Requirements — CEFR Curriculum ("Mi'yar")

> **Codename: Mi'yar (معيار)** — Arabic for "standard / benchmark / criterion."
> The whole point: rebuild Empire English's curriculum so it is **100%
> aligned to the CEFR** (Common European Framework of Reference) across all
> **six levels (A1 → C2)** — a professional, market-competitive, genuinely
> valuable English program. Directory: `cefr-curriculum`.

## Origin

Empire English today has 4 internal levels (L0–L3) roughly matching A1–B2,
with content that was authored ad-hoc (themes + ~56 words + one grammar
pattern + speaking/writing per week) rather than *against* the CEFR. The owner
wants the program rebuilt so it is **fully CEFR-aligned** — content, learning
objectives, and assessments all following the official CEFR descriptors — so
Empire English can compete in the market as a serious, credentialed program
and protect its growing reputation.

## Truth-in-labelling (reputation guardrail — R0)

**CEFR is a framework, not a certifying authority.** No body "certifies" a
program as CEFR (not even the Council of Europe). Therefore:

1. All public/marketing/certificate wording SHALL use **"CEFR-aligned"** and
   **"Empire English certifies … at CEFR Level X"** — never "CEFR certified"
   (an unbackable claim that a knowledgeable party could challenge).
2. Certificates SHALL read: *"Empire English certifies that [name] has
   demonstrated proficiency at CEFR Level [X]"* + the level's can-do checklist.
3. The system SHALL be built to genuinely satisfy the official CEFR descriptors
   so the alignment claim is defensible on inspection.
4. (Future, optional) The exit exam MAY be mapped to a recognised external
   test (Aptis / Linguaskill / Cambridge) for third-party validation.

## Constraints

1. **ZERO harm to current students (highest priority).** The 16 active
   students (all on L0 today) MUST be migrated **silently** into the new CEFR
   structure with **no loss** of streak, points, mastery records, calendar
   position, level, or device sessions — and **no disruption** to their daily
   flow. This is the single most important requirement.
2. **Fully curated, quality-gated.** Every level's content is authored
   meticulously against the **official CEFR sources** (Council of Europe
   Companion Volume 2020 can-do descriptors; public CEFR-mapped grammar and
   vocabulary references, from which we build our OWN lists to avoid any IP
   issue). **Every level passes an owner approval gate before going live.**
3. **Build level-by-level.** A1 fully complete + live before A2 begins, etc.
   Students always have a working, complete system.
4. **Reuse the existing engine.** The daily 7-task loop, the practice site,
   the Taqdeem assessment engine (weekly/monthly/advancement), the SRS, the
   recording infrastructure, and the flag/config system are REUSED, not
   rebuilt — retargeted to CEFR content.
5. **Budget:** same server + free/cheap AI for scoring. No new paid services.
6. **Bilingual, Arabic-first**, bidi-safe, throughout.
7. **Reversible + tested.** Migration is snapshotted (reversible) and dry-run
   on a ghost/clone before touching real students; every affected student is
   verified after.

## Glossary

- **CEFR:** Common European Framework of Reference for Languages. Six levels:
  A1, A2, B1, B2, C1, C2 (+ optional "plus" bands A2+, B1+, B2+).
- **Can-Do descriptor:** an official CEFR statement of what a learner CAN do at
  a level (e.g. A2: "Can describe their family, living conditions, educational
  background in simple terms"). These are the **learning objectives**.
- **Functional syllabus:** the communicative functions/notions taught at a
  level (greeting, apologising, describing, hypothesising, …).
- **Grammar profile:** the grammatical structures expected at each level.
- **Vocabulary band:** the vocabulary range expected at each level.
- **Level exit exam:** the advancement exam retargeted as the CEFR level test —
  passing certifies the student at that level and promotes them.
- **Mi'yar:** this whole CEFR-alignment initiative.

---

## Requirements

### R1 — Six CEFR levels
**User story:** As the owner, I want the program organised into the six
official CEFR levels so it is a recognisable, professional English course.

Acceptance criteria:
1. THE SYSTEM SHALL define six levels: **A1, A2, B1, B2, C1, C2**, each with an
   English name, Arabic name, official CEFR title, and colour/emoji.
2. Each level SHALL declare its **week count** (anchored to CEFR guided-learning
   -hour ratios — higher levels take longer; exact counts fixed at design
   sign-off).
3. THE SYSTEM SHALL treat the CEFR level as the single source of truth for a
   student's stage (replacing the legacy L0–L3 labels, which are mapped).
4. Level progression SHALL be A1→A2→A2→B1→B2→C1→C2, gated by the level exit exam.

### R2 — Can-Do learning objectives per level
**User story:** As a student, I want to know exactly what I'll be able to DO at
each level, and as the owner I want assessments that test those abilities.

Acceptance criteria:
1. Each level SHALL have a curated set of **CEFR can-do descriptors** (drawn
   from the Council of Europe Companion Volume), organised by mode: **reception**
   (listening/reading), **production** (spoken/written), **interaction**, and
   **mediation**.
2. Each **week** within a level SHALL map to a subset of that level's can-do
   descriptors (the week's objectives).
3. Can-do descriptors SHALL be stored bilingually (EN + AR) and surfaced to the
   student (a "can-do checklist" they progress through).
4. The level exit exam (R7) SHALL test the level's can-do descriptors.

### R3 — Grammar syllabus per level (CEFR-aligned)
Acceptance criteria:
1. Each level SHALL have a **grammar syllabus** appropriate to its CEFR band
   (e.g. A1: present simple, articles, plurals; A2: past simple, comparatives,
   going-to future; B1: present perfect, conditionals 0–1, passives intro;
   B2: conditionals 2–3, reported speech, relative clauses; C1: mixed
   conditionals, cleft sentences, inversion, nuanced modality; C2: full range
   + stylistic control).
2. Each week SHALL teach a defined grammar point from its level's syllabus.
3. The grammar syllabus SHALL be authored against a public CEFR grammar
   reference (English Grammar Profile concepts), building our own descriptions.

### R4 — Vocabulary band per level (CEFR-aligned)
Acceptance criteria:
1. Each level SHALL have a **vocabulary set** sized and selected to its CEFR
   band (approx cumulative targets: A1 ~750, A2 ~1,500, B1 ~3,250, B2 ~5,000,
   C1 ~8,000, C2 ~10,000+ words — per-level increments authored accordingly).
2. Vocabulary SHALL be selected against public CEFR-mapped references
   (e.g. Oxford 3000/5000 CEFR tags, English Vocabulary Profile) but stored as
   **our own list** (word, CEFR band, POS, Arabic gloss, pronunciation,
   example) to avoid IP issues.
3. Each word SHALL carry its CEFR band so the SRS + assessments can respect it.
4. Vocabulary SHALL feed the existing daily tasks + SRS + assessments unchanged
   in mechanism.

### R5 — Full skill coverage per week
**User story:** As a student, each week should build all my skills the CEFR way.

Acceptance criteria:
1. Each week SHALL provide content for all skills the daily loop uses:
   **vocabulary, listening, pronunciation/phonology, speaking, writing**, plus
   the level-appropriate **grammar** point and **can-do** objective(s).
2. Content difficulty (text length, task complexity, expected output) SHALL
   scale with the CEFR level (A1 = single words/short phrases; C2 = extended,
   nuanced discourse).
3. The daily 7-task structure and the practice-site flow SHALL be **unchanged
   in mechanism** — only the content is CEFR-authored.

### R6 — CEFR placement test
**User story:** As a new student (or a current one), I want a placement test
that tells me my CEFR level and starts me in the right place.

Acceptance criteria:
1. The existing placement test SHALL be upgraded to **output a CEFR level**
   (A1–C2) based on performance across its modules.
2. The placement result SHALL slot the student into the correct level + week 1.
3. Current students MAY optionally re-take it (some may test higher than A1);
   by default they are auto-mapped (see R9), never forced to re-test.

### R7 — CEFR level exit exam (certification)
**User story:** As a student, passing the level exam should certify me at that
CEFR level and advance me — a real, earned credential.

Acceptance criteria:
1. The Taqdeem **advancement exam** SHALL be retargeted per level as the **CEFR
   level exit exam**, testing that level's can-do descriptors across skills
   (Part A structured + Part B production task appropriate to the level).
2. Pass criteria SHALL reflect the level (production weight and difficulty rise
   with the level).
3. ON PASS: THE SYSTEM SHALL certify the student at that CEFR level, issue the
   CEFR certificate (R8), and promote them to the next level.
4. The weekly (Itqan) + monthly (retention) assessments SHALL test the current
   level's can-do descriptors + vocabulary + grammar.

### R8 — CEFR certificates
Acceptance criteria:
1. On passing a level exit exam, THE SYSTEM SHALL issue a certificate reading
   *"Empire English certifies that [name] has demonstrated proficiency at CEFR
   Level [X]"* + the level's **can-do checklist** achieved + date.
2. Certificates SHALL be bilingual and available on the practice site
   (extends the existing certificate page).
3. Wording SHALL follow the R0 truth-in-labelling rule (never "CEFR certified").

### R9 — Silent, zero-loss migration of current students (CRITICAL)
**User story:** As a current student, I should wake up in the new CEFR system
exactly where I was — my streak, points, progress, and calendar intact — with
nothing broken and no confusing reset.

Acceptance criteria:
1. THE SYSTEM SHALL map the legacy levels to CEFR: **L0→A1, L1→A2, L2→B1,
   L3→B2** (all 16 current students are L0 → A1).
2. Migration SHALL **preserve**: `level` (remapped), `level_started_at`
   (calendar anchor), `current_streak`, `longest_streak`, `total_points`,
   `week_mastery` records (mapped by week number), SRS queue, device sessions /
   link tokens (so nobody is logged out), notification prefs, and journey state.
3. A student's **current week position** SHALL be preserved: if a student is on
   week N of L0, they continue on week N of A1 (new A1 content for weeks they
   haven't done yet; already-mastered weeks stay mastered).
4. Migration SHALL take a **full snapshot first** (reversible) and SHALL be
   **dry-run on the ghost instance / a clone** before touching real data.
5. Migration SHALL be **verified per-student** afterwards (a report the owner
   can read), and SHALL be **idempotent** (safe to re-run).
6. Migration SHALL cause **zero disruption** to the daily flow — ideally run in
   a low-activity window; students see continuity, not a reset.
7. IF anything looks wrong for any student, THE SYSTEM SHALL support a
   **per-student rollback** from the snapshot.

### R10 — Reuse the engine; build behind flags
Acceptance criteria:
1. The daily loop, practice site, Taqdeem engine, SRS, recordings, and
   flag/config system SHALL be **reused** (retargeted), not rebuilt.
2. New CEFR content + levels SHALL be built **behind a flag** and only enabled
   per level after the owner's approval gate — so the current live system is
   never disturbed mid-build.
3. WITH the CEFR flag off, behaviour SHALL be identical to today (legacy L0–L3).

### R11 — Owner approval gate + quality control
Acceptance criteria:
1. Each level's authored content SHALL be presented to the owner for review
   (can-do set, grammar syllabus, vocabulary band, sample weeks) and SHALL NOT
   go live until the owner approves.
2. Each level SHALL ship with a short **CEFR-alignment rationale** (which
   descriptors, which grammar/vocab band) so the alignment is auditable.

### R12 — Guides + transparency
Acceptance criteria:
1. Student `/guide` + owner `/ops-guide` SHALL be updated to explain the CEFR
   structure, the can-do checklists, the level exams, and the certificates.
2. Students SHALL be able to see their **current CEFR level** and **can-do
   progress** clearly (in `!progress` and on the practice site).

### R13 — Weeks & guided-hours anchoring (design sign-off item)
Acceptance criteria:
1. Per-level week counts SHALL be anchored to CEFR guided-learning-hour ratios
   (higher levels longer). Proposed default (adjustable at design sign-off):
   **A1=10, A2=12, B1=14, B2=16, C1=18, C2=20** (≈90 weeks total).
2. The exact counts SHALL be fixed with the owner before content authoring of
   each level begins.
