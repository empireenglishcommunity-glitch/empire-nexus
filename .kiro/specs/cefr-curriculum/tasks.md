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

**The single biggest live/not-live fact:** the exit-exam system (Phase 8b) is
fully built, tested, and deployed, but it is **gated behind the
`assessment_advancement_exam` flag, which is OFF.** It is NOT live to students
until the owner runs `!flag enable assessment_advancement_exam` in
#admin-commands. Until then, every 8b item is `[~]`, not `[x]`.

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

### 8b — exit exams (retarget advancement) · [nexus] — 🟡 BUILT + DEPLOYED, NOT LIVE (flag OFF)
- [~] `_PART_B_PROMPTS` extended A1–C2 (legacy keys kept as aliases).
- [~] Part A items tagged with `can_do` codes.
- [~] AI descriptor-rater for Part B + rule-based fallback (no network in tests).
- [~] `exit_exam_reviews` boundary queue + `!exam-review`/`!exam-pass`/`!exam-fail`.
- [~] Cut scores in one config block; pass → promote + certificate.
- [~] Wired into the live finish path (`finish_advancement_exit` → api_server →
      `deliver_exit_exam_outcome`). Merged (#369) + auto-deployed.
- **All `[~]` because `assessment_advancement_exam` is OFF.** Flip it to make
  these `[x]`. Kill switch: `!flag disable assessment_advancement_exam`.

### 8c — placement (self-contained, per-skill) · [nexus] — ❌ NOT USABLE (engine only)
- [ ] Branching placement → per-skill CEFR profile → conservative overall level.
      **NOTE:** the scoring/branching MATH exists in `src/placement.py`
      (`band_index`, `step_band`, `resolve_skill_band`, `conservative_overall`,
      `build_placement_pool`, `place_student`) and is unit-tested, **but nothing
      calls it** — there is NO session runner, NO API endpoint, and NO command
      or practice-site screen. **A new student cannot take a placement test.**
- [~] `placement_result` table (exists) + `place_student(..., slot=)` (exists,
      opt-in) — but uncalled, so not reachable in production.

### 8d — certificate · [nexus] + [dojo] — 🟡 PARTIAL
- [x] Certificate page shows the level's **can-do checklist** + the compliant
      bilingual footer ("CEFR-aligned … not an official certification"). LIVE
      on the practice site (dojo #102, wrangler-deployed).
- [ ] **Exam-based path NOT built:** the certificate still reads "Certificate of
      Mastery / mastered every week" and is gated on all-weeks-mastered — NOT
      the spec's *"has demonstrated proficiency at CEFR Level X"* wording, and it
      is not issued on exit-exam pass. Exam distinction (Part B ≥ 90) not wired.

### 8e — tests + deploy + verify · [nexus] — ✅ DONE
- [x] Unit tests for the built pieces; full suite **1569 passing**; deployed.
      New exam surfaces correctly stay behind the OFF flag (zero student-facing
      change until enabled) — which is exactly why 8b is `[~]` above.

## Phase 9 — Guides + transparency · [dojo] + [nexus] + [chronicle] — ❌ NOT DONE
- [ ] Student `/guide` + owner `/ops-guide`: NOT updated for CEFR structure,
      can-do checklists, level exams, certificates (commands exist but pre-date
      this and were not revised).
- [ ] `!progress` does NOT show CEFR level + can-do progress (no can-do surface
      in the command).
- [ ] Per-level can-do checklist on the practice site — NOT built (only the
      certificate page shows can-do).
- [x] `STATUS.md` updated (chronicle) to reflect the go-live.
- [ ] `SYSTEM-MAP.md` not yet updated for Phase 8.

## Phase 10 — Final verification + full enable · [nexus] — ❌ NOT DONE
- [ ] End-to-end ghost journey A1→A2 via the exit exam.
- [ ] Placement + certificates fully live (blocked on 8c + 8d).
- [ ] Guides live (blocked on Phase 9).
- [ ] `assessment_advancement_exam` enabled (owner action, pending).
- [ ] Legacy L0–L3 fully retired (currently kept; map retained).

---

## What is genuinely OUTSTANDING (the honest "not yet" list)
1. **Placement (8c):** the whole student-facing test — runner + endpoint +
   command/screen. Engine is a shell with no caller. **Biggest real gap.**
2. **Certificate (8d):** exam-based issuance + "demonstrated proficiency"
   wording + exam distinction.
3. **Phase 9:** `/guide` + `/ops-guide` CEFR update, `!progress` can-do view,
   per-level site can-do checklist, `SYSTEM-MAP.md` update.
4. **Phase 10:** end-to-end ghost verification; owner flips
   `assessment_advancement_exam` ON; decide on legacy retirement.

## Cross-cutting (every phase)
- Full nexus test suite green; bump `BOT_VERSION` on each bot deploy.
- Bilingual, Arabic-first, bidi-safe.
- Every level: owner approval gate + written CEFR-alignment rationale.
- All new behaviour behind flags until deliberately enabled.
- Migration: snapshot-first, dry-run, ghost-test, idempotent, reversible.
- Truth-in-labelling: "CEFR-aligned", never "CEFR-certified".
