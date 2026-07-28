# Pronunciation Feedback — Requirements

**Codename:** (pending — suggest "Nutq" / نُطق = "pronunciation/speech")
**Status:** DRAFT — awaiting owner approval before any implementation.
**Owner decisions locked (2026-07-28):** D1 page · D2 synchronous best-effort ·
D3 accent + shadowing only · D4 reuse "Send to Discord" · D5 keep beginner-kind ·
D6 show missed word + sound tip · D7 adaptive OUT of scope · D8 flag-gated pilot →
all 16. Plus the four "out-of-box" enhancements (R5, R6, R11, R12), scoped into
later phases.

---

## Background (why this exists)

The bot already contains a complete, beginner-kind pronunciation-scoring engine
(`src/pronunciation_scorer.py`): Groq-Whisper transcription, Arabic-speaker sound
tolerance, stop-word forgiveness, fuzzy matching, a 40% floor, level-aware bonus,
first-3-recordings grace, and warm bilingual feedback (runs on Groq, so it works
without Gemini). It stores results to `pronunciation_scores` (which already feeds
`!progress`).

Since the Session-33 "Empire Reset" moved the 5 core exercises to the practice
page, the engine's **only trigger** (`!done accent` / `!done shadow`) is now
redirected to the page before it runs — so `_score_pronunciation` is unreachable
and students get **no pronunciation feedback** when they record on the page. The
`tatawwur_pronunciation` flag is currently OFF (it did nothing while on).

This spec re-connects that engine to where students actually record now — the
practice-page recording flow (`POST /api/submit-recording`) — and surfaces kind,
immediate feedback in the recorder UI.

---

## Requirements (EARS-style acceptance criteria)

### R1 — Immediate on-page feedback (D1)
WHEN a student finishes an **accent** or **shadowing** recording on the practice
page and sends it, THE SYSTEM SHALL score their pronunciation and display a score
+ warm bilingual (English + Egyptian Arabic) message **in the recorder area of
the same page**, without a page change and without requiring Discord.

### R2 — Scoring is best-effort and NEVER blocks the core flow (D2)
THE SYSTEM SHALL record exercise completion and post the recording to `#showcase`
**before** attempting scoring, and IF transcription/scoring is slow, fails, or is
disabled, THE SYSTEM SHALL still complete the exercise and post normally, showing
a neutral "saved — couldn't score this time" note (never an error, never a lost
completion).

### R3 — Beginner-kind scoring preserved (D5)
THE SYSTEM SHALL reuse the existing engine's kindness behaviors unchanged:
first-3-recordings encouragement-only (no number), 40% score floor, Arabic-speaker
sound tolerance, stop-word forgiveness, fuzzy matching, and level-aware leniency.

### R4 — Actionable, specific feedback (D6)
WHEN a score is shown, THE SYSTEM SHALL name the specific word(s) the student
missed and give **one** short, actionable tip, in both English and Egyptian
Arabic. Feedback SHALL be encouragement-first and SHALL NOT correct grammar or
critique content (that is `#writing-feedback`'s job).

### R5 — Visual "heard vs. target" (out-of-box)
WHEN a score is shown, THE SYSTEM SHALL display what the recognizer heard next to
the target sentence, with the missed word(s) highlighted, so the fix is concrete.

### R6 — Instant "try again" loop (out-of-box)
AFTER feedback is shown, THE SYSTEM SHALL offer a one-tap "try again" that lets the
student re-record and re-score **in place**, turning one recording into deliberate
practice. Re-scoring SHALL NOT create duplicate completions or double-count points
(completion/mastery is already once-per-day; re-scores only refresh the feedback).

### R7 — Persistence + trend (D1 tail)
THE SYSTEM SHALL store each score to `pronunciation_scores` so the existing
`!progress` average continues to work, and (out-of-box, R11) surface a simple
pronunciation trend to the student.

### R8 — Scope: accent + shadowing only (D3)
THE SYSTEM SHALL score only **accent** and **shadowing** (which have exact target
text). Speaking is open-ended (a prompt, no exact words) and is explicitly OUT of
scope for accuracy scoring in this spec.

### R9 — Privacy (D1)
Pronunciation feedback SHALL be private to the student (shown only in their own
authenticated recorder session), never posted publicly. The existing `#showcase`
recording post behavior is unchanged.

### R10 — Flag-gated pilot → rollout (D8)
THE SYSTEM SHALL gate the feature behind `tatawwur_pronunciation`, ship it OFF,
and roll it out to 1–2 pilot students first (BioRoMa / Mai), live-verify, then
enable for all 16.

### R11 — Pronunciation trend surface (out-of-box, later phase)
THE SYSTEM SHALL (in a later phase) show the student their pronunciation trend
(e.g., a small sparkline/average on the page or calendar) using stored scores.

### R12 — Owner teaching insight (out-of-box, later phase)
THE SYSTEM SHALL (in a later phase) give the owner a periodic "which sounds/words
the cohort is struggling with most" summary via Empire Ops, turning individual
scores into teaching intelligence. Aggregate only; no per-student shaming.

### R13 — Bounded cost & latency (D2)
Scoring SHALL run within a bounded time budget (target ≤ ~8s) with a visible
"🎧 checking…" indicator; on timeout it degrades per R2. Transcription cost
(Groq Whisper, ~2 recordings/day/student × 16) SHALL remain negligible.

---

## Non-goals (explicitly out of scope)
- Speaking-accuracy scoring (open-ended; different feedback model — future spec).
- Re-enabling adaptive difficulty (`tatawwur_adaptive`) — separate decision (D7).
- Any change to how recordings are stored/posted to `#showcase`.
- Any change to completion/points/streak/mastery mechanics.

## Constraints
- Reuse the existing engine + `pronunciation_scores` table (no schema change for
  the core; R12 may add a read-only query, not a table).
- No new paid vendor (Groq Whisper already provisioned; feedback on Groq).
- Bilingual (EN + Egyptian Arabic) student-facing copy; NOT Nour-voiced.
- Same safe-deploy discipline: flag-gated, phased, tests green, owner-merged,
  live-verified, zero disruption to the daily flow.
