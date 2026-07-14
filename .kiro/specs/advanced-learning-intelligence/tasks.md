# Tasks — Dhaka' (ذكاء): Advanced Learning Intelligence

> **How to use this file:** same discipline as all other specs — work
> top to bottom, check off tasks. Each phase builds on the previous.

---

## Phase P0 — Pronunciation Scoring Infrastructure

- [x] **P0.1** Add `pronunciation_scores` table to `database.py` schema.
  Add migration for existing databases (ALTER TABLE if not exists).
- [x] **P0.2** Add `GROQ_WHISPER_MODEL` config to `config.py`
  (default: `whisper-large-v3`).
- [x] **P0.3** Create `src/pronunciation_scorer.py` with:
  - `download_audio(url)` → returns bytes
  - `transcribe_audio(audio_bytes)` → calls Groq Whisper API → returns text
  - `compare_words(transcript, expected)` → returns (score, missed_words)
  - `generate_feedback(score, expected, transcript, missed_words)` → calls Gemini
  - `score_recording(audio_url, expected_text, discord_id, task_id)` → full pipeline
- [x] **P0.4** Add `store_pronunciation_score()` and
  `get_recent_scores(discord_id, days=7)` to `database.py`.
- [x] **P0.5** Unit test the word comparison algorithm with 10+ cases
  (exact match, partial, completely wrong, empty, extra words, etc.)

## Phase P1 — Wire Into !done Flow

- [x] **P1.1** In `bot.py` `cmd_done`: after `verify_audio()` succeeds
  for `accent` task, fire `asyncio.create_task(_score_and_notify(...))`.
  This must NOT block the !done response — student gets their points
  immediately, scoring happens in background.
- [x] **P1.2** Implement `_score_and_notify()`: calls `score_recording()`,
  then DMs the student with their score + feedback. Handle all errors
  (log + skip, never crash).
- [x] **P1.3** Get the expected text from `curriculum.get_daily_content()`
  → `accent_drill.record_this` for the student's level/week/day.
- [x] **P1.4** Identify the audio attachment: when `!done accent` runs,
  pass the audio URL from the most recent attachment in `#l{X}-showcase`
  (already found by `verify_audio()` — thread the URL through).
- [x] **P1.5** Test end-to-end: upload a test audio, run `!done accent`,
  verify score arrives in DM within 30 seconds.
- [x] **P1.6** Enable `tatawwur_pronunciation` flag. Monitor logs for
  1 day before proceeding.

## Phase P2 — Shadowing Scoring + Portfolio

- [x] **P2.1** Extend `_score_and_notify()` to also handle `shadow` task
  (same pipeline, different expected text source — shadowing passage).
- [x] **P2.2** Update `!portfolio` command to show last 7 pronunciation
  scores with dates and trend arrow (↑ improving / → stable / ↓ declining).
- [x] **P2.3** Update the `/api/progress` endpoint to include
  `pronunciation` object in the response (last_score, average_7d, trend).
- [x] **P2.4** Update practice platform's ConnectedProgress to display
  pronunciation stats when connected.

## Phase A0 — Adaptive Difficulty Engine

> **Prerequisite:** Phase P1 deployed and generating real scores for
> at least 7 days. Do NOT start this phase before you have real data.

- [x] **A0.1** Add `difficulty_level` column to `members` table
  (INTEGER DEFAULT 2). Add migration.
- [x] **A0.2** Create `src/adaptive_engine.py` with:
  - `get_difficulty(discord_id)` → returns 1/2/3
  - `check_and_adjust(discord_id)` → reads last 7 scores, adjusts if threshold crossed
  - `get_difficulty_label(level)` → "Easy" / "Normal" / "Challenging"
- [x] **A0.3** Call `adaptive_engine.check_and_adjust()` at end of
  `_score_and_notify()` (after storing the new score).
- [x] **A0.4** If difficulty changes: DM the student with an encouraging
  message explaining the adjustment (Arabic + English).

## Phase A1 — Difficulty Affects Content

- [x] **A1.1** In `tasks.py` `generate_daily_tasks()`: read member's
  `difficulty_level` and adjust parameters:
  - Easy: shorter sentences, fewer minimal pairs, repeat material
  - Challenging: longer sentences, more pairs, faster speed
- [x] **A1.2** In the practice platform URL generation: optionally pass
  a `?speed=` parameter that the web platform respects for TTS rate.
- [x] **A1.3** Update `!progress` / `!level` to show current difficulty
  level with an appropriate emoji.
- [x] **A1.4** Enable `tatawwur_adaptive` flag. Monitor for 1 week.

## Phase A2 — Refinement (after 2+ weeks of data)

- [x] **A2.1** Analyze real scoring data: are thresholds (85%/50%)
  appropriate? Adjust if too aggressive or too lenient.
- [x] **A2.2** Add hysteresis: don't oscillate difficulty every day.
  Require 3 consecutive days above/below threshold to change.
- [x] **A2.3** Add `!difficulty` command so students can see and
  optionally override their difficulty level.
- [x] **A2.4** Weekly admin report: how many students at each difficulty
  level, score distributions, any stuck students.

---

## Cross-phase notes

- **Phase P depends on Groq API key** already in `.env` (confirmed present).
- **Phase A depends on Phase P data** — minimum 7 days of scoring history
  before adaptive logic can make meaningful decisions.
- **All scoring is async/non-blocking** — never delay `!done` response.
- **All failures are silent to the student** — they still get their points.
  Errors are logged for admin review.
- **Flag gating:** `tatawwur_pronunciation` gates all scoring;
  `tatawwur_adaptive` gates difficulty adjustment separately. Both can
  be disabled instantly without redeploy.
- **Test with the Ghost bot first** (Empire Ghost#3420) before enabling
  on the main bot, following Aegis discipline.
