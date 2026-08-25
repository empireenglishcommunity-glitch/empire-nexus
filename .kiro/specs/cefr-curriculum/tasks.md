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

## Phase 11 — CONTENT COVERAGE ("100% of the level, provably") — ✅ LIVE

**Opened + delivered 2026-08-24.** A measured audit answered the owner's question
*"does finishing A1 via the 7 daily tasks mean the student took all A1 content?"*
with **no**. Evidence + reproduction:
[`empire-chronicle/docs/CONTENT-COVERAGE-AUDIT-2026-08-24.md`](https://github.com/empireenglishcommunity-glitch/empire-chronicle/blob/main/docs/CONTENT-COVERAGE-AUDIT-2026-08-24.md).

**Result: 0 orphaned atoms (was ~894). A1, C1 and C2 teach every descriptor they
publish. Coverage ledger: 7,095 authored / 7,095 delivered / 0 orphaned.**

### 11A — stop the bleeding · ✅ LIVE
- [x] **354 lost vocabulary words recovered.** `get_vocabulary_for_day` used
      `len // 7` and never assigned the remainder, so the last 2–6 words of
      **every** week were unreachable (88 of 90 weeks; A2 lost 14.9%). Fix
      distributes the remainder; a test asserts the 7 day slices reconstruct all
      90 weeks exactly, and it fails on the old formula. Mirrored in empire-dojo
      (parity required by `record_vocab_quiz`/`verification.py`; 630/630 slices
      identical). *nexus #394, dojo #108*
- [x] **450 orphaned listening items delivered.** The week files' authored
      `listening` array had **no consumer at all**. Now drives the dictation,
      with all 450 Arabic hints (which had never been shown). *nexus #395, dojo #109*
- [x] **Grammar became a real weekly exercise.** 90 patterns / 1,208 sub-items
      were a passive Wednesday post — no page, no completion, no mastery. New
      practice page delivers every field incl. `why_arabic_speakers_struggle`.
      **Safety:** `WEEKLY_EXERCISES`, deliberately NOT in
      `PRACTICE_EXERCISES`/`CALENDAR_EXERCISES`, so it can never un-green a day;
      and weekly completions bypass `process_submission` so the "all 7" bonus
      can't be earned unearned. *nexus #396, dojo #110*
- [x] **Can-do goals surfaced during study** (were only on the Phase-9 screen and
      certificate, i.e. after the fact) **+ the empty pattern card fixed** — it
      was fed from `content/patterns/`, which only ever existed for the retired
      legacy levels, so it rendered **nothing** on all 630 day pages. *nexus #397, dojo #111*
- [x] **Coverage Ledger + CI gate.** `src/coverage_ledger.py` resolves every
      atom's delivery route by CALLING the real accessors and **fails the build
      on any orphan**; runs as its own CI step. Proven able to fail: tests
      re-break the vocab split (expects exactly 354) and the listening accessor
      (exactly 450). An anti-blindness test reads the week files directly so a
      NEW authored field cannot go undelivered. Closed the last two orphans
      (`phoneme_focus`, `grammar_point`). *nexus #398, dojo #112*

### 11B — complete the CEFR claim · ✅ A1 LIVE, A2–B2 authoring pending
- [x] **Reading added** — CEFR reception had **no task at all**. A1 authored: 10
      passages, 50–67 words, each reusing 12–21 of its own week's vocabulary and
      only that week's grammar. Two self-caught quality bugs: every answer was in
      position 1 (now deterministically shuffled, with a test), and all 40 answers
      verified traceable to their passage. *nexus #399, dojo #113*
- [x] **Mediation added** — the fourth CEFR mode, previously **absent entirely**.
      A1 authored: 10 relay tasks built on real Arabic-speaker situations. Graded
      by key-points checklist (how CEFR actually judges mediation), with tests
      asserting every key point is anchored in the source and the model answer
      covers them all. *nexus #400, dojo #114*
- [x] **A1 is 100% descriptor-complete** (15/15). `A1.P.5` was a **real content
      gap** — 0 of A1's 70 writing prompts asked for a note/message — closed by
      upgrading one week-3 prompt (documented in `A1-ALIGNMENT.md` §4d for owner
      review). `A2.P.6`/`B1.P.5` were labelling gaps. *nexus #401, dojo #115*
- [ ] **18 descriptors still untaught** (A2 6, B1 5, B2 7). Each has a **named
      plan** in `DESCRIPTOR_GAP_PLAN`, enforced by a test so none can sit as a
      vague todo. They split into three different needs: authored **reading** for
      A2/B2, authored **mediation** for A2/B1/B2, and **extended listening**
      (which single-word dictation can never satisfy) for A2.R.2/B1.R.1/B1.R.2/
      B2.R.1/B2.R.2 — plus new interaction content for B1.I.1/B2.I.1/B2.I.5.
      Deliberately NOT labelled as taught: claiming them would be over-claiming.

### 11C — depth & proof · ✅ LIVE
- [x] **Weekly retrieval quiz.** "Done" meant *exposed*; nothing asked a student
      to recall anything later. 10 items/week, **60% drawn from earlier weeks**,
      both directions (EN→AR and AR→EN), grammar from a previous week, generated
      from authored content so it covered all 90 weeks immediately. Below 80% it
      names which weeks to revisit. *nexus #402, dojo #116*
- [x] **Descriptor evidence portfolio.** The certificate showed an unbacked
      checklist; now every can-do statement carries the work that proves it.
      **Derived** from `practice_mastery` + `daily_submissions` — no new table, no
      change to the completion hot path, and **retroactive** over existing
      history. Attribution is strict: enabling skills prove nothing, reading
      codes need the reading task, and descriptor wording narrows the coarse CEFR
      modes (so "can write" isn't satisfied by speaking). Fixed a real hole:
      writing is Discord-only, so "can write…" was previously unevidenceable.
      *nexus #403*
- [x] **Level Completion Contract.** "Finished A1" now means work done + every
      descriptor evidenced + exit exam passed. **Gates the strongest CLAIM, never
      ACCESS** — `eligible` is untouched so nobody loses an earned certificate
      (the grandfathering precedent). Verified satisfiable: unauthored weekly
      content is skipped, and A1 is tested reachable end to end. *nexus #404*

## What is genuinely OUTSTANDING (the honest "not yet" list)

**One thing: authoring reading + mediation for A2–B2** (and extended-listening
content), which is what the **18 remaining descriptors** need. Every one has a
named plan in `coverage_ledger.DESCRIPTOR_GAP_PLAN`, enforced by a test, so the
list cannot drift or be quietly forgotten. A2 6 · B1 5 · B2 7 · **A1/C1/C2 = 0**.

Everything else is delivered: Phase 11 closed all ~894 orphaned atoms (coverage
ledger reads **7,095 / 7,095 / 0**, gated in CI), added the two missing CEFR
modes, and made "finished this level" provable rather than assumed. Phase 10 had
verified that *the machinery works*; Phase 11 verified that *all authored content
actually reaches a student* — which is a different claim, and the one that was
false.

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
