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
import asyncio
import json
import logging
import re
from typing import Optional

from . import config, ai_engine

logger = logging.getLogger("empire-bot.sawt.story")

# The recurring cast the renderer knows how to voice (see render_podcast_episode
# CHARACTER_VOICES). Keep new characters within these names/roles or add a voice.
STORY_CAST = ["Narrator", "Maya", "Leo", "Sara", "Omar", "The Stranger", "Mrs. Adel"]

# Available inline effect + timing markers the script may use.
STORY_SFX = ["knock", "creak", "shimmer"]

# Level band for the story: mixed but pitched around A2–B1 so it's approachable
# for most students while still engaging (English-only per the owner's decision).
STORY_LEVEL = "A2"


_STORY_SYSTEM = (
    "You are the head writer of 'Empire English Chronicles', a serialized audio "
    "drama for English learners. You write natural, cinematic, suspenseful spoken "
    "scripts in CLEAR, simple English. Return ONLY valid JSON — no preamble.")


def target_length(level: str = None) -> tuple:
    """(target_words, target_minutes) for an episode at `level`.

    Derived from the SAME CEFR profile the rest of Empire English uses, so episode
    length follows the learner's level (spec R7.1). Every v1 episode was 98-161s
    against A2's 300-420s window and failed the duration gate — the generator was
    asking for "~2 minutes" regardless of level.

    Words are computed from the level's delivery pace: at slower paces the same
    minute holds fewer words, so a slower level needs FEWER words for the same
    duration, not more."""
    lvl = level or STORY_LEVEL
    try:
        from . import config
        prof = config.podcast_level_profile(lvl)
        dmin, dmax = float(prof["duration_min"]), float(prof["duration_max"])
        pace = prof.get("pace", "slow")
    except Exception:                                            # noqa: BLE001
        dmin, dmax, pace = 300.0, 420.0, "slow"
    # Measured words-per-minute of the cast at each CEFR pace (benchmarked with
    # scripts/benchmark_story_voices.py — see src/sawt_cast.PACE_SPEED).
    wpm = {"very_slow": 118.0, "slow": 133.0, "moderate": 155.0,
           "natural": 175.0, "fast": 190.0, "native": 205.0}.get(pace, 133.0)
    # Aim just inside the middle of the window so normal variation stays legal.
    target_seconds = dmin + (dmax - dmin) * 0.45
    words = target_seconds / 60.0 * wpm
    # OVER-ASK: language models reliably under-deliver on length. Measured — asked
    # for 780 words, got 586 (75%). Asking for ~1.3x lands the real output inside
    # the CEFR duration window instead of just under it.
    words *= 1.3
    return int(round(words / 10.0) * 10), target_seconds / 60.0


def build_story_prompt(previous_summary: str, winning_choice: str,
                       episode_number: int, level: str = None) -> str:
    """Prompt the LLM to write the next episode as JSON (script + recap + the
    next A/B vote). `previous_summary` is the story so far; `winning_choice` is
    what the audience voted to happen next (empty for the very first episode).
    `level` selects the CEFR profile that sets length and pace."""
    cast = ", ".join(STORY_CAST)
    sfx = ", ".join(f"[SFX:{s}]" for s in STORY_SFX)
    target_words, target_minutes = target_length(level)

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

Write the next episode of Empire English Chronicles as a spoken audio script.

LENGTH — this is a hard requirement, not a guideline:
Write approximately {target_words} words of SPOKEN text (all speaker lines added
together). That is what fills a {target_minutes:.0f}-minute episode at this level's
delivery pace, and an episode outside its length window is rejected automatically.
Do not pad with repetition to reach it — use the room to develop the scene, let
characters react, and build the tension properly.

CAST (use these names exactly; the audio engine maps each to a distinct voice).
The three LEADS appear often; the others are recurring/guest roles you may bring
in when the story calls for them, to keep the cast varied and alive:
- Narrator — warm host who tells the story slowly and speaks directly to the audience.
- Maya — the protagonist (young woman, curious, brave).
- Leo — a supporting character (young man, cautious).
- Sara — a bright, quick friend (young woman).
- Omar — a warm, steady man (a friend or ally).
- The Stranger — a mysterious, low-voiced figure (use sparingly, for tension).
- Mrs. Adel — an older, gentle mentor.
Use 2–4 speaking characters per episode (not all at once) — enough for lively
dialogue, not so many it gets confusing for a learner.

STYLE:
- CLEAR simple English (learners), but genuinely suspenseful and cinematic.
- Real spoken dialogue, short sentences, natural rhythm.
- IMPORTANT — who says what: CHARACTERS speak ONLY the words they say out loud.
  The NARRATOR describes all ACTION and scene. NEVER put narration in a
  character's line — do NOT write "Maya: I push the door open" or "Leo: I hear a
  sound". Instead: "Narrator: Maya pushes the door open." A character line is
  only the actual spoken words (e.g. "Maya: Hello? Is someone there?").
- Do NOT write stage directions or delivery hints in parentheses (no "(low)",
  "(whisper)", "(through comm)") — they get read aloud. Show tone through the
  words themselves and the Narrator.
- Sound effects: ONLY these exist — {sfx}. Use them on their OWN, never spoken by
  a character. Do NOT invent other effects (no [SFX:wind], [SFX:heartbeat], etc.);
  if you need atmosphere, have the Narrator describe it in words instead.
- Use [PAUSE 2s] to hold tension, especially right before the cliffhanger.
- Open with the Narrator's signature: "Welcome to Empire English Chronicles..."
  and a one-line recap if this is not episode 1.
