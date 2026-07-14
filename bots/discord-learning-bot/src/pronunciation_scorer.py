"""Dhaka' (ذكاء) — Pronunciation Scoring Engine.

Scores student audio recordings against expected text using:
1. Groq Whisper API for transcription
2. Fair, level-aware word comparison algorithm
3. Gemini for personalized, encouraging feedback

DESIGN PRINCIPLES:
- Scoring is ENCOURAGING, never punitive
- Arabic speakers get tolerance for known substitutions (p/b, v/f, th)
- Stop words (the, a, in, to) don't penalize the student
- Fuzzy matching: close pronunciations count (Levenshtein ≤ 2)
- Minimum floor: never show below 40% (reframe as progress)
- Beginner grace: first 3 recordings get encouragement only, no number
- Level-aware: L0 is generous, L3 is strict

All operations are async and designed to run as background tasks
(never block the !done response). All failures degrade gracefully
(log + skip, never crash the bot).
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import aiohttp

from . import config, database

logger = logging.getLogger("empire-bot.pronunciation")


@dataclass
class ScoringResult:
    """Result of scoring a pronunciation recording."""
    score: float  # 0-100 (after fairness adjustments)
    raw_score: float  # 0-100 (before adjustments)
    transcript: str
    expected_text: str
    missed_words: list[str]
    feedback_en: str
    feedback_ar: str
    is_beginner_grace: bool = False  # First 3 recordings — no score shown
    success: bool = True
    error: str = ""


# Words that don't penalize the student if missing/extra
STOP_WORDS = frozenset([
    "the", "a", "an", "in", "on", "at", "to", "of", "for", "is", "it",
    "and", "or", "but", "my", "your", "his", "her", "its", "this", "that",
    "was", "were", "be", "been", "have", "has", "had", "do", "does", "did",
])

# Known Arabic-speaker sound substitutions (transcript → expected)
# If Whisper transcribes one of these substitutions, it's a PARTIAL match (not full miss)
ARABIC_SUBSTITUTIONS = {
    "b": "p", "p": "b",   # /p/ ↔ /b/
    "f": "v", "v": "f",   # /v/ ↔ /f/
    "s": "th", "z": "th", # th sounds
    "d": "th",
}


# ============================================================
#  AUDIO DOWNLOAD
# ============================================================

async def download_audio(url: str) -> Optional[bytes]:
    """Download audio from a Discord CDN URL. Returns bytes or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    logger.warning(f"Audio download failed: HTTP {resp.status} for {url[:80]}")
                    return None
                data = await resp.read()
                if len(data) < 1000:  # Less than 1KB = probably not real audio
                    logger.warning(f"Audio too small ({len(data)} bytes), skipping")
                    return None
                return data
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        return None


# ============================================================
#  GROQ WHISPER TRANSCRIPTION
# ============================================================

async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> Optional[str]:
    """Transcribe audio via Groq Whisper API. Returns transcript text or None."""
    if not config.GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set, skipping transcription")
        return None

    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}

    # Determine content type from filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    content_types = {
        "webm": "audio/webm",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
        "opus": "audio/opus",
        "mp4": "video/mp4",
    }
    content_type = content_types.get(ext, "audio/webm")

    try:
        form = aiohttp.FormData()
        form.add_field("file", audio_bytes, filename=filename, content_type=content_type)
        form.add_field("model", config.GROQ_WHISPER_MODEL)
        form.add_field("language", "en")
        form.add_field("response_format", "json")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"Whisper API error: HTTP {resp.status} — {body[:200]}")
                    return None
                data = await resp.json()
                transcript = data.get("text", "").strip()
                if not transcript:
                    logger.info("Whisper returned empty transcript")
                    return None
                return transcript
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None


# ============================================================
#  FAIR WORD-LEVEL COMPARISON
# ============================================================

def _normalize(text: str) -> list[str]:
    """Normalize text for comparison: lowercase, strip punctuation, split into words."""
    text = text.lower()
    text = re.sub(r"[^\w\s']", "", text)  # Keep apostrophes (don't, it's)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1)
            ))
        prev = curr
    return prev[-1]


