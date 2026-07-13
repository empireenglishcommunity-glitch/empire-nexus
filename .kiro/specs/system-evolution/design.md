# Design — Tatawwur (تطور): System Evolution

## Architecture: Evidence-Based Transformation

The current system tracks ACTIVITY (did you do the task?). Tatawwur
adds the layer that tracks ABILITY (can you actually do the thing?).

```
Current System (Activity Layer):
  Tasks → Points → Streaks → Levels

Tatawwur (Ability Layer):
  Recordings → Scores → Abilities → Portfolio → Success Stories
       ↕            ↕           ↕            ↕
  Spaced Rep → Patterns → Conversations → Adaptive Pacing
```

Every enhancement feeds into ONE goal: creating undeniable, shareable,
audible PROOF that this student transformed.

---

## Component 1 — Voice Progress Portfolio

**The "before and after" that sells itself.**

### Design:
- New `voice_portfolio` table: stores recording metadata (discord_id,
  recorded_at, recording_url, type [benchmark/daily/assessment], week,
  duration_seconds, ai_score)
- Benchmark recordings taken at:
  - Day 1 (first join — "read this sentence" prompt in the tutorial)
  - End of each level (advancement exam recordings already exist!)
  - Every 4 weeks (periodic check-in via a scheduled prompt)
- `!portfolio` / `!صوتي` command: shows a chronological list of their
  recordings with dates and scores
- Storage: recordings stay on Discord (attachment URLs) + metadata in
  the DB. No server-side file storage needed (Discord CDN handles it).

### Key insight:
The advancement exam ALREADY collects a speaking recording (the exam DM
flow saves `speaking_recording_url`). Tatawwur just needs to also save
a benchmark recording on day 1, and provide a way to VIEW the
progression.

---

## Component 2 — AI Pronunciation Scoring

**Makes accent training REAL, not just "upload and ✅".**

### Design:
- Use Groq's Whisper (free tier: speech-to-text) to transcribe the
  student's audio → compare to expected text → calculate accuracy
- Use phoneme comparison: the student reads a KNOWN sentence (displayed
  in the task), the AI transcribes what they actually said, differences
  reveal pronunciation issues
- Scoring: overall accuracy % + specific flagged sounds
- Store scores over time → trend analysis