- END on a strong cliffhanger, then the Narrator asks the audience to choose
  between EXACTLY TWO options and says "Vote below. Tomorrow, the story continues
  the way you choose."

Return ONLY this JSON object:
{{
  "title": "short episode title",
  "script": "the full speaker-labelled script, one line per speaker turn, using Narrator:/Maya:/Leo:/Sara:/Omar:/The Stranger:/Mrs. Adel: and inline [SFX:...] and [PAUSE 2s] markers",
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
    # The script must contain at least a few "Speaker: line" turns. Match any
    # capitalized speaker label (Narrator/Maya/Leo/Sara/Omar/The Stranger/…),
    # not a fixed list, so the expanded cast doesn't get rejected.
    lines = [ln for ln in d["script"].splitlines()
             if re.match(r"^\s*[A-Z][\w.'\- ]{0,30}:\s*\S", ln)]
    return len(lines) >= 4


async def generate_episode(previous_summary: str = "", winning_choice: str = "",
                           episode_number: int = 1,
                           level: str = None) -> Optional[dict]:
    """Generate the next Empire Chronicles episode. Returns a dict with keys
    title, script, recap, vote_a, vote_b — or None if the LLM is unavailable or
    returns something unusable. Never raises."""
    prompt = build_story_prompt(previous_summary, winning_choice, episode_number,
                                level=level)
    try:
        text = await _call_llm_json(prompt, temperature=0.9, level=level)
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


def _max_tokens_for(level: str = None) -> int:
    """Completion-token budget for one episode, sized from its target length.

    WHY THIS IS COMPUTED, NOT GUESSED (all measured against the live provider):
      * With no `max_tokens` at all, a CEFR-length episode came back truncated.
      * `max_tokens=8000` was rejected outright with **HTTP 413 Payload Too Large**
        — the cap applies to prompt + completion TOGETHER, so a big number is not
        "safe", it is fatal.
      * `max_tokens=2000` succeeded and produced a 725-word script (A2 target 780).
      * The configured model is a REASONING model (`openai/gpt-oss-120b`), which
        spends part of the budget thinking. Too small a budget therefore returns
        HTTP 200 with EMPTY content rather than an error — a failure mode that is
        easy to misread as "the LLM is down".
    So the budget must be big enough to think AND write, but small enough to avoid
    413: ~2.4 tokens per target word plus overhead, clamped to a proven window."""
    words, _minutes = target_length(level)
    return int(min(3200, max(2000, words * 2.4 + 800)))


async def _call_llm_json(prompt: str, temperature: float = 0.9,
                         level: str = None) -> Optional[str]:
    """Story LLM call: Groq primary (story-writer system prompt), Gemini
    fallback. Returns raw text (expected to contain a JSON object) or None.

    Retries with a smaller completion budget on HTTP 413, so a fully automatic
    pipeline heals itself instead of silently producing no episode.

    PROVIDER ORDER IS EVIDENCE-BASED, and deliberately different from the rest of
    the bot. Elsewhere Groq is primary because it is fast for short JSON answers.
    For a STORY it is the wrong primary: the configured Groq model
    (`openai/gpt-oss-120b`) is a REASONING model that spends its budget thinking and
    then returns HTTP 200 with EMPTY content on long generations, and Groq's free
    tier rate-limits quickly. Measured 2026-09-06: Groq failed three attempts in a
    row on a CEFR-length episode while Gemini produced a complete 586-word script.
    So story generation tries **Gemini first** and keeps Groq as the fallback."""
    max_tokens = _max_tokens_for(level)

    # 1) Gemini first for long-form story text (see docstring).
    try:
        text = await ai_engine._call_gemini(prompt, temperature,
                                            max_output_tokens=max_tokens)
        if text:
            return text
        logger.warning("sawt.story: Gemini returned nothing; trying Groq")
    except Exception as e:  # noqa: BLE001
        logger.warning("sawt.story: Gemini error (%s); trying Groq", e)
    if config.GROQ_API_KEY:
        from . import groq_client
        payload = {
            "model": config.GROQ_MODEL,
            "temperature": temperature,
            # Sized to the episode, not guessed. See _max_tokens_for().
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": _STORY_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        }
        # Retry ladder. Each failure mode needs a DIFFERENT response, which is why
        # a single blanket retry never fixed this:
        #   413            -> asked for too much: SHRINK the completion budget.
        #   200 + no text  -> reasoning model ran out of room: GROW the budget.
        #   429            -> rate limited: WAIT, then try the same budget again.
        #   anything else   -> transport/model error: stop, let Gemini try.
        budget = max_tokens
        for attempt in range(1, 4):
            payload["max_tokens"] = budget
            try:
                result = await groq_client.chat_completion(payload,
                                                           timeout_seconds=120)
                if result.ok and result.text:
                    return result.text
                text_len = len(result.text or "")
                logger.warning("sawt.story: Groq unusable (attempt %s, "
                               "max_tokens=%s, status=%s, text_len=%s)",
                               attempt, budget, result.status, text_len)
                if result.status == 413:
                    budget = max(1200, int(budget * 0.6))
                elif result.status == 429:
                    await asyncio.sleep(min(30, 8 * attempt))
                elif result.status == 200 and text_len == 0:
                    budget = min(3200, int(budget * 1.4))
                else:
                    break
            except Exception as e:  # noqa: BLE001
                logger.warning("sawt.story: Groq call error (attempt %s): %s",
                               attempt, e)
                break
    # Gemini was already tried first (see docstring); nothing left to fall back to.
    logger.warning("sawt.story: no provider produced a usable script")
    return None