def _words_match(transcript_word: str, expected_word: str) -> float:
    """Determine how well two words match, returning a score 0.0-1.0.

    - Exact match → 1.0
    - Fuzzy match (Levenshtein ≤ 2) → 0.8
    - Arabic substitution pattern → 0.6
    - No match → 0.0
    """
    if transcript_word == expected_word:
        return 1.0

    # Fuzzy match (handles slight mispronunciations Whisper still catches)
    distance = _levenshtein(transcript_word, expected_word)
    if distance <= 1:
        return 0.9
    if distance <= 2 and len(expected_word) >= 4:
        return 0.75

    # Check Arabic substitution patterns (b/p, v/f, th)
    # If first letter is a known substitution and rest matches
    if len(transcript_word) >= 2 and len(expected_word) >= 2:
        if (ARABIC_SUBSTITUTIONS.get(transcript_word[0]) == expected_word[0] and
                transcript_word[1:] == expected_word[1:]):
            return 0.7
        # Also check common th→d/s substitution
        if expected_word.startswith("th") and transcript_word[0] in ("d", "s", "z"):
            if transcript_word[1:] == expected_word[2:] or _levenshtein(transcript_word, expected_word) <= 2:
                return 0.7

    return 0.0


def compare_words(transcript: str, expected: str, level: str = "L0") -> tuple[float, list[str]]:
    """Fair word-level comparison with fuzzy matching and stop-word tolerance.

    Returns:
        (score_0_to_100, list_of_missed_content_words)

    Improvements over strict LCS:
    - Stop words don't penalize (only content words matter)
    - Fuzzy matching (Levenshtein ≤ 2 = partial credit)
    - Arabic substitution awareness (b/p, v/f, th = partial credit)
    - Extra words in transcript don't penalize (fillers, additions)
    """
    expected_words = _normalize(expected)
    transcript_words = _normalize(transcript)

    if not expected_words:
        return 100.0, []
    if not transcript_words:
        return 0.0, [w for w in expected_words if w not in STOP_WORDS][:5]

    # Score each expected word
    total_weight = 0.0
    earned_weight = 0.0
    missed_content_words = []

    for exp_word in expected_words:
        is_stop = exp_word in STOP_WORDS
        weight = 0.5 if is_stop else 1.0  # Stop words count half
        total_weight += weight

        # Find best match in transcript
        best_match = 0.0
        for tr_word in transcript_words:
            match_score = _words_match(tr_word, exp_word)
            best_match = max(best_match, match_score)
            if match_score == 1.0:
                break  # Perfect match, no need to check more

        earned_weight += weight * best_match

        # Track missed CONTENT words (not stop words) for feedback
        if best_match < 0.5 and not is_stop:
            missed_content_words.append(exp_word)

    raw_score = (earned_weight / total_weight) * 100 if total_weight > 0 else 100.0

    # Level-aware bonus: L0 gets +10, L1 gets +5, L2/L3 get raw
    level_bonus = {"L0": 10, "L1": 5, "L2": 2, "L3": 0}.get(level, 10)
    adjusted_score = min(100.0, raw_score + level_bonus)

    # Floor: never below 40% (reframe as "good start")
    final_score = max(40.0, adjusted_score)

    return round(final_score, 1), missed_content_words[:5]


# ============================================================
#  FEEDBACK GENERATION (Gemini — always encouraging)
# ============================================================

