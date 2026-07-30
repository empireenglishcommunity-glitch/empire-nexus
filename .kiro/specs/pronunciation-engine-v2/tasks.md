# Nutq — Implementation Plan (CONSOLIDATED, FINAL)

**Status:** DRAFT — awaiting owner approval. **No code until approved.** Each phase:
own PR → tests green → owner merges → deploy → live-verify → check off. Flag stays
OFF until the pilot (Phase A4). Legend: [ ] todo · [~] wip · [x] done.

---

## Already shipped (Nutq 1 + 2 — the reusable pipeline + fallback engine)
- [x] Page recorder → `/api/submit-recording` + `/api/pronunciation-check`
- [x] On-page score panel, heard-vs-target, "try again", storage, flag-gating
- [x] Beginner-grace removed
- [x] `_pronunciation_expected_text` mirrors the shown passage (drift closed)
- [x] `services/nutq-scorer` self-hosted engine — **kept as the fallback**

## Phase 0 — Approval + free Azure resource
- [ ] 0.1 Owner approves this consolidated spec.
- [ ] 0.2 Owner creates a **free Azure Speech resource (F0)** — I guide click-by-click —
      and provides `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION`.

## Phase A1 — Azure client (R1, R2, R8, R13)
- [ ] A1.1 `src/pronunciation_azure.py`: REST call to Pronunciation Assessment
      (ReferenceText, HundredMark, Phoneme granularity, Comprehensive), parse
      Accuracy/Fluency/Completeness + per-word + per-phoneme.
- [ ] A1.2 Map result → `ScoringResult` (same shape) + pick worst phoneme → tip.
- [ ] A1.3 `config.py`: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `NUTQ_AZURE_ENABLED`.
- [ ] A1.4 Tests with a mocked Azure response (well/wrong/accented → correct mapping).

## Phase A2 — Engine selector + usage guard + cost policy (R3, R4, R5)
- [ ] A2.1 `src/pronunciation_engine.py`: choose Azure vs local per request.
- [ ] A2.2 Cost policy: shadow-only; 1 graded/day/student; ≤2 try-again/day; weekly
      checkpoint. DB counters (discord_id, date) + (discord_id, iso-week).
- [ ] A2.3 Usage guard: `azure_usage(month, audio_seconds)`; stop Azure at ~90% of
      5 h/month; per-clip duration cap. Record engine used per score.
- [ ] A2.4 Wire `score_recording_bytes` to call the selector (Azure → else local).
- [ ] A2.5 Tests: policy limits, guard trip → local, Azure-down → local, local-down
      → scored:false, completion always succeeds. Full suite green.

## Phase A3 — Feedback polish (R8, R5)
- [ ] A3.1 Reliable bilingual per-sound tips from Azure phonemes (EN + Egyptian Arabic).
- [ ] A3.2 Fallback (local) feedback = band + encouragement, no specific sound named.
- [ ] A3.3 Owner reviews sample outputs (Azure + fallback) and signs off the "feel".

## Phase A4 — Pilot (R12)
- [ ] A4.1 Add Azure key/region to `.env`; deploy bot; verify health + Azure reachable.
- [ ] A4.2 Enable `tatawwur_pronunciation` for BioRoMa + Mai.
- [ ] A4.3 **Live-verify with owner from BioRoMa:** read well → high + CORRECT sound;
      read wrong → low + the real sound; try-again cap works; usage counter moves;
      completion + #showcase unaffected. Owner confirms it "feels professional".

## Phase A5 — Rollout + LOCK-DOWN
- [ ] A5.1 Enable for all students; re-verify a couple.
- [ ] A5.2 **Lock-down master doc** in `empire-chronicle` — the full Nutq story
      (Nutq 1 → 2 → 3), final architecture, cost policy, and ops runbook.
- [ ] A5.3 Update SYSTEM-MAP + STATUS: Nutq live (Azure primary + local fallback).

---

## Cross-cutting guardrails
- Flag OFF until A4.2; completion/points/streak/mastery + #showcase never touched.
- Best-effort chain: Azure → local → scored:false. Never an error, never a lost day.
- Usage guard makes runaway cost impossible; secrets only in `.env`.
- Backup before any server change; own PR per phase; tests green; owner-merged;
  live-verify; no guessing — verified on real recordings before rollout.
