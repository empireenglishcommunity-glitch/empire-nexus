# Nutq 2 — Implementation Plan (Tasks)

**Status:** DRAFT — awaiting owner approval. **No implementation starts until the
owner approves this spec.** Every phase: own feature branch → full test suite green
→ owner merges → deploy → live-verify → check off here. The
`tatawwur_pronunciation` flag stays OFF (already off) until Phase 4.

Legend: [ ] not started · [~] in progress · [x] done

---

## Phase 0 — Feasibility spike (measure, don't guess) — R2, R3, R4
- [ ] 0.1 In an **isolated** throwaway environment (not the live bot), benchmark
      the top-2 model candidates (quantized wav2vec2-phoneme ONNX; allosaurus) on
      real Arabic-accented English clips: **RSS memory, latency on 2 vCPU, and
      does-it-catch-a-wrong-read**.
- [ ] 0.2 Validate the G2P → model phoneme-set mapping (eSpeak/phonemizer vs model).
- [ ] 0.3 **Go/No-Go report to owner:** chosen model + measured numbers vs R4, plus
      a sample "read wrong → low / read well → high" demonstration. Owner confirms
      before Phase 1. (If neither fits the current box, we pause and revisit
      hardware — no silent compromise.)

## Phase 1 — `nutq-scorer` service — R1, R3, R4, R14
- [ ] 1.1 New containerized service: loads the chosen model once; `POST /score`
      {audio, reference_text, level} → {score, per_word, missed_sounds, heard}.
- [ ] 1.2 Pipeline: G2P → phoneme recognition → alignment → per-word/overall score
      (§3 of design). Deterministic, offline.
- [ ] 1.3 Hard `mem_limit` (~1 GB), internal-only networking, shared-secret auth,
      `restart: unless-stopped`, healthcheck.
- [ ] 1.4 Unit tests for the scoring math (exact read = high; wrong read = low;
      Arabic substitution = partial credit; empty/garbage = graceful).

## Phase 2 — Wire into the bot behind the flag — R5, R7, R9, R10
- [ ] 2.1 Replace `score_recording_bytes()` internals with a call to `nutq-scorer`,
      returning the same `ScoringResult`; keep the best-effort wrapper, ≤8s timeout,
      flag gate, `store` flag, accent/shadow scope **unchanged**.
- [ ] 2.2 Fix `_pronunciation_expected_text()` so shadow scores the shadow passage
      and day-7 scores the shown passage (or cleanly skips) — close the drift gaps.
- [ ] 2.3 Tests: endpoint returns the `pronunciation` object when flag on /
      `scored:false` when off/timeout/scorer-down; **completion + #showcase always
      succeed** even if the scorer errors or times out. Full suite green.
- [ ] 2.4 Confirm the dojo UI needs **no change** (same JSON shape).

## Phase 3 — Calibrate fairness for Arabic L0 — R6, R8
- [ ] 3.1 Assemble a small labelled set of real Arabic-accented reads (good / wrong)
      and tune thresholds: partial-credit for known substitutions, the kindness
      floor/tone, per-word sensitivity — kind but honest (a wrong read stays low).
- [ ] 3.2 Finalise bilingual template feedback keyed to phoneme errors (EN + Egyptian
      Arabic), encouragement-first, not Nour-voiced.
- [ ] 3.3 Owner reviews sample outputs and signs off the "feel".

## Phase 4 — Pilot — R13
- [ ] 4.1 Deploy `nutq-scorer` (additive container; bot unaffected if it's down).
      Back up first; verify all containers healthy.
- [ ] 4.2 Enable `tatawwur_pronunciation` for BioRoMa + Mai only.
- [ ] 4.3 **Live-verify with the owner from BioRoMa:** read wrong → low score + the
      failed sound named; read well → high score; try-again works; completion +
      #showcase unaffected; score stored; `!progress` moves. Owner confirms it now
      "feels real".

## Phase 5 — Rollout + record — R13
- [ ] 5.1 Enable for all students (empty allowlist); re-verify a couple.
- [ ] 5.2 Update `empire-chronicle` STATUS + SYSTEM-MAP: Nutq 2 engine live
      (self-hosted phoneme scorer), Nutq 1 pipeline reused, flag re-enabled.
- [ ] 5.3 Document the scale playbook (add a replica / move to a bigger host).

---

## Cross-cutting guardrails (every phase)
- Flag OFF until 4.2; completion/points/streak/mastery and #showcase never touched.
- Self-hosted, open-source, CPU-only, hard memory cap; scorer isolated from the bot.
- Best-effort everywhere: any scorer failure/timeout → `scored:false`, never an
  error, never a lost completion.
- Backup before any server change; own PR per phase; tests green; owner-merged;
  live-verify the daily flow after each deploy.
- No guessing — Phase 0 measurement gates the whole build.
