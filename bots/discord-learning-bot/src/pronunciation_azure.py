"""Nutq — Azure Pronunciation Assessment client (PRIMARY engine).

A thin, dependency-light REST client (no Azure SDK): convert audio → 16k mono wav
with ffmpeg, POST to the Speech short-audio endpoint with the Pronunciation-
Assessment header, and parse the per-word / per-phoneme result.

Everything is best-effort: any missing config / non-200 / exception returns None so
the engine selector falls back to the local scorer and the student flow is never
affected. The scoring MATH here is the pure `parse_azure_response` (unit-tested,
no network, no ffmpeg).
"""
import base64
import json
import logging
import shutil
import subprocess
import tempfile
import os
from typing import Optional

import aiohttp

from . import config

logger = logging.getLogger("empire-bot.nutq.azure")

# A word is "to work on" if Azure flags it or scores it low.
_MISS_ERROR_TYPES = {"Mispronunciation", "Omission", "Insertion"}
_WORD_MISS_THRESHOLD = 60.0  # AccuracyScore below this → needs work


def _pa_header(reference_text: str) -> str:
    """Base64-encoded Pronunciation-Assessment config header."""
    cfg = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": True,
    }
    return base64.b64encode(json.dumps(cfg).encode("utf-8")).decode("ascii")


def _endpoint() -> str:
    return (f"https://{config.AZURE_SPEECH_REGION}.stt.speech.microsoft.com"
            f"/speech/recognition/conversation/cognitiveservices/v1")


