"""Sawt (صوت) — podcast script generation (Phase 2).

Turns a topic + CEFR level + episode format into a natural, level-graded
multi-speaker conversation SCRIPT (plain text, speaker-labelled) for the owner
to review and edit before recording. This module only WRITES a script; it never
generates audio (Phase 3) and never publishes anything.

The level profile (config.podcast_level_profile) drives the Arabic ratio, pace,
vocabulary band, and target length, so an A1 script is slow/simple with heavy
Arabic support while a C2 script is native-paced English.
"""
import logging
from typing import Optional

from . import config, ai_engine

logger = logging.getLogger("empire-bot.sawt.script")

# Human-readable speaker line-ups per format. The owner can edit these after.
FORMAT_SPEAKERS = {
    "solo_ai": ["Host (you)", "AI co-host"],
    "owner_group": ["Host (you)", "AI guest 1", "AI guest 2"],
    "ai_only": ["AI host", "AI guest"],
}


def build_prompt(topic: str, level: str, format: str,
                 speakers: list = None) -> str:
    """Build the LLM prompt for a level-graded podcast conversation script."""
    key = config.cefr_key(level)
    profile = config.podcast_level_profile(key)
    li = config.level_info(key)
    spk = speakers or FORMAT_SPEAKERS.get(format, FORMAT_SPEAKERS["solo_ai"])
    ar_pct = int(round(profile["arabic_ratio"] * 100))
    dur_min = profile["duration_min"] // 60
    dur_max = profile["duration_max"] // 60

    # Arabic guidance scales with the level's ratio.
    if ar_pct >= 30:
        arabic_line = (f"About {ar_pct}% of the episode is in Egyptian Arabic: "
                       f"explain every new English word in Arabic, translate key "
                       f"sentences, and keep the English extremely simple and short.")
    elif ar_pct > 0:
        arabic_line = (f"About {ar_pct}% Arabic — use Egyptian Arabic ONLY to "
                       f"clarify hard words or confirm understanding; the rest is "
                       f"simple English.")
    else:
        arabic_line = "English only — no Arabic at all."

    return f"""You are scripting an episode of an English-learning podcast for
Empire English Community (MACAL EMPIRE). Write a NATURAL spoken conversation,
not an article.

Level: {key} — {li['name']} ({profile['description']})
Language mix: {arabic_line}
Pace / difficulty: {profile['pace']} pace, {profile['vocab']} vocabulary band.
Target length: about {dur_min}-{dur_max} minutes of speech.
Format: {format}. Speakers: {', '.join(spk)}.
Topic: {topic}

Rules for the script:
- Start each line with the speaker's name and a colon, e.g. "Host (you): ...".
- Make it sound like real people talking: turn-taking, short back-channels
  ("mm-hmm", "right", "exactly"), natural transitions, occasional light humor.
- Use [PAUSE] where a natural pause helps a learner follow.
- Keep vocabulary within the {profile['vocab']} band for this level.
- Open with a short, warm intro that names the topic; close with a one-line wrap.
- Do NOT include stage directions in parentheses other than [PAUSE].

Write ONLY the script (speaker-labelled lines). No preamble, no explanation."""


async def generate_script(topic: str, level: str, format: str,
                          speakers: list = None) -> Optional[str]:
    """Generate a level-graded conversation script for a topic. Returns the
    script text, or None if the LLM is unavailable / returns nothing.

    Uses a PLAIN-TEXT LLM call (not ai_engine._call_llm) on purpose: that path
    hardcodes a 'always return valid JSON' system prompt, which mangles a
    free-form podcast script. Here the model is told it's a scriptwriter and to
    return only the script."""
    if format not in FORMAT_SPEAKERS:
        raise ValueError(f"Invalid format {format!r}; must be one of "
                         f"{tuple(FORMAT_SPEAKERS)}")
    prompt = build_prompt(topic, level, format, speakers)
    try:
        text = await _call_llm_text(prompt, temperature=0.85)
    except Exception as e:  # noqa: BLE001 — never crash the command on an LLM error
        logger.warning("sawt: script generation failed: %s", e)
        return None
    if not text or not text.strip():
        return None
    return text.strip()


_SCRIPT_SYSTEM = ("You are an expert scriptwriter for an English-learning "
                  "podcast for Arabic speakers. Return ONLY the script — "
                  "speaker-labelled lines of natural spoken dialogue. No JSON, "
                  "no preamble, no explanation.")


async def _call_llm_text(prompt: str, temperature: float = 0.85) -> Optional[str]:
    """Plain-text LLM call for scripts: Groq primary (with a scriptwriter system
    prompt, NOT the JSON-forcing one), Gemini fallback. Returns text or None."""
    # Groq primary.
    if config.GROQ_API_KEY:
        from . import groq_client
        payload = {
            "model": config.GROQ_MODEL,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": _SCRIPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            result = await groq_client.chat_completion(payload, timeout_seconds=45)
            if result.ok and result.text:
                return result.text
            logger.warning("sawt: Groq script call failed (status=%s)", result.status)
        except Exception as e:  # noqa: BLE001
            logger.warning("sawt: Groq script call error: %s", e)
    # Gemini fallback (plain text — ai_engine._call_gemini has no JSON system prompt).
    try:
        return await ai_engine._call_gemini(prompt, temperature)
    except Exception as e:  # noqa: BLE001
        logger.warning("sawt: Gemini script fallback error: %s", e)
        return None
