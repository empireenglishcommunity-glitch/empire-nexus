# Tasks — Tatawwur (تطور): System Evolution

> **How to use this file:** same discipline as Aegis/Bawaba/Nabd — work
> top to bottom, check off tasks, ship behind feature flags. Each phase
> builds on the previous but is independently valuable.

---

## Phase T0 — Voice Progress Portfolio (THE proof)

- [ ] **T0.1** Add `voice_portfolio` table to `database.py`:
  (discord_id, recorded_at, recording_url, recording_type, week, level,
  duration_seconds, ai_score, notes)
- [ ] **T0.2** Add Day 1 benchmark prompt to the tutorial quest (Bawaba
  B2): after step 5, add step 6: "Record yourself reading this sentence
  in English" → store as type='benchmark_day1'
- [ ] **T0.3** Add periodic benchmark prompt: every 4 weeks, DM the
  student with a standardized sentence to read and record.
- [ ] **T0.4** Add `!portfolio` / `!صوتي` command: shows chronological
  list of recordings with dates, scores, and playback links.
- [ ] **T0.5** Wire advancement exam recordings (already collected via
  the exam DM flow) into the portfolio table automatically.
- [ ] **T0.6** Gate behind `tatawwur_portfolio` flag.

## Phase T1 — Conversational Patterns Library

- [ ] **T1.1** Create `content/patterns/` directory with JSON files per
  category (greetings, opinions, agreement, disagreement, clarifying,
  transitions, reactions). 5-10 patterns per category for L0-L1.
- [ ] **T1.2** Add `get_daily_pattern(week, day, level)` to
  `curriculum.py` — returns one pattern for today.
- [ ] **T1.3** Integrate into daily task post: add a "Today's Pattern"
  section showing the phrase + when to use it + Arabic meaning.
- [ ] **T1.4** Integrate into speaking mission: "Use today's pattern in
  your recording."
- [ ] **T1.5** Gate behind `tatawwur_patterns` flag.

## Phase T2 — Spaced Repetition Engine

- [ ] **T2.1** Add `vocab_srs` table: (discord_id, word, ease_factor,
  interval_days, next_review_date, review_count, last_score)
- [ ] **T2.2** Implement SM-2 algorithm functions: `schedule_review()`,
  `get_due_reviews(discord_id, limit)`, `record_review_result()`.
- [ ] **T2.3** When a student does `!done vocab` and passes the quiz,
  add the word to their SRS queue with initial interval=1 day.
- [ ] **T2.4** Modify the vocab quiz to include 2-3 REVIEW words (from
  SRS due today) alongside the current-day quiz.
- [ ] **T2.5** Add `!words` / `!كلماتي` command: shows vocab stats
  (total words, known, learning, weak, next review count).
- [ ] **T2.6** Gate behind `tatawwur_srs` flag.

## Phase T3 — Ability Milestones

- [ ] **T3.1** Add `ability_milestones` table: (discord_id, milestone_id,
  completed_at, evidence_url, level)
- [ ] **T3.2** Define milestone sets per level (5 milestones for L0,
  5 for L1, 5 for L2) — concrete, testable challenges.
- [ ] **T3.3** Add `!abilities` / `!قدراتي` command: shows
  completed ✅ vs. pending ⬜ milestones for their current level.
- [ ] **T3.4** Add `!challenge <milestone_id>` command to attempt a
  milestone (triggers the specific challenge prompt).
- [ ] **T3.5** On completion: auto-post to #success-stories (with
  permission check).
- [ ] **T3.6** Gate behind `tatawwur_milestones` flag.

## Phase T4 — AI Pronunciation Scoring (Groq Whisper)

- [ ] **T4.1** Add Groq Whisper integration to `ai_engine.py`:
  `transcribe_audio(audio_url) -> str` (calls Groq's audio transcription API).
- [ ] **T4.2** Add `score_pronunciation(expected_text, actual_transcription)
  -> dict` — word-level accuracy, flagged problem patterns.
- [ ] **T4.3** Wire into the accent task verification: after audio is
  uploaded, transcribe it and compare to the expected sentence
  (`record_this` field from accent drills).
- [ ] **T4.4** Store scores in `voice_portfolio` table (ai_score field).
- [ ] **T4.5** Add pronunciation trend to `!portfolio`: "Your accent
  accuracy: Week 1: 45% → Week 4: 72% → Now: 85%"
- [ ] **T4.6** Provide specific feedback: "Focus on: /θ/ ('th' sound) —
  you consistently say /z/ instead. Practice: think, this, that."
- [ ] **T4.7** Gate behind `tatawwur_pronunciation` flag.
- [ ] **T4.8** Handle Groq free-tier limits (1000 req/day): queue and
  batch if needed, fallback to simple ✅ if quota exhausted.

## Phase T5 — Structured Conversation Sessions

- [ ] **T5.1** Add `conversation_sessions` table: (id, scheduled_at,
  level, status, participant_ids)
- [ ] **T5.2** Add `!conversation` / `!محادثة` command: sign up for
  next session. Bot pairs same-level students.
- [ ] **T5.3** Add conversation prompts per level (stored in
  `content/conversations/` JSON files).
- [ ] **T5.4** Add a weekly scheduled loop: 30 min before session time,
  DM paired partners with prompt + voice channel info.
- [ ] **T5.5** After session: bot posts debrief prompt in channel,
  attendance counts toward `community` task.
- [ ] **T5.6** Gate behind `tatawwur_conversations` flag.

## Phase T6 — Student Showcase / Success Stories

- [ ] **T6.1** Add `#success-stories` channel to `setup_server.py`
  (public, read-only for non-admin).
- [ ] **T6.2** Auto-post on: level advancement, 30-day streak,
  pronunciation improvement ≥20%, all ability milestones complete.
- [ ] **T6.3** Add `!showcase` admin command: manually post a curated
  success story with before/after recordings.
- [ ] **T6.4** Monthly stats auto-post: "This month: X improvements,
  Y milestones, Z conversation hours."
- [ ] **T6.5** Gate behind `tatawwur_showcase` flag.

## Phase T7 — Adaptive Difficulty

- [ ] **T7.1** Add `pace_factor` column to `members` table (default 1.0).
- [ ] **T7.2** Weekly pace recalculation (in the existing weekly loops):
  completion >90% for 2 weeks → speed up; <50% for 2 weeks → slow down.
- [ ] **T7.3** Manifestation: fast learners get bonus challenges,
  slow learners get fewer tasks + more review content.
- [ ] **T7.4** Notify the student when their pace adjusts (transparent).
- [ ] **T7.5** Gate behind `tatawwur_adaptive` flag.

---

## Cross-phase notes

- **Feature flag naming:** all use `tatawwur_` prefix.
- **Ghost bot testing:** test each phase on ghost bot first.
- **The founder's recordings:** YOU (the owner) should record benchmark
  sentences that serve as the "native model" for comparison. Same
  sentences students are asked to read. This is the differentiator —
  YOUR accent journey IS the proof the system works.
- **Groq rate limits (T4):** 1000 req/day free tier. With 16 students
  doing 1-2 recordings/day each, that's ~32 requests. Plenty of room.
  At 100+ students, need to monitor and potentially batch.
- **Content creation (T1, T3, T5):** patterns, milestones, and
  conversation prompts need to be AUTHORED (curated, not AI-generated)
  — they define the unique value of the system. The agent creates the
  infrastructure; the founder creates the content that fills it.
