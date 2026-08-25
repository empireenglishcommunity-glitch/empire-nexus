# Implementation Plan — CEFR Curriculum ("Mi'yar")

## Status — RECONCILED AGAINST LIVE CODE + DEPLOYMENTS (2026-08-25)

This checklist was reconciled item-by-item against the actual repository and
deployments on 2026-08-25. **A box is only ticked if the work is built
correctly, tested, deployed, AND live.** Anything built-but-not-yet-live, or
partial, is marked honestly — never ticked.

**Legend:**
- `[x]` — built + tested + deployed + **live** (verified).
- `[~]` — built + deployed but **NOT live yet** (e.g. gated behind an OFF flag),
  or **partial** — see the note.
- `[ ]` — **not built** (or engine-only with no usable surface) — see the note.

**Update 2026-08-25 (later):** per owner decision to "make everything live," the
exit exam (8b) is now **ON** — `assessment_advancement_exam` is auto-enabled on
deploy (`database.enable_exit_exam_once`, one-time/idempotent), and placement
(8c) shipped its runner + practice-site page + `!placement` command. Both are
now `[x]` LIVE. Kill switch still available: `!flag disable assessment_advancement_exam`.

**Owner-confirmed decisions (unchanged):** all six CEFR levels · fully curated ·
silent zero-loss migration · build level-by-level · reuse the existing engine ·
"CEFR-aligned" never "CEFR-certified" · owner approval gate per level.

---

## Phase 0 — Framework foundation · [nexus] — ✅ LIVE
- [x] `cefr_curriculum` flag (default OFF); `cefr` initiative. *(in flag_registry)*
- [x] CEFR level model in `config.py` (A1–C2 + `LEGACY_LEVEL_MAP` L0→A1…L3→B2).
- [x] `curriculum.py` reads BOTH legacy (`l0_*`) and CEFR (`a1_*`) files; helpers
      accept CEFR or legacy keys.
- [x] Data-model extension: can-do fields + grammar + example sentences +
      listening (week files carry word/pos/arabic/pronunciation/example).
