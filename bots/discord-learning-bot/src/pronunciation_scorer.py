"""Dhaka' (ذكاء) — Pronunciation Scoring Engine.

Scores student audio recordings against expected text using:
1. Groq Whisper API for transcription
2. Word-level comparison algorithm
3. Gemini for personalized feedback generation

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
    score: float  # 0-100
    transcript: str
    expected_text: str
    missed_words: list[str]
    feedback_en: str
    feedback_ar: str
    success: bool = True
    error: str = ""


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
#  WORD-LEVEL COMPARISON
# ============================================================

def _normalize(text: str) -> list[str]:
    """Normalize text for comparison: lowercase, strip punctuation, split into words."""
    text = text.lower()
    text = re.sub(r"[^\w\s']", "", text)  # Keep apostrophes (don't, it's)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()


def compare_words(transcript: str, expected: str) -> tuple[float, list[str]]:
    """Compare transcript against expected text at word level.

    Returns:
        (score_0_to_100, list_of_missed_words)

    Algorithm:
    - Normalize both strings
    - Use longest common subsequence (LCS) for word matching
      (handles insertions/deletions/reorderings better than strict positional)
    - Score = (LCS length / expected word count) * 100
    - Missed words = expected words not in the LCS
    """
    expected_words = _normalize(expected)
    transcript_words = _normalize(transcript)

    if not expected_words:
        return 100.0, []
    if not transcript_words:
        return 0.0, expected_words[:5]

    # LCS via dynamic programming
    m, n = len(expected_words), len(transcript_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if expected_words[i - 1] == transcript_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]
    score = (lcs_length / m) * 100

    # Find which expected words were missed (backtrack LCS)
    matched = set()
    i, j = m, n
    while i > 0 and j > 0:
        if expected_words[i - 1] == transcript_words[j - 1]:
            matched.add(i - 1)
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    missed = [expected_words[i] for i in range(m) if i not in matched]
    return round(score, 1), missed[:5]  # Max 5 missed words


# ============================================================
#  FEEDBACK GENERATION (Gemini)
# ============================================================

async def generate_feedback(score: float, expected: str, transcript: str,
                            missed_words: list[str]) -> tuple[str, str]:
    """Generate encouraging bilingual feedback via Gemini.

    Returns (feedback_en, feedback_ar). Falls back to template if Gemini fails.
    """
    from . import ai_engine

    if not missed_words:
        # Perfect or near-perfect score
        if score >= 95:
            return ("Excellent! Your pronunciation is spot-on. Keep it up!",
                    "ممتاز! نطقك دقيق جداً. استمر!")
        return ("Great job! Very close to the model. Minor differences only.",
                "أحسنت! قريب جداً من النموذج. فروقات بسيطة بس.")

    missed_str = ", ".join(missed_words[:3])
    prompt = (
        f"You are a pronunciation coach for Arabic speakers learning English.\n"
        f"The student tried to say: \"{expected}\"\n"
        f"They actually said: \"{transcript}\"\n"
        f"Accuracy: {score:.0f}%\n"
        f"Words they missed or mispronounced: {missed_str}\n\n"
        f"Give brief, encouraging feedback (2-3 sentences):\n"
        f"1. What they did well\n"
        f"2. 1-2 specific words to practice (with a simple pronunciation tip)\n\n"
        f"Respond EXACTLY in this JSON format:\n"
        f'{{"en": "your English feedback here", "ar": "نفس الفيدباك بالعربي المصري هنا"}}'
    )

    try:
        result = await ai_engine._call_llm(prompt, temperature=0.5)
        if result:
            # Try to parse JSON
            result = result.strip()
            if result.startswith("```"):
                result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(result)
            return (data.get("en", ""), data.get("ar", ""))
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Feedback generation failed: {e}")

    # Template fallback
    en = f"Good effort! Focus on: {missed_str}. Try saying them slowly, then speed up."
    ar = f"مجهود كويس! ركّز على: {missed_str}. قولهم ببطء الأول، وبعدين سرّع."
    return (en, ar)


# ============================================================
#  FULL SCORING PIPELINE
# ============================================================

async def score_recording(audio_url: str, expected_text: str,
                          discord_id: str, task_id: str,
                          filename: str = "recording.webm") -> ScoringResult:
    """Full pronunciation scoring pipeline.

    1. Download audio from Discord CDN
    2. Transcribe via Groq Whisper
    3. Compare words
    4. Generate feedback
    5. Store result in database

    Returns ScoringResult (always — even on failure).
    """
    # Step 1: Download
    audio_bytes = await download_audio(audio_url)
    if not audio_bytes:
        return ScoringResult(
            score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="Could not download audio"
        )

    # Step 2: Transcribe
    transcript = await transcribe_audio(audio_bytes, filename)
    if not transcript:
        return ScoringResult(
            score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="Transcription failed"
        )

    # Step 3: Compare
    score, missed_words = compare_words(transcript, expected_text)

    # Step 4: Generate feedback
    feedback_en, feedback_ar = await generate_feedback(score, expected_text, transcript, missed_words)

    # Step 5: Store in database
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

    logger.info(f"Pronunciation scored: {discord_id} {task_id} → {score:.0f}% ({len(missed_words)} missed)")

    return ScoringResult(
        score=score,
        transcript=transcript,
        expected_text=expected_text,
        missed_words=missed_words,
        feedback_en=feedback_en,
        feedback_ar=feedback_ar,
    )
