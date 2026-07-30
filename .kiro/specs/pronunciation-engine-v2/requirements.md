# Nutq 2 — Accurate Self-Hosted Pronunciation Engine — Requirements

**Codename:** Nutq 2 (نُطق) — the accurate engine behind the shipped Nutq feature.
**Status:** DRAFT — awaiting owner approval before any implementation.
**Supersedes:** the *scoring engine* of `pronunciation-feedback` (Nutq 1). It does
**not** replace Nutq 1's delivery pipeline (page recorder → endpoint → flag →
on-page panel → heard-vs-target → try-again → storage), which is kept and reused.

---

## Background (why this exists — verified, not assumed)

Nutq 1 shipped and was piloted with BioRoMa + Mai. The pilot did its job: it
exposed that the scoring **feels unreal**. Root cause, confirmed by reading the
code and by a live test against the pilot student's real data:

- The engine scores with **Groq Whisper transcription + word comparison**. Whisper
  is engineered to output clean, correct text, so when a learner mispronounces, it
  quietly "hears" the intended words. The result: reading **wrong** still scored
  well and returned praise ("feedback based on what I said"). The pronunciation
  signal (dropped sounds, wrong stress, accent errors) is discarded at the
  transcription step, and the word-comparison layer then adds even more leniency
  (40% floor, +level bonus, fuzzy + accent tolerance).
- **Conclusion:** the current approach measures *"did you say roughly the right
  words?"*, not *"how well did you pronounce them?"*. No tuning fixes this — the
  needed signal is gone before scoring begins.

**Owner decisions locked (2026-07):**
- Build a **real pronunciation engine** that scores **acoustically at the
  phoneme/word level** against each day's task text.
- It must be **free on the long run and fully owned** — **self-hosted**, no
  per-use vendor fee, no quota that grows with student count.
- Build it on the **current server** for the pilot (measured: 2 vCPU, ~2 GB free
  RAM, no GPU); **grow hardware only when real growth demands it** (Hetzner rescale
  / cheaper-region migration is a separate, later decision — not required now).
- Keep the **Nutq 1 delivery pipeline** and the same on-page experience.

---

## Requirements (EARS-style acceptance criteria)

### R1 — Real phoneme-level scoring against the day's task (core)
WHEN a student records an **accent** or **shadowing** exercise on the practice
page, THE SYSTEM SHALL score their pronunciation by comparing the **sounds they
produced** against the **expected sounds of that exercise's exact target text for
that specific week/day/level**, and return an accuracy score (0–100) plus the
specific words/sounds that were mispronounced.

### R2 — Correctly detects a wrong read
WHEN a student reads the target **incorrectly** (wrong or badly mispronounced
words), THE SYSTEM SHALL return a **meaningfully lower** score and identify the
failed word(s)/sound(s); WHEN a student reads it **well**, THE SYSTEM SHALL return
a **high** score. (This is the acceptance test the pilot failed.)

### R3 — Self-hosted, free, and owned
THE SYSTEM SHALL run the scoring engine on Empire's **own infrastructure** using
**open-source** models, with **no per-request cost** and **no external
pronunciation-scoring vendor**. Groq/LLM MAY be used only for optional warm
feedback wording, never for the score itself, and the score MUST work if that
optional call is unavailable.

### R4 — Fits the current server, capped, and cannot starve the bot
THE SYSTEM SHALL run within a **hard memory limit** sized to fit the current
server (target ≤ ~1 GB RSS for the scorer), isolated from the student-facing bot
(its own process/container), so that heavy audio work can never exhaust RAM/CPU
for the bot or the other 8 containers.

### R5 — Best-effort and NEVER blocks the core flow
THE SYSTEM SHALL record exercise completion and post to `#showcase` **before**
scoring, and IF scoring is slow, fails, or is disabled, THE SYSTEM SHALL still
complete the exercise and post normally, showing a neutral "saved — couldn't score
this time" note (never an error, never a lost completion). Scoring SHALL run within
a bounded time budget (target ≤ ~8 s) with a visible "🎧 checking…" indicator.

### R6 — Beginner-kind, but honest (Arabic L0 fairness)
THE SYSTEM SHALL be fair to Arabic L0 learners — giving **partial credit** for
known Arabic-speaker sound substitutions (e.g. /p/↔/b/, /v/↔/f/, θ/ð) and using
warm, encouragement-first wording — **without** hiding a genuinely low score for a
wrong read. Fairness thresholds SHALL be **calibrated on real Arabic-accented
samples** (a dedicated tuning phase), not guessed.

### R7 — Reuse the Nutq 1 delivery pipeline unchanged
THE SYSTEM SHALL plug into the existing `POST /api/submit-recording` and
`POST /api/pronunciation-check` paths and return the **same `pronunciation` JSON
shape** already consumed by the dojo UI (`scored`, `score`, `feedback_en`,
`feedback_ar`, `missed_words`, `transcript`/heard, `expected`), so the on-page
panel, heard-vs-target, and "try again" require **no dojo change**.

### R8 — Actionable bilingual feedback
WHEN a score is shown, THE SYSTEM SHALL name the specific word(s)/sound(s) to work
on and give **one** short, actionable tip, in English + Egyptian Arabic,
encouragement-first, NOT Nour-voiced, and SHALL NOT critique grammar/content.

### R9 — Scope: accent + shadowing only
THE SYSTEM SHALL score only **accent** and **shadowing** (exact target text).
Free-form **speaking** (a prompt, no exact words) is explicitly OUT of scope for
accuracy scoring here.

### R10 — Score against exactly what the student saw
THE SYSTEM SHALL score against the **same target text the page displayed** for that
exercise/day, eliminating drift between the page and the server. WHERE a day has no
scoreable target (e.g. an assessment-day passage with no `record_this`), THE SYSTEM
SHALL score the shown passage or cleanly skip (R5), never score against a different
sentence.

### R11 — Persistence + existing progress intact
THE SYSTEM SHALL store each score to `pronunciation_scores` so `!progress`
continues to work, with no breaking schema change (a read-only/additive column for
phoneme detail is allowed).

### R12 — Privacy
Pronunciation feedback SHALL remain private to the student's own authenticated
session, never posted publicly. `#showcase` posting behavior is unchanged.

### R13 — Flag-gated pilot → rollout
THE SYSTEM SHALL gate the new engine behind `tatawwur_pronunciation` (currently
OFF), pilot on BioRoMa + Mai, live-verify R1/R2, then enable for all students.

### R14 — Designed to scale (portable, horizontal)
THE SYSTEM SHALL be **stateless and horizontally scalable** — scoring capacity
grows by running additional identical scorer instances and/or moving to a larger
host — with **no rewrite** required as the student count grows.

---

## Non-goals (explicitly out of scope)
- Free-form speaking-accuracy / fluency scoring (future spec).
- Prosody/intonation scoring in v1 (may be a later enhancement).
- Re-enabling adaptive difficulty (`tatawwur_adaptive`).
- Any change to completion/points/streak/mastery, or to `#showcase` posting.
- Hardware upgrade / server migration (separate decision; not required for v1).

## Constraints
- Open-source, self-hosted, CPU-only (no GPU on the current box).
- Hard memory cap; best-effort; flag-gated; bilingual (EN + Egyptian Arabic).
- Same safe-deploy discipline: own PR per phase, tests green, owner-merged,
  backup before server change, live-verify, zero disruption to the daily flow.
- **No guessing:** a feasibility spike measures model RAM/latency/accuracy on the
  real server before we commit to the full build.