# ── audio ────────────────────────────────────────────────────────────────────
def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def to_wav16k(audio_bytes: bytes, filename: str = "rec.webm") -> Optional[bytes]:
    """Decode any browser recording → 16 kHz mono 16-bit PCM wav bytes (or None)."""
    src = tempfile.mktemp(suffix="_" + os.path.basename(filename or "rec.webm"))
    dst = tempfile.mktemp(suffix=".wav")
    try:
        with open(src, "wb") as f:
            f.write(audio_bytes)
        subprocess.run(
            [_ffmpeg(), "-y", "-i", src, "-ar", "16000", "-ac", "1", "-f", "wav", dst],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        with open(dst, "rb") as f:
            return f.read()
    except Exception as e:  # noqa: BLE001
        logger.warning("azure to_wav16k failed: %s", e)
        return None
    finally:
        for p in (src, dst):
            try:
                os.remove(p)
            except OSError:
                pass


def wav_duration_seconds(wav_bytes: bytes) -> float:
    """Approx duration of a 16k mono 16-bit PCM wav (for the usage guard)."""
    # 44-byte header, then 2 bytes/sample @ 16000 Hz.
    n = max(0, len(wav_bytes) - 44)
    return n / 2.0 / 16000.0


# ── parsing (pure, unit-tested) ───────────────────────────────────────────────
def _field(obj: dict, name: str):
    """Read an assessment field. Azure's short-audio REST returns the scores FLAT
    on each object (verified live); older/SDK shapes nest them under
    'PronunciationAssessment'. Support both (flat first, nested fallback)."""
    if name in obj:
        return obj[name]
    return (obj.get("PronunciationAssessment") or {}).get(name)


def parse_azure_response(data: dict) -> Optional[dict]:
    """Azure Pronunciation Assessment JSON → normalized dict, or None if unusable.

    Headline `score` = **AccuracyScore** (pronunciation quality). We deliberately
    do NOT use PronScore as the headline: PronScore folds in fluency, which unfairly
    penalizes L0 beginners for reading slowly (verified live — an accented but
    correct read scored Accuracy 89 while PronScore was dragged to 50 by fluency).
    Returns: {score, accuracy, pron_score, fluency, completeness, missed_words[],
              per_word[], worst_phoneme}.
    """
    try:
        if not isinstance(data, dict) or data.get("RecognitionStatus") != "Success":
            return None
        nbest = data.get("NBest") or []
        if not nbest:
            return None
        top = nbest[0]
        accuracy = _field(top, "AccuracyScore")
        if accuracy is None:
            return None

        missed, per_word = [], []
        worst_phoneme, worst_acc = None, 101.0
        for w in (top.get("Words") or []):
            acc = _field(w, "AccuracyScore")
            acc = 100.0 if acc is None else acc
            etype = _field(w, "ErrorType") or "None"
            word = w.get("Word", "")
            per_word.append({"word": word, "accuracy": acc, "error": etype})
            needs_work = (etype in _MISS_ERROR_TYPES) or (acc < _WORD_MISS_THRESHOLD)
            if needs_work and word and etype != "Insertion":  # inserted words aren't targets
                missed.append(word)
                for ph in (w.get("Phonemes") or []):
                    pacc = _field(ph, "AccuracyScore")
                    pacc = 100.0 if pacc is None else pacc
                    if pacc < worst_acc:
                        worst_acc, worst_phoneme = pacc, ph.get("Phoneme", "")

        return {
            "score": round(float(accuracy), 1),          # AccuracyScore = fair-for-L0 headline
            "accuracy": accuracy,
            "pron_score": _field(top, "PronScore"),
            "fluency": _field(top, "FluencyScore"),
            "completeness": _field(top, "CompletenessScore"),
            "missed_words": missed[:5],
            "per_word": per_word,
            "worst_phoneme": worst_phoneme,
            "display_text": data.get("DisplayText", "") or "",  # readable "we heard" for the UI
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("parse_azure_response failed: %s", e)
        return None


# ── network call ──────────────────────────────────────────────────────────────
async def call_azure(wav_bytes: bytes, reference_text: str) -> Optional[dict]:
    """POST wav to Azure Pronunciation Assessment; return parsed dict or None."""
    if not (config.AZURE_SPEECH_KEY and config.AZURE_SPEECH_REGION):
        logger.info("Azure Speech key/region not set — skipping Azure")
        return None
    headers = {
        "Ocp-Apim-Subscription-Key": config.AZURE_SPEECH_KEY,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        "Pronunciation-Assessment": _pa_header(reference_text),
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(_endpoint(), params={"language": "en-US"},
                                    data=wav_bytes, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=7)) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.info("Azure PA HTTP %s: %s", resp.status, body[:200])
                    return None
                return parse_azure_response(await resp.json())
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning("Azure PA call failed (non-fatal): %s", e)
        return None


async def score(audio_bytes: bytes, filename: str, reference_text: str) -> Optional[dict]:
    """Full Azure path: bytes → wav → assessment. Returns parsed dict (+ duration_s)
    or None on any failure. Duration is included for the usage guard (A2)."""
    wav = to_wav16k(audio_bytes, filename)
    if not wav:
        return None
    result = await call_azure(wav, reference_text)
    if result is not None:
        result["duration_s"] = wav_duration_seconds(wav)
    return result



# ── reliable bilingual feedback (Azure gives correct per-phoneme detail) ──────
# Keyed to Azure en-US phoneme symbols, focused on sounds Arabic speakers find
# hardest. EN + Egyptian Arabic; encouragement-first; NOT Nour-voiced.
PHONEME_TIP = {
    "th": ("For 'th' (think), put your tongue between your teeth and blow.",
           "لصوت 'th' زي think، حّط طرف لسانك بين سنانك وانفخ."),
    "dh": ("For the soft 'th' (this), tongue between your teeth with your voice on.",
           "لصوت 'th' الناعم زي this، لسانك بين سنانك وصوّت."),
    "p": ("Press both lips and pop the air for 'p' — stronger than 'b'.",
          "اضغط شفايفك وطلّع الهوا فجأة لصوت 'p' — أقوى من 'b'."),
    "b": ("Press both lips for 'b' — softer than 'p'.",
          "اضغط شفايفك لصوت 'b' — أنعم من 'p'."),
    "v": ("For 'v', rest your top teeth on your bottom lip and use your voice (not 'f').",
          "لصوت 'v' حّط سنانك الفوق على شفتك التحت وصوّت (مش 'f')."),
    "f": ("For 'f', top teeth on bottom lip, blow air with no voice.",
          "لصوت 'f' سنانك الفوق على شفتك التحت وانفخ من غير صوت."),
    "r": ("For English 'r', curl your tongue back without touching the roof.",
          "لصوت 'r' الإنجليزي لُف لسانك لورا من غير ما يلمس سقف الحلق."),
    "l": ("For 'l', touch the tip of your tongue behind your top teeth.",
          "لصوت 'l' المس طرف لسانك ورا سنانك الفوق."),
    "ng": ("For 'ng' (sing), let the sound come through your nose.",
           "لصوت 'ng' زي sing، خلي الصوت يطلع من مناخيرك."),
    "sh": ("For 'sh', round your lips and push the air softly.",
           "لصوت 'sh' دوّر شفايفك وادفع الهوا بهدوء."),
    "zh": ("For the soft 'zh' sound, round your lips with your voice on.",
           "لصوت 'zh' الناعم دوّر شفايفك وصوّت."),
    "w": ("For 'w', round your lips like a small kiss.",
          "لصوت 'w' دوّر شفايفك زي بوسة صغيرة."),
}


def build_feedback(score: float, missed_words, worst_phoneme=None):
    """Bilingual, encouragement-first feedback from Azure's reliable output.
    Names the specific failed sound when we have one; else the missed word."""
    tip = PHONEME_TIP.get((worst_phoneme or "").lower())
    w = missed_words[0] if missed_words else ""
    if score >= 90:
        return ("Excellent! Your pronunciation is very clear.",
                "ممتاز! نطقك واضح جداً.")
    if score >= 70:
        if tip:
            return (f"Great job! Very close. {tip[0]}", f"أحسنت! قريب جداً. {tip[1]}")
        if w:
            return (f"Great job! Very close. Practice the word '{w}' a few times slowly.",
                    f"أحسنت! قريب جداً. اتمرّن على كلمة '{w}' كذا مرة ببطء.")
        return ("Great job! Very natural. Keep practicing daily!",
                "أحسنت! صوتك طبيعي. استمر كل يوم!")
    if score >= 45:
        if tip:
            return (f"Good effort! {tip[0]}", f"مجهود كويس! {tip[1]}")
        if w:
            return (f"Good effort! Focus on '{w}' — say it 5 times slowly, then speed up.",
                    f"مجهود كويس! ركّز على '{w}' — قولها ٥ مرات ببطء وبعدين بسرعة.")
        return ("Good effort! Listen to the model again and record once more.",
                "مجهود كويس! اسمع النموذج تاني وسجّل مرة كمان.")
    if tip:
        return (f"Nice try! {tip[0]} Listen to the model and record again.",
                f"محاولة حلوة! {tip[1]} اسمع النموذج وسجّل تاني.")
    mw = ", ".join(missed_words[:3]) if missed_words else "the sounds"
    return (f"Nice try! Let's work on: {mw}. Listen to the model 3 times, then record again.",
            f"محاولة حلوة! نشتغل على: {mw}. اسمع النموذج ٣ مرات وسجّل تاني.")
