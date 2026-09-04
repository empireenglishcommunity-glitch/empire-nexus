"""Sawt (صوت) — Empire Chronicles serialized-story generation.

The storytelling podcast is ONE continuous story told one episode per day. Each
episode ends on a cliffhanger with an A/B audience vote; the next day's episode
continues the story the way the audience chose. This module generates the NEXT
episode's script (English-only) from the running story so far + the winning
choice, in the cast format the renderer understands:

    Narrator: ...              (owner's cloned voice)
    Maya: ...                  (Mai's cloned voice)
    Leo: ...                   (a distinct American voice)
    ... [SFX:knock|creak]      (real sound effects, inline)
    ... [PAUSE 2s]             (dramatic timing)

It WRITES a script + the two vote options; it never renders audio (that's the
offline renderer) and never posts anything (that's the bot).
"""
import json
import logging
import re
from typing import Optional

from . import config, ai_engine

logger = logging.getLogger("empire-bot.sawt.story")

# The recurring cast the renderer knows how to voice (see render_podcast_episode
# CHARACTER_VOICES). Keep new characters within these names/roles or add a voice.
STORY_CAST = ["Narrator", "Maya", "Leo"]

# Available inline effect + timing markers the script may use.
STORY_SFX = ["knock", "creak", "shimmer"]

# Level band for the story: mixed but pitched around A2–B1 so it's approachable
# for most students while still engaging (English-only per the owner's decision).
STORY_LEVEL = "A2"


_STORY_SYSTEM = (
    "You are the head writer of 'Empire Chronicles', a serialized audio drama "
    "for English learners. You write natural, cinematic, suspenseful spoken "
    "scripts in CLEAR, simple English. Return ONLY valid JSON — no preamble.")


def build_story_prompt(previous_summary: str, winning_choice: str,
                       episode_number: int) -> str:
    """Prompt the LLM to write the next episode as JSON (script + recap + the
    next A/B vote). `previous_summary` is the story so far; `winning_choice` is
    what the audience voted to happen next (empty for the very first episode)."""
    cast = ", ".join(STORY_CAST)
    sfx = ", ".join(f"[SFX:{s}]" for s in STORY_SFX)

    if winning_choice:
        continuity = (
            f"This is episode {episode_number}. The story so far:\n"
            f"{previous_summary}\n\n"
            f"The audience voted for this to happen next: \"{winning_choice}\".\n"
            f"Continue the story from that choice.")
    else:
        continuity = (
            f"This is episode {episode_number} — the OPENING episode. Introduce "
            f"the world and characters and hook the listener fast.")

    return f"""{continuity}

Write the next ~2-minute episode of Empire Chronicles as a spoken audio script.

CAST (use these names exactly; the audio engine maps each to a distinct voice):
- Narrator — warm host who tells the story and speaks directly to the audience.
- Maya — the protagonist (young woman, curious, brave).
- Leo — a supporting character (young man, cautious).

STYLE:
- CLEAR simple English (learners), but genuinely suspenseful and cinematic.
- Real spoken dialogue, short sentences, natural rhythm.
- Weave in sound effects on their own where they fit: {sfx}. Do NOT have a
  character SAY the sound (never write "tap tap tap" — use [SFX:knock] instead).
- Use [PAUSE 2s] to hold tension, especially right before the cliffhanger.
- Open with the Narrator's signature: "Welcome to Empire Chronicles..." and a
  one-line recap if this is not episode 1.
- END on a strong cliffhanger, then the Narrator asks the audience to choose
  between EXACTLY TWO options and says "Vote below. Tomorrow, the story continues
  the way you choose."

Return ONLY this JSON object:
{{
  "title": "short episode title",
  "script": "the full speaker-labelled script, one line per speaker turn, using Narrator:/Maya:/Leo: and inline [SFX:...] and [PAUSE 2s] markers",
  "recap": "2-3 sentence summary of what happened this episode (used to seed the next one)",
  "vote_a": "short label for choice A (what Maya could do)",
  "vote_b": "short label for choice B (the other option)"
}}"""


def _extract_json(text: str) -> Optional[dict]:
    """Pull the JSON object out of an LLM response (tolerant of code fences)."""
    if not text:
        return None
    # Strip ```json fences if present.
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    # Grab the outermost {...}.
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


def _valid_episode(d: dict) -> bool:
    """A usable episode has a title, a parseable script, and two vote options."""
    if not isinstance(d, dict):
        return False
    for k in ("title", "script", "vote_a", "vote_b"):
        if not str(d.get(k, "")).strip():
            return False
    # The script must contain at least a couple of "Speaker: line" turns.
    lines = [ln for ln in d["script"].splitlines()
             if re.match(r"^\s*(Narrator|Maya|Leo)\s*:", ln)]
    return len(lines) >= 4


async def generate_episode(previous_summary: str = "", winning_choice: str = "",
                           episode_number: int = 1) -> Optional[dict]:
    """Generate the next Empire Chronicles episode. Returns a dict with keys
    title, script, recap, vote_a, vote_b — or None if the LLM is unavailable or
    returns something unusable. Never raises."""
    prompt = build_story_prompt(previous_summary, winning_choice, episode_number)
    try:
        text = await _call_llm_json(prompt, temperature=0.9)
    except Exception as e:  # noqa: BLE001
        logger.warning("sawt.story: generation failed: %s", e)
        return None
    d = _extract_json(text or "")
    if not _valid_episode(d):
        logger.warning("sawt.story: LLM returned an unusable episode")
        return None
    # Normalize: keep only the fields we use, stringified + stripped.
    return {
        "title": str(d["title"]).strip()[:200],
        "script": str(d["script"]).strip(),
        "recap": str(d.get("recap", "")).strip(),
        "vote_a": str(d["vote_a"]).strip()[:100],
        "vote_b": str(d["vote_b"]).strip()[:100],
    }


async def _call_llm_json(prompt: str, temperature: float = 0.9) -> Optional[str]:
    """Story LLM call: Groq primary (story-writer system prompt), Gemini
    fallback. Returns raw text (expected to contain a JSON object) or None."""
    if config.GROQ_API_KEY:
        from . import groq_client
        payload = {
            "model": config.GROQ_MODEL,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": _STORY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            result = await groq_client.chat_completion(payload, timeout_seconds=60)
            if result.ok and result.text:
                return result.text
            logger.warning("sawt.story: Groq call failed (status=%s)", result.status)
        except Exception as e:  # noqa: BLE001
            logger.warning("sawt.story: Groq call error: %s", e)
    try:
        return await ai_engine._call_gemini(prompt, temperature)
    except Exception as e:  # noqa: BLE001
        logger.warning("sawt.story: Gemini fallback error: %s", e)
        return None
