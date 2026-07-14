# Design — Dhaka' (ذكاء): Advanced Learning Intelligence

## Architecture Overview

```
Student uploads audio to #l{X}-showcase
         ↓
Student types !done accent
         ↓
verification.py → verify_audio() [existing — checks file exists]
         ↓ (new)
pronunciation_scorer.py → score_recording()
  1. Download audio from Discord CDN (attachment URL)
  2. Send to Groq Whisper API → get transcript
  3. Compare transcript vs expected_text (word-level diff)
  4. Generate score (0-100) + feedback (via Gemini)
  5. Store in pronunciation_scores table
  6. Return score + feedback to bot
         ↓
bot.py → DM student with score + tips
         ↓ (async, non-blocking)
adaptive_engine.py → check_and_adjust()
  1. Read last 7 scores for this student
  2. Calculate rolling average
  3. If threshold crossed → adjust difficulty setting
  4. Next daily task uses adjusted difficulty
```

## Component 1 — Pronunciation Scorer (`src/pronunciation_scorer.py`)

**New module.** Handles the full scoring pipeline.

### API Flow

```python
async def score_recording(audio_url: str, expected_text: str, 
                          discord_id: str, task_id: str) -> ScoringResult:
    """
    1. Download audio from Discord CDN
    2. Transcribe via Groq Whisper
    3. Compare words (normalized)
    4. Generate feedback via Gemini
    5. Store result
    6. Return ScoringResult
    """
```

### Groq Whisper API

```
POST https://api.groq.com/openai/v1/audio/transcriptions
Headers: Authorization: Bearer <GROQ_API_KEY>
Body: multipart/form-data
  - file: <audio bytes>
  - model: "whisper-large-v3"
  - language: "en"
  - response_format: "json"
```

Free tier: 2 hours/day audio, 100 req/min — more than sufficient for
16 students × ~3 recordings/day = ~48 requests/day.

### Word-Level Comparison Algorithm

```python
def compare_words(transcript: str, expected: str) -> tuple[float, list[str]]:
    """
    1. Normalize both: lowercase, strip punctuation
    2. Split into words
    3. Compute word-level accuracy (Levenshtein on word sequence)
    4. Identify mismatched words (max 5)
    5. Return (accuracy_0_to_100, list_of_missed_words)
    """
```

### Feedback Generation (Gemini)

```python
SCORING_PROMPT = """
You are a pronunciation coach for Arabic speakers learning English.
The student tried to say: "{expected}"
They actually said: "{transcript}"
Accuracy: {score}%
Missed words: {missed_words}

Give brief, encouraging feedback in 2-3 sentences:
1. What they did well
2. 1-2 specific words to practice (with pronunciation tip)

Respond in this format:
ENGLISH: <feedback>
ARABIC: <same feedback in Egyptian Arabic>
"""
```

### Database Schema Addition

```sql
CREATE TABLE IF NOT EXISTS pronunciation_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    date            TEXT NOT NULL,
    task_id         TEXT NOT NULL,     -- 'accent' or 'shadow'
    score           REAL NOT NULL,     -- 0-100
    expected_text   TEXT NOT NULL,
    transcript      TEXT NOT NULL,
    missed_words    TEXT DEFAULT '',   -- JSON array
    feedback        TEXT DEFAULT '',
    audio_url       TEXT DEFAULT '',
    scored_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_pronunciation_scores 
    ON pronunciation_scores(discord_id, date);
```

## Component 2 — Adaptive Engine (`src/adaptive_engine.py`)

**New module.** Reads scoring history and adjusts difficulty.

### Difficulty Levels

| Level | Name | Criteria | Effect |
|:-----:|------|----------|--------|
| 1 | Easy | avg < 50% for 3+ days | Repeat current week, simpler sentences |
| 2 | Normal | default | Standard curriculum progression |
| 3 | Challenging | avg >= 85% for 7+ days | Faster speed, longer sentences |

### Storage

```sql
-- Add column to members table
ALTER TABLE members ADD COLUMN difficulty_level INTEGER NOT NULL DEFAULT 2;
```

### Logic

```python
def check_and_adjust(discord_id: str) -> Optional[str]:
    """
    1. Get last 7 pronunciation scores
    2. Calculate rolling average
    3. Compare to thresholds
    4. If change needed: update members.difficulty_level
    5. Return notification message or None
    """
```

### How Difficulty Affects Tasks

| Aspect | Easy (1) | Normal (2) | Challenging (3) |
|--------|----------|------------|-----------------|
| TTS speed | 0.5x | 0.7x | 1.0x |
| Record_this length | Short (≤8 words) | Medium (8-15) | Long (15+) |
| Minimal pairs | 3 | 5 | 7 |
| Shadowing passage | Same as last week | Current week | Next week preview |
| Vocab quiz | 5 words | 8 words | 12 words |

## Component 3 — Integration Points

### In `bot.py` (cmd_done)

After `verify_audio()` succeeds for accent/shadow tasks:

```python
# Pronunciation scoring (non-blocking — don't delay the !done response)
if database.is_feature_enabled("tatawwur_pronunciation"):
    asyncio.create_task(_score_and_notify(ctx, member, task_id))
```

### In `tasks.py` (generate_daily_tasks)

```python
# Adaptive difficulty (affects content selection)
if database.is_feature_enabled("tatawwur_adaptive"):
    difficulty = adaptive_engine.get_difficulty(discord_id)
    # Adjust content parameters based on difficulty
```

### In API (`api_server.py`)

Add pronunciation stats to the progress endpoint:

```python
"pronunciation": {
    "last_score": 78,
    "average_7d": 72,
    "trend": "improving",  # improving | stable | declining
    "difficulty": "normal"
}
```

## Failure Modes & Graceful Degradation

| Failure | Behavior |
|---------|----------|
| Groq Whisper API down | Skip scoring, log warning, accept submission normally |
| Groq rate limited | Queue for later? No — just skip this one, student still submits |
| Audio too short (<1 sec) | Skip scoring, accept submission |
| Audio is not speech (music, noise) | Whisper returns garbled text → low score, give generic "try again" feedback |
| Gemini feedback generation fails | Use template feedback based on score range |
| Student hasn't done 7 days yet | Adaptive engine does nothing (needs 7 data points) |

## Privacy & Data

- Audio files are downloaded temporarily to memory (never saved to disk)
- Only the transcript, score, and feedback are stored
- Audio URLs from Discord CDN expire after ~24h anyway
- Students can see their own scores; no one else can