async def generate_feedback(score: float, expected: str, transcript: str,
                            missed_words: list[str], level: str = "L0",
                            is_beginner: bool = False) -> tuple[str, str]:
    """Generate encouraging bilingual feedback via Gemini.

    Returns (feedback_en, feedback_ar). Falls back to template if Gemini fails.
    """
    from . import ai_engine

    # Beginner grace period — only encouragement, no corrections
    if is_beginner:
        return (
            "Great job recording yourself! The more you practice, the better you'll get. Keep it up!",
            "أحسنت إنك سجلت نفسك! كل ما تتمرن أكتر، هتتحسن أكتر. استمر!"
        )

    if score >= 90:
        return ("Excellent! Your pronunciation is very clear. Native speakers would understand you perfectly!",
                "ممتاز! نطقك واضح جداً. أي حد أجنبي هيفهمك تمام!")

    if score >= 75:
        if not missed_words:
            return ("Great job! Very natural sounding. Keep practicing daily!",
                    "أحسنت! صوتك طبيعي جداً. استمر كل يوم!")

    missed_str = ", ".join(missed_words[:3]) if missed_words else "none"

    prompt = (
        f"You are a warm, encouraging pronunciation coach for Arabic speakers learning English.\n"
        f"Student level: {level} ({'complete beginner' if level == 'L0' else 'intermediate' if level in ('L1', 'L2') else 'advanced'})\n"
        f"The student tried to say: \"{expected}\"\n"
        f"They actually said: \"{transcript}\"\n"
        f"Score: {score:.0f}%\n"
        f"Words to work on: {missed_str}\n\n"
        f"IMPORTANT: Be ENCOURAGING first. They're paying for this and need to feel good.\n"
        f"Give feedback in 2-3 SHORT sentences:\n"
        f"1. Compliment something specific they did well (even if small)\n"
        f"2. ONE specific tip for improvement (not a list of problems)\n\n"
        f"Respond EXACTLY in this JSON format:\n"
        f'{{"en": "your encouraging English feedback", "ar": "نفس الكلام بالعربي المصري"}}'
    )

    try:
        result = await ai_engine._call_llm(prompt, temperature=0.6)
        if result:
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(result)
            en = data.get("en", "")
            ar = data.get("ar", "")
            if en and ar:
                return (en, ar)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Feedback generation failed: {e}")

    # Template fallback — always encouraging
    if score >= 70:
        en = f"You're doing great! Most words were clear. Try repeating '{missed_words[0]}' a few times slowly." if missed_words else "Excellent work!"
        ar = f"انت كويس جداً! معظم الكلمات واضحة. جرب تكرر '{missed_words[0]}' ببطء." if missed_words else "شغل ممتاز!"
    elif score >= 50:
        en = f"Good effort! I can tell you're improving. Focus on '{missed_words[0]}' — say it 5 times slowly, then speed up." if missed_words else "Keep going, you're improving!"
        ar = f"مجهود كويس! واضح إنك بتتحسن. ركز على '{missed_words[0]}' — قولها ٥ مرات ببطء." if missed_words else "استمر، انت بتتحسن!"
    else:
        en = "Great start! Recording yourself takes courage. Try listening to the model 3 more times, then record again."
        ar = "بداية حلوة! إنك تسجل نفسك ده شجاعة. اسمع النموذج ٣ مرات تاني وسجل مرة كمان."
    return (en, ar)


# ============================================================
#  FULL SCORING PIPELINE
# ============================================================

async def score_recording(audio_url: str, expected_text: str,
                          discord_id: str, task_id: str,
                          level: str = "L0",
                          filename: str = "recording.webm") -> ScoringResult:
    """Full pronunciation scoring pipeline with fairness adjustments.

    1. Download audio from Discord CDN
    2. Transcribe via Groq Whisper
    3. Fair word comparison (fuzzy + stop-word tolerant + level-aware)
    4. Check beginner grace period (first 3 recordings)
    5. Generate encouraging feedback
    6. Store result in database

    Returns ScoringResult (always — even on failure).
    """
    # Step 1: Download
    audio_bytes = await download_audio(audio_url)
    if not audio_bytes:
        return ScoringResult(
            score=0, raw_score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="Could not download audio"
        )

    # Step 2: Transcribe
    transcript = await transcribe_audio(audio_bytes, filename)
    if not transcript:
        return ScoringResult(
            score=0, raw_score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="Transcription failed"
        )

    # Step 3: Fair comparison
    score, missed_words = compare_words(transcript, expected_text, level)

    # Step 4: Check beginner grace period
    recent_scores = database.get_recent_scores(discord_id, days=30)
    is_beginner = len(recent_scores) < 3
    raw_score = score  # Store raw for analytics

    # Step 5: Generate feedback
    feedback_en, feedback_ar = await generate_feedback(
        score, expected_text, transcript, missed_words,
        level=level, is_beginner=is_beginner
    )

    # Step 6: Store in database
    import datetime
    today = datetime.date.today().isoformat()
    database.store_pronunciation_score(
        discord_id=discord_id,
        date=today,
        task_id=task_id,
        score=score,
        expected_text=expected_text,
        transcript=transcript,
        missed_words=json.dumps(missed_words),
        feedback=feedback_en,
        audio_url=audio_url,
    )

    logger.info(f"Pronunciation scored: {discord_id} {task_id} → {score:.0f}% "
                f"(raw={raw_score:.0f}%, missed={len(missed_words)}, beginner={is_beginner})")

    return ScoringResult(
        score=score,
        raw_score=raw_score,
        transcript=transcript,
        expected_text=expected_text,
        missed_words=missed_words,
        feedback_en=feedback_en,
        feedback_ar=feedback_ar,
        is_beginner_grace=is_beginner,
    )
