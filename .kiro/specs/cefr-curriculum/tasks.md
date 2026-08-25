# Implementation Plan — CEFR Curriculum ("Mi'yar")

## Status — SPEC WRITTEN, AWAITING OWNER APPROVAL TO BEGIN

Owner approved the direction (all 6 CEFR levels, fully curated, silent
zero-loss migration, level-by-level). Two reputation guardrails accepted:
**"CEFR-aligned" not "CEFR-certified"** wording, and **owner approval gate**
on every level. Awaiting go-ahead on Phase 0 + design sign-off items
(week counts R13, legacy→CEFR map).

**Owner-confirmed decisions:**
- ✅ All six CEFR levels: A1, A2, B1, B2, C1, C2
- ✅ Fully curated content, authored against official CEFR sources
- ✅ Silent, zero-loss migration of current students (CRITICAL, must not hurt)
- ✅ Build level-by-level; take the time to do it right
- ✅ Reuse the existing engine (daily loop, Taqdeem, SRS, site)

---

Build order. **Every phase = its own owner-merged PR, fully tested, deployed +
verified, ZERO disruption to the 16 live students.** All behind the
`cefr_curriculum` flag until each level is deliberately enabled.

Legend: **[nexus]** = bot/curriculum · **[dojo]** = practice site ·
**[chronicle]** = docs.

---

## Phase 0 — Framework foundation (no student-facing change) · [nexus]
- [ ] `cefr_curriculum` flag (default OFF); `cefr` initiative.
- [ ] CEFR level model in `config.py` (A1–C2: cefr, name, name_ar, title,
      emoji, color, weeks, order) + `LEGACY_LEVEL_MAP` (L0→A1…L3→B2).
- [ ] `curriculum.py`: CEFR-keyed `LEVEL_WEEK_COUNTS`; loader reads BOTH legacy
      (`l0_*`) and CEFR (`a1_*`) files (transition shim); helpers accept CEFR
      or legacy keys.
- [ ] Data-model extension: can-do fields + structured grammar + example
      sentences + listening (backwards-compatible; legacy files still load).
- [ ] `content/cefr/can_do.json` skeleton + `grammar_syllabus.json` skeleton +
      `vocab/` dir (structure only, populated per level later).
- [ ] Migration engine (built, NOT run): `migrate_to_cefr(dry_run=True/False)`,
      `cefr_migration_log` table (snapshots), `rollback_cefr_migration()`,
      idempotency + per-student verify + report.
- [ ] Tests: level model, legacy map, loader reads both, migration dry-run
      preserves everything (on a seeded fake DB), idempotency, rollback.
- **Verify:** full suite green; flag OFF ⇒ zero behaviour change.

## Phase 1 — Author + ship A1 (Beginner) content · [nexus]
- [ ] Curate A1 can-do descriptors (all 4 modes) → `can_do.json` (A1).
- [ ] A1 grammar syllabus (10 weeks of points) → `grammar_syllabus.json`.
- [ ] A1 vocabulary band (~750 words, CEFR-A1) → `vocab/a1.json`.
- [ ] Author 10 A1 week files (`data/a1_week1..10.json`): theme, can-do,
      grammar point, phonemes, vocab slice, speaking, writing, listening.
- [ ] A1 alignment rationale doc (which descriptors/bands) for the approval gate.
- [ ] **OWNER APPROVAL GATE** — owner reviews A1 before it can go live.
- [ ] Tests: A1 files valid + load; week counts; can-do coverage.
- **Verify:** suite green; A1 loads behind the flag; owner signs off.

## Phase 2 — SILENT MIGRATION of current students (L0→A1) · [nexus]
- [ ] Pre-flight: full DB backup on the server.
- [ ] Run `migrate_to_cefr(dry_run=True)` → owner reads the per-student report.
- [ ] Ghost/clone run: execute on a DB copy, verify all 16 students intact.
- [ ] Execute for real in a low-activity window (snapshots each student first).
- [ ] Per-student verification report (level=A1, streak/points/mastery/calendar
      unchanged, sessions valid).
- [ ] Enable `cefr_curriculum` for A1.
- **Verify:** all 16 students continue seamlessly — same week position, streak,
      points, no logout, no reset. Live-checked. Rollback ready if needed.