### Approach (no paid service needed):
1. Student reads a known sentence (e.g. "The cat sat on the mat")
2. Audio submitted via Discord (#showcase or DM)
3. Bot sends to Groq Whisper → gets transcription
4. Compare transcription to expected text:
   - Word-level accuracy (did they say the right words?)
   - Phoneme-level patterns (consistent /r/→/l/ substitution?)
5. Return: "Score: 78%. Focus on: 'th' sounds — you said 'ze' instead
   of 'the'. Practice: 'think, this, that'"

### Limitation:
Groq's Whisper transcription reveals WHAT they said, not exactly HOW
they said it at the phoneme level. For a $7/mo system, this is the
best available approach. A native speaker (the founder) can provide
subjective feedback on recordings flagged as low-scoring.

---

## Component 3 — Ability Milestones

**Students feel what they CAN DO, not just points.**

### Design:
Per-level "I can now..." challenges that are TESTED, not self-reported:

**Level 0 milestones:**
- [ ] Introduce yourself in 30 seconds (tested: recording submitted)
- [ ] Order food at a restaurant (tested: role-play scenario prompt)
- [ ] Describe 5 objects in the room (tested: recording + word count)
- [ ] Count to 100 without pausing (tested: recording duration)
- [ ] Spell your full name letter by letter (tested: transcription match)

**Level 1 milestones:**
- [ ] Tell a 2-minute story about your day (tested: recording duration + coherence)
- [ ] Explain how to cook your favorite food (tested: recording)
- [ ] Have a 3-minute phone conversation (tested: paired session log)
- [ ] Read a news headline and explain it (tested: comprehension quiz)

**Level 2 milestones:**
- [ ] Give a 5-minute presentation on any topic (tested: recording)
- [ ] Debate a topic for 3 minutes (tested: paired session)
- [ ] Write a 300-word essay without a translator (tested: writing submission)

**Implementation:**
- New `ability_milestones` table (discord_id, milestone_id, completed_at, evidence_url)
- `!abilities` / `!قدراتي` command: shows completed vs. pending milestones
- Each milestone completion auto-posts to #success-stories (with permission)

---

## Component 4 — Spaced Repetition Engine

**Words actually STICK.**

### Design:
- New `vocab_srs` table: (discord_id, word, ease_factor, interval_days,
  next_review_date, review_count, last_score)
- SM-2 algorithm (same as Anki — proven, simple):
  - New word: review tomorrow
  - Got it right: double the interval
  - Got it wrong: reset to 1 day
  - Ease factor adjusts per word (some words are harder for this student)
- Integrated into the daily `vocab` task: instead of (or in addition to)
  new words, the vocab quiz pulls REVIEW words from the SRS queue
- `!words` / `!كلماتي` command: shows vocab strength stats
  (known / learning / weak / total)

### Flow:
1. Daily task posts 8 new words (current behavior)
2. When student does `!done vocab`, the quiz now includes 2-3 REVIEW
   words alongside the current-day quiz
3. Correct answers extend the interval; wrong answers reset it
4. Over time, the student's "known" count grows (visible motivation)

---

## Component 5 — Structured Conversation Sessions

**Can't get fluent by talking to yourself.**

### Design:
- Weekly scheduled conversation sessions (voice channel, 30 min)
- Bot facilitates pairing: matches students at similar levels
- Provides conversation prompts based on level:
  - L0: "Introduce yourself. Ask your partner 3 questions."
  - L1: "Describe what you did yesterday. Your partner asks follow-ups."
  - L2: "Discuss: Is social media good or bad? Take turns for 2 min each."
- Session attendance tracked: counts toward `community` task for the day
- Post-session: each participant rates their partner's fluency (peer feedback)

### Implementation:
- `!conversation` / `!محادثة` command: sign up for next session
- Bot DMs paired partners 30 min before the session starts
- A voice channel is designated for each pair (or small group)
- After 30 min, bot posts a summary prompt: "How did it go? Rate 1-5"

---

## Component 6 — Conversational Patterns Library

**How natives ACTUALLY talk.**

### Design:
- A curated library of conversational patterns grouped by function:
  - Greetings (formal / informal / slang)
  - Opinions ("I think...", "In my opinion...", "If you ask me...")
  - Agreement ("That makes sense", "Exactly!", "I see what you mean")
  - Disagreement ("I'm not sure about that", "Actually, I think...")
  - Clarifying ("What do you mean by...?", "Could you repeat that?")
  - Transitions ("By the way...", "Speaking of which...", "Anyway...")
  - Reactions ("No way!", "That's crazy!", "I had no idea!")
- Delivered as a "Daily Pattern" alongside the existing daily tasks
- Each pattern: the phrase + when to use it + example dialogue + Arabic
  meaning (natural, not literal translation)
- Students practice using the pattern in their speaking task

### Implementation:
- New content directory: `content/patterns/` (JSON files per category)
- Integrated into the daily task post: "Today's Pattern: ..."
- The speaking mission references the day's pattern: "Use today's
  pattern in your recording"

---

## Component 7 — Student Showcase / Success Stories

**Social proof that grows the community.**

### Design:
- `#success-stories` channel (public, read-only for students)
- Auto-posted by the bot when:
  - A student completes all ability milestones for a level
  - A student's pronunciation score improves by 20%+ over a month
  - A student passes an advancement exam
  - A student hits 30/60/100 day streak
- With the student's permission: includes their voice recordings
  (before/after) as proof
- Monthly community stats post: "This month: X members improved, Y
  new milestones completed, Z hours of speaking practice"

### Marketing angle:
These success stories, accumulated over months, become the marketing
engine. Not ads — PROOF. "Here's Ahmed, 3 months ago vs. today.
Listen to the difference." Shareable on social media, embeddable in
landing pages.

---

## Component 8 — Adaptive Difficulty

**No one left behind, no one held back.**

### Design:
- A `pace_factor` per member (stored in DB, default 1.0):
  - Completion rate >90% for 2 weeks: pace_factor += 0.2 (faster)
  - Completion rate <50% for 2 weeks: pace_factor -= 0.2 (slower)
  - Assessment score consistently >85%: suggest early exam
  - Assessment score consistently <60%: reduce daily task count
- Manifestation:
  - Fast learners: unlock next week's content early, get bonus
    challenges, see "🚀 You're progressing fast!"
  - Slow learners: review tasks replace new content, fewer daily
    tasks (4 instead of 7), encouraging tone ("Focus on quality")
- The student is TOLD when their pace adjusts (transparent, not hidden)

---

## Implementation Priority

| Phase | Component | Effort | Impact |
|---|---|---|---|
| T0 | Voice Progress Portfolio | Medium | Highest — THE proof |
| T1 | Conversational Patterns Library | Low | High — daily value |
| T2 | Spaced Repetition Engine | Medium | High — retention |
| T3 | Ability Milestones | Medium | High — motivation |
| T4 | AI Pronunciation Scoring (Groq Whisper) | Medium-High | Very High — differentiator |
| T5 | Structured Conversation Sessions | Medium | High — fluency bridge |
| T6 | Student Showcase / Success Stories | Low | Medium — marketing |
| T7 | Adaptive Difficulty | Medium | Medium — personalization |

---

## Open Design Questions

1. **AI pronunciation scoring accuracy:** Groq Whisper's transcription
   reveals what words were said, but not phoneme-level detail. Is
   word-accuracy sufficient, or do we need a more specialized model?
   (Answer: start with word-accuracy, iterate based on student feedback.)

2. **Conversation session facilitation:** who moderates? The founder?
   A bot can pair people but can't moderate a voice conversation.
   (Answer: first sessions moderated by founder, later by L2/L3 students
   who've graduated to "mentor" status.)

3. **Recording storage long-term:** Discord CDN URLs can expire for
   deleted messages. Should recordings be copied to the server's
   persistent storage? (Answer: yes, for the portfolio. Store a copy
   in the bot-data volume for benchmarks.)