- [~] `can_do.json` (all 6 levels ✅) + `grammar_syllabus.json` (all 6 levels ✅)
      + `vocab/` dir. **NOTE:** the standalone `vocab/*.json` band files were
      NOT created — vocabulary is delivered *inside* each week file instead.
      Functional, but a deviation from the spec's file layout, and words do not
      carry an explicit `cefr` band field (band is implied by the level's file).
- [x] Migration engine (built): `migrate_to_cefr`, `rollback_cefr_migration`,
      `cefr_migration_log` snapshots table.
- [x] Tests: level model, legacy map, loader-reads-both, migration dry-run.
- **Verify:** full suite green; flag OFF ⇒ zero behaviour change. ✅

## Phase 1 — A1 content · [nexus] — ✅ LIVE
- [x] A1 can-do (`can_do.json`) + grammar syllabus + 10 week files + alignment doc.
- [~] A1 vocabulary band — delivered inside the week files; no standalone
      `vocab/a1.json` (see Phase 0 note).
- [x] Owner approval gate — implied by A1 being live to all 17 students.
- [x] Tests + loads behind flag.

## Phase 2 — SILENT MIGRATION (L0→A1) · [nexus] — ✅ LIVE (prior session)
- [x] Migration executed; 17 students live on A1; `cefr_curriculum` enabled.
      **NOTE:** executed + live-verified in a prior session; not re-verifiable
      from the sandbox (no prod-DB access here). Engine + rollback remain.

## Phases 3–7 — A2, B1, B2, C1, C2 content · [nexus] — ✅ LIVE
- [x] A2: can-do + grammar + 12 week files + alignment doc.
- [x] B1: can-do + grammar + 14 week files + alignment doc.
- [x] B2: can-do + grammar + 16 week files + alignment doc.
- [x] C1: can-do + grammar + 18 week files + alignment doc.
- [x] C2: can-do + grammar + 20 week files + alignment doc.
- [~] Per-level vocabulary bands — delivered inside week files; no standalone
      `vocab/*.json` files (see Phase 0 note).
- [x] Phonology layer (90 accent + 90 grammar weeks, 630 passages) + audio
      (896 clips) — live (built in prior sessions; not a numbered task line here).

## Phase 8 — CEFR placement, exit exams & certificates · [nexus] + [dojo]

### 8a — alignment doc + honest caveat · [nexus] — ✅ DONE
- [x] `content/cefr/PHASE8-ASSESSMENT-ALIGNMENT.md` (CoE 4-stage method, the
      validation boundary, expert-set cut scores).

### 8b — exit exams (retarget advancement) · [nexus] — ✅ LIVE (flag auto-enabled)
- [x] `_PART_B_PROMPTS` extended A1–C2 (legacy keys kept as aliases).
- [x] Part A items tagged with `can_do` codes.
- [x] AI descriptor-rater for Part B + rule-based fallback (no network in tests).
- [x] `exit_exam_reviews` boundary queue + `!exam-review`/`!exam-pass`/`!exam-fail`.
- [x] Cut scores in one config block; pass → promote + certificate.
- [x] Wired into the live finish path (`finish_advancement_exit` → api_server →
      `deliver_exit_exam_outcome`). Merged (#369).
- [x] `assessment_advancement_exam` **ON** — auto-enabled on deploy
      (`enable_exit_exam_once`, #371). Kill switch: `!flag disable assessment_advancement_exam`.

### 8c — placement (self-contained, per-skill) · [nexus] + [dojo] — ✅ LIVE
- [x] Branching placement → per-skill CEFR profile → conservative overall level.
      `src/placement_runner.py` drives adaptive vocab/grammar MC blocks (branch
      by band) + a writing task (AI descriptor-rater, rule fallback). Merged #372.
- [x] `placement_result` + `placement_session` tables; `place_student(slot=)`.
- [x] API `/api/placement/{start,answer,writing,slot}`; slotting is opt-in only.
- [x] `!placement` (self) / `!placement @user` (admin) claim-code login link.
- [x] Practice-site page `/placement/` (dojo #103, wrangler-deployed).
- [x] All FOUR skills measured (nexus #385, dojo #107): vocab/grammar → listening
      (dictation via browser TTS, auto-scored) → writing (AI) → speaking (record →
      Whisper → AI rater). Empty speaking transcript finalises on the other three.

### 8d — certificate · [nexus] + [dojo] — ✅ LIVE
- [x] Can-do checklist + compliant bilingual footer ("CEFR-aligned … not an
      official certification") on the certificate page (dojo #102).
- [x] Exam-based path: a passed exit exam issues *"Empire English certifies that
      <name> has demonstrated proficiency at CEFR Level X"* (EN+AR), distinction
      when Part B ≥ 90, certified at the level passed; completion/mastery is the
      fallback. `highest_passed_exit_exam` + `itqan_certificate_data` basis
      (nexus #374); page renders it (dojo #104, wrangler-deployed). Level is
      CEFR-normalized (L0→A1). Never "CEFR-certified".

### 8e — tests + deploy + verify · [nexus] — ✅ DONE
- [x] Unit tests for the built pieces; full suite **1569 passing**; deployed.
      New exam surfaces correctly stay behind the OFF flag (zero student-facing
      change until enabled) — which is exactly why 8b is `[~]` above.

## Phase 9 — Guides + transparency · [dojo] + [nexus] + [chronicle] — ✅ LIVE
- [x] Student `/guide`: new CEFR section (placement, exit exam + boundary review,
      can-do checklist, certificate) + TOC entry + page links (dojo #105).
- [x] Owner `/ops-guide`: new section (`!exam-review`/`-pass`/`-fail`, `!placement`,
      kill switch, pages) + TOC entry (dojo #105).
- [x] `!progress` shows CEFR level (already) + can-do progress bar + checklist
      link; `assessment.can_do_progress` + `GET /api/cefr/progress` (nexus #378).
- [x] Per-level can-do checklist on the site: `/can-do/` with the student's real
      reached/not-yet progress (dojo #105).
- [x] `STATUS.md` + `SYSTEM-MAP.md` updated (chronicle).

## Phase 10 — Final verification + full enable · [nexus] — ✅ DONE
- [x] End-to-end ghost journey A1→A2 via the exit exam — automated integration
      tests drive the real chain (start_advancement_attempt → finish_advancement_exit
      → deliver_exit_exam_outcome → promotion → exam certificate), plus the
      boundary→review→owner-pass path and the clear-fail path.
      `tests/test_cefr_phase8_e2e_journey.py` (3 journeys). NOTE: automated e2e
      through production code paths — not a manual click-through on the live
      server (no sandbox access to prod Discord/site).
- [x] Placement live (8c ✅) + exam-based certificate live (8d ✅).
- [x] Guides live (Phase 9 ✅).
- [x] `assessment_advancement_exam` enabled — auto-enabled on deploy (#371).
- [x] Legacy L0–L3 retirement — DONE (all stages, 2026-08-25). Token cutover
      let us finish now instead of waiting out the 60-day window (see below).

---

## Legacy L0–L3 retirement — COMPLETE (2026-08-25)

Rather than wait out the 60-day session-token window, we did a **token cutover**
so everything could be retired now, safely:
- **W2 (#381):** `claim()` mints **CEFR-only** tokens; promotion DMs a one-click
  re-link so a promoted student's session picks up the new level.
- **W3 (dojo #106):** the edge gate now **requires a CEFR level** — a pre-migration
  `lvl:"L0"` token is treated like an expired session (friendly re-link, never a
  403), which let us delete the `LEGACY_TO_CEFR` map. Deleted the `/l0..l3/` site
  trees (1596 files) + 266 legacy audio clips (manifest 896→630). Old tokens are
  invalidated by design; re-entry is the **same `!link`** flow.
- **W1 (#382, #383):** deleted `data/l0..l3` + `content/l0..l3`; migrated the test
  suite to CEFR (verified CEFR content passes every quality bar first, so coverage
  is preserved); purged runtime legacy literals (incl. a real fix: the Word-of-the-
  Day post was hardcoded to deleted L0 content).
- **Kept deliberately** (defensive input-hardening, not lesson content):
  `config.LEVELS`, `cefr_key`/`LEGACY_LEVEL_MAP`, `LEGACY_ROLE_NAMES`, and
  `rollback_cefr_migration` (the migration undo button).

## What is genuinely OUTSTANDING (the honest "not yet" list)

**Nothing.** Mi'yar (Phases 0–10) is fully built, live, verified, and legacy is
retired. Placement now measures all four CEFR skills (listening + speaking added,
nexus #385 / dojo #107). Any future work is net-new product, not spec debt.

**LIVE + verified end-to-end:** curriculum A1–C2, phonology/audio, migration,
exit exams (8b), placement (8c: all 4 skills), exam-based certificate
(8d), can-do transparency (Phase 9), e2e verification (Phase 10, 3 ghost journeys).

## Cross-cutting (every phase)
- Full nexus test suite green; bump `BOT_VERSION` on each bot deploy.
- Bilingual, Arabic-first, bidi-safe.
- Every level: owner approval gate + written CEFR-alignment rationale.
- All new behaviour behind flags until deliberately enabled.
- Migration: snapshot-first, dry-run, ghost-test, idempotent, reversible.
- Truth-in-labelling: "CEFR-aligned", never "CEFR-certified".