## Phase 3 — Author + ship A2 (Elementary) · [nexus]
- [ ] A2 can-do + grammar syllabus + vocab band (~+750 words) + 12 week files.
- [ ] Alignment rationale + **OWNER APPROVAL GATE**.
- [ ] Tests + deploy + enable A2.

## Phase 4 — Author + ship B1 (Intermediate) · [nexus]
- [ ] B1 can-do + grammar + vocab (~+1,750) + 14 week files + rationale + gate.

## Phase 5 — Author + ship B2 (Upper-Intermediate) · [nexus]
- [ ] B2 can-do + grammar + vocab (~+1,750) + 16 week files + rationale + gate.

## Phase 6 — Author + ship C1 (Advanced) · [nexus]
- [ ] C1 can-do + grammar + vocab (~+3,000) + 18 week files + rationale + gate.

## Phase 7 — Author + ship C2 (Proficiency) · [nexus]
- [ ] C2 can-do + grammar + vocab (~+2,000) + 20 week files + rationale + gate.

## Phase 8 — CEFR placement, exit exams & certificates · [nexus] + [dojo]

> Detailed buildable design in `design.md` → "Phase 8 — detailed implementation
> design". Criterion-referenced (can-do based); empire-oracle IRT intentionally
> NOT integrated this phase (documented there). Honest validation caveat
> ("aligned by design, pending empirical validation") is mandatory in the
> alignment doc + certificate footer.

### 8a — alignment doc + honest caveat · [nexus]
- [ ] `content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md`: CoE 4-stage method, what we
      do (stages 1–3), the validation boundary, expert-set cut scores.

### 8b — R7 exit exams (retarget advancement) · [nexus]
- [ ] `_PART_B_PROMPTS` extended L0–L3 → A1–C2 (legacy keys kept as aliases),
      authored from each level's production descriptors.
- [ ] Part A items tagged with `can_do` codes; coverage rule enforced.
- [ ] AI descriptor-rater for Part B (fluency/accuracy/vocab/pron + evidenced
      descriptors + confidence); rule-based fallback stays (no network in tests).
- [ ] `exit_exam_reviews` boundary queue + `!exam-pass`/`!exam-fail`/`!exam-review`.
- [ ] Cut scores in one documented config block; pass → promote + certificate.

### 8c — R6 placement (self-contained, per-skill) · [nexus]
- [ ] Branching placement → per-skill CEFR profile → conservative overall level.
- [ ] `placement_result` table; slot via `set_level` + week 1; opt-in only.

### 8d — R8 certificate · [nexus] + [dojo]
- [ ] Exam-based `itqan_certificate_data` path: level + can-do checklist +
      distinction + date; compliant bilingual footer on the dojo page.

### 8e — tests + deploy + verify
- [ ] Unit tests per the design's 6-point test plan; full suite green; all new
      surfaces behind flags (OFF) — zero student-facing change until enabled.

## Phase 9 — Guides + transparency · [dojo] + [nexus] + [chronicle]
- [ ] Student `/guide` + owner `/ops-guide`: CEFR structure, can-do checklists,
      level exams, certificates.
- [ ] `!progress` shows current CEFR level + can-do progress; site can-do
      checklist per level.
- [ ] SYSTEM-MAP + STATUS updated.

## Phase 10 — Final verification + full enable · [nexus]
- [ ] End-to-end: a student journeys A1→A2 via the exit exam on a ghost.
- [ ] All 6 levels live; placement + certificates live; guides live.
- [ ] `cefr_curriculum` fully on. Legacy L0–L3 fully retired (map retained).

---

## Cross-cutting (every phase)
- Full nexus test suite green; bump `BOT_VERSION` on each bot deploy.
- Bilingual, Arabic-first, bidi-safe; run `scripts/bidi_check`.
- Every level: **owner approval gate + written CEFR-alignment rationale**.
- All new behaviour behind `cefr_curriculum` (OFF) until deliberately enabled.
- Migration: snapshot-first, dry-run, ghost-test, idempotent, per-student
  verify, reversible. **Never risk a live student.**
- Truth-in-labelling: "CEFR-aligned", never "CEFR-certified".

## Sign-off items before authoring begins
1. **Week counts** (R13): proposed A1=10, A2=12, B1=14, B2=16, C1=18, C2=20.
2. **Legacy→CEFR map**: L0→A1, L1→A2, L2→B1, L3→B2 (all current students L0→A1).
3. Confirm the two reputation guardrails (wording + approval gate).
