# Pronunciation Feedback — Implementation Plan (Tasks)

## Status — ⛔ SUPERSEDED by `pronunciation-engine-v2` (header added 2026-08-29)

> **This is the earlier of two pronunciation specs. Do not work from it.**
> `.kiro/specs/pronunciation-engine-v2/` is the consolidated, final plan and is
> the one that shipped as **Nutq**.
>
> The "DRAFT — awaiting owner approval / no implementation starts" line below is
> **false as of 2026-08-29**: pronunciation feedback is built and deployed.
> Evidence — `src/pronunciation_scorer.py` (523 lines, engine selector),
> `src/pronunciation_azure.py` (253 lines, Azure Pronunciation Assessment client),
> the standalone `services/nutq-scorer/` container (free self-hosted fallback),
> the `pronunciation_scores` / `azure_usage` / `azure_shadow_calls` /
> `nutq_daily_cap_overrides` tables, and **8** test files (`test_nutq_*.py`,
> `test_pronunciation_*.py`).
>
> See `empire-chronicle/SYSTEM-MAP.md` §2 for how the live "🏅 Grade my best read"
> model actually works — notably that a normal practice send uses the free engine
> and shows no number, while the one official daily grade goes to Azure under an
> atomic per-day cap. Kept as a design record.

**Original status line (superseded):** DRAFT — awaiting owner approval.

Legend: [ ] not started · [~] in progress · [x] done

---

## Phase 0 — Spec sign-off
- [ ] 0.1 Owner reviews `requirements.md` + `design.md` + this plan.
- [ ] 0.2 Owner picks the codename (proposed: **Nutq** / نُطق).
- [ ] 0.3 Owner approves → we begin Phase 1. (Until then, nothing is built.)

## Phase 1 — Backend: score page recordings (bytes path), flag-gated, best-effort
- [ ] 1.1 Add a bytes-based scoring entry to `pronunciation_scorer.py`
      (`score_recording_bytes(...)` or refactor `score_recording` to accept
      bytes OR url). No change to the scoring math (R3).
- [ ] 1.2 Add an expected-text lookup for `(week, day, level)` → accent/shadow
      `record_this` (map day 1–7 → curriculum day_index). Returns "" if absent.
- [ ] 1.3 Hook into `POST /api/submit-recording` AFTER completion + `#showcase`
      post: gated on `tatawwur_pronunciation` + `exercise in (accent, shadow)` +
      expected text present; run inside a ~8s timeout; wrap in try/except;
      attach the `pronunciation` object to the JSON response (or `scored:false`).
      MUST NOT alter/gate completion (R2).
- [ ] 1.4 Persist each score via the existing `pronunciation_scores` path (R7).
- [ ] 1.5 Tests: bytes scorer happy-path + beginner-grace + fair-match cases;
      endpoint returns `pronunciation` when flag on / `scored:false` when off,
      failed transcription, non-recording exercise, missing expected text; and a
      regression proving completion still succeeds when scoring raises/times out.
      Full suite green.

## Phase 2 — Frontend: on-page feedback (core UI)
- [ ] 2.1 `DarbRecording`: after "Sent!", show a "🎧 checking your pronunciation…"
      spinner; render score ring (green/amber/orange) + bilingual feedback +
      missed-word chips (R1, R4). Beginner-grace → warm no-number note (R3).
- [ ] 2.2 Graceful `scored:false` → neutral "saved, couldn't check this time"
      (never an error) (R2).
- [ ] 2.3 Confirm no other exercise page shows the panel; confirm privacy —
      panel only in the student's own session (R9).
- [ ] 2.4 Local verification (node --check + manual DOM reasoning; no student impact).

## Phase 3 — Out-of-box UI: heard-vs-target + instant try-again
- [ ] 3.1 Render `expected` with `missed_words` highlighted + muted "we heard:
      {transcript}" line (R5).
- [ ] 3.2 "Try again" button: reset the recorder in place; re-record + re-send
      re-scores and refreshes the panel; NO duplicate completion / double points
      (R6). Test the no-double-count guard.

## Phase 4 — Pilot → rollout (D8, R10)
- [ ] 4.1 Enable `tatawwur_pronunciation` for BioRoMa + Mai only (allowlist).
- [ ] 4.2 Live-verify end-to-end (record on the real page → score + feedback +
      heard-vs-target + try-again; completion + #showcase unaffected; score
      stored; `!progress` average moves). Confirm daily flow untouched.
- [ ] 4.3 Enable for all 16 (empty allowlist). Re-verify a couple students.

## Phase 5 — Out-of-box (optional, later; each its own go/no-go)
- [ ] 5.1 Student pronunciation **trend** surface (small average/sparkline on the
      page or calendar) from stored scores (R11).
- [ ] 5.2 Owner **teaching insight** via Empire Ops: periodic aggregate "top
      missed sounds/words across the cohort" (R12). Aggregate only, no shaming.
- [ ] 5.3 (Deferred/parked) Speaking fluency feedback + adaptive-difficulty
      re-enable — separate specs/decisions (non-goals here).

---

## Cross-cutting guardrails (every phase)
- Flag OFF until 4.1; completion/points/streak/mastery never touched.
- Bilingual (EN + Egyptian Arabic), encouragement-only, NOT Nour-voiced.
- Backup before any server change; deploy dojo-first or bot-first as appropriate;
  live-verify the daily flow after each deploy.
- Update `empire-chronicle` SYSTEM-MAP + STATUS when the feature ships (note the
  `tatawwur_pronunciation` flag is live again and re-wired to the page).
