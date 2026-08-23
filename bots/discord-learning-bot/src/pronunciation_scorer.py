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
- Level-aware: L0 is generous, L3 is strict

NOTE (Nutq pilot): the former "beginner grace" (hide the score + correction
for a student's first 3 recordings) was REMOVED. Live pilot feedback showed it
made the feature feel unresponsive — students read wrong on purpose yet got
only a generic encouragement with no number and no correction. Every recording
now returns a real score + correction from attempt #1; kindness is preserved by
the 40% floor, Arabic-sound tolerance, and the level bonus above.

All operations are async and designed to run as background tasks
(never block the !done response). All failures degrade gracefully
(log + skip, never crash the bot).
"""
import base64
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
    is_beginner_grace: bool = False  # Deprecated (Nutq): grace removed — always False; kept for response-shape/back-compat
    success: bool = True
    error: str = ""
    engine: str = "local"  # which engine produced this score: "azure" | "local"


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

    # Level-aware bonus (CEFR): A1 +10, A2 +5, B1 +2, B2+ raw. Legacy keys are
    # normalized to their CEFR level first (L0->A1, L1->A2, ...).
    level_bonus = {"A1": 10, "A2": 5, "B1": 2, "B2": 0, "C1": 0, "C2": 0}.get(config.cefr_key(level), 0)
    adjusted_score = min(100.0, raw_score + level_bonus)

    # Floor: never below 40% (reframe as "good start")
    final_score = max(40.0, adjusted_score)

    return round(final_score, 1), missed_content_words[:5]


# ============================================================
#  FEEDBACK GENERATION (Gemini — always encouraging)
# ============================================================

async def generate_feedback(score: float, expected: str, transcript: str,
                            missed_words: list[str], level: str = "L0") -> tuple[str, str]:
    """Generate encouraging bilingual feedback via Gemini.

    Returns (feedback_en, feedback_ar). Falls back to template if Gemini fails.
    Every recording gets a real, score-based correction (the former beginner
    grace was removed — see the module docstring).
    """
    from . import ai_engine

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
#  NUTQ 2 — self-hosted phoneme scorer client
# ============================================================

async def _call_nutq_scorer(audio_bytes: bytes, expected_text: str,
                            level: str, filename: str) -> Optional[dict]:
    """Call the self-hosted nutq-scorer service (services/nutq-scorer).

    Returns the parsed JSON result on success, or None on any failure/timeout
    (best-effort — the caller degrades gracefully and the student flow is never
    affected). Inner timeout is < the endpoint's outer 8s wait_for.
    """
    url = (config.NUTQ_SCORER_URL or "").rstrip("/")
    if not url:
        logger.info("NUTQ_SCORER_URL not set — skipping pronunciation scoring")
        return None
    payload = {
        "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
        "reference_text": expected_text,
        "level": level,
        "filename": filename,
    }
    headers = {}
    if config.NUTQ_SCORER_TOKEN:
        headers["X-Nutq-Token"] = config.NUTQ_SCORER_TOKEN
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/score", json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=7)) as resp:
                data = await resp.json()
                if resp.status != 200 or not data.get("ok"):
                    logger.info(f"nutq-scorer non-ok (HTTP {resp.status}): "
                                f"{data.get('error') if isinstance(data, dict) else ''}")
                    return None
                return data
    except Exception as e:  # noqa: BLE001 — best-effort, never raise to caller
        logger.warning(f"nutq-scorer call failed (non-fatal): {e}")
        return None


# ============================================================
#  FULL SCORING PIPELINE
# ============================================================

async def score_recording(audio_url: str, expected_text: str,
                          discord_id: str, task_id: str,
                          level: str = "L0",
                          filename: str = "recording.webm") -> ScoringResult:
    """Score a recording given a Discord CDN URL: download, then delegate to
    score_recording_bytes (the shared pipeline). Kept for the Discord-side
    caller; the practice page uses score_recording_bytes directly.

    Returns ScoringResult (always — even on failure).
    """
    audio_bytes = await download_audio(audio_url)
    if not audio_bytes:
        return ScoringResult(
            score=0, raw_score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="Could not download audio"
        )
    return await score_recording_bytes(
        audio_bytes, filename, expected_text, discord_id, task_id,
        level=level, audio_url=audio_url,
    )


async def score_recording_bytes(audio_bytes: bytes, filename: str,
                                 expected_text: str, discord_id: str,
                                 task_id: str, level: str = "L0",
                                 audio_url: str = "", store: bool = True,
                                 allow_azure: bool = True) -> ScoringResult:
    """Full pronunciation scoring pipeline (Nutq final — pronunciation-engine-v2):

    Engine selector:
      • PRIMARY = Azure Pronunciation Assessment (accurate per-phoneme) — used
        when eligible (Azure on + key set + task=shadow + usage guard OK + within
        the per-day cost cap). On success, records usage + the daily call count.
      • FALLBACK = the free local self-hosted engine (services/nutq-scorer) — used
        when Azure is ineligible/unavailable. Its per-sound detail is unreliable,
        so its feedback is coarse (a band + encouragement, no specific sound).

    Best-effort: if BOTH fail, returns success=False → caller shows scored:false;
    completion + #showcase always proceed. Same ScoringResult/JSON shape as before
    (dojo unchanged); `transcript` carries Azure's readable "we heard" (empty for
    the local engine, whose output is phonemes).
    """
    today = database._today_local().isoformat()
    month = database._today_local().strftime("%Y-%m")

    # ── PRIMARY: Azure ────────────────────────────────────────────────
    # allow_azure=False (the "try again" re-check) → free engine only, so
    # practice reps never spend the student's one daily Azure grade. When Azure
    # is available we ATOMICALLY reserve the daily slot BEFORE calling out, so a
    # double-tap / retry can't sneak in a second paid call (strict N/day).
    if allow_azure and _azure_available(task_id):
        cap = config.NUTQ_AZURE_MAX_CALLS_PER_DAY
        if database.reserve_azure_call_today(discord_id, today, cap):
            from . import pronunciation_azure
            az = None
            try:
                az = await pronunciation_azure.score(audio_bytes, filename, expected_text)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Azure scoring raised, falling back to local: {e}")
                az = None
            if az:
                database.add_azure_usage(month, float(az.get("duration_s", 0.0)))
                score = float(az.get("score", 0.0))
                missed_words = az.get("missed_words", []) or []
                heard = az.get("display_text", "") or ""
                feedback_en, feedback_ar = pronunciation_azure.build_feedback(
                    score, missed_words, az.get("worst_phoneme"))
                if store:
                    database.store_pronunciation_score(
                        discord_id=discord_id, date=today, task_id=task_id, score=score,
                        expected_text=expected_text, transcript=heard,
                        missed_words=json.dumps(missed_words), feedback=feedback_en,
                        audio_url=audio_url)
                logger.info(f"Pronunciation scored (azure): {discord_id} {task_id} → "
                            f"{score:.0f}% missed={len(missed_words)}")
                return ScoringResult(
                    score=score, raw_score=float(az.get("accuracy", score) or score),
                    transcript=heard, expected_text=expected_text,
                    missed_words=missed_words, feedback_en=feedback_en,
                    feedback_ar=feedback_ar, is_beginner_grace=False, engine="azure")
            # Azure failed after reserving → refund the slot so the student keeps
            # their one daily grade, then fall through to the local engine.
            database.release_azure_call_today(discord_id, today)

    # ── FALLBACK: free local engine ───────────────────────────────────
    result = await _call_nutq_scorer(audio_bytes, expected_text, level, filename)
    if not result:
        return ScoringResult(
            score=0, raw_score=0, transcript="", expected_text=expected_text,
            missed_words=[], feedback_en="", feedback_ar="",
            success=False, error="scorer unavailable")

    score = float(result.get("score", 0.0))
    raw_score = float(result.get("raw_score", score))
    missed_words = result.get("missed_words", []) or []
    heard_phonemes = result.get("heard_phonemes", "") or ""
    # Local per-sound detail is unreliable → coarse, honest feedback (no sound named).
    feedback_en, feedback_ar = _local_feedback(score)

    if store:
        database.store_pronunciation_score(
            discord_id=discord_id, date=today, task_id=task_id, score=score,
            expected_text=expected_text, transcript=heard_phonemes,
            missed_words=json.dumps(missed_words), feedback=feedback_en,
            audio_url=audio_url)

    logger.info(f"Pronunciation scored (local): {discord_id} {task_id} → {score:.0f}% "
                f"(raw={raw_score:.0f}%, missed={len(missed_words)})")

    return ScoringResult(
        score=score, raw_score=raw_score,
        transcript="",  # local engine → phonemes, not a readable "we heard"
        expected_text=expected_text, missed_words=missed_words,
        feedback_en=feedback_en, feedback_ar=feedback_ar, is_beginner_grace=False,
        engine="local")


def _azure_available(task_id: str) -> bool:
    """Cheap gates for using Azure: only for shadow, only while enabled +
    configured, and only under the monthly usage guard.

    The per-day per-student cap is intentionally NOT checked here — that is
    claimed atomically via database.reserve_azure_call_today() right before the
    call, which is race-safe (see that function). Splitting the cheap gates from
    the atomic reservation avoids an extra DB read on the ineligible paths.
    """
    if not (config.NUTQ_AZURE_ENABLED and config.AZURE_SPEECH_KEY and config.AZURE_SPEECH_REGION):
        return False
    if task_id != "shadow":
        return False
    month = database._today_local().strftime("%Y-%m")
    if database.azure_usage_seconds(month) >= config.NUTQ_AZURE_FREE_SECONDS * config.NUTQ_AZURE_GUARD_FRACTION:
        return False  # usage guard → free local engine for the rest of the month
    return True


def _local_feedback(score: float):
    """Coarse, honest bilingual feedback for the fallback engine — a band +
    encouragement, WITHOUT naming a specific sound (local detail is unreliable)."""
    if score >= 85:
        return ("Great job! Keep practicing daily.", "أحسنت! استمر في التمرين كل يوم.")
    if score >= 60:
        return ("Good effort — keep practicing!", "مجهود كويس — استمر في التمرين!")
    return ("Keep practicing — listen to the model again and record once more.",
            "استمر في التمرين — اسمع النموذج تاني وسجّل مرة كمان.")
