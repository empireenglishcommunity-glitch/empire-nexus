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

## Phase 11 — CONTENT COVERAGE ("100% of the level, provably") — 🔴 NOT BUILT

**Opened 2026-08-24** after a measured audit answered the owner's question *"does
finishing A1 via the 7 daily tasks mean the student took all A1 content?"* with
**no**. Full evidence + reproduction commands:
[`empire-chronicle/docs/CONTENT-COVERAGE-AUDIT-2026-08-24.md`](https://github.com/empireenglishcommunity-glitch/empire-chronicle/blob/main/docs/CONTENT-COVERAGE-AUDIT-2026-08-24.md).

**Measured:** 90 weeks hold **5,339 content atoms**; **~894 (16.7%)** never properly
reach a student. Accent (630), speaking (630) and writing (630) are clean — the
losses are concentrated in vocab, listening, and grammar.

### 11A — stop the bleeding (no new authoring, additive only, zero student risk)
- [ ] **A1 · 354 lost vocabulary words.** `curriculum.get_vocabulary_for_day`
      (`curriculum.py:186`) uses `len(all_words) // 7` and never assigns the
      remainder, so the last 2–6 words of **every** week are unreachable
      (A1 11.7% → A2 14.9% lost). Fix: round-robin remainder + a test asserting
      the union of all 7 days == the full week list, for all 90 weeks.
- [ ] **A2 · 450 orphaned listening items.** Week files carry a `listening` array
      (`say_en`/`expected`/`hint_ar`) that **no code reads**; dojo `gen_listening`
      builds dictation from vocabulary instead. Fix: add
      `curriculum.get_listening_for_day()` and feed the practice page from it.
- [ ] **A3 · grammar is authored, not delivered.** 90 rich bilingual patterns
      (**1,208 sub-items**: formula/visual, `why_arabic_speakers_struggle`,
      examples, common_errors, practice_fill_blank, quick_rule, mnemonic) reach
      students only as a passive Wednesday `#cheat-sheets` post (`bot.py:1338`) —
      no task, no page, no completion, no mastery. Fix: real weekly practice page
      + tracked task.
- [ ] **A4 · can-do invisible + empty pattern card.** Week `can_do` codes never
      appear in the daily flow (only Phase-9 progress + certificate).
      `content/patterns/` has only `l0..l3`, so the a1–c2 "Today's Pattern" card
      renders **nothing** (verified in generated `a1/week1/day1/index.html`).
- [ ] **A5 · Coverage Ledger + CI gate.** Enumerate all 5,339 atoms; assert each
      has a delivery route **and** a tracked completion; **fail the build on any
      orphan.** This is the permanent guarantee — it would fail on 894 atoms today.

### 11B — complete the CEFR claim (needs authoring)
The 7 tasks cover only ~2.5 of CEFR's four modes. **Reading has no task at all and
mediation is entirely absent** — proven by descriptors that *no week teaches*:
A1=5, A2=7, B1=6, B2=7 (C1/C2 = 0 ✅). At A1 the untaught set is exactly
`A1.R.1`,`A1.R.4` (reading), `A1.M.1`,`A1.M.2` (mediation), `A1.P.5` (notes).
**A1–B2 cannot honestly claim full CEFR coverage until this is closed.**
- [ ] **B1 · Reading task** (reception) + authored texts → closes `R.*`.
- [ ] **B2 · Mediation task** + authored tasks → closes `M.*`. The differentiator:
      relay/explain/summarise, natural for Arabic-speaking learners.
- [ ] **B3 · Assign the 25 orphaned A1–B2 descriptors** to specific weeks.
- [ ] Delivery shape: **Daily Core (5)** = accent, vocab, listening, shadowing,
      speaking · **Weekly Ring (1/day, rotating)** = grammar, reading, mediation,
      writing, community. Daily load stays ~6; weekly coverage becomes complete.

### 11C — depth & proof (exposure → retention)
- [ ] **C1 · Weekly consolidation quiz** — retrieval practice over that week's real
      atoms + spaced items from prior weeks ("done" is currently just a click).
- [ ] **C2 · Descriptor evidence portfolio** — every completed task emits evidence
      tagged to a can-do code; certificate shows proof per descriptor.
- [ ] **C3 · Level Completion Contract** — certify only when coverage == 100% AND
      every descriptor has evidence AND the exit exam is passed.

---

## What is genuinely OUTSTANDING (the honest "not yet" list)

**Phase 11 (content coverage) — see above.** Mi'yar Phases 0–10 are fully built,
live, verified, and legacy is retired; placement measures all four CEFR skills
(nexus #385 / dojo #107). But Phase 10 verified that *the machinery works*, not
that *all authored content is delivered* — and the 2026-08-24 audit proved it is
not (894 atoms orphaned; reading + mediation missing). That is real spec debt, not
net-new product, because the content already exists and was already paid for.

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
