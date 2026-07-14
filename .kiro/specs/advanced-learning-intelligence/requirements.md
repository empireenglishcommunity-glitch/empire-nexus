# Requirements — Advanced Learning Intelligence ("Dhaka'")

> **Codename: Dhaka' (ذكاء).** Arabic for "intelligence" — this initiative
> adds AI-powered learning feedback that evolves with each student.
> Directory name (`advanced-learning-intelligence`) stays literal/technical
> so it's discoverable without knowing the codename.

## Origin

The Empire English system has 38 commands, 21 feature flags, full
curriculum delivery, and a gamified practice platform — but it currently
treats every audio recording as a binary "did they submit or not" check.
Students record accent drills, shadowing passages, and speaking missions
daily, uploading audio to `#l{X}-showcase` — but the bot only verifies
the file EXISTS (is it audio? is it recent?). It never actually LISTENS.

Two flags were registered but never built:
- `tatawwur_pronunciation` — "AI pronunciation scoring (Groq Whisper)"
- `tatawwur_adaptive` — "Adaptive difficulty pacing"

The user wants these built properly as a spec, not hacked in.

## Constraints

1. **Budget:** Same Hetzner CX23 (~$7/mo) + free/cheap AI APIs.
   Groq Whisper API: free tier available (audio transcription).
   Gemini: already in use, free tier sufficient.
   No new paid services.
2. **Architecture:** Must work within the existing Docker container
   (no new containers, no GPU, no heavy models).
3. **Graceful degradation:** If the AI scoring API is down or rate-
   limited, the system must fall back to the current behavior (accept
   submission, skip scoring). Never block a student from completing
   their daily tasks because an AI call failed.
4. **Privacy:** Audio is already uploaded to Discord (public channel).
   We download it for analysis, score it, then discard the file.
   Only the score and feedback text are stored.
5. **Student experience:** Scoring must feel ENCOURAGING, not punitive.
   Arabic speakers learning English already feel self-conscious about
   pronunciation — the feedback must be specific, actionable, and kind.
6. **Performance data required for adaptive:** The pronunciation scoring
   feature (Phase P) MUST be deployed and generating real scores for at
   least 1 week before the adaptive difficulty system (Phase A) can be
   calibrated. You cannot adapt to data you haven't collected yet.

## Requirements

### Requirement 1 — Pronunciation scoring must be automatic and immediate

**User story:** As a student, after I upload my accent drill recording,
I want to receive a pronunciation score and specific feedback within
30 seconds, so I know what to improve before my next attempt.

**Acceptance criteria:**
1. WHEN a student uploads audio to `#l{X}-showcase` and marks `!done accent`
   THEN the system SHALL download the audio, transcribe it via Whisper,
   compare it to the expected text, and return a score (0-100) with
   specific mispronounced words highlighted.
2. WHEN the AI scoring fails (API error, timeout, rate limit) THEN the
   system SHALL accept the submission normally with a note "scoring
   unavailable" — never block task completion.
3. Scoring SHALL complete within 30 seconds of the `!done` command.

### Requirement 2 — Scoring must compare against the expected text

**User story:** As a student practicing "Pat put the pen in the paper
bag", I want the system to tell me which specific words I mispronounced,
not just give me a generic score.

**Acceptance criteria:**
1. The system SHALL know what sentence the student was supposed to say
   (from the day's accent drill `record_this` field).
2. The score SHALL be based on word-level accuracy: how many words in
   the transcript match the expected text.
3. Feedback SHALL highlight the specific words that differed (max 3-5
   words, in both English and Arabic explanation).

### Requirement 3 — Scores must be stored and trackable over time

**User story:** As a student, I want to see my pronunciation improving
week over week, so I stay motivated.

**Acceptance criteria:**
1. Each scored recording SHALL be stored: discord_id, date, task_id,
   score (0-100), transcript, expected_text, feedback.
2. The `!portfolio` command SHALL show a pronunciation trend (last 7
   scores with dates).
3. The practice platform's ConnectedProgress API SHALL include
   pronunciation stats in the progress payload.

### Requirement 4 — Adaptive difficulty must adjust based on real performance

**User story:** As a student who consistently scores 90%+ on accent
drills, I want harder material (faster speech, longer sentences,
trickier minimal pairs), so I keep growing. As a student scoring below
60%, I want the system to give me simpler material and more repetition.

**Acceptance criteria:**
1. The system SHALL track a rolling average of the last 7 pronunciation
   scores per student.
2. IF average >= 85% for 7+ days THEN increase difficulty:
   - Faster TTS speed in shadowing
   - Longer record_this sentences
   - More challenging minimal pairs
3. IF average <= 50% for 3+ days THEN decrease difficulty:
   - Repeat this week's material instead of advancing
   - Show encouragement + specific tips
   - Recommend the easiest day's drill for re-practice
4. Difficulty adjustments SHALL be logged and visible to the student
   via `!level` or `!progress` (e.g. "Difficulty: Challenging ⬆️").

### Requirement 5 — Shadowing scoring (stretch goal)

**User story:** As a student, I want my shadowing recordings scored too
(not just accent drills), so I get feedback on rhythm and fluency.

**Acceptance criteria:**
1. Same pipeline as accent scoring, but for shadowing tasks.
2. Score based on: word accuracy + approximate timing match.
3. Gated behind a separate sub-flag or the same `tatawwur_pronunciation`
   flag (since it uses the same infrastructure).

## Out of Scope (explicitly)

- Real-time pronunciation scoring during recording (requires WebRTC +
  streaming Whisper — too complex for current infrastructure)
- Phoneme-level analysis (IPA comparison) — word-level is sufficient
  for the target audience (beginner/intermediate Arabic speakers)
- Custom model training — use off-the-shelf Whisper + text comparison
- Video analysis of mouth position — audio only
