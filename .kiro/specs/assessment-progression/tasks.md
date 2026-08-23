# Implementation Plan — Assessment Progression (Monthly Review + Level Advancement)

## Status — PLAN WRITTEN, AWAITING OWNER APPROVAL

Owner brainstormed the direction and said "ok" to the recommendation.
Full spec written. **Implementation has not begun** — awaiting explicit
go-ahead on the phased plan below.

**Key decisions confirmed:**
- ✅ Monthly = diagnostic (not a daily-task gate), but prerequisite for advancement
- ✅ Monthly triggers after every 4 weekly passes (not calendar-based)
- ✅ Advancement = two parts (structured + integrated production task)
- ✅ L0 Part B = 60-second self-introduction recording
- ✅ Automatic promotion on advancement pass
- ✅ 7-day retake cooldown on advancement
- ✅ Build monthly first, then advancement

---

Build order. **Every phase is its own owner-merged PR, fully tested, and
deployed + live-verified with zero disruption.** Everything behind flags
(default OFF) until rollout.

Legend: **[nexus]** = bot/API repo · **[dojo]** = practice site repo

---

## Phase 0 — Foundations · [nexus]
- [ ] Register 2 flags: `assessment_monthly_review`, `assessment_advancement_exam`
      (both default OFF).
- [ ] `PROGRESSION_CONFIG_DEFAULTS` + `get_progression_config()` +
      `set_progression_config()` (same pattern as Itqan/Majlis).
- [ ] DB: `monthly_reviews` table, `advancement_exams` table, `type` column
      migration on `assessment_attempts`.
- [ ] Helper: `monthly_review_due(discord_id)` — check if the student has
      enough weekly passes for a new monthly review.
- [ ] Helper: `advancement_exam_due(discord_id)` — check all weeklies passed
      + ≥1 monthly passed.
- [ ] Unit tests: config, trigger logic, table creation.
- **Verify:** suite green; no behavior change.

## Phase 1 — Monthly Review: Generation + Scoring · [nexus]
- [ ] `generate_monthly_blueprint(discord_id, level, weeks_covered)` — equal
      weight across weeks, SRS-biased, production-heavy (≥50% speaking+writing).
- [ ] Scoring: single Retention Score (0–100%), per-skill breakdown, review list
      generation, AI grading (reuse Itqan's scoring helpers).
- [ ] Tests: correct item distribution, SRS bias, production weighting, score
      calculation, borderline flagging.
- **Verify:** suite green; pure logic, nothing wired to users.

## Phase 2 — Monthly Review: API + Calendar · [nexus] + [dojo]
- [ ] API endpoints: `/api/assessment/status?type=monthly`,
      `/api/assessment/start?type=monthly`, item/finish flow (extend existing).
- [ ] `darb.build_calendar`: Monthly Review stop (locked/available/passed).
- [ ] Dojo calendar render: show the monthly stop with appropriate state.
- [ ] Server enforcement: unlock check, cooldown (72h), single in-progress.
- [ ] Tests: unlock gating, cooldown, calendar states.
- **Verify:** suite green; with flag OFF = no visible change.

## Phase 3 — Monthly Review: Outcomes + Owner Report · [nexus]
- [ ] Outcome delivery: pass → private congrats + skill radar + trajectory;
      not-pass → private review list + retake pointer; 2× fail → owner alert.
- [ ] Optional Monthly Star in Champions (sub-flag or config toggle).
- [ ] Owner report: `/monthly` command (Discord + Telegram) — cohort view.
- [ ] Tests: outcome routing, owner notification, report format.
- **Verify:** suite green; deploy; pilot on owner → verify pass/not-pass paths.

## Phase 4 — Advancement Exam Part A: Structured Skills · [nexus]
- [ ] `generate_advancement_blueprint_a(discord_id, level)` — full level
      coverage, 5 skills × 3-4 items, SRS-weighted.
- [ ] Scoring: per-skill scores, skill-minimum check (60% each), Part A
      aggregate.
- [ ] API: `/api/assessment/start?type=advancement`, Part A flow.
- [ ] Calendar: Advancement Exam stop (locked/available/passed).
- [ ] Tests: full-level coverage, skill-min logic, scoring.
- **Verify:** suite green.

## Phase 5 — Advancement Exam Part B: Integrated Task · [nexus] + [dojo]
- [ ] Part B page UX: instructions → prep timer (60s) → record (60s max) →
      review + submit.
- [ ] API: `/api/assessment/part-b/start`, `/submit-recording` (reuse infra).
- [ ] AI scoring: Whisper transcription → Groq evaluation (fluency, accuracy,
      vocab range, pronunciation clarity — each 0–25).
- [ ] Overall score calculation: Part A (60%) + Part B (40%).
- [ ] Pass determination: overall ≥ 75% + skill mins + Part B ≥ 50%.
- [ ] Tests: Part B scoring prompt, overall calculation, edge cases.
- **Verify:** suite green.

## Phase 6 — Advancement Outcomes + Auto-Promotion · [nexus] + [dojo]
- [ ] On pass: auto-promote (`set_level`), certificate DM, Champions post,
      calendar reset, owner notification.
- [ ] On not-pass: private feedback (per-skill + Part B breakdown), 7-day
      cooldown, owner notification.
- [ ] Owner commands: `!advance @student` (manual override), view attempts.
- [ ] Anti-gaming: 7-day cooldown server-enforced, owner notified per attempt,
      item pool rotation.
- [ ] Tests: promotion flow, cooldown enforcement, manual override, notifications.
- **Verify:** suite green; pilot → full rollout.

## Phase 7 — Guides + Rollout · [nexus] + [dojo] + [chronicle]
- [ ] Student `/guide`: Monthly Review card + Advancement Exam card.
- [ ] Owner `/ops-guide`: monthly/advancement controls, flag reference, flow.
- [ ] SYSTEM-MAP + STATUS updated.
- [ ] Rollout: enable flags, pilot on owner, then all students.
- **Verify:** guides live; full experience verified end-to-end.

---

## Cross-cutting (every phase)
- Full test suite green; bump `BOT_VERSION` on each bot deploy.
- Bilingual, Arabic-first, bidi-safe.
- Every AI op flag-gated + try/except + graceful fallback.
- Reuse Itqan infrastructure wherever possible (DRY).
- With all flags OFF = production identical to today.

## Suggested priority
Monthly (Phases 0–3) first, then Advancement (Phases 4–6), then Guides (Phase 7).
Monthly is lighter and gives students a taste before the high-stakes exam.
